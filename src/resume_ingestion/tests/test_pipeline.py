#!/usr/bin/env python3
"""
Test script to verify the complete pipeline with Docker services.
"""

import time

from resume_ingestion.database.mongodb_manager import MongoDBManager
from resume_ingestion.vector_store.qdrant_manager import QdrantManager
from resume_ingestion.vector_store.embeddings import EmbeddingService
from resume_ingestion.ingestion.batch_ingestion_processor import BatchIngestionProcessor
from src.utils.logger import get_logger
logger = get_logger("PipelineTest")
# Configure logging


def test_mongodb_connection():
    """Test MongoDB connection and basic operations."""
    logger.info("🧪 Testing MongoDB connection...")
    
    try:
        mongo_manager = MongoDBManager()
        
        # Test connection
        if not mongo_manager.health_check():
            logger.error("❌ MongoDB health check failed")
            return False
        
        # Test basic operations
        test_doc = {
            "_id": "pipeline-test-doc",
            "source_url": "https://example.com/pipeline-test",
            "category": "pipeline_test",
            "domain": "Software Engineering", 
            "job_role": "Pipeline Test Engineer",
            "qdrant_status": "pending",
            "processing_status": "test_data",
            "scraped_at": "2024-01-15T10:00:00Z",
            "experiences": [
                {
                    "job_role": "Test Developer",
                    "responsibilities": ["Testing the pipeline", "Verifying data flow"]
                }
            ],
            "skills": ["Python", "Testing", "Docker", "MongoDB"]
        }
        
        # Insert test document
        result = mongo_manager.collection.insert_one(test_doc)
        logger.info(f"✅ MongoDB test document inserted: {result.inserted_id}")
        
        # Read it back
        retrieved = mongo_manager.collection.find_one({"_id": "pipeline-test-doc"})
        if retrieved:
            logger.info("✅ MongoDB document retrieval successful")
        else:
            logger.error("❌ MongoDB document retrieval failed")
            return False
            
        # Test batch operations
        pending_docs = mongo_manager.get_pending_documents_batch(limit=5)
        logger.info(f"✅ MongoDB batch operation: Found {len(pending_docs)} pending documents")
        
        mongo_manager.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ MongoDB test failed: {e}")
        return False

def test_embedding_service():
    """Test embedding service initialization and encoding."""
    logger.info("🧪 Testing Embedding Service...")
    
    try:
        embedding_service = EmbeddingService()
        
        # Test model info
        model_info = embedding_service.get_model_info()
        logger.info(f"✅ Embedding model loaded: {model_info}")
        
        # Test encoding
        test_texts = ["This is a test sentence.", "Another test for embedding."]
        embeddings = embedding_service.encode_texts(test_texts)
        
        if embeddings and len(embeddings) == len(test_texts):
            logger.info(f"✅ Embedding generation successful: {len(embeddings)} vectors created")
            logger.info(f"✅ Vector dimension: {len(embeddings[0])}")
        else:
            logger.error("❌ Embedding generation failed")
            return False
            
        # Test text chunking
        long_text = "This is a long text that should be chunked. " * 50
        chunks = embedding_service.chunk_text(long_text)
        
        if chunks and len(chunks) > 0:
            logger.info(f"✅ Text chunking successful: {len(chunks)} chunks created")
        else:
            logger.error("❌ Text chunking failed")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Embedding service test failed: {e}")
        return False

def test_qdrant_connection():
    """Test Qdrant connection and collection management."""
    logger.info("🧪 Testing Qdrant connection...")
    
    try:
        qdrant_manager = QdrantManager()
        
        # Test connection
        if not qdrant_manager.health_check():
            logger.error("❌ Qdrant health check failed")
            return False
        
        # Test collection info
        collections = qdrant_manager.collections_mapping
        logger.info(f"✅ Qdrant collections configured: {list(collections.values())}")
        
        for collection_name in collections.values():
            info = qdrant_manager.get_collection_info(collection_name)
            if info:
                logger.info(f"✅ Collection '{collection_name}': {info['points_count']} points")
            else:
                logger.warning(f"⚠️  Collection '{collection_name}' not found (will be created during processing)")
        
        qdrant_manager.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Qdrant test failed: {e}")
        return False

def test_complete_pipeline():
    """Test the complete pipeline with a sample resume."""
    logger.info("🧪 Testing Complete Pipeline...")
    
    try:
        # Create a test resume
        test_resume = {
            "_id": "complete-pipeline-test",
            "source_url": "https://example.com/complete-test",
            "category": "software_engineer",
            "domain": "Software Engineering",
            "job_role": "Senior Full Stack Developer",
            "qdrant_status": "pending",
            "processing_status": "test_data",
            "scraped_at": "2024-01-15T10:00:00Z",
            "experiences": [
                {
                    "job_role": "Senior Developer",
                    "environment": "AWS, Docker, Kubernetes, React, Node.js",
                    "responsibilities": [
                        "Developed scalable microservices architecture",
                        "Led team of 5 developers on product features",
                        "Implemented CI/CD pipelines reducing deployment time by 60%"
                    ]
                }
            ],
            "skills": ["Python", "JavaScript", "React", "Node.js", "AWS", "Docker", "Kubernetes"],
            "education": [
                "Bachelor of Science in Computer Science - University of Test (2015-2019)"
            ]
        }
        
        # Initialize pipeline components
        mongo_manager = MongoDBManager()
        qdrant_manager = QdrantManager()
        
        # Insert test resume into MongoDB
        mongo_manager.collection.insert_one(test_resume)
        logger.info("✅ Test resume inserted into MongoDB")
        
        # Process through pipeline
        processor = BatchIngestionProcessor(batch_size=10)
        
        # Test single document processing
        success = processor.process_single_document(test_resume)
        
        if success:
            logger.info("✅ Complete pipeline test successful!")
            
            # Verify the document was marked as ingested
            updated_doc = mongo_manager.collection.find_one({"_id": "complete-pipeline-test"})
            if updated_doc and updated_doc.get("qdrant_status") == "ingested":
                logger.info("✅ Document successfully marked as ingested in MongoDB")
            else:
                logger.warning("⚠️  Document not marked as ingested")
                
        else:
            logger.error("❌ Pipeline processing failed")
            return False
            
        # Clean up
        mongo_manager.collection.delete_one({"_id": "complete-pipeline-test"})
        processor.close()
        mongo_manager.close()
        qdrant_manager.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Complete pipeline test failed: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("🚀 Starting Pipeline Integration Tests")
    logger.info("=" * 60)
    
    # Wait a bit for Docker services to be fully ready
    logger.info("⏳ Waiting for Docker services to be ready...")
    time.sleep(10)
    
    tests = [
        ("MongoDB Connection", test_mongodb_connection),
        ("Embedding Service", test_embedding_service),
        ("Qdrant Connection", test_qdrant_connection),
        ("Complete Pipeline", test_complete_pipeline),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
            # Small delay between tests
            time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    logger.info("=" * 60)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{test_name:.<30} {status}")
    
    all_passed = all(success for _, success in results)
    
    if all_passed:
        logger.info("🎉 ALL TESTS PASSED! Pipeline is ready.")
    else:
        logger.error("💥 SOME TESTS FAILED! Check the logs above.")
    
    return all_passed

if __name__ == "__main__":
    print("")
    print("Running tests...")
    success = main()
    print("Tests completed.")
    exit(0 if success else 1)