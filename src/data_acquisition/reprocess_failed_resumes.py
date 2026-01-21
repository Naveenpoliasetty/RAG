from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from src.resume_ingestion.database.mongodb_manager import MongoDBManager
from src.data_acquisition.run_data_scraping import ScrapePipeline
from src.data_acquisition.validate_sections import ResumeValidator
from src.utils.logger import get_pipeline_logger

logger = get_pipeline_logger(__name__, "ReprocessFailed")

def reprocess_failed_resumes():
    """
    Fetch resumes from 'failed_resumes' collection, attempt to re-scrape and parse them.
    If successful, save to 'resumes' and remove from 'failed_resumes'.
    """
    mongo_manager = MongoDBManager()
    
    # Check connection
    if not mongo_manager.health_check():
        logger.critical("MongoDB connection failed")
        return

    try:
        # 1. Fetch failed URLs
        failed_col = mongo_manager.db["failed_resumes"]
        # Use aggregation to get unique URLs if needed, or just distinct
        failed_urls = failed_col.distinct("source_url")
        
        if not failed_urls:
            logger.info("No failed resumes found in 'failed_resumes' collection.")
            return

        # Original:
         logger.info(f"Found {len(failed_urls)} unique URLs in 'failed_resumes' to reprocess.")
        
        # TEST MODE: Process only 5 URLs
        #failed_urls = failed_urls[:5]
        #logger.info(f"TEST MODE: Processing {len(failed_urls)} unique URLs from 'failed_resumes'.")

        # 2. Initialize Pipeline
        # We assume the standard parsing logic defined in ScrapePipeline is what we want.
        pipeline = ScrapePipeline(mongo_manager=mongo_manager, batch_size=1) 
        # Batch size 1 because we want to handle per-resume success/fail granularly for the cleanup 
        # (or we handle saving manually).

        # Initialize Validator
        validator = ResumeValidator(max_workers=1)
        discarded_col = mongo_manager.db["discarded_resume"]

        processed_count = 0
        success_count = 0
        still_failed_count = 0
        inconsistent_count = 0

        # Helper function for threaded execution
        def process_url(url: str):
            # 1. Check Consistency First
            # pass dummy _id as we don't strictly need it for validation logic return
            val_result = validator.validate_resume({"source_url": url, "_id": None})
            
            if val_result and not val_result["is_consistent"]:
                return url, {"status": "inconsistent", "missing": val_result["missing"]}

            # 2. If Consistent, Proceed to Scrape -> Validate -> Parse
            result = pipeline.scrape_single_resume(url)
            return url, result

        # 3. Process URLs with separate logic from standard run_pipeline
        # We want to DELETE from failed_resumes on success.
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(process_url, url): url for url in failed_urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                processed_count += 1
                try:
                    url, result = future.result()
                    
                    if result["status"] == "inconsistent":
                         # Handle Inconsistent Resume
                         missing = result["missing"]
                         logger.warning(f"Inconsistent resume found: {url} (Missing: {missing})")
                         
                         # 1. Update failed_resumes -> inconsistent_resume: True
                         failed_col.update_many(
                             {"source_url": url},
                             {"$set": {"inconsistent_resume": True}}
                         )
                         
                         # 2. Add to discarded_resume
                         if not discarded_col.find_one({"source_url": url}):
                             discard_record = {
                                 "source_url": url,
                                 "missing_part": ", ".join(missing),
                                 "ingested_at": datetime.now(timezone.utc)
                             }
                             discarded_col.insert_one(discard_record)
                             logger.info(f"Added to discarded_resume: {url}")
                         
                         inconsistent_count += 1
                         
                    elif result["status"] == "success":
                        # Success!
                        resume_data = result["resume"]
                        
                        # Original:
                         pipeline.save_to_mongodb([resume_data], collection_name="resumes")
                        
                        # Save to parsed_resume_hybrid collection (TEST MODE)
                        #pipeline.save_to_mongodb([resume_data], collection_name="parsed_resume_hybrid")
                        
                        # Remove from failed_resumes
                        # TEST MODE: Do NOT delete for now
                         delete_result = failed_col.delete_many({"source_url": url})
                         logger.info(f"Reprocessed and moved to resumes: {url} (Deleted {delete_result.deleted_count} failed entries)")
                        #logger.info(f"TEST MODE: Reprocessed and saved to 'parsed_resume_hybrid': {url} (Deletion skipped)")
                        
                        success_count += 1
                    else:
                        # Failed again
                        # We do NOT save to failed_resumes again to avoid duplicates, 
                        # or we could update the existing entry. 
                        # For now, we just log it. The existing entry serves as the record.
                        # Optionally, we could update 'last_attempt' timestamp if we wanted.
                        logger.warning(f"Still failed: {url} - Error: {result.get('error', 'Unknown')}")
                        still_failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Exception processing future for {url}: {e}")
                    still_failed_count += 1

        # Summary
        logger.info("\n" + "="*60)
        logger.info("REPROCESSING SUMMARY")
        logger.info("="*60)
        logger.info(f"Total urls checked: {len(failed_urls)}")
        logger.info(f"Processed:        {processed_count}")
        logger.info(f"Success (Moved):  {success_count}")
        logger.info(f"Inconsistent:     {inconsistent_count}")
        logger.info(f"Still Failed:     {still_failed_count}")
        logger.info("="*60)

    except Exception as e:
        logger.critical(f"Critical error during reprocessing: {e}")
    finally:
        pipeline.close()

if __name__ == "__main__":
    reprocess_failed_resumes()
