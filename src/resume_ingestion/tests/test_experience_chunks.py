# tests/test_experience_chunks.py
from resume_ingestion.vector_store.qdrant_manager import QdrantManager
from resume_ingestion.database.mongodb_manager import MongoDBManager

def test_experience_chunks():
    qdrant = QdrantManager()
    mongo = MongoDBManager()
    
    # Get a document
    doc = mongo.collection.find_one({"qdrant_status": "pending"})
    if not doc:
        print("❌ No pending documents found")
        return
    
    print("🧪 Testing experience chunk processing...")
    
    # Prepare points
    points = qdrant.prepare_points_for_resume(doc)
    
    for collection_name, collection_points in points.items():
        print(f"\n📊 {collection_name}: {len(collection_points)} points")
        
        if collection_points and collection_name == "experiences":
            # Show experience chunks
            for i, point in enumerate(collection_points[:2]):  # Show first 2
                payload = point['payload']
                print(f"   Experience {i}:")
                print(f"     Role: {payload.get('experience_role')}")
                print(f"     Chunk: {payload.get('chunk_index')+1}/{payload.get('total_chunks')}")
                print(f"     Text preview: {payload.get('text', '')[:100]}...")
    
    if points:
        print(f"\nUpserting to vector store...")
        qdrant.upsert_to_qdrant(points)
        
        # Check what got stored
        for collection_name in points.keys():
            sample_payloads = qdrant.get_payload_sample(collection_name, 2)
            print(f"\n📋 Sample payloads from {collection_name}:")
            for i, payload in enumerate(sample_payloads):
                print(f"   [{i}] {payload}")

if __name__ == "__main__":
    test_experience_chunks()