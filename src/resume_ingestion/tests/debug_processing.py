# debug_processing.py
from resume_ingestion.vector_store.qdrant_manager import QdrantManager
from resume_ingestion.database.mongodb_manager import MongoDBManager

def debug_single_document():
    mongo = MongoDBManager()
    qdrant = QdrantManager()
    
    # Get one pending document
    doc = mongo.collection.find_one({"qdrant_status": "pending"})
    if not doc:
        print("❌ No pending documents found")
        return
    
    print(f"🔍 Processing document: {doc.get('_id')}")
    print(f"   Category: {doc.get('category')}")
    print(f"   Job Role: {doc.get('job_role')}")
    
    # Check content sections
    sections = ['professional_summary', 'technical_skills', 'experiences']
    for section in sections:
        content = doc.get(section)
        if content:
            if isinstance(content, list):
                print(f"   ✅ {section}: {len(content)} items")
                if content and isinstance(content[0], str):
                    print(f"      Preview: {content[0][:100]}...")
            elif isinstance(content, str):
                print(f"   ✅ {section}: {len(content)} chars")
                print(f"      Preview: {content[:100]}...")
        else:
            print(f"   ❌ {section}: EMPTY")
    
    # Test embedding generation
    print("\n🧪 Testing embedding generation...")
    points = qdrant.prepare_points_for_resume(doc)
    
    total_points = 0
    for collection_name, collection_points in points.items():
        print(f"   {collection_name}: {len(collection_points)} points")
        total_points += len(collection_points)
        
        # Show first point details if available
        if collection_points:
            first_point = collection_points[0]
            print(f"      First point - ID: {first_point['id']}")
            print(f"      Vector length: {len(first_point['vector'])}")
            print(f"      Payload section: {first_point['payload'].get('section')}")
            print(f"      Text preview: {first_point['payload'].get('text', '')[:80]}...")
    
    print(f"\n📊 Total points generated: {total_points}")
    
    if total_points > 0:
        print("✅ Ready to upsert to Qdrant!")
        # Actually upsert to test
        qdrant.upsert_to_qdrant(points)
        
        # Update document status
        mongo.collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"qdrant_status": "completed"}}
        )
        print("✅ Document marked as completed")
    else:
        print("❌ No points generated - check document content")

if __name__ == "__main__":
    debug_single_document()