# check_qdrant.py
from resume_ingestion.vector_store.qdrant_manager import QdrantManager

def check_qdrant_collections():
    qdrant = QdrantManager()
    
    print("🔍 Qdrant Collections Status:")
    for key, collection_name in qdrant.collections_mapping.items():
        info = qdrant.get_collection_info(collection_name)
        if info:
            print(f"   {collection_name}: {info['points_count']} points")
        else:
            print(f"   {collection_name}: Failed to get info")
    
    # Test if we can query points
    try:
        for collection_name in qdrant.collections_mapping.values():
            points = qdrant.client.scroll(collection_name=collection_name, limit=5)
            print(f"\n📋 Sample points from {collection_name}:")
            for point in points[0]:  # points[0] contains the actual points
                print(f"   - ID: {point.id}, Payload keys: {list(point.payload.keys())}")
                break  # Just show first point
    except Exception as e:
        print(f"❌ Error querying points: {e}")

if __name__ == "__main__":
    check_qdrant_collections()