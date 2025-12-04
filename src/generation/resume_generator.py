from typing import Callable, Dict, Any, List, Type
from pydantic import BaseModel
from src.generation.output_classes import SummaryOutput, TechnicalSkillsOutput, ExperienceOutput
from src.generation.prompts import SUMMARY_SYSTEM_PROMPT, SKILLS_SYSTEM_PROMPT, EXPERIENCE_SYSTEM_PROMPT, SUMMARY_USER_PROMPT, SKILLS_USER_PROMPT, EXPERIENCE_USER_PROMPT
import asyncio
from src.core.db_manager import get_qdrant_manager, get_mongodb_manager
from src.retriever.get_ids import ResumeIdsRetriever
from src.generation.call_llm import llm_json
import json
from src.utils.logger import get_logger
from src.utils.llm_client import load_llm_config
logger = get_logger(__name__)


class ResumeGenerator:
    def __init__(self, llm_json_fn: Callable, qdrant_manager, mongodb_manager):
        """
        Args:
            llm_json_fn: async function(prompt: str, model: BaseModel, max_tokens: int) -> BaseModel
                         Should perform async LLM JSON call using Groq/OpenAI/Gemini etc.
        """
        self.llm_json_fn = llm_json_fn
        # Use singleton instances
        self.qdrant_manager = qdrant_manager
        self.mongodb_manager = mongodb_manager
        
        # Load LLM config
        self.llm_config = load_llm_config()
        self.summary_max_tokens = self.llm_config.get("SUMMARY_MAX_TOKENS", 3000)
        self.skills_max_tokens = self.llm_config.get("SKILLS_MAX_TOKENS", 1500)
        self.experience_max_tokens = self.llm_config.get("EXPERIENCE_MAX_TOKENS", 3000)
    # -----------------------------------------------------
    # Select Top Resumes by Section Score
    # -----------------------------------------------------

    def _select_top_resumes(self, details, score_key, top_k):
        sorted_items = sorted(
            details.items(),
            key=lambda x: x[1].get("signals", {}).get(score_key, 0.0),
            reverse=True
        )
        return [rid for rid, _ in sorted_items[:top_k]]

    # -----------------------------------------------------
    # Prepare Data for Prompts
    # -----------------------------------------------------
    def fetch_text_data_from_qdrant(
        self,
        resume_ids: List[str],
        section: str
    ):
        """
        Fetch ALL chunks for given resume_ids directly from Qdrant,
        then concatenate them into a single text block.
        """

        output_blocks = []  

        for rid in resume_ids:

            # Fetch full payloads for this resume
            # This calls your existing _fetch_all_payloads_for_resume_id inside QdrantManager
            data = self.qdrant_manager.fetch_all_payloads_for_resume_ids([rid])[rid]

            # Choose section chunks
            if section == "summary":
                chunks = data.get("professional_summary", [])

            elif section == "skills":
                chunks = data.get("technical_skills", [])

            elif section == "experience":
                chunks = data.get("experiences", [])

            else:
                raise ValueError(f"Unknown section: {section}")

            # Join all chunk text
            full_text = " ".join([c.get("text", "") for c in chunks])

            output_blocks.append(full_text)

        return output_blocks
    # -----------------------------------------------------
    # Build prompt
    # -----------------------------------------------------
    def _build_prompt(
        self,
        template: str,
        job_description: str,
        data: Any,
        top_k: int
    ):
        # Use string replacement instead of .format() to avoid the JSON confusion
        prompt = template
        prompt = prompt.replace("{job_description}", job_description)
        prompt = prompt.replace("{data}", str(data))  # Convert data to string
        prompt = prompt.replace("{top_k}", str(top_k))
        
        return prompt

    # -----------------------------------------------------
    # Async LLM JSON Call
    # -----------------------------------------------------
    async def _call_llm_json_async(
        self,
        output_model: Type[BaseModel],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.4
    ):

        return await self.llm_json_fn(output_model, system_prompt, user_prompt, max_tokens, temperature)

    # -----------------------------------------------------
    # Post-Processing Hard Enforcement
    # -----------------------------------------------------


     # ----------------------------------------------------- MAIN ORCHESTRATOR
    # -----------------------------------------------------
    async def generate_all_sections(
        self,
        job_description: str,
        details: Dict[str, Dict],
        top_k: int = 3,
        default_top_k_experience: int = 2,
    ):

        top_k_experience = default_top_k_experience * 3
        # ------------ SELECT RESUMES ------------
        summary_rids = self._select_top_resumes(details, "summary_score", top_k)
        skills_rids = self._select_top_resumes(details, "skills_score", top_k)
        exp_rids = self._select_top_resumes(details, "experience_score", top_k_experience)

        # ------------ PREPARE DATA ------------
        summary_data = self.mongodb_manager.get_sections_by_resume_ids(summary_rids, "professional_summary")
        skills_data = self.mongodb_manager.get_sections_by_resume_ids(skills_rids, "technical_skills")
        exp_data = self.mongodb_manager.get_sections_by_resume_ids(exp_rids, "experiences")

        # ------------ PROMPTS -----------------
        summary_prompt = self._build_prompt(template=SUMMARY_USER_PROMPT, job_description=job_description, data=summary_data, top_k=top_k)
        skills_prompt = self._build_prompt(template=SKILLS_USER_PROMPT, job_description=job_description, data=skills_data, top_k=top_k)
        exp_prompt = self._build_prompt(template=EXPERIENCE_USER_PROMPT, job_description=job_description, data=exp_data, top_k=top_k_experience)


        logger.info(f"Skills Prompt: {skills_prompt}")

        # ------------ ASYNC LLM CALLS ----------
        summary_task = asyncio.create_task(
            self._call_llm_json_async(SummaryOutput, SUMMARY_SYSTEM_PROMPT, summary_prompt, max_tokens=self.summary_max_tokens, temperature=0.4)
        )
        skills_task = asyncio.create_task(
            self._call_llm_json_async(TechnicalSkillsOutput, SKILLS_SYSTEM_PROMPT, skills_prompt, max_tokens=self.skills_max_tokens, temperature=0.3)
        )
        exp_task = asyncio.create_task(
            self._call_llm_json_async(ExperienceOutput, EXPERIENCE_SYSTEM_PROMPT, exp_prompt, max_tokens=self.experience_max_tokens, temperature=0.4)
        )

        summary_out, skills_out, exp_out = await asyncio.gather(
            summary_task, skills_task, exp_task
        )


        # ------------ RETURN -------------------
        return {
            "professional_summary": summary_out.model_dump(),
            "technical_skills": skills_out.model_dump(),
            "experience": exp_out.model_dump()
        }

    async def _generate_all_sections_direct(
        self,
        job_description: str,
        summary_data: Any,
        skills_data: Any,
        exp_data: Any,
        top_k_summary: int = 3,
        top_k_skills: int = 3,
        top_k_experience: int = 6
    ):
        """
        Generate all sections directly from provided data (used for section-level search).
        
        Args:
            job_description: Job description text
            summary_data: Professional summary data from MongoDB
            skills_data: Technical skills data from MongoDB
            exp_data: Experience data from MongoDB
            top_k_summary: Number of summaries to generate
            top_k_skills: Number of skills to generate
            top_k_experience: Number of experiences to generate
        """
        # ------------ PROMPTS -----------------
        summary_prompt = self._build_prompt(SUMMARY_USER_PROMPT, job_description, summary_data, top_k_summary)
        skills_prompt = self._build_prompt(SKILLS_USER_PROMPT, job_description, skills_data, top_k_skills)
        exp_prompt = self._build_prompt(EXPERIENCE_USER_PROMPT, job_description, exp_data, top_k_experience)

        logger.info(f"Skills Prompt: {skills_prompt}")

        # ------------ ASYNC LLM CALLS ----------
        summary_task = asyncio.create_task(
            self._call_llm_json_async(SummaryOutput, SUMMARY_SYSTEM_PROMPT, summary_prompt, max_tokens=self.summary_max_tokens, temperature=0.4)
        )
        skills_task = asyncio.create_task(
            self._call_llm_json_async(TechnicalSkillsOutput, SKILLS_SYSTEM_PROMPT, skills_prompt, max_tokens=self.skills_max_tokens, temperature=0.3)
        )
        exp_task = asyncio.create_task(
            self._call_llm_json_async(ExperienceOutput, EXPERIENCE_SYSTEM_PROMPT, exp_prompt, max_tokens=self.experience_max_tokens, temperature=0.4)
        )

        summary_out, skills_out, exp_out = await asyncio.gather(
            summary_task, skills_task, exp_task
        )



        # ------------ RETURN -------------------
        return {
            "professional_summary": summary_out.model_dump(),
            "technical_skills": skills_out.model_dump(),
            "experience": exp_out.model_dump()
        }

        # -----------------------------------------------------
    # NEW: Experience Processing Functions
    # -----------------------------------------------------

    def _prepare_experience_batches(
        self,
        exp_data: List[Dict[str, Any]],
        num_experiences: int
    ):
        """
        Prepare unique data batches for each experience to avoid redundancy.
        
        Args:
            exp_data: List of experience sections from MongoDB
            num_experiences: Number of experiences to generate
            
        Returns:
            List of data batches, each batch for one experience
        """
        if not exp_data:
            return [[] for _ in range(num_experiences)]
        
        # Flatten all experiences from all resumes
        all_experiences = []
        
        for item in exp_data:
            resume_id = item.get("resume_id")
            experiences = item.get("experiences", [])
            
            for exp in experiences:
                # Add resume_id context to each experience
                exp_with_context = exp.copy()
                exp_with_context["_source_resume_id"] = resume_id
                all_experiences.append(exp_with_context)
        
        # Shuffle to avoid bias
        import random
        random.shuffle(all_experiences)
        
        # Split into batches for each experience to generate
        # Each batch gets unique experiences to avoid redundancy
        batches = []
        
        for i in range(num_experiences):
            # For each experience, select different source experiences
            # Using modular arithmetic to distribute evenly
            batch = []
            for j in range(min(3, len(all_experiences))):  # 3 experiences per generated one
                idx = (i * 3 + j) % len(all_experiences)
                if idx < len(all_experiences):
                    batch.append(all_experiences[idx])
            
            batches.append(batch)
        
        # If we don't have enough unique experiences, allow some overlap only if necessary
        if len(all_experiences) < num_experiences * 3:
            logger.warning(f"Only {len(all_experiences)} source experiences available for {num_experiences} target experiences")
        
        return batches

    async def _generate_single_experience(
        self,
        job_description: str,
        experience_batch: List[Dict],
        experience_num: int,
        total_experiences: int
    ):
        """
        Generate a single experience section using its unique data batch.
        
        Args:
            job_description: Job description text
            experience_batch: Unique batch of source experiences for this specific experience
            experience_num: Which experience number this is (1-based)
            total_experiences: Total number of experiences to generate
        """
        if not experience_batch:
            logger.warning(f"No data for experience {experience_num}")
            return None
        
        # Prepare prompt for this specific experience
        exp_prompt = self._build_prompt(
            EXPERIENCE_USER_PROMPT,
            job_description,
            experience_batch,
            top_k=len(experience_batch)  # Use actual batch size
        )
        
        # Add context about which experience we're generating
        system_prompt_with_context = EXPERIENCE_SYSTEM_PROMPT
        system_prompt_with_context += f"\n\nYou are generating experience #{experience_num} of {total_experiences}."
        system_prompt_with_context += "\n\nIMPORTANT: You are receiving multiple source experiences for CONTEXT only. Use them as reference material."
        system_prompt_with_context += "\n\nJOB ROLE FUSION RULES:"
        system_prompt_with_context += "\n- Look at the job roles from the 3 source experiences"
        system_prompt_with_context += "\n- If multiple sources have the same/similar job title, use that title"
        system_prompt_with_context += "\n- If source roles are different but related, intelligently fuse them into one representative title"
        system_prompt_with_context += "\n- DO NOT consider the job description when determining the job role"
        system_prompt_with_context += "\n- Keep it authentic - use actual titles from the sources, don't invent new ones"
        system_prompt_with_context += "\n- Prefer the most common or senior title from the sources"
        system_prompt_with_context += "\n\nCRITICAL OUTPUT REQUIREMENT: Generate EXACTLY ONE experience object in the output array, NOT multiple."
        system_prompt_with_context += "\n\nThis single experience MUST have 15-20 detailed bullet points (80-100 words each). Be comprehensive and include ALL relevant responsibilities and achievements from the source data. Do not summarize or truncate - include full details."
        
        try:
            # Call LLM for this specific experience
            exp_out = await self._call_llm_json_async(
                ExperienceOutput,
                system_prompt_with_context,
                exp_prompt, 
                max_tokens=self.experience_max_tokens,
                temperature=0.8
            )
            

            return exp_out
            
        except Exception as e:
            logger.error(f"Error generating experience {experience_num}: {e}")
            return None

    # -----------------------------------------------------
    # UPDATED: Main Orchestrator with Individual Experience Processing
    # -----------------------------------------------------

    async def generate_all_sections_individual_experiences(
        self,
        job_description: str,
        details: Dict[str, Dict],
        top_k: int = 3,
        num_experiences: int = 3,  # How many experiences to generate
    ):
        """
        Generate all sections with individual LLM calls for each experience.
        
        Args:
            job_description: Job description text
            details: Resume details with scores
            top_k: Number of top resumes to use per section
            num_experiences: Number of experiences to generate
        """
        # ------------ SELECT RESUMES ------------
        summary_rids = self._select_top_resumes(details, "summary_score", top_k)
        skills_rids = self._select_top_resumes(details, "skills_score", top_k)
        exp_rids = self._select_top_resumes(details, "experience_score", num_experiences * 2)
        
        # ------------ PREPARE DATA ------------
        summary_data = self.mongodb_manager.get_sections_by_resume_ids(summary_rids, "professional_summary")
        skills_data = self.mongodb_manager.get_sections_by_resume_ids(skills_rids, "technical_skills")
        exp_data = self.mongodb_manager.get_sections_by_resume_ids(exp_rids, "experiences")
        
        # ------------ PREPARE EXPERIENCE BATCHES ------------
        # Create unique data batches for each experience
        experience_batches = self._prepare_experience_batches(exp_data, num_experiences)
        
        # Log what we're doing
        for i, batch in enumerate(experience_batches):
            source_ids = set(exp.get("_source_resume_id", "unknown") for exp in batch)
            logger.info(f"Experience {i+1} will use {len(batch)} source experiences from resumes: {list(source_ids)}")
        
        # ------------ ASYNC LLM CALLS ----------
        # Generate summary and skills (unchanged)
        summary_task = asyncio.create_task(
            self._call_llm_json_async(SummaryOutput, SUMMARY_SYSTEM_PROMPT, 
                                    self._build_prompt(SUMMARY_USER_PROMPT, job_description, summary_data, top_k), max_tokens=self.summary_max_tokens, temperature=0.4)
        )
        
        skills_task = asyncio.create_task(
            self._call_llm_json_async(TechnicalSkillsOutput, SKILLS_SYSTEM_PROMPT,
                                    self._build_prompt(SKILLS_USER_PROMPT, job_description, skills_data, top_k), max_tokens=self.skills_max_tokens, temperature=0.3)
        )
        
        # Generate experiences INDIVIDUALLY
        experience_tasks = []
        for i, batch in enumerate(experience_batches):
            task = asyncio.create_task(
                self._generate_single_experience(
                    job_description=job_description,
                    experience_batch=batch,
                    experience_num=i + 1,
                    total_experiences=num_experiences
                )
            )
            experience_tasks.append(task)
        
        # Wait for all tasks to complete
        summary_out, skills_out = await asyncio.gather(summary_task, skills_task)
        experience_results = await asyncio.gather(*experience_tasks)
        
        # Filter out failed experience generations
        valid_experiences = []
        for i, result in enumerate(experience_results):
            if result and result.experience:
                valid_experiences.append(result.experience[0])
                logger.info(f"Successfully generated experience {i+1}")
            else:
                logger.warning(f"Failed to generate experience {i+1}")
        
        # ------------ CREATE FINAL OUTPUT ------------
        final_output = {
            "professional_summary": summary_out.model_dump() if summary_out else {},
            "technical_skills": skills_out.model_dump() if skills_out else {},
            "experience": [exp.dict() for exp in valid_experiences] if valid_experiences else []
        }
        
        return final_output


    # -----------------------------------------------------
    # UPDATED: Direct Generation with Individual Experiences
    # -----------------------------------------------------

    async def _generate_all_sections_direct_individual(
        self,
        job_description: str,
        summary_data: Any,
        skills_data: Any,
        exp_data: Any,
        num_experiences: int = 3,  # Number of experiences to generate
        top_k_summary: int = 3,
        top_k_skills: int = 3
    ):
        """
        Generate all sections with individual processing for each experience.
        """
        # ------------ LOG DATA COUNTS ------------
        logger.info(f"Summary data count: {len(summary_data) if isinstance(summary_data, list) else 'N/A (not a list)'}")
        logger.info(f"Skills data count: {len(skills_data) if isinstance(skills_data, list) else 'N/A (not a list)'}")
        logger.info(f"Experience data count: {len(exp_data) if isinstance(exp_data, list) else 'N/A (not a list)'}")
        
        # ------------ PROMPTS FOR SUMMARY AND SKILLS ------------
        summary_prompt = self._build_prompt(SUMMARY_USER_PROMPT, job_description, summary_data, top_k_summary)
        skills_prompt = self._build_prompt(SKILLS_USER_PROMPT, job_description, skills_data, top_k_skills)
        
        # ------------ PREPARE EXPERIENCE BATCHES ------------
        experience_batches = self._prepare_experience_batches(exp_data, num_experiences)
        
        # Log experience batches
        for i, batch in enumerate(experience_batches):
            logger.info(f"Experience {i+1} batch size: {len(batch)}")
        
        # ------------ ASYNC LLM CALLS ----------
        summary_task = asyncio.create_task(                 
            self._call_llm_json_async(SummaryOutput, SUMMARY_SYSTEM_PROMPT, summary_prompt, max_tokens=self.summary_max_tokens, temperature=0.4)
        )
        
        skills_task = asyncio.create_task(
            self._call_llm_json_async(TechnicalSkillsOutput, SKILLS_SYSTEM_PROMPT, skills_prompt, max_tokens=self.skills_max_tokens, temperature=0.3)
        )
        
        # Individual experience tasks
        experience_tasks = []
        for i, batch in enumerate(experience_batches):
            task = asyncio.create_task(
                self._generate_single_experience(
                    job_description=job_description,
                    experience_batch=batch,
                    experience_num=i + 1,
                    total_experiences=num_experiences
                )
            )
            experience_tasks.append(task)
        
        # Execute all tasks in parallel
        summary_out, skills_out = await asyncio.gather(summary_task, skills_task)
        experience_results = await asyncio.gather(*experience_tasks)
        
        # ------------ COMBINE RESULTS ------------
        # Take only the FIRST experience from each LLM call to ensure we get exactly num_experiences
        all_experiences = []
        for i, result in enumerate(experience_results):
            if result and result.experience and len(result.experience) > 0:
                # Only take the first experience from this call
                all_experiences.append(result.experience[0])
                logger.info(f"Collected experience {i+1} from LLM call")
            else:
                logger.warning(f"Experience {i+1} LLM call returned no experiences")
        
        # ------------ HARD TRUNCATION ----------

        
        # ------------ RETURN -------------------
        return {
            "professional_summary": summary_out.model_dump(),
            "technical_skills": skills_out.model_dump(),
            "experience": [exp.dict() for exp in all_experiences]
        }



async def orchestrate_resume_generation_individual_experiences(
    qdrant_manager,
    mongodb_manager,
    job_description: str, 
    job_roles: List[str],
    num_experiences: int = 3,  # Number of experiences to generate
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
    top_k_summary: int = 3,
    top_k_skills: int = 3,
    top_k_experience_multiplier: int = 3  # Multiplier for experience source count
):
    """
    Orchestrate with individual experience generation.
    """
    generator = ResumeGenerator(llm_json_fn=llm_json, qdrant_manager=qdrant_manager, mongodb_manager=mongodb_manager)
    retriever = ResumeIdsRetriever(mongo_manager=mongodb_manager, qdrant_manager=qdrant_manager)
    
    # Filter by job roles
    filtered_resume_object_ids = retriever.get_resume_ids_by_job_roles(job_roles)
    filtered_resume_ids = [str(oid) for oid in filtered_resume_object_ids]
    
    if not filtered_resume_ids:
        return {"professional_summary": {}, "technical_skills": {}, "experience": []}
    
    # Calculate how many source resumes we need for experiences
    # We need more source resumes since each experience gets unique data
    top_k_experience = num_experiences * top_k_experience_multiplier
    
    # Section-specific searches
    summary_results = qdrant_manager.match_resumes_by_section(
        job_description=job_description,
        section_key="professional_summary",
        top_k=top_k_summary,
        resume_ids_filter=filtered_resume_ids,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )
    summary_rids = [rid for rid, score in summary_results]
    
    skills_results = qdrant_manager.match_resumes_by_section(
        job_description=job_description,
        section_key="technical_skills",
        top_k=top_k_skills,
        resume_ids_filter=filtered_resume_ids,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )
    skills_rids = [rid for rid, score in skills_results]
    
    exp_results = qdrant_manager.match_resumes_by_section(
        job_description=job_description,
        section_key="experiences",
        top_k=top_k_experience,  # Get MORE source resumes
        resume_ids_filter=filtered_resume_ids,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )
    exp_rids = [rid for rid, score in exp_results]
    
    # Debug logging
    logger.info(f"Experience search returned {len(exp_rids)} resume IDs from Qdrant: {exp_rids[:5]}...")
    
    # Fetch data
    mongodb_manager = get_mongodb_manager()
    summary_data = mongodb_manager.get_sections_by_resume_ids(summary_rids, "professional_summary")
    skills_data = mongodb_manager.get_sections_by_resume_ids(skills_rids, "technical_skills")
    exp_data = mongodb_manager.get_sections_by_resume_ids(exp_rids, "experiences")
    
    # Log how many documents were actually retrieved
    logger.info(f"MongoDB returned {len(exp_data)} experience documents")
    logger.info(f"Unique resume IDs in exp_data: {set(item.get('resume_id') for item in exp_data)}")
    
    # Generate with individual experiences
    result = await generator._generate_all_sections_direct_individual(
        job_description=job_description,
        summary_data=summary_data,
        skills_data=skills_data,
        exp_data=exp_data,
        num_experiences=num_experiences,
        top_k_summary=top_k_summary,
        top_k_skills=top_k_skills
    )
    
    return result