from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from resume_ingestion.database.mongodb_manager import MongoDBManager
from src.data_acquisition.run_data_scraping import ScrapePipeline
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

        logger.info(f"Found {len(failed_urls)} unique URLs in 'failed_resumes' to reprocess.")

        # 2. Initialize Pipeline
        # We assume the standard parsing logic defined in ScrapePipeline is what we want.
        pipeline = ScrapePipeline(mongo_manager=mongo_manager, batch_size=1) 
        # Batch size 1 because we want to handle per-resume success/fail granularly for the cleanup 
        # (or we handle saving manually).

        processed_count = 0
        success_count = 0
        still_failed_count = 0

        # Helper function for threaded execution
        def process_url(url: str):
            # scrape_single_resume handles: Scrape -> Validate -> Parse
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
                    
                    if result["status"] == "success":
                        # Success!
                        resume_data = result["resume"]
                        
                        # Save to resumes collection
                        pipeline.save_to_mongodb([resume_data], collection_name="resumes")
                        
                        # Remove from failed_resumes
                        # We delete ALL entries with this URL to clean up history
                        delete_result = failed_col.delete_many({"source_url": url})
                        logger.info(f"Reprocessed and moved to resumes: {url} (Deleted {delete_result.deleted_count} failed entries)")
                        
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
        logger.info(f"Still Failed:     {still_failed_count}")
        logger.info("="*60)

    except Exception as e:
        logger.critical(f"Critical error during reprocessing: {e}")
    finally:
        pipeline.close()

if __name__ == "__main__":
    reprocess_failed_resumes()
