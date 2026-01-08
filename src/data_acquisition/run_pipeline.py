import os
import sys
import time
from pymongo import MongoClient

# Add project root to path
sys.path.append(os.getcwd())

from src.core.settings import config
from src.utils.logger import get_logger
from src.data_acquisition.validate_sections import ResumeValidator
from src.data_acquisition.hybrid_scraping_pipeline import HybridScraper

logger = get_logger("PipelineMonitor")

class PipelineMonitor:
    def __init__(self):
        self.validator = ResumeValidator(max_workers=10)
        self.scraper = HybridScraper()
        
        self.client = MongoClient(config.mongodb_uri)
        self.db = self.client[config.mongodb_database]
        self.failed_collection = self.db["failed_resumes"]
        
        # Poll interval from config or default 10s
        self.poll_interval = config.poll_interval 

    def check_for_new_resumes(self):
        """Check if there are any resumes without the 'inconsistent_resume' flag."""
        query = {"inconsistent_resume": {"$exists": False}}
        count = self.failed_collection.count_documents(query)
        return count

    def run(self):
        logger.info(f"Starting Pipeline Monitor. Poll Interval: {self.poll_interval}s")
        
        while True:
            try:
                # 1. Check for new entries
                new_count = self.check_for_new_resumes()
                
                if new_count > 0:
                    logger.info(f"Detected {new_count} NEW resumes. Triggering pipeline...")
                    
                    # Step 1: Validation (flagging inconsistent/consistent)
                    logger.info(">>> STEP 1: VALIDATION <<<")
                    self.validator.run(process_all=False)
                    
                    # Step 2: Extraction (processing consistent ones)
                    logger.info(">>> STEP 2: HYBRID SCRAPING <<<")
                    self.scraper.run(dry_run=False)
                    
                    logger.info("Pipeline cycle complete.")
                else:
                    logger.debug("No new resumes found. Waiting...")
                
                time.sleep(self.poll_interval)
                
            except KeyboardInterrupt:
                logger.info("Stopping Pipeline Monitor...")
                break
            except Exception as e:
                logger.error(f"Error in pipeline loop: {e}")
                time.sleep(self.poll_interval) # Wait before retrying

if __name__ == "__main__":
    monitor = PipelineMonitor()
    monitor.run()
