#!/usr/bin/env python3
"""
Test script to diagnose Qdrant connection issue.
This replicates the exact initialization sequence from the application.
"""
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import time
from qdrant_client import QdrantClient
from src.core.settings import config
from src.utils.logger import get_logger

logger = get_logger("TestQdrant")

def test_direct_connection():
    """Test 1: Direct connection before any other imports"""
    print("\n" + "="*60)
    print("TEST 1: Direct Qdrant connection (before embedding model)")
    print("="*60)
    try:
        client = QdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port,
            timeout=30
        )
        collections = client.get_collections()
        print(f"✅ Connection successful!")
        print(f"   Host: {config.qdrant_host}:{config.qdrant_port}")
        print(f"   Collections: {[c.name for c in collections.collections]}")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def test_with_embedding_model():
    """Test 2: Connection after loading embedding model"""
    print("\n" + "="*60)
    print("TEST 2: Qdrant connection AFTER loading embedding model")
    print("="*60)
    
    # Load embedding model (this is what happens in QdrantManager.__init__)
    print("Loading embedding model...")
    from src.resume_ingestion.vector_store.embeddings import create_embedding_service
    embedding_service = create_embedding_service()
    print(f"✅ Embedding model loaded (dimension: {embedding_service.get_vector_size()})")
    
    # Now try Qdrant connection
    print("Connecting to Qdrant...")
    try:
        client = QdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port,
            timeout=30
        )
        collections = client.get_collections()
        print(f"✅ Connection successful!")
        print(f"   Host: {config.qdrant_host}:{config.qdrant_port}")
        print(f"   Collections: {[c.name for c in collections.collections]}")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_qdrant_manager():
    """Test 3: Full QdrantManager initialization"""
    print("\n" + "="*60)
    print("TEST 3: Full QdrantManager initialization")
    print("="*60)
    try:
        from src.resume_ingestion.vector_store.qdrant_manager import QdrantManager
        manager = QdrantManager()
        print("✅ QdrantManager initialized successfully!")
        return True
    except Exception as e:
        print(f"❌ QdrantManager initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n🔍 QDRANT CONNECTION DIAGNOSTIC TEST")
    print(f"   Config file: {config.config_path}")
    print(f"   Qdrant host: {config.qdrant_host}")
    print(f"   Qdrant port: {config.qdrant_port}")
    
    results = []
    
    # Run tests
    results.append(("Direct connection", test_direct_connection()))
    time.sleep(2)  # Brief pause between tests
    
    results.append(("With embedding model", test_with_embedding_model()))
    time.sleep(2)
    
    results.append(("QdrantManager", test_qdrant_manager()))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    if all(result for _, result in results):
        print("\n🎉 All tests passed! Qdrant connection is working.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
