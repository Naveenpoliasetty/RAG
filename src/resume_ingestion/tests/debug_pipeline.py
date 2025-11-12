# debug_pipeline.py
import sys
from pymongo import MongoClient
from src.utils.logger import get_logger
logger = get_logger("DebugPipeline")
# Configure logging to see ALL output


def test_basic_connectivity():
    logger.info("🔧 Testing basic connectivity...")
    
    # Test MongoDB
    try:
        client = MongoClient("mongodb://admin:password@localhost:27017/", serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        logger.info("✅ MongoDB connection successful")
        
        db = client["resumes_db"]
        count = db.resumes.count_documents({})
        logger.info(f"✅ MongoDB has {count} documents in resumes collection")
        client.close()
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        return False
    
    # Test if we can import the modules
    try:
        logger.info("✅ MongoDBManager import successful")
    except ImportError as e:
        logger.error(f"❌ MongoDBManager import failed: {e}")
        return False
        
    try:
        from resume_ingestion.vector_store.qdrant_manager import QdrantManager #type: ignore
        logger.info("✅ QdrantManager import successful")
    except ImportError as e:
        logger.error(f"❌ QdrantManager import failed: {e}")
        return False
        
    try:
        from resume_ingestion.vector_store.embeddings import EmbeddingService
        logger.info("✅ EmbeddingService import successful")
    except ImportError as e:
        logger.error(f"❌ EmbeddingService import failed: {e}")
        return False
        
    return True

def test_mongodb_manager():
    logger.info("🔧 Testing MongoDBManager...")
    try:
        from resume_ingestion.database.mongodb_manager import MongoDBManager
        
        mongo = MongoDBManager()
        
        # Test health check
        if mongo.health_check():
            logger.info("✅ MongoDBManager health check passed")
        else:
            logger.error("❌ MongoDBManager health check failed")
            return False
        
        # Test getting pending documents
        pending = mongo.get_pending_documents_batch(limit=5)
        logger.info(f"✅ Found {len(pending)} pending documents")
        
        mongo.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ MongoDBManager test failed: {e}")
        return False

def test_qdrant_connection():
    logger.info("🔧 Testing Qdrant connection...")
    try:
        from resume_ingestion.vector_store.qdrant_manager import QdrantManager
        
        qdrant = QdrantManager()
        
        if qdrant.health_check():
            logger.info("✅ Qdrant health check passed")
        else:
            logger.error("❌ Qdrant health check failed")
            return False
            
        logger.info(f"✅ Qdrant collections: {qdrant.collections_mapping}")
        qdrant.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Qdrant test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting Pipeline Debug...")
    
    tests = [
        ("Basic Connectivity", test_basic_connectivity),
        ("MongoDB Manager", test_mongodb_manager), 
        ("Qdrant Connection", test_qdrant_connection),
    ]
    
    all_passed = True
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"🧪 Running: {test_name}")
        logger.info('='*50)
        try:
            success = test_func()
            if success:
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
                all_passed = False
        except Exception as e:
            logger.error(f"💥 {test_name} CRASHED: {e}")
            all_passed = False
    
    logger.info(f"\n{'='*50}")
    if all_passed:
        logger.info("🎉 ALL DEBUG TESTS PASSED!")
    else:
        logger.error("💥 SOME DEBUG TESTS FAILED!")
    
    sys.exit(0 if all_passed else 1)