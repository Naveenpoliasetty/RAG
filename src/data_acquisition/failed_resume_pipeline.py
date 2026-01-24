"""
Failed Resume Recovery Pipeline

Fetches failed resumes from MongoDB, uses Groq LLM to extract data,
validates structure, and either:
- Success: Insert to resumes DB + delete from failed_resumes  
- Failure: Update error_message + keep in failed_resumes
"""
from datetime import datetime, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any

from src.data_acquisition.llm_resume_scraper import scrape_resume_with_llm
from src.data_acquisition.get_urls import extract_category_from_url
from src.resume_ingestion.database.mongodb_manager import MongoDBManager
from src.utils.logger import get_pipeline_logger

logger = get_pipeline_logger(__name__, "FailedResumeRecovery")


class FailedResumeRecoveryPipeline:
    """Pipeline to recover failed resumes using Groq LLM extraction."""
    
    def __init__(self, mongo_manager: MongoDBManager = None, batch_size: int = 10, max_workers: int = 1, test_mode: bool = False):
        """
        Initialize the failed resume recovery pipeline.
        
        Args:
            mongo_manager: MongoDB manager instance
            batch_size: Number of resumes to process in a batch before saving
            max_workers: Number of concurrent workers for processing
            test_mode: If True, save to 'test_resumes' collection instead of 'resumes'
        """
        self.mongo_manager = mongo_manager or MongoDBManager()
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.test_mode = test_mode
        
        # Collections
        self.failed_col = self.mongo_manager.db["failed_resumes"]
        
        # Use test collection if in test mode
        if test_mode:
            self.resumes_col = self.mongo_manager.db["test_resumes"]
            logger.info("🧪 TEST MODE ENABLED - Using 'test_resumes' collection")
        else:
            self.resumes_col = self.mongo_manager.collection  # Uses default "resumes" collection
            logger.info("✅ PRODUCTION MODE - Using 'resumes' collection")
        
    def clean_empty_environment(self, resume_dict: dict) -> dict:
        """
        Remove 'environment' key from experiences if it's empty or null.
        
        Args:
            resume_dict: Resume dictionary
        
        Returns:
            dict: Cleaned resume dictionary
        """
        for exp in resume_dict.get("experiences", []):
            env = exp.get("environment", None)
            if env is None or not str(env).strip():
                exp.pop("environment", None)
        return resume_dict
    
    def prepare_resume_for_db(self, resume_data: dict, url: str) -> dict:
        """
        Add necessary metadata to resume before inserting to DB.
        Uses the exact same schema as existing resumes.
        
        Args:
            resume_data: Raw resume data from LLM
            url: Source URL
        
        Returns:
            dict: Resume with all required metadata
        """
        # Extract category from URL
        category = extract_category_from_url(url)
        if not category:
            logger.warning(f"Could not extract category from URL: {url}")
            category = "unknown"
        
        # Add metadata (same as run_data_scraping.py)
        resume_data["resume_id"] = str(uuid4())
        resume_data["category"] = category
        resume_data["source_url"] = url
        resume_data["scraped_at"] = datetime.now(timezone.utc)
        resume_data["qdrant_status"] = "pending"
        resume_data["processing_status"] = "scraped_success"
        
        # Clean empty environments
        resume_data = self.clean_empty_environment(resume_data)
        
        return resume_data
    
    def process_single_failed_resume(self, failed_record: dict) -> dict:
        """
        Process a single failed resume: scrape with LLM, validate, save or update error.
        
        Args:
            failed_record: Failed resume document from MongoDB
        
        Returns:
            dict: Result with status, details, and rate_limit_info
        """
        url = failed_record.get("source_url")
        failed_id = failed_record.get("_id")
        
        if not url:
            logger.warning(f"Failed resume record {failed_id} has no source_url")
            return {"status": "error", "error": "No source_url in failed record", "rate_limit_info": None}
        
        logger.info(f"Processing failed resume: {url}")
        
        try:
            # Scrape with Groq LLM - returns rate_limit_info
            resume_obj, error_msg, rate_info = scrape_resume_with_llm(url)
            
            # Check if rate limits were exhausted during scraping
            if rate_info and rate_info.get("limit_exhausted"):
                logger.warning(f"Rate limits exhausted while processing {url}")
                return {
                    "status": "rate_limit_exhausted",
                    "url": url,
                    "error": "Rate limits exhausted during scraping",
                    "rate_limit_info": rate_info
                }
            
            if resume_obj is None:
                # Scraping/validation failed
                logger.warning(f"Failed to recover resume from {url}: {error_msg}")
                
                # Update error_message in failed_resumes
                self.failed_col.update_one(
                    {"_id": failed_id},
                    {"$set": {"error_message": error_msg}}
                )
                
                return {
                    "status": "still_failed",
                    "url": url,
                    "error": error_msg,
                    "rate_limit_info": rate_info
                }
            
            # Success! Prepare for insertion
            resume_dict = resume_obj.model_dump()
            resume_dict = self.prepare_resume_for_db(resume_dict, url)
            
            # Insert into resumes collection
            self.resumes_col.insert_one(resume_dict)
            
            # Delete from failed_resumes  
            self.failed_col.delete_one({"_id": failed_id})
            
            logger.info(f"✅ Successfully recovered and moved resume: {url}")
            
            return {
                "status": "recovered",
                "url": url,
                "resume_id": resume_dict["resume_id"],
                "rate_limit_info": rate_info
            }
            
        except Exception as e:
            logger.error(f"Exception processing {url}: {e}")
            
            # Update error in failed_resumes
            error_msg = f"Recovery pipeline error: {str(e)}"
            self.failed_col.update_one(
                {"_id": failed_id},
                {"$set": {"error_message": error_msg}}
            )
            
            return {
                "status": "error",
                "url": url,
                "error": str(e),
                "rate_limit_info": None
            }
    
    def run_recovery_pipeline(self) -> dict:
        """
        Main recovery pipeline: Fetch failed resumes and attempt recovery with Groq LLM.
        
        Returns:
            dict: Statistics about the recovery run
        """
        logger.info("=" * 60)
        logger.info("STARTING FAILED RESUME RECOVERY PIPELINE")
        logger.info("=" * 60)
        
        # Check MongoDB connection
        if not self.mongo_manager.health_check():
            logger.critical("MongoDB connection failed")
            return {"success": False, "error": "MongoDB connection failed"}
        
        # Fetch all failed resumes
        logger.info("Fetching failed resumes from MongoDB...")
        failed_resumes = list(self.failed_col.find({}))
        
        if not failed_resumes:
            logger.info("No failed resumes found in database")
            return {
                "success": True,
                "total": 0,
                "recovered": 0,
                "still_failed": 0,
                "errors": 0
            }
        
        logger.info(f"Found {len(failed_resumes)} failed resume(s) to process")
        
        # Process with ThreadPoolExecutor
        recovered_count = 0
        still_failed_count = 0
        error_count = 0
        rate_limit_exhausted = False
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_record = {
                executor.submit(self.process_single_failed_resume, record): record
                for record in failed_resumes
            }
            
            # Process results as they complete
            for future in as_completed(future_to_record):
                record = future_to_record[future]
                
                try:
                    result = future.result()
                    
                    # Check for rate limit exhaustion status
                    if result["status"] == "rate_limit_exhausted":
                        logger.critical(
                            f"🛑 RATE LIMIT EXHAUSTED during processing - Stopping pipeline immediately! "
                            f"URL: {result.get('url')}"
                        )
                        rate_limit_exhausted = True
                        # Cancel all pending futures
                        for f in future_to_record.keys():
                            f.cancel()
                        break
                    
                    # Check rate limit info
                    rate_info = result.get("rate_limit_info")
                    if rate_info and rate_info.get("limit_exhausted"):
                        logger.critical(
                            f"🛑 RATE LIMIT EXHAUSTED - Stopping pipeline immediately! "
                            f"Remaining requests: {rate_info.get('remaining_requests')}, "
                            f"Remaining tokens: {rate_info.get('remaining_tokens')}"
                        )
                        rate_limit_exhausted = True
                        # Cancel all pending futures
                        for f in future_to_record.keys():
                            f.cancel()
                        break
                    
                    if result["status"] == "recovered":
                        recovered_count += 1
                    elif result["status"] == "still_failed":
                        still_failed_count += 1
                    else:  # error
                        error_count += 1
                        
                except Exception as e:
                    logger.error(f"Future execution error: {e}")
                    error_count += 1
        
        # Print summary
        logger.info("=" * 60)
        logger.info("RECOVERY PIPELINE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total failed resumes: {len(failed_resumes)}")
        logger.info(f"✅ Recovered:        {recovered_count} (moved to resumes DB)")
        logger.info(f"❌ Still failed:     {still_failed_count} (error_message updated)")
        logger.info(f"⚠️  Errors:           {error_count}")
        
        if rate_limit_exhausted:
            logger.warning(f"🛑 Pipeline stopped early due to rate limit exhaustion")
            logger.info(f"Processed:          {recovered_count + still_failed_count + error_count}/{len(failed_resumes)}")
        
        logger.info("=" * 60)
        
        return {
            "success": True,
            "total": len(failed_resumes),
            "processed": recovered_count + still_failed_count + error_count,
            "recovered": recovered_count,
            "still_failed": still_failed_count,
            "errors": error_count,
            "rate_limit_exhausted": rate_limit_exhausted,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    
    def close(self):
        """Close MongoDB connection."""
        try:
            self.mongo_manager.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.warning(f"Warning during shutdown: {e}")


def main():
    """Main entry point for the recovery pipeline."""
    # 🧪 TEST MODE ENABLED BY DEFAULT
    # Saves to 'test_resumes' collection instead of 'resumes'
    # Set test_mode=False for production use
    pipeline = FailedResumeRecoveryPipeline(batch_size=10, max_workers=1, test_mode=True)
    
    try:
        result = pipeline.run_recovery_pipeline()
        
        if not result["success"]:
            logger.error(f"Pipeline failed: {result.get('error')}")
            return 1
        
        return 0
        
    except Exception as e:
        logger.critical(f"Critical pipeline failure: {e}")
        return 1
    finally:
        pipeline.close()


if __name__ == "__main__":
    exit(main())
