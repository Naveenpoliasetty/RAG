"""
Quick test to verify the generate_resume API uses hybrid search
"""
import asyncio
from src.generation.resume_generator import orchestrate_resume_generation

async def test_hybrid_search_in_api():
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
    job_roles = ["Oracle Sales Cloud Consultant", "Oracle Consultant", "Sales Consultant"]
    
    print("Testing hybrid search in orchestrate_resume_generation...")
    print(f"Using JD with Oracle Sales Cloud keywords")
    print(f"Job roles filter: {job_roles}")
    print(f"Hybrid weights: semantic=0.7, keyword=0.3 (defaults)")
    print()
    
    result = await orchestrate_resume_generation(
        job_description=jd,
        job_roles=job_roles
        # Using default weights: semantic_weight=0.7, keyword_weight=0.3
    )
    
    print(" Test completed successfully!")
    print(f"Result keys: {result.keys()}")
    
    # Test with custom weights
    print("\n" + "="*50)
    print("Testing with custom weights (semantic=0.5, keyword=0.5)...")
    result2 = await orchestrate_resume_generation(
        job_description=jd,
        job_roles=job_roles,
        semantic_weight=0.5,
        keyword_weight=0.5
    )
    print(" Custom weights test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_hybrid_search_in_api())
