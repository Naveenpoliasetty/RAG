import re
from typing import Dict, List, Any, Optional
from src.resume_ingestion.vector_store.qdrant_manager import QdrantManager
from qdrant_client.http import models as qmodels
import logging

logger = logging.getLogger("ResumeRetriever")

class ResumeRetriever:
    """
    Advanced retrieval system for resume redesign with hybrid search capabilities
    """
    
    def __init__(self, qdrant_manager: QdrantManager):
        self.qdrant = qdrant_manager
        self.collections_mapping = qdrant_manager.collections_mapping
        
    def retrieve_for_redesign(self, job_description: str, user_resume: Dict = None, top_k: int = 5) -> Dict[str, Any]:
        """
        Main retrieval method that implements all strategies
        """
        logger.info("Starting advanced resume retrieval for redesign")
        
        # Stage 1: Analyze job description
        jd_analysis = self._analyze_job_description(job_description)
        logger.info(f"JD Analysis - Domain: {jd_analysis.get('domain')}, Key Skills: {len(jd_analysis.get('key_skills', []))}")
        
        # Stage 2: Multi-collection hybrid retrieval
        collection_results = {}
        
        # Professional Summaries - Semantic focus
        collection_results["professional_summaries"] = self._retrieve_summaries_hybrid(jd_analysis, top_k)
        
        # Technical Skills - Keyword + Semantic
        collection_results["technical_skills"] = self._retrieve_skills_hybrid(jd_analysis, top_k)
        
        # Experiences - Domain-aware semantic
        collection_results["experiences"] = self._retrieve_experiences_hybrid(jd_analysis, top_k)
        
        # Stage 3: Cross-collection ranking and deduplication
        final_results = self._rank_and_deduplicate_results(collection_results, jd_analysis)
        
        logger.info(f"Retrieval complete - Found {sum(len(v) for v in final_results.values())} total items")
        return {
            "jd_analysis": jd_analysis,
            "results_by_collection": collection_results,
            "ranked_results": final_results
        }

    # ---------------------------------------------------------------------
    # Job Description Analysis
    # ---------------------------------------------------------------------
    
    def _analyze_job_description(self, job_description: str) -> Dict[str, Any]:
        """Extract key components from job description for targeted retrieval"""
        
        # Generate embedding for semantic search
        jd_vector = self.qdrant.embedding_service.encode_texts([job_description])[0]
        
        # Extract key information
        key_terms = self._extract_key_terms(job_description)
        domain = self._infer_domain(job_description, key_terms)
        seniority = self._infer_seniority(job_description)
        
        return {
            "vector": jd_vector,
            "domain": domain,
            "key_skills": key_terms.get("skills", []),
            "key_technologies": key_terms.get("technologies", []),
            "key_qualifications": key_terms.get("qualifications", []),
            "seniority_level": seniority,
            "raw_text": job_description
        }
    
    def _extract_key_terms(self, text: str) -> Dict[str, List[str]]:
        """Extract key skills, technologies, and qualifications from text"""
        
        # Common patterns for extraction
        skills_patterns = [
            r"(?:skills? in|proficient in|experienced with|knowledge of)\s+([^.,]+)",
            r"(?:required|required skills?|qualifications?):\s*([^.,]+)",
        ]
        
        tech_pattern = r"\b(?:Python|Java|JavaScript|React|AWS|Docker|Kubernetes|SQL|NoSQL|Machine Learning|AI|TensorFlow|PyTorch)\b"
        
        skills = []
        technologies = []
        qualifications = []
        
        # Extract skills from patterns
        for pattern in skills_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                skills.extend([s.strip() for s in match.split(',')])
        
        # Extract technologies
        tech_matches = re.findall(tech_pattern, text, re.IGNORECASE)
        technologies.extend(list(set(tech_matches)))
        
        # Extract qualifications (simplified)
        qual_patterns = [r"\b(\d+\+? years? experience)\b", r"\b(Bachelor|Master|PhD)\b", r"\b(degree|certification)\b"]
        for pattern in qual_patterns:
            qualifications.extend(re.findall(pattern, text, re.IGNORECASE))
        
        return {
            "skills": list(set(skills))[:10],  # Limit to top 10
            "technologies": technologies,
            "qualifications": qualifications
        }
    
    def _infer_domain(self, job_description: str, key_terms: Dict) -> str:
        """Infer domain from job description content"""
        domain_keywords = {
            "software engineering": ["software", "developer", "engineer", "programming", "coding"],
            "data science": ["data science", "machine learning", "ai", "analytics", "data analysis"],
            "devops": ["devops", "cloud", "aws", "azure", "kubernetes", "docker", "infrastructure"],
            "frontend": ["frontend", "react", "angular", "vue", "javascript", "ui", "ux"],
            "backend": ["backend", "api", "server", "database", "microservices"],
            "fullstack": ["fullstack", "full stack", "end-to-end"]
        }
        
        domain_scores = {}
        text_lower = job_description.lower()
        
        for domain, keywords in domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                domain_scores[domain] = score
        
        # Also check technologies for domain hints
        for tech in key_terms.get("technologies", []):
            tech_lower = tech.lower()
            if any(tech_lower in domain for domain in domain_keywords.keys()):
                domain_scores[tech_lower] = domain_scores.get(tech_lower, 0) + 1
        
        return max(domain_scores, key=domain_scores.get) if domain_scores else "general"

    def _infer_seniority(self, job_description: str) -> str:
        """Infer seniority level from job description"""
        text_lower = job_description.lower()
        
        seniority_keywords = {
            "senior": ["senior", "lead", "principal", "architect", "experienced"],
            "mid": ["mid-level", "mid level", "intermediate"],
            "junior": ["junior", "entry-level", "entry level", "graduate", "associate"]
        }
        
        for level, keywords in seniority_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return level
        
        return "mid"  # Default

    # ---------------------------------------------------------------------
    # Collection-Specific Hybrid Retrieval Strategies
    # ---------------------------------------------------------------------
    
    def _retrieve_summaries_hybrid(self, jd_analysis: Dict, top_k: int) -> List[Dict]:
        """Hybrid retrieval for professional summaries - Semantic focus with domain filtering"""
        
        base_filters = self._build_domain_filter(jd_analysis)
        
        # Primary: Semantic search
        semantic_results = self.qdrant.client.search(
            collection_name="professional_summaries",
            query_vector=jd_analysis["vector"],
            query_filter=base_filters,
            limit=top_k * 2,  # Get more for ranking
            with_payload=True,
            score_threshold=0.6
        )
        
        # Secondary: Keyword boost for relevant summaries
        keyword_boosted = []
        for skill in jd_analysis["key_skills"][:3]:
            keyword_results = self.qdrant.client.query(
                collection_name="professional_summaries",
                query=skill,
                query_filter=base_filters,
                limit=2
            )
            keyword_boosted.extend(keyword_results)
        
        # Combine and rank
        all_results = list(semantic_results) + keyword_boosted
        ranked_results = self._rank_summaries(all_results, jd_analysis)
        
        return ranked_results[:top_k]
    
    def _retrieve_skills_hybrid(self, jd_analysis: Dict, top_k: int) -> List[Dict]:
        """Hybrid retrieval for technical skills - Keyword primary with semantic fallback"""
        
        base_filters = self._build_domain_filter(jd_analysis)
        all_results = []
        
        # Primary: Keyword matching for exact skill matches
        for skill in jd_analysis["key_skills"][:5]:
            keyword_results = self.qdrant.client.query(
                collection_name="technical_skills",
                query=skill,
                query_filter=base_filters,
                limit=3
            )
            all_results.extend(keyword_results)
        
        # Secondary: Technology keyword matching
        for tech in jd_analysis["key_technologies"][:5]:
            tech_results = self.qdrant.client.query(
                collection_name="technical_skills", 
                query=tech,
                query_filter=base_filters,
                limit=2
            )
            all_results.extend(tech_results)
        
        # Tertiary: Semantic search for broader skill context
        if len(all_results) < top_k:
            semantic_results = self.qdrant.client.search(
                collection_name="technical_skills",
                query_vector=jd_analysis["vector"],
                query_filter=base_filters,
                limit=top_k - len(all_results),
                with_payload=True
            )
            all_results.extend(semantic_results)
        
        # Rank and deduplicate skills
        ranked_results = self._rank_skills(all_results, jd_analysis)
        return self._deduplicate_skills(ranked_results)[:top_k]
    
    def _retrieve_experiences_hybrid(self, jd_analysis: Dict, top_k: int) -> List[Dict]:
        """Hybrid retrieval for experiences - Domain-aware semantic with role matching"""
        
        # Build comprehensive experience filters
        experience_filters = self._build_experience_filters(jd_analysis)
        
        # Primary: Semantic search with domain context
        semantic_results = self.qdrant.client.search(
            collection_name="experiences",
            query_vector=jd_analysis["vector"],
            query_filter=experience_filters,
            limit=top_k * 2,
            with_payload=True,
            score_threshold=0.65  # Higher threshold for experiences
        )
        
        # Secondary: Role-specific keyword matching
        role_boosted = []
        for skill in jd_analysis["key_skills"][:3]:
            role_results = self.qdrant.client.query(
                collection_name="experiences",
                query=skill,
                query_filter=experience_filters,
                limit=2
            )
            role_boosted.extend(role_results)
        
        # Combine and rank experiences
        all_results = list(semantic_results) + role_boosted
        ranked_results = self._rank_experiences(all_results, jd_analysis)
        
        return ranked_results[:top_k]

    # ---------------------------------------------------------------------
    # Smart Filtering Strategies
    # ---------------------------------------------------------------------
    
    def _build_domain_filter(self, jd_analysis: Dict) -> Optional[qmodels.Filter]:
        """Build domain-based filter for all collections"""
        if not jd_analysis.get("domain"):
            return None
            
        return qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="domain",
                    match=qmodels.MatchValue(value=jd_analysis["domain"])
                )
            ]
        )
    
    def _build_experience_filters(self, jd_analysis: Dict) -> Optional[qmodels.Filter]:
        """Build comprehensive filters for experience retrieval"""
        must_conditions = []
        should_conditions = []
        
        # Domain filter
        if jd_analysis.get("domain"):
            must_conditions.append(
                qmodels.FieldCondition(
                    key="domain",
                    match=qmodels.MatchValue(value=jd_analysis["domain"])
                )
            )
        
        # Role matching (boost)
        for skill in jd_analysis["key_skills"][:2]:
            should_conditions.append(
                qmodels.FieldCondition(
                    key="experience_role",
                    match=qmodels.MatchText(text=skill)
                )
            )
        
        # Build filter with must and should conditions
        filter_conditions = {}
        if must_conditions:
            filter_conditions["must"] = must_conditions
        if should_conditions:
            filter_conditions["should"] = should_conditions
            filter_conditions["min_should"] = 1  # At least one should match
        
        return qmodels.Filter(**filter_conditions) if filter_conditions else None

    # ---------------------------------------------------------------------
    # Collection-Specific Ranking
    # ---------------------------------------------------------------------
    
    def _rank_summaries(self, results: List, jd_analysis: Dict) -> List[Dict]:
        """Rank professional summaries by relevance to JD"""
        
        def calculate_score(result):
            base_score = result.score
            payload = result.payload
            
            # Boost for domain match
            if payload.get("domain") == jd_analysis.get("domain"):
                base_score *= 1.3
            
            # Boost for containing key skills
            text = payload.get("text", "").lower()
            skill_matches = sum(1 for skill in jd_analysis["key_skills"] if skill.lower() in text)
            base_score *= (1 + skill_matches * 0.1)
            
            return base_score
        
        return sorted(results, key=calculate_score, reverse=True)
    
    def _rank_skills(self, results: List, jd_analysis: Dict) -> List[Dict]:
        """Rank technical skills by relevance"""
        
        def calculate_score(result):
            base_score = getattr(result, 'score', 0.5)  # Default score for keyword results
            payload = result.payload
            text = payload.get("text", "").lower()
            
            # High boost for exact skill matches
            for skill in jd_analysis["key_skills"]:
                if skill.lower() in text:
                    base_score *= 1.5
                    break
            
            # Boost for technology matches
            for tech in jd_analysis["key_technologies"]:
                if tech.lower() in text:
                    base_score *= 1.3
                    break
            
            # Domain match boost
            if payload.get("domain") == jd_analysis.get("domain"):
                base_score *= 1.2
            
            return base_score
        
        return sorted(results, key=calculate_score, reverse=True)
    
    def _rank_experiences(self, results: List, jd_analysis: Dict) -> List[Dict]:
        """Rank experiences by comprehensive relevance scoring"""
        
        def calculate_score(result):
            base_score = result.score
            payload = result.payload
            text = payload.get("text", "").lower()
            
            # Role matching boost
            experience_role = payload.get("experience_role", "").lower()
            for skill in jd_analysis["key_skills"]:
                if skill.lower() in experience_role:
                    base_score *= 1.4
                    break
            
            # Skill mentions in experience text
            skill_matches = sum(1 for skill in jd_analysis["key_skills"] if skill.lower() in text)
            base_score *= (1 + skill_matches * 0.15)
            
            # Technology mentions
            tech_matches = sum(1 for tech in jd_analysis["key_technologies"] if tech.lower() in text)
            base_score *= (1 + tech_matches * 0.1)
            
            # Domain match
            if payload.get("domain") == jd_analysis.get("domain"):
                base_score *= 1.3
            
            return base_score
        
        return sorted(results, key=calculate_score, reverse=True)

    # ---------------------------------------------------------------------
    # Cross-Collection Ranking & Deduplication
    # ---------------------------------------------------------------------
    
    def _rank_and_deduplicate_results(self, collection_results: Dict, jd_analysis: Dict) -> Dict[str, List]:
        """Apply cross-collection ranking and deduplication"""
        
        # Flatten all results for cross-collection ranking
        all_results = []
        for collection_name, results in collection_results.items():
            for result in results:
                all_results.append({
                    "collection": collection_name,
                    "result": result,
                    "cross_score": self._calculate_cross_relevance_score(result, jd_analysis, collection_name)
                })
        
        # Sort by cross-collection relevance
        all_results.sort(key=lambda x: x["cross_score"], reverse=True)
        
        # Apply deduplication and reorganize by collection
        final_results = {
            "professional_summaries": [],
            "technical_skills": [], 
            "experiences": []
        }
        
        seen_content = set()
        
        for item in all_results:
            content_key = self._create_content_fingerprint(item["result"])
            
            if content_key not in seen_content:
                seen_content.add(content_key)
                final_results[item["collection"]].append(item["result"])
        
        return final_results
    
    def _calculate_cross_relevance_score(self, result, jd_analysis: Dict, collection: str) -> float:
        """Calculate unified relevance score across all collections"""
        
        base_score = getattr(result, 'score', 0.5)
        payload = result.payload
        text = payload.get("text", "").lower()
        
        # Collection-specific weights
        collection_weights = {
            "experiences": 1.2,        # Experiences are most valuable
            "professional_summaries": 1.1,  # Summaries are important
            "technical_skills": 1.0     # Skills are baseline
        }
        
        base_score *= collection_weights.get(collection, 1.0)
        
        # Domain match boost (applies to all collections)
        if payload.get("domain") == jd_analysis.get("domain"):
            base_score *= 1.25
        
        # Skill relevance boost
        skill_relevance = sum(1 for skill in jd_analysis["key_skills"] if skill.lower() in text)
        base_score *= (1 + skill_relevance * 0.1)
        
        return base_score
    
    def _create_content_fingerprint(self, result) -> str:
        """Create fingerprint for deduplication"""
        payload = result.payload
        text = payload.get("text", "").lower()
        
        # Create a simplified fingerprint (first 50 chars + collection)
        collection = getattr(result, 'collection', 'unknown')
        return f"{collection}:{text[:50]}"
    
    def _deduplicate_skills(self, skills_results: List) -> List:
        """Specialized deduplication for technical skills"""
        seen_skills = set()
        deduplicated = []
        
        for result in skills_results:
            skill_text = result.payload.get("text", "").lower().strip()
            
            # Normalize skill text for comparison
            normalized = re.sub(r'[^\w\s]', '', skill_text)
            words = normalized.split()
            
            # Check if this is a duplicate of a previously seen skill
            is_duplicate = False
            for seen in seen_skills:
                if any(word in seen for word in words) or any(seen_word in normalized for seen_word in seen.split()):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                seen_skills.add(normalized)
                deduplicated.append(result)
        
        return deduplicated

    # ---------------------------------------------------------------------
    # Utility Methods
    # ---------------------------------------------------------------------
    
    def get_retrieval_metrics(self, results: Dict) -> Dict[str, Any]:
        """Calculate retrieval metrics for analysis"""
        total_results = sum(len(v) for v in results["results_by_collection"].values())
        domain_matches = 0
        skill_matches = 0
        
        for collection_name, results_list in results["results_by_collection"].items():
            for result in results_list:
                if result.payload.get("domain") == results["jd_analysis"].get("domain"):
                    domain_matches += 1
        
        return {
            "total_results": total_results,
            "domain_match_rate": domain_matches / total_results if total_results > 0 else 0,
            "collections_retrieved": list(results["results_by_collection"].keys())
        }