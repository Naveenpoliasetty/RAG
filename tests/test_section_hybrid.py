"""
Test script for section-level hybrid search
"""
import asyncio
from src.generation.resume_generator import orchestrate_resume_generation

async def test_section_level_hybrid():
    jd = """Job Description:
We are seeking an experienced Oracle Sales Cloud Consultant to support implementation, customization, and optimization of Oracle CX Sales applications.

Key Responsibilities:
- Implement and configure Oracle Sales Cloud modules (Leads, Opportunities, Accounts, Contacts, and Forecasting).
- Gather business requirements and translate them into functional solutions.  
- Develop custom reports and dashboards using OTBI/BIP.
- Collaborate with technical teams for integrations and data migration.

Required Skills:
- Hands-on experience in Oracle Sales Cloud (B2B/B2C) implementation and support.
- Strong understanding of sales automation processes and CRM best practices.
- Knowledge of OIC, Groovy scripting, and REST/SOAP integrations.
"""
    job_roles = ["Oracle Sales Cloud Consultant", "Oracle Consultant", "Sales Consultant"]
    
    print("="*80)
    print("TESTING SECTION-LEVEL HYBRID SEARCH")
    print("="*80)
    print(f"Job Description: Oracle Sales Cloud Consultant")
    print(f"Job Roles Filter: {job_roles}")
    print(f"Hybrid Weights: semantic=0.7, keyword=0.3 (defaults)")
    print()
    
    print("Testing section-specific hybrid search...")
    print("Each section will search independently and may return different resumes!")
    print()
    
    result = await orchestrate_resume_generation(
        job_description=jd,
        job_roles=job_roles,
        top_k_summary=3,
        top_k_skills=3,
        top_k_experience=5
    )
    
    print("\n" + "="*80)
    print(" Section-level hybrid search completed successfully!")
    print("="*80)
    print(f"Result sections: {list(result.keys())}")
    
    return result

if __name__ == "__main__":
    result = asyncio.run(test_section_level_hybrid())
