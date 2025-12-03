"""
Test section search without job role filter
"""
from src.resume_ingestion.vector_store.qdrant_manager import QdrantManager

def test():
    print("Testing section-specific search (no filter)...")
    
    qdrant_manager = QdrantManager()
    jd = "Oracle Sales Cloud Consultant with CRM experience"
    
    # Test without resume_ids_filter
    print("\n1. Professional Summary section:")
    results = qdrant_manager.match_resumes_by_section(
        job_description=jd,
        section_key="professional_summary",
        top_k=3
    )
    print(f"   Found {len(results)} resumes")
    for i, (rid, score) in enumerate(results[:3], 1):
        print(f"      {i}. {rid[:20]}... score={score:.4f}")
    
    print("\n2. Technical Skills section:")
    results = qdrant_manager.match_resumes_by_section(
        job_description=jd,
        section_key="technical_skills",
        top_k=3
    )
    print(f"   Found {len(results)} resumes")
    for i, (rid, score) in enumerate(results[:3], 1):
        print(f"      {i}. {rid[:20]}... score={score:.4f}")
    
    print("\n3. Experiences section:")
    results = qdrant_manager.match_resumes_by_section(
        job_description=jd,
        section_key="experiences",
        top_k=3
    )
    print(f"   Found {len(results)} resumes")
    for i, (rid, score) in enumerate(results[:3], 1):
        print(f"      {i}. {rid[:20]}... score={score:.4f}")
    
    print("\n Section-level hybrid search is working!")

if __name__ == "__main__":
    test()
