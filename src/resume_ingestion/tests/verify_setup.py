# verify_setup.py
from pymongo import MongoClient
import sys

def verify_mongodb_setup():
    try:
        client = MongoClient("mongodb://admin:password@localhost:27017/", serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        print(" MongoDB connection successful")
        
        db = client["resumes_db"]
        
        print("🔍 Checking MongoDB setup...")
        
        # Check database exists
        db_names = client.list_database_names()
        if "resumes_db" in db_names:
            print(" Database 'resumes_db' exists")
        else:
            print("❌ Database 'resumes_db' not found")
            return False
        
        # Check collection exists
        collection_names = db.list_collection_names()
        if "resumes" in collection_names:
            print(" Collection 'resumes' exists")
        else:
            print("❌ Collection 'resumes' not found")
            return False
        
        # Check indexes
        indexes = db.resumes.index_information()
        print("📊 Current indexes:", list(indexes.keys()))
        
        expected_indexes = ['source_url_1', 'qdrant_status_1', 'scraped_at_-1', 'category_1']
        
        for index in expected_indexes:
            if index in indexes:
                print(f" Index '{index}' exists")
            else:
                print(f"❌ Index '{index}' not found")
        
        # Check test data
        count = db.resumes.count_documents({})
        print(f"📊 Total documents: {count}")
        
        test_doc = db.resumes.find_one({"_id": "test-resume-001"})
        if test_doc:
            print(" Test document found")
            print(f"   Category: {test_doc.get('category')}")
            print(f"   Status: {test_doc.get('qdrant_status')}")
        else:
            print("❌ Test document not found")
            print("   Inserting test document...")
            
            # Insert test document
            db.resumes.insert_one({
                "_id": "test-resume-001",
                "source_url": "https://example.com/test-resume",
                "category": "test",
                "domain": "Software Engineering",
                "job_role": "Test Engineer",
                "qdrant_status": "pending",
                "processing_status": "test_data",
                "scraped_at": "2024-01-15T10:00:00Z",
                "experiences": [
                    {
                        "job_role": "Test Developer",
                        "responsibilities": ["Testing pipeline", "Writing test cases"]
                    }
                ],
                "skills": ["Python", "Testing", "Docker"]
            })
            print(" Test document inserted")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ MongoDB verification failed: {e}")
        return False

if __name__ == "__main__":
    success = verify_mongodb_setup()
    sys.exit(0 if success else 1)