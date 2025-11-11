# test_embeddings.py
import logging
from resume_ingestion.vector_store.embeddings import EmbeddingService
from resume_ingestion.database.mongodb_manager import MongoDBManager

logging.basicConfig(level=logging.DEBUG)

def test_embeddings():
    print("🧪 Testing Embedding Service...")
    
    # Test embedding service
    try:
        embedding_service = EmbeddingService()
        print(f"✅ Embedding service loaded: {embedding_service.get_model_info()}")
        
        # Test encoding
        test_texts = ["Hello world", "This is a test sentence for embedding"]
        vectors = embedding_service.encode_texts(test_texts)
        print(f"✅ Test encoding successful: {len(vectors)} vectors, each {len(vectors[0])} dimensions")
        
    except Exception as e:
        print(f"❌ Embedding service failed: {e}")
        return
    
    # Test MongoDB data
    try:
        mongo = MongoDBManager()
        # Get one document to test
        doc = mongo.collection.find_one({"qdrant_status": "pending"})
        if doc:
            print(f"✅ Found test document: {doc.get('_id')}")
            print(f"   Professional Summary: {doc.get('professional_summary', 'N/A')}")
            print(f"   Technical Skills: {doc.get('technical_skills', 'N/A')}")
        else:
            print("❌ No pending documents found")
            
    except Exception as e:
        print(f"❌ MongoDB test failed: {e}")

if __name__ == "__main__":
    test_embeddings()