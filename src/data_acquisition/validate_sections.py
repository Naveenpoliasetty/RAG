import os
import sys
import re
import requests
from datetime import datetime
from pymongo import MongoClient
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Add project root to path to ensure we can import src modules if needed
sys.path.append(os.getcwd())

from src.core.settings import config

def validate_resumes():
    """
    Scans 'failed_resumes' for documents missing 'TECHNICAL SKILLS'.
    Verifies if they are truly missing using Regex.
    If missing:
        - Inserts into 'discarded_resume' collection.
        - Updates 'failed_resumes' document with 'inconsistent_resume': True.
    """
    
    # 1. Connect to MongoDB
    # Using config for URI, but defaulting to hardcoded DB/Collection names as per user context
    client = MongoClient(config.mongodb_uri)
    db = client[config.mongodb_database]
    
    # Collections
    failed_collection = db["failed_resumes"]
    discarded_collection = db["discarded_resume"]
    
    print(f"Connected to DB: {config.mongodb_database}")
    
    # 2. Query for likely candidates (optimization)
    # We look for documents that failed due to missing technical skills
    query = {"error_message": {"$regex": "Missing TECHNICAL SKILLS section", "$options": "i"}}
    
    cursor = failed_collection.find(query)
    count = failed_collection.count_documents(query)
    
    print(f"Found {count} candidate resumes to validate.")
    
    processed_count = 0
    discarded_count = 0
    
    # Compile Regex Pattern
    # Matches "TECHNICAL SKILLS" or just "SKILLS" (case-insensitive)
    # Anchored to ensure it's a standalone header, allowing optional colon and whitespace
    skills_pattern = re.compile(r"^\s*(?:TECHNICAL\s+)?SKILLS\s*:?\s*$", re.IGNORECASE)
    
    for doc in cursor:
        url = doc.get('source_url')
        if not url:
            continue
            
        try:
            # 3. Fetch Content
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            if resp.status_code != 200:
                print(f"xx Failed to fetch URL: {url} (Status: {resp.status_code})")
                continue
                
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 4. robust Regex Check
            # Targeted search within 'single-post-body' as per user knowledge
            container = soup.find("div", class_="single-post-body")
            skills_found = False
            
            if container:
                # We look specifically within <u> tags as they denote headers in this dataset
                # Scan paragraphs WITHIN the container
                for p in container.find_all("p"):
                    u_tag = p.find("u")
                    if u_tag:
                        text = u_tag.get_text(strip=True)
                        if skills_pattern.search(text):
                            skills_found = True
                            break
            else:
                print(f"xx Container 'single-post-body' not found for: {url}")
                # If container is missing, we can't verify 'Technical Skills' is missing safely, 
                # or we assume it's a structural failure. 
                # For now, let's skip processing if container is gone to be safe, 
                # or treat as broken. Given explicit instruction, if container is missing, we likely can't validate.
                continue
            
            # 5. Handle Results
            if not skills_found:
                print(f"__ CONFIRMED MISSING: {url}")
                
                # Check if already in discarded to avoid duplicates
                if not discarded_collection.find_one({"source_url": url}):
                    discard_record = {
                        "source_url": url,
                        "missing_part": "TECHNICAL SKILLS",
                        "ingested_at": datetime.now()
                    }
                    discarded_collection.insert_one(discard_record)
                    print("   -> Added to discarded_resume")
                else:
                    print("   -> Already in discarded_resume")

                # Update failed_resumes
                failed_collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"inconsistent_resume": True}}
                )
                print("   -> Flagged as inconsistent_resume")
                discarded_count += 1
            else:
                print(f"OK FALSE POSITIVE (Skills Found): {url}")
            
            processed_count += 1
            
        except Exception as e:
            print(f"!! Error processing {url}: {e}")

    print(f"\nValidation Complete.")
    print(f"Processed: {processed_count}")
    print(f"Discarded: {discarded_count}")

if __name__ == "__main__":
    validate_resumes()
