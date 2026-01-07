import os
import sys
import re
import time
import concurrent.futures
import requests
from datetime import datetime
from pymongo import MongoClient, UpdateOne
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.core.settings import config
from src.utils.logger import get_logger

logger = get_logger("ValidateSections")

class ResumeValidator:
    def __init__(self, max_workers=10):
        self.max_workers = max_workers
        self.client = MongoClient(config.mongodb_uri)
        self.db = self.client[config.mongodb_database]
        
        # Collections
        self.failed_collection = self.db["failed_resumes"]
        self.discarded_collection = self.db["discarded_resume"]
        
        # Regex Patterns (Pre-compiled)
        self.patterns = {
            "SUMMARY": re.compile(r"^\s*(?:PROFESSIONAL\s+)?SUMMARY\s*:?", re.IGNORECASE),
            "TECHNICAL SKILLS": re.compile(r"^\s*(?:TECHNICAL\s+)?SKILLS\s*:?", re.IGNORECASE),
            "PROFESSIONAL EXPERIENCE": re.compile(r"^\s*PROFESSIONAL\s+EXPERIENCE\s*:?", re.IGNORECASE)
        }
        
    def fetch_url(self, url, retries=3):
        headers = {"User-Agent": "Mozilla/5.0"}
        for attempt in range(retries):
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    return resp.text
                elif resp.status_code == 429:
                    time.sleep(2 ** attempt) # Backoff
            except requests.RequestException:
                pass
        return None

    def validate_resume(self, doc):
        url = doc.get('source_url')
        if not url:
            return None

        try:
            html_content = self.fetch_url(url)
            if not html_content:
                logger.warning(f"Failed to fetch content for: {url}")
                return None

            soup = BeautifulSoup(html_content, "html.parser")
            container = soup.find("div", class_="single-post-body")

            if not container:
                logger.debug(f"Missing 'single-post-body' in: {url}")
                return None

            found_sections = {k: False for k in self.patterns}
            
            # Scan for headers
            for p in container.find_all("p"):
                u_tag = p.find("u")
                if u_tag:
                    text = u_tag.get_text(strip=True)
                    for key, pattern in self.patterns.items():
                        if pattern.match(text):
                            found_sections[key] = True

            missing = [k for k, v in found_sections.items() if not v]
            
            # Return result structure
            return {
                "doc_id": doc["_id"],
                "url": url,
                "missing": missing,
                "is_consistent": len(missing) == 0
            }

        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            return None

    def run(self):
        query = {} # Process all
        total_docs = self.failed_collection.count_documents(query)
        cursor = self.failed_collection.find(query)
        
        logger.info(f"Starting validation for {total_docs} resumes with {self.max_workers} threads.")
        
        processed = 0
        inconsistent = 0
        consistent = 0
        
        # Batch updates for efficiency
        batch_updates = []
        discard_inserts = []
        BATCH_SIZE = 50

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_doc = {executor.submit(self.validate_resume, doc): doc for doc in cursor}
            
            for future in concurrent.futures.as_completed(future_to_doc):
                processed += 1
                result = future.result()
                
                if result:
                    # Queue Update
                    batch_updates.append(
                        UpdateOne({"_id": result["doc_id"]}, {"$set": {"inconsistent_resume": not result["is_consistent"]}})
                    )
                    
                    if not result["is_consistent"]:
                        inconsistent += 1
                        logger.info(f"INCONSISTENT: {result['url']} missing {result['missing']}")
                        
                        # Queue Discard Insert (Check explicitly to avoid duplication mostly handled by logic flow)
                        if not self.discarded_collection.find_one({"source_url": result["url"]}):
                            discard_inserts.append({
                                "source_url": result["url"],
                                "missing_part": ", ".join(result["missing"]),
                                "ingested_at": datetime.now()
                            })
                    else:
                        consistent += 1
                
                # Execute Batch
                if len(batch_updates) >= BATCH_SIZE:
                    self.failed_collection.bulk_write(batch_updates)
                    if discard_inserts:
                        self.discarded_collection.insert_many(discard_inserts)
                    batch_updates = []
                    discard_inserts = []
                    logger.info(f"Progress: {processed}/{total_docs} | Consistent: {consistent} | Inconsistent: {inconsistent}")

            # Flush remaining
            if batch_updates:
                self.failed_collection.bulk_write(batch_updates)
            if discard_inserts:
                self.discarded_collection.insert_many(discard_inserts)

        logger.info(f"DONE. Processed: {processed}, Consistent: {consistent}, Inconsistent: {inconsistent}")

if __name__ == "__main__":
    validator = ResumeValidator(max_workers=20)   
    validator.run()
