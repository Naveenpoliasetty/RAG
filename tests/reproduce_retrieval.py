import json
from src.retriever.get_ids import ResumeIdsRetriever

def run_retrieval():
    retriever = ResumeIdsRetriever()
    
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
    
    print("Running retrieval with sample JD...")
    top_list, compact = retriever.generate_candidate_pool_and_contents(jd, top_k_resume=5)
    
    print(f"Top {len(top_list)} results:")
    for rank, (rid, score) in enumerate(top_list, 1):
        print(f"{rank}. Resume ID: {rid}, Score: {score}")
        # Print some keywords if available in compact
        if rid in compact:
            print(f"   Signals: {compact[rid].get('signals', {}).get('raw', {}).keys()}")

if __name__ == "__main__":
    run_retrieval()
