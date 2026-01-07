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
    
    # 2. Query for ALL failed resumes (or filter as needed, but logic implies comprehensive check)
    # User requested checking resumes even if they didn't fail specifically on skills
    # So we remove the specific error filter.
    query = {} 
    
    cursor = failed_collection.find(query)
    count = failed_collection.count_documents(query)
    
    print(f"Found {count} candidate resumes to validate.")
    
    processed_count = 0
    discarded_count = 0
    valid_count = 0
    
    # Compile Regex Patterns
    # 1. Summary: Matches 'SUMMARY', 'PROFESSIONAL SUMMARY', optionally with colon
    #    Anchored start, allows trailing text directly (merged case) or optional colon + space
    #    Pattern: ^\s*(PROFESSIONAL\s+)?SUMMARY\s*:?\s*.*$ (but we just search for the header)
    summary_pattern = re.compile(r"^\s*(?:PROFESSIONAL\s+)?SUMMARY\s*:?", re.IGNORECASE)
    
    # 2. Skills: Matches 'SKILLS', 'TECHNICAL SKILLS', optionally with colon
    skills_pattern = re.compile(r"^\s*(?:TECHNICAL\s+)?SKILLS\s*:?", re.IGNORECASE)
    
    # 3. Experience: Matches 'PROFESSIONAL EXPERIENCE', optionally with colon
    #    Handles merged text like "EXPERIENCEConfidential" by not enforcing strict end boundary/whitespace after header
    experience_pattern = re.compile(r"^\s*PROFESSIONAL\s+EXPERIENCE\s*:?", re.IGNORECASE)
    
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
            
            # 4. Check for Sections
            container = soup.find("div", class_="single-post-body")
            
            # Track found sections
            found_sections = {
                "SUMMARY": False,
                "TECHNICAL SKILLS": False,
                "PROFESSIONAL EXPERIENCE": False
            }
            
            if container:
                for p in container.find_all("p"):
                    u_tag = p.find("u")
                    if u_tag:
                        text = u_tag.get_text(strip=True)
                        # Check each pattern
                        if summary_pattern.match(text):
                            found_sections["SUMMARY"] = True
                        if skills_pattern.match(text):
                            found_sections["TECHNICAL SKILLS"] = True
                        if experience_pattern.match(text):
                            found_sections["PROFESSIONAL EXPERIENCE"] = True
            else:
                print(f"xx Container 'single-post-body' not found for: {url}")
                continue
            
            # 5. Determine Status
            # Identify missing sections
            missing_sections = [key for key, found in found_sections.items() if not found]
            
            if missing_sections:
                print(f"__ INCONSISTENT: {url} (Missing: {missing_sections})")
                
                # Update failed_resumes -> inconsistent_resume: True
                failed_collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"inconsistent_resume": True}}
                )
                
                # Add to discarded_resume
                if not discarded_collection.find_one({"source_url": url}):
                    discard_record = {
                        "source_url": url,
                        "missing_part": ", ".join(missing_sections),
                        "ingested_at": datetime.now()
                    }
                    discarded_collection.insert_one(discard_record)
                    print("   -> Added to discarded_resume")
                
                discarded_count += 1
            else:
                # All sections present
                print(f"OK CONSISTENT: {url}")
                # Update failed_resumes -> inconsistent_resume: False
                failed_collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"inconsistent_resume": False}}
                )
                valid_count += 1
            
            processed_count += 1
            
        except Exception as e:
            print(f"!! Error processing {url}: {e}")

    print(f"\nValidation Complete.")
    print(f"Processed: {processed_count}")
    print(f"Inconsistent (Discarded): {discarded_count}")
    print(f"Consistent: {valid_count}")

if __name__ == "__main__":
    validate_resumes()
