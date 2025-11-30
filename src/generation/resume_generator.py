from typing import Callable, Dict, Any, List, Type
from pydantic import BaseModel
from src.generation.output_classes import SummaryOutput, TechnicalSkillsOutput, ExperienceOutput
from src.generation.prompts import SUMMARY_SYSTEM_PROMPT, SKILLS_SYSTEM_PROMPT, EXPERIENCE_SYSTEM_PROMPT, SUMMARY_USER_PROMPT, SKILLS_USER_PROMPT, EXPERIENCE_USER_PROMPT
import asyncio
from src.resume_ingestion.vector_store.qdrant_manager import QdrantManager
from src.resume_ingestion.database.mongodb_manager import MongoDBManager
from src.retriever.get_ids import ResumeIdsRetriever
from src.generation.call_llm import llm_json
import json
from src.utils.logger import get_logger
logger = get_logger(__name__)


class ResumeGenerator:
    def __init__(self, llm_json_fn: Callable):
        """
        Args:
            llm_json_fn: async function(prompt: str, model: BaseModel, max_tokens: int) -> BaseModel
                         Should perform async LLM JSON call using Groq/OpenAI/Gemini etc.
        """
        self.llm_json_fn = llm_json_fn
        self.qdrant_manager = QdrantManager()
        self.mongodb_manager = MongoDBManager()
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
        user_prompt: str
    ):

        return await self.llm_json_fn(output_model, system_prompt, user_prompt)

    # -----------------------------------------------------
    # Post-Processing Hard Enforcement
    # -----------------------------------------------------
    def _enforce_output_limits(
        self,
        summary: SummaryOutput,
        skills: TechnicalSkillsOutput,
        exp: ExperienceOutput
    ):
        # ---- SUMMARY ----
        summary.summaries = summary.summaries[:5]
        summary.summaries = [
            s if len(s.split()) <= 20 else " ".join(s.split()[:20])
            for s in summary.summaries
        ]

        # ---- SKILLS ----
        # limit total categories
        if len(skills.skills) > 10:
            skills.skills = dict(list(skills.skills.items())[:10])

        # limit each category
        for cat in skills.skills:
            skills.skills[cat] = skills.skills[cat][:10]

        # ---- EXPERIENCE ----
        for section in exp.experience:
            # limit bullet count
            section.bullets = section.bullets[:7]

            # limit bullet length
            section.bullets = [
                b if len(b.split()) <= 25 else " ".join(b.split()[:25])
                for b in section.bullets
            ]

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
        summary_prompt = self._build_prompt(SUMMARY_USER_PROMPT, job_description, summary_data, top_k)
        skills_prompt = self._build_prompt(SKILLS_USER_PROMPT, job_description, skills_data, top_k)
        exp_prompt = self._build_prompt(EXPERIENCE_USER_PROMPT, job_description, exp_data, top_k_experience)


        logger.info(f"Skills Prompt: {skills_prompt}")

        # ------------ ASYNC LLM CALLS ----------
        summary_task = asyncio.create_task(
            self._call_llm_json_async(SummaryOutput, SUMMARY_SYSTEM_PROMPT, summary_prompt)
        )
        skills_task = asyncio.create_task(
            self._call_llm_json_async(TechnicalSkillsOutput, SKILLS_SYSTEM_PROMPT, skills_prompt)
        )
        exp_task = asyncio.create_task(
            self._call_llm_json_async(ExperienceOutput, EXPERIENCE_SYSTEM_PROMPT, exp_prompt)
        )

        summary_out, skills_out, exp_out = await asyncio.gather(
            summary_task, skills_task, exp_task
        )

        # ------------ HARD TRUNCATION ----------
        self._enforce_output_limits(summary_out, skills_out, exp_out)

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
            self._call_llm_json_async(SummaryOutput, SUMMARY_SYSTEM_PROMPT, summary_prompt)
        )
        skills_task = asyncio.create_task(
            self._call_llm_json_async(TechnicalSkillsOutput, SKILLS_SYSTEM_PROMPT, skills_prompt)
        )
        exp_task = asyncio.create_task(
            self._call_llm_json_async(ExperienceOutput, EXPERIENCE_SYSTEM_PROMPT, exp_prompt)
        )

        summary_out, skills_out, exp_out = await asyncio.gather(
            summary_task, skills_task, exp_task
        )

        # ------------ HARD TRUNCATION ----------
        self._enforce_output_limits(summary_out, skills_out, exp_out)

        # ------------ RETURN -------------------
        return {
            "professional_summary": summary_out.model_dump(),
            "technical_skills": skills_out.model_dump(),
            "experience": exp_out.model_dump()
        }


async def orchestrate_resume_generation(
    job_description: str, 
    job_roles: List[str],
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
    top_k_summary: int = 3,
    top_k_skills: int = 3,
    top_k_experience: int = 6
):
    """
    Orchestrate resume generation using section-level hybrid search.
    Each section (summary, skills, experiences) is searched independently with hybrid scoring.
    
    Args:
        job_description: Job description text
        job_roles: List of job role strings to filter resumes by
        semantic_weight: Weight for semantic similarity (default 0.7)
        keyword_weight: Weight for keyword matching (default 0.3)
        top_k_summary: Number of resumes to use for professional summary (default 3)
        top_k_skills: Number of resumes to use for technical skills (default 3)
        top_k_experience: Number of resumes to use for experiences (default 6)
    """
    generator = ResumeGenerator(llm_json_fn=llm_json)
    qdrant_manager = QdrantManager()
    retriever = ResumeIdsRetriever()
    
    # First, filter resumes by job roles
    filtered_resume_object_ids = retriever.get_resume_ids_by_job_roles(job_roles)
    filtered_resume_ids = [str(oid) for oid in filtered_resume_object_ids]
    
    if not filtered_resume_ids:
        logger.warning(f"No resumes found matching job roles: {job_roles}")
        return {
            "professional_summary": {},
            "technical_skills": {},
            "experience": {}
        }
    
    logger.info(f"Found {len(filtered_resume_ids)} resumes matching job roles: {job_roles}")
    
    # Section-specific hybrid searches
    logger.info("Performing section-level hybrid search...")
    
    # Search for best professional summaries
    summary_results = qdrant_manager.match_resumes_by_section(
        job_description=job_description,
        section_key="professional_summary",
        top_k=top_k_summary,
        resume_ids_filter=filtered_resume_ids,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )
    summary_rids = [rid for rid, score in summary_results]
    logger.info(f"Top {len(summary_rids)} resumes for professional_summary: {summary_rids}")
    
    # Search for best technical skills
    skills_results = qdrant_manager.match_resumes_by_section(
        job_description=job_description,
        section_key="technical_skills",
        top_k=top_k_skills,
        resume_ids_filter=filtered_resume_ids,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )
    skills_rids = [rid for rid, score in skills_results]
    logger.info(f"Top {len(skills_rids)} resumes for technical_skills: {skills_rids}")
    
    # Search for best experiences
    exp_results = qdrant_manager.match_resumes_by_section(
        job_description=job_description,
        section_key="experiences",
        top_k=top_k_experience,
        resume_ids_filter=filtered_resume_ids,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )
    exp_rids = [rid for rid, score in exp_results]
    logger.info(f"Top {len(exp_rids)} resumes for experiences: {exp_rids}")
    
    # Fetch data from MongoDB for each section
    mongodb_manager = MongoDBManager()
    summary_data = mongodb_manager.get_sections_by_resume_ids(summary_rids, "professional_summary")
    skills_data = mongodb_manager.get_sections_by_resume_ids(skills_rids, "technical_skills")
    exp_data = mongodb_manager.get_sections_by_resume_ids(exp_rids, "experiences")
    
    # Generate sections using section-specific data
    result = await generator._generate_all_sections_direct(
        job_description=job_description,
        summary_data=summary_data,
        skills_data=skills_data,
        exp_data=exp_data,
        top_k_summary=top_k_summary,
        top_k_skills=top_k_skills,
        top_k_experience=top_k_experience
    )
    
    return result

if __name__ == "__main__":
    jd = """Job Description:
We are seeking an experienced Oracle Sales Cloud Consultant to support implementation, customization, and optimization of Oracle CX Sales applications. The ideal candidate will work closely with business stakeholders to gather requirements, configure the system, and ensure seamless integration with other Oracle and third-party applications.

Key Responsibilities:

Implement and configure Oracle Sales Cloud modules (Leads, Opportunities, Accounts, Contacts, and Forecasting).
Gather business requirements and translate them into functional solutions.
Develop custom reports and dashboards using OTBI/BIP.
Collaborate with technical teams for integrations and data migration.
Provide end-user training, documentation, and post-implementation support.
Required Skills:

Hands-on experience in Oracle Sales Cloud (B2B/B2C) implementation and support.
Strong understanding of sales automation processes and CRM best practices.
Knowledge of OIC, Groovy scripting, and REST/SOAP integrations is a plus.
Excellent communication and problem-solving skills.
"""
    job_roles = ["Oracle Sales Cloud Consultant", "Sales Cloud Consultant", "Oracle Consultant"]
    result = asyncio.run(orchestrate_resume_generation(jd, job_roles))
    with open("resume_generation/result.json", "w") as f:
        json.dump(result, f, indent=4)