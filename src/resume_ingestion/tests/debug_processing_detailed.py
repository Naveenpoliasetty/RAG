# tests/debug_processing_detailed.py
import logging
from resume_ingestion.vector_store.qdrant_manager import QdrantManager
from resume_ingestion.database.mongodb_manager import MongoDBManager

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

def debug_processing_detailed():
    mongo = MongoDBManager()
    qdrant = QdrantManager()
    
    print("=" * 60)
    print("🔍 DETAILED PROCESSING DEBUG")
    print("=" * 60)
    
    # Get one pending document
    doc = mongo.collection.find_one({"qdrant_status": "pending"})
    if not doc:
        print("No pending documents found")
        return
    
    doc_id = doc.get('_id', 'Unknown')
    print(f"📄 Document ID: {doc_id}")
    print(f"   Category: {doc.get('category')}")
    print(f"   Job Role: {doc.get('job_role')}")
    print(f"   Source URL: {doc.get('source_url')}")
    
    # Detailed content analysis
    print("\nCONTENT ANALYSIS:")
    
    # Professional Summary
    prof_summary = doc.get('professional_summary')
    if prof_summary:
        if isinstance(prof_summary, list):
            print(f"   ✅ Professional Summary: {len(prof_summary)} items")
            for i, item in enumerate(prof_summary[:2]):  # Show first 2 items
                if item and isinstance(item, str):
                    print(f"      [{i}] {item[:100]}...")
                else:
                    print(f"      [{i}] INVALID TYPE: {type(item)}")
        elif isinstance(prof_summary, str):
            print(f"Professional Summary: string ({len(prof_summary)} chars)")
            print(f"Preview: {prof_summary[:100]}...")
        else:
            print(f"Professional Summary: UNEXPECTED TYPE: {type(prof_summary)}")
    else:
        print("Professional Summary: EMPTY")
    
    # Technical Skills
    tech_skills = doc.get('technical_skills')
    if tech_skills:
        if isinstance(tech_skills, list):
            print(f"   ✅ Technical Skills: {len(tech_skills)} items")
            for i, skill in enumerate(tech_skills[:3]):  # Show first 3 skills
                if skill and isinstance(skill, str):
                    print(f"      [{i}] {skill}")
                else:
                    print(f"      [{i}] INVALID TYPE: {type(skill)}")
        else:
            print(f"Technical Skills: UNEXPECTED TYPE: {type(tech_skills)}")
    else:
        print("Technical Skills: EMPTY")
    
    # Experiences
    experiences = doc.get('experiences', [])
    print(f"   Experiences: {len(experiences)} items")
    for i, exp in enumerate(experiences[:2]):  # Show first 2 experiences
        print(f"      Experience {i}:")
        print(f"        Job Role: {exp.get('job_role', 'N/A')}")
        print(f"        Company: {exp.get('company', 'N/A')}")
        responsibilities = exp.get('responsibilities', [])
        print(f"        Responsibilities: {len(responsibilities)} items")
        for j, resp in enumerate(responsibilities[:2]):  # Show first 2 responsibilities
            if resp and isinstance(resp, str):
                print(f"          [{j}] {resp[:80]}...")
            else:
                print(f"          [{j}] INVALID: {type(resp)}")
    
    print("\nESTING EMBEDDING GENERATION...")
    
    # Test the prepare_points_for_resume method step by step
    try:
        points = qdrant.prepare_points_for_resume(doc)
        print("prepare_points_for_resume completed")
    except Exception as e:
        print(f"prepare_points_for_resume FAILED: {e}")
        return
    
    # Analyze the generated points
    total_points = 0
    print("\nPOINTS GENERATION RESULTS:")
    
    for collection_name, collection_points in points.items():
        print(f"   {collection_name}: {len(collection_points)} points")
        total_points += len(collection_points)
        
        # Show details of first point if available
        if collection_points:
            first_point = collection_points[0]
            print("      First point details:")
            print("        ID: {first_point.get('id')}")
            vector = first_point.get('vector', [])
            print(f"        Vector: {len(vector)} dimensions")
            payload = first_point.get('payload', {})
            print(f"        Payload keys: {list(payload.keys())}")
            print(f"        Section: {payload.get('section')}")
            text = payload.get('text', '')
            print(f"        Text length: {len(text)} chars")
            print(f"        Text preview: {text[:80]}...")
        else:
            print("      No points generated for this collection")
    
    print(f"\nSUMMARY: {total_points} total points generated")
    
    if total_points > 0:
        print("\n TESTING QDRANT UPSERT...")
        try:
            qdrant.upsert_to_qdrant(points)
            print(" Upsert completed successfully!")
            
            # Update document status
            mongo.collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"qdrant_status": "completed"}}
            )
            print("✅ Document marked as completed")
            
        except Exception as e:
            print(f"❌ Upsert FAILED: {e}")
    else:
        print("❌ No points were generated - this is the problem!")
        
        # Let's test embedding generation manually
        print("\nMANUAL EMBEDDING TEST:")
        test_text = "This is a test sentence for embedding generation"
        try:
            vectors = qdrant.embedding_service.encode_texts([test_text])
            if vectors and len(vectors) > 0:
                print(f"✅ Manual embedding test PASSED: {len(vectors[0])} dimensions")
            else:
                print("Manual embedding test FAILED: No vectors returned")
        except Exception as e:
            print(f"❌ Manual embedding test FAILED: {e}")

if __name__ == "__main__":
    debug_processing_detailed()