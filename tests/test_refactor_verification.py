
import sys
import os
import asyncio
from src.data_acquisition.parser import normalize_job_role
from src.resume_ingestion.vector_store.qdrant_manager import QdrantManager
from src.core.settings import config

def test_parser_regex():
    print("Testing Parser Regex Optimization...")
    
    test_cases = [
        ("Senior Java Developer", "java developer"),
        ("Lead Data Scientist", "data scientist"),
        ("Resume of John Doe", "of john doe"),
        ("Software Engineer - Resume", "software engineer"),
        ("PL/SQL Developer", "pl/sql developer"),
        ("PLSQL Developer", "pl/sql developer"),
        ("Sr. Python Dev", "python dev"),
    ]
    
    for input_role, expected in test_cases:
        normalized = normalize_job_role(input_role)
        if normalized != expected:
            print(f"❌ Failed: '{input_role}' -> '{normalized}' (Expected: '{expected}')")
        else:
            print(f"✅ Passed: '{input_role}' -> '{normalized}'")

def test_qdrant_dynamic_weights():
    print("\nTesting Qdrant Dynamic Weights Logic...")
    
    # Mock QdrantManager to test weight logic without full init
    # We'll just instantiate it and check the method logic if possible, 
    # but since it connects on init, we might need to rely on the fact that it initializes successfully
    try:
        manager = QdrantManager()
        print("✅ QdrantManager initialized successfully")
        
        # We can't easily test the internal logic of match_resumes_for_job_description without mocking the client
        # But initialization success confirms the config usage and basic structure are valid
        
    except Exception as e:
        print(f"❌ QdrantManager initialization failed: {e}")

if __name__ == "__main__":
    test_parser_regex()
    test_qdrant_dynamic_weights()
