from typing import List
from pymongo.errors import PyMongoError
from src.utils.logger import get_logger
from src.core.db_manager import get_mongodb_manager, get_qdrant_manager
from src.data_acquisition.parser import normalize_job_role
import json


logger = get_logger("DataRetrieverPipeline")

class ResumeIdsRetriever:
    def __init__(self, mongo_manager, qdrant_manager):
        # Use singleton instances
        self.mongo_manager = mongo_manager
        self.qdrant_manager = qdrant_manager
    
    def get_resume_ids_by_job_roles(self, job_roles: List[str]) -> List[str]:
        """
        Retrieve document IDs for given job roles from MongoDB.
        Uses consistent normalization to match how data is stored.
        
        Args:
            job_roles: List of job roles to filter by
            
        Returns:
            List of document IDs as strings (for use with Qdrant)
        """
        if not job_roles:
            logger.warning("Empty job_roles list provided")
            return []
        
        # Normalize job roles using the same function used during ingestion
        normalized_job_roles = []
        for role in job_roles:
            if role and role.strip():
                normalized = normalize_job_role(role.strip())
                if normalized:
                    normalized_job_roles.append(normalized)
        
        if not normalized_job_roles:
            logger.warning("No valid job roles after normalization")
            return []
        
        # Generate variations for roles with slashes to handle inconsistent DB data
        expanded_roles = set(normalized_job_roles)
        for role in normalized_job_roles:
            if "/" in role:
                # We want to generate all 4 combinations of spacing around slash:
                # "a/b", "a / b", "a/ b", "a /b"
                
                # First, standardize to " / " to make splitting easy
                # (normalize_job_role already reduces multiple spaces to one)
                temp = role.replace("/", " / ").replace("  ", " ")
                parts = temp.split(" / ")
                
                if len(parts) > 1:
                    # Reconstruct with different separators
                    # Note: This simple approach assumes one slash. 
                    # For multiple slashes, it might be combinatorial, but let's stick to simple replacement for now.
                    
                    # 1. No spaces: "a/b"
                    expanded_roles.add("/".join(parts))
                    # 2. Both spaces: "a / b"
                    expanded_roles.add(" / ".join(parts))
                    # 3. Left space: "a /b"
                    expanded_roles.add(" /".join(parts))
                    # 4. Right space: "a/ b"
                    expanded_roles.add("/ ".join(parts))

        search_roles = list(expanded_roles)
        logger.info(f"Searching MongoDB for job roles (normalized): {search_roles[:5]}...")

        try:
            # Query MongoDB - job_role field should be normalized during ingestion
            documents = list(self.mongo_manager.collection.find(
                {"job_role": {"$in": search_roles}},
                {"resume_id": 1}  # Return only resume_id
            ))
            
            # Extract resume_id as strings
            document_ids = [str(doc.get("resume_id", "")) for doc in documents if doc.get("resume_id")]
            
            logger.info(f"Retrieved {len(document_ids)} document IDs from MongoDB for job roles: {job_roles}")
            return document_ids
            
        except PyMongoError as e:
            logger.error(f"Error retrieving document IDs for job roles {job_roles}: {e}", exc_info=True)
            return []

    def generate_candidate_pool_and_contents(self, job_description: str, top_k_resume=10):
        
        top_list, details = self.qdrant_manager.match_resumes_for_job_description(
            job_description=job_description,
            per_collection_top_k=200,
            aggregate_top_k=top_k_resume,
            weights={"technical_skills": 0.45, "experiences": 0.35, "professional_summary": 0.2},
            score_aggregation="max"
        )

        top_ids = [rid for rid, _ in top_list]
        contents = self.qdrant_manager.fetch_all_payloads_for_resume_ids(top_ids)

        # Optionally, prepare compact structures for downstream LLM prompt
        compact = {}
        for rid in top_ids:
            comp = {
                "resume_id": rid,
                "summary_text": " ".join([p.get("text", "") for p in contents[rid].get("professional_summary", [])])[:2000],
                "skills_text": " ".join([p.get("text", "") for p in contents[rid].get("technical_skills", [])])[:2000],
                "experience_texts": [p.get("text", "") for p in contents[rid].get("experiences", [])],
                "signals": details.get(rid, {})
            }
            compact[rid] = comp

        return top_list, compact



if __name__ == "__main__":
    retriever = ResumeIdsRetriever()
    job_roles = ["Sap Modular", "Sap Pp/mm/qm Functional Analyst"]
    document_ids = retriever.get_resume_ids_by_job_roles(job_roles)
    print(document_ids)
    jd = """
    Job Description:
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
    top_list, compact = retriever.generate_candidate_pool_and_contents(jd)
    print(top_list)
    print("\n\n\n")
    print(compact)
    rr = {'job_description': jd, 'top_list': top_list, 'compact': compact}
    with open("result.json", "w") as f:
        json.dump(rr, f, indent=4)