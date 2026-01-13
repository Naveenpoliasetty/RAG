
import json
import os
import sys
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.core.settings import config

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)

def extract_failed_resumes():
    client = None
    try:
        print("Connecting to MongoDB...")
        # Connect directly using config to avoid unexpected refactoring dependencies
        client = MongoClient(
            config.mongodb_uri,
            serverSelectionTimeoutMS=config.get('mongodb.timeout_ms', 30000)
        )
        db = client[config.mongodb_database]
        # Use the hardcoded collection name as seen in llm_scraper.py or from config
        collection_name = "failed_resumes"
        collection = db[collection_name]
        
        print(f"Fetching records from '{collection_name}' collection...")
        cursor = collection.find({})
        records = list(cursor)
        
        print(f"Found {len(records)} records.")
        
        output_file = "failed_resumes.json"
        print(f"Writing to {output_file}...")
        
        with open(output_file, 'w') as f:
            json.dump(records, f, cls=JSONEncoder, indent=2)
            
        print("Extraction complete.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if client:
            client.close()
            print("MongoDB connection closed.")

if __name__ == "__main__":
    extract_failed_resumes()
