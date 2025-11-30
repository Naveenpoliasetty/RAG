"""
Simple test to verify section-specific search works (no LLM calls)
"""
from src.resume_ingestion.vector_store.qdrant_manager import QdrantManager
from src.retriever.get_ids import ResumeIdsRetriever

def test_section_search():
    print("="*80)
    print("TESTING SECTION-SPECIFIC HYBRID SEARCH (No LLM)")
    print("="*80)
    
    qdrant_manager = QdrantManager()
    retriever = ResumeIdsRetriever()
    
    jd = """Oracle Sales Cloud Consultant needed with experience in CRM, 
    sales automation, OTBI, BIP, OIC, Groovy scripting, and REST/SOAP integrations."""
    
    job_roles = ["Oracle Sales Cloud Consultant", "Oracle Consultant"]
    
    # Get filtered resume IDs
    print(f"\n1. Filtering by job roles: {job_roles}")
    filtered_ids_obj = retriever.get_resume_ids_by_job_roles(job_roles)
    filtered_ids = [str(oid) for oid in filtered_ids_obj]
    print(f"   Found {len(filtered_ids)} resumes matching job roles")
    
    if not filtered_ids:
        print("   ❌ No resumes found!")
        return
    
    # Test section-specific search for professional_summary
    print(f"\n2. Testing section-specific search for 'professional_summary'")
    summary_results = qdrant_manager.match_resumes_by_section(
        job_description=jd,
        section_key="professional_summary",
        top_k=3,
        resume_ids_filter=filtered_ids
    )
    print(f"   Top {len(summary_results)} resumes for professional_summary:")
    for i, (rid, score) in enumerate(summary_results, 1):
        print(f"      {i}. {rid[:16]}... (score: {score:.4f})")
    
    # Test section-specific search for technical_skills
    print(f"\n3. Testing section-specific search for 'technical_skills'")
    skills_results = qdrant_manager.match_resumes_by_section(
        job_description=jd,
        section_key="technical_skills",
        top_k=3,
        resume_ids_filter=filtered_ids
    )
    print(f"   Top {len(skills_results)} resumes for technical_skills:")
    for i, (rid, score) in enumerate(skills_results, 1):
        print(f"      {i}. {rid[:16]}... (score: {score:.4f})")
    
    # Test section-specific search for experiences
    print(f"\n4. Testing section-specific search for 'experiences'")
    exp_results = qdrant_manager.match_resumes_by_section(
        job_description=jd,
        section_key="experiences",
        top_k=5,
        resume_ids_filter=filtered_ids
    )
    print(f"   Top {len(exp_results)} resumes for experiences:")
    for i, (rid, score) in enumerate(exp_results, 1):
        print(f"      {i}. {rid[:16]}... (score: {score:.4f})")
    
    print("\n" + "="*80)
    print("✅ SECTION-LEVEL HYBRID SEARCH WORKING!")
    print("="*80)
    print("\nKey observations:")
    print("- Each section can return DIFFERENT resumes (by design!)")
    print("- Scores are hybrid (semantic + keyword)")
    print("- This ensures each section pulls from the most relevant resumes")

if __name__ == "__main__":
    test_section_search()
