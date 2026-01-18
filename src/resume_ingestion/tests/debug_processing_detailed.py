# tests/debug_processing_detailed.py
from src.utils.logger import get_logger
from resume_ingestion.vector_store.qdrant_manager import QdrantManager
from resume_ingestion.database.mongodb_manager import MongoDBManager

# Enable detailed logging
logger = get_logger("DebugProcessingDetailed")

def debug_processing_detailed():
    mongo = MongoDBManager()
    qdrant = QdrantManager()
    
    logger.info("=" * 60)
    logger.info("🔍 DETAILED PROCESSING DEBUG")
    logger.info("=" * 60)
    
    # Get one pending document
    doc = mongo.collection.find_one({"qdrant_status": "pending"})
    if not doc:
        logger.error("No pending documents found")
        return
    
    doc_id = doc.get('_id', 'Unknown')
    logger.info(f"📄 Document ID: {doc_id}")
    logger.info(f"   Category: {doc.get('category')}")
    logger.info(f"   Job Role: {doc.get('job_role')}")
    logger.info(f"   Source URL: {doc.get('source_url')}")
    
    # Detailed content analysis
    logger.info("\nCONTENT ANALYSIS:")
    
    # Professional Summary
    prof_summary = doc.get('professional_summary')
    if prof_summary:
        if isinstance(prof_summary, list):
            logger.info(f"    Professional Summary: {len(prof_summary)} items")
            for i, item in enumerate(prof_summary[:2]):  # Show first 2 items
                if item and isinstance(item, str):
                    logger.info(f"      [{i}] {item[:100]}...")
                else:
                    logger.info(f"      [{i}] INVALID TYPE: {type(item)}")
        elif isinstance(prof_summary, str):
            logger.info(f"Professional Summary: string ({len(prof_summary)} chars)")
            logger.info(f"Preview: {prof_summary[:100]}...")
        else:
            logger.info(f"Professional Summary: UNEXPECTED TYPE: {type(prof_summary)}")
    else:
        logger.info("Professional Summary: EMPTY")
    
    # Technical Skills
    tech_skills = doc.get('technical_skills')
    if tech_skills:
        if isinstance(tech_skills, list):
            logger.info(f"    Technical Skills: {len(tech_skills)} items")
            for i, skill in enumerate(tech_skills[:3]):  # Show first 3 skills
                if skill and isinstance(skill, str):
                    logger.info(f"      [{i}] {skill}")
                else:
                    logger.info(f"      [{i}] INVALID TYPE: {type(skill)}")
        else:
            logger.info(f"Technical Skills: UNEXPECTED TYPE: {type(tech_skills)}")
    else:
        logger.info("Technical Skills: EMPTY")
    
    # Experiences
    experiences = doc.get('experiences', [])
    logger.info(f"   Experiences: {len(experiences)} items")
    for i, exp in enumerate(experiences[:2]):  # Show first 2 experiences
        logger.info(f"      Experience {i}:")
        logger.info(f"        Job Role: {exp.get('job_role', 'N/A')}")
        logger.info(f"        Company: {exp.get('company', 'N/A')}")
        responsibilities = exp.get('responsibilities', [])
        logger.info(f"        Responsibilities: {len(responsibilities)} items")
        for j, resp in enumerate(responsibilities[:2]):  # Show first 2 responsibilities
            if resp and isinstance(resp, str):
                logger.info(f"          [{j}] {resp[:80]}...")
            else:
                logger.info(f"          [{j}] INVALID: {type(resp)}")
    
    logger.info("\nESTING EMBEDDING GENERATION...")
    
    # Test the prepare_points_for_resume method step by step
    try:
        points = qdrant.prepare_points_for_resume(doc)
        logger.info("prepare_points_for_resume completed")
    except Exception as e:
        logger.error(f"prepare_points_for_resume FAILED: {e}")
        return
    
    # Analyze the generated points
    total_points = 0
    logger.info("\nPOINTS GENERATION RESULTS:")
    
    for collection_name, collection_points in points.items():
        logger.info(f"   {collection_name}: {len(collection_points)} points")
        total_points += len(collection_points)
        
        # Show details of first point if available
        if collection_points:
            first_point = collection_points[0]
            logger.info("      First point details:")
            logger.info(f"        ID: {first_point.get('id')}")
            vector = first_point.get('vector', [])
            logger.info(f"        Vector: {len(vector)} dimensions")
            payload = first_point.get('payload', {})
            logger.info(f"        Payload keys: {list(payload.keys())}")
            logger.info(f"        Section: {payload.get('section')}")
            text = payload.get('text', '')
            logger.info(f"        Text length: {len(text)} chars")
            logger.info(f"        Text preview: {text[:80]}...")
        else:
            logger.info("      No points generated for this collection")
    
    logger.info(f"\nSUMMARY: {total_points} total points generated")
    
    if total_points > 0:
        logger.info("\n TESTING QDRANT UPSERT...")
        try:
            qdrant.upsert_to_qdrant(points)
            logger.info(" Upsert completed successfully!")
            
            # Update document status
            mongo.collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"qdrant_status": "completed"}}
            )
            logger.info(" Document marked as completed")
            
        except Exception as e:
            logger.error(f"❌ Upsert FAILED: {e}")
    else:
        logger.error("❌ No points were generated - this is the problem!")
        
        # Let's test embedding generation manually
        logger.info("\nMANUAL EMBEDDING TEST:")
        test_text = "This is a test sentence for embedding generation"
        try:
            vectors = qdrant.embedding_service.encode_texts([test_text])
            if vectors and len(vectors) > 0:
                logger.info(f" Manual embedding test PASSED: {len(vectors[0])} dimensions")
            else:
                logger.error("Manual embedding test FAILED: No vectors returned")
        except Exception as e:
            logger.error(f"❌ Manual embedding test FAILED: {e}")

if __name__ == "__main__":
    debug_processing_detailed()