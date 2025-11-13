import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone
import json
from uuid import uuid4

# Import pipeline modules
from .get_urls import get_urls, extract_category_from_url
from .scrape import extract_post_body_safe
from .validate_structure import validate_structured_resume
from .parser import parse_resume

# Import MongoDB Manager
from resume_ingestion.database.mongodb_manager import MongoDBManager

from src.utils.logger import get_logger
logger = get_logger("RunDataScraping")

# -----------------------------------------------------------------------------
# LOGGING SETUP
# -----------------------------------------------------------------------------
global base_path
base_path = Path(__file__).resolve().parents[2]
LOG_DIR = base_path / "logs"
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / "scrape_pipeline.log"

    


# -----------------------------------------------------------------------------
# PIPELINE FUNCTIONS
# -----------------------------------------------------------------------------
class ScrapePipeline:
    def __init__(self, batch_size: int = 50, output_dir: str = base_path / "output"):
        self.batch_size = batch_size
        
        self.mongo_manager = MongoDBManager()
        
    def scrape_single_resume(self, url: str):
        """Scrape -> Validate -> Parse one resume end-to-end."""
        try:
            logger.info(f"🔍 Scraping: {url}")
            extraction = extract_post_body_safe(url)

            # --- Validate structured content ---
            validation = validate_structured_resume(extraction.model_dump())
            if not validation["is_valid"]:
                logger.warning(f"Validation failed for {url}: {validation['errors']}")
                return {"url": url, "error": validation["errors"], "status": "validation_failed"}

            # --- Parse into final structured format ---
            parsed_resume = parse_resume(extraction.model_dump())
            
            # --- Extract and add category from URL ---
            category = extract_category_from_url(url)
            if not category:
                logger.warning(f"Could not extract category from URL: {url}")
            
            # --- Add metadata for MongoDB and tracking ---
            # Generate a unique ID for MongoDB _id field
            resume_id = str(uuid4())
            parsed_resume["_id"] = resume_id                    # MongoDB primary key
            parsed_resume["category"] = category
            parsed_resume["source_url"] = url
            parsed_resume["scraped_at"] = datetime.now(timezone.utc)
            parsed_resume["qdrant_status"] = "pending"          # Ready for embedding ingestion
            parsed_resume["processing_status"] = "scraped_success"
            
            # Clean empty environment fields
            parsed_resume = self.clean_empty_environment(parsed_resume)
            
            logger.info(f"Parsed successfully: {url} (category: {category})")
            return {"url": url, "resume": parsed_resume, "status": "success"}

        except Exception as e:
            logger.exception(f"Error processing {url}: {e}")
            return {"url": url, "error": str(e), "status": "processing_error"}

    def clean_empty_environment(self, resume: dict) -> dict:
        """
        Remove 'environment' key from experiences if it's empty or null.
        Works in-place and returns the cleaned resume dict.
        """
        for exp in resume.get("experiences", []):
            env = exp.get("environment", None)
            # If environment is None, empty string, or only whitespace
            if env is None or not str(env).strip():
                exp.pop("environment", None)
        return resume

    def save_to_mongodb(self, resumes: list, collection_name: str = "resumes") -> int:
        """Save resumes to MongoDB and return count of successfully inserted documents."""
        if not resumes:
            logger.warning(f"No resumes to save to MongoDB collection: {collection_name}")
            return 0
        
        try:
            # Use different collection based on the type
            if collection_name == "failed_resumes":
                collection = self.mongo_manager.db[collection_name]
                result = collection.insert_many(resumes)
            else:
                result = self.mongo_manager.collection.insert_many(resumes)
                
            inserted_count = len(result.inserted_ids)
            
            logger.info(f"Saved {inserted_count} resumes to MongoDB collection: {collection_name}")
            return inserted_count
            
        except Exception as e:
            logger.error(f"Failed to save resumes to MongoDB: {e}")
            return 0

    def save_failed_resumes_to_mongodb(self, failed_entries: list) -> int:
        """Save failed resume processing attempts to MongoDB failed_resumes collection."""
        if not failed_entries:
            return 0
        
        failed_resumes_for_db = []
        
        for entry in failed_entries:
            # Create a structured failed resume document
            failed_resume = {
                "_id": str(uuid4()),
                "source_url": entry["url"],
                "error_type": entry["status"],
                "error_message": entry["error"],
                "failed_at": datetime.now(timezone.utc),
                "retry_count": 0
            }
            failed_resumes_for_db.append(failed_resume)
        
        return self.save_to_mongodb(failed_resumes_for_db, "failed_resumes")

    def check_existing_urls(self, urls: list) -> list:
        """Check which URLs already exist in MongoDB to avoid duplicates."""
        try:
            existing_docs = self.mongo_manager.collection.find(
                {"source_url": {"$in": urls}},
                {"source_url": 1}
            )
            existing_urls = {doc["source_url"] for doc in existing_docs}
            
            new_urls = [url for url in urls if url not in existing_urls]
            
            if existing_urls:
                logger.info(f"Found {len(existing_urls)} existing URLs, processing {len(new_urls)} new URLs")
            else:
                logger.info(f"No existing URLs found, processing all {len(new_urls)} URLs")
                
            return new_urls
            
        except Exception as e:
            logger.error(f"Error checking existing URLs: {e}")
            return urls  # Fallback: process all URLs

    def run_pipeline(self, urls: list = None, skip_existing: bool = True) -> dict:
        """Run the complete scraping pipeline with MongoDB storage only."""
        logger.info("Starting scraping pipeline with MongoDB storage only")
        
        # Initialize MongoDB connection
        if not self.mongo_manager.health_check():
            logger.critical("MongoDB connection failed")
            return {"success": False, "error": "MongoDB connection failed"}
        
        # --- Step 1: Get URLs if not provided ---
        if urls is None:
            logger.info("Fetching resume URLs...")
            try:
                urls = get_urls()
            except Exception as e:
                logger.critical(f"Failed to retrieve URLs: {e}")
                return {"success": False, "error": f"URL retrieval failed: {e}"}

        if not urls:
            logger.warning("No resume URLs found. Exiting.")
            return {"success": False, "error": "No URLs found"}

        logger.info(f"Collected {len(urls)} URLs to process")
        
        # --- Step 1.5: Filter existing URLs ---
        if skip_existing:
            urls = self.check_existing_urls(urls)
            if not urls:
                logger.info("All URLs already exist in database. Nothing to process.")
                return {"success": True, "processed": 0, "message": "All URLs already processed"}

        # --- Step 2–4: Scrape + Validate + Parse ---
        successful_resumes = []  # Current batch for MongoDB
        failed_entries = []
        saved_to_mongo_count = 0     # Track actual MongoDB saves
        saved_failed_to_mongo_count = 0  # Track failed resumes saved to MongoDB
        
        # Reset counters for this run
        processed_count = 0
        success_count = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {
                executor.submit(self.scrape_single_resume, url): url 
                for url in urls
            }

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    processed_count += 1
                    
                    if result["status"] == "success":
                        successful_resumes.append(result["resume"])
                        success_count += 1
                    else:
                        failed_entries.append(result)
                        failed_count += 1
                    
                    # Save in batches to avoid memory issues
                    if len(successful_resumes) >= self.batch_size:
                        # Save to MongoDB only
                        batch_saved = self.save_to_mongodb(successful_resumes)
                        saved_to_mongo_count += batch_saved
                        successful_resumes = []  # Clear batch after saving
                        
                except Exception as e:
                    logger.error(f"Error in future for {url}: {e}")
                    failed_entries.append({"url": url, "error": str(e), "status": "future_error"})
                    failed_count += 1
                    processed_count += 1

        # --- Step 5: Save remaining results ---
        if successful_resumes:
            final_batch_saved = self.save_to_mongodb(successful_resumes)
            saved_to_mongo_count += final_batch_saved

        # --- Step 6: Save failed resumes to MongoDB ---
        if failed_entries:
            saved_failed_to_mongo_count = self.save_failed_resumes_to_mongodb(failed_entries)
            logger.info(f"Saved {saved_failed_to_mongo_count} failed resumes to MongoDB failed_resumes collection")

        # --- Step 7: Return statistics ---
        stats = {
            "success": True,
            "total_urls": len(urls),
            "processed": processed_count,
            "successful": success_count,
            "failed": failed_count,
            "saved_to_mongodb": saved_to_mongo_count,  # Use actual MongoDB count
            "saved_failed_to_mongodb": saved_failed_to_mongo_count,  # Failed resumes in MongoDB
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Pipeline complete! Statistics: {stats}")
        return stats

    def close(self):
        """Close MongoDB connection."""
        try:
            self.mongo_manager.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.warning(f"Warning during shutdown: {e}")


def main():
    """Main function with MongoDB storage only."""
    pipeline = ScrapePipeline(batch_size=20)
    
    try:
        # Run the complete pipeline
        result = pipeline.run_pipeline()
        
        # Log comprehensive summary
        logger.info("\n" + "="*60)
        logger.info("SCRAPING PIPELINE SUMMARY - MONGODB ONLY")
        logger.info("="*60)
        
        if result["success"]:
            logger.info(f"Success: {result['successful']} resumes")
            logger.info(f"Failed:  {result['failed']} URLs")
            logger.info(f"MongoDB: {result['saved_to_mongodb']} successful resumes saved to 'resumes' collection")
            logger.info(f"MongoDB: {result['saved_failed_to_mongodb']} failed resumes saved to 'failed_resumes' collection")
            logger.info(f"Total:   {result['total_urls']} URLs processed")
            logger.info(f"\nAll data stored in MongoDB - no local files created")
        else:
            logger.error(f"Pipeline failed: {result.get('error', 'Unknown error')}")
            
        logger.info("="*60)
        
    except Exception as e:
        logger.critical(f"Critical pipeline failure: {e}")
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()