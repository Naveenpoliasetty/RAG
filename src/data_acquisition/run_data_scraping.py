import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone
import json
from uuid import uuid4

# Import pipeline modules
from get_urls import get_urls, extract_category_from_url
from scrape import extract_post_body_safe
from validate_structure import validate_structured_resume
from parser import parse_resume

# Import MongoDB Manager
from resume_ingestion.database.mongodb_manager import MongoDBManager

# -----------------------------------------------------------------------------
# LOGGING SETUP
# -----------------------------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / "scrape_pipeline.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("scrape_pipeline")


# -----------------------------------------------------------------------------
# PIPELINE FUNCTIONS
# -----------------------------------------------------------------------------
class ScrapePipeline:
    def __init__(self, batch_size: int = 50, output_dir: str = "output"):
        self.batch_size = batch_size
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.mongo_manager = MongoDBManager()
        
        # Files for local saving
        self.json_output_file = self.output_dir / "resumes.json"
        self.failed_urls_file = self.output_dir / "failed_urls.json"
        
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

    def save_to_mongodb(self, resumes: list) -> int:
        """Save resumes to MongoDB and return count of successfully inserted documents."""
        if not resumes:
            logger.warning("No resumes to save to MongoDB")
            return 0
        
        try:
            # Insert resumes into MongoDB collection
            result = self.mongo_manager.collection.insert_many(resumes)
            inserted_count = len(result.inserted_ids)
            
            logger.info(f"Saved {inserted_count} resumes to MongoDB")
            return inserted_count
            
        except Exception as e:
            logger.error(f"Failed to save resumes to MongoDB: {e}")
            return 0

    def save_to_json_local(self, resumes: list, mode: str = "append"):
        """Save resumes to local JSON file for cross-verification."""
        if not resumes:
            return
        
        try:
            data = []
            
            # Read existing data if appending
            if mode == "append" and self.json_output_file.exists():
                with open(self.json_output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # Add new resumes
            data.extend(resumes)
            
            # Write back to file
            with open(self.json_output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Saved {len(resumes)} resumes to local JSON: {self.json_output_file}")
            
        except Exception as e:
            logger.error(f"Error saving to local JSON: {e}")

    def save_failed_urls(self, failed_entries: list):
        """Save failed URLs to a separate JSON file for debugging."""
        if not failed_entries:
            return
        
        try:
            data = []
            
            # Read existing failed URLs if appending
            if self.failed_urls_file.exists():
                with open(self.failed_urls_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # Add new failed entries
            data.extend(failed_entries)
            
            # Write back to file
            with open(self.failed_urls_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"📁 Saved {len(failed_entries)} failed URLs to: {self.failed_urls_file}")
            
        except Exception as e:
            logger.error(f"Error saving failed URLs: {e}")

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
        """Run the complete scraping pipeline with dual saving."""
        logger.info("Starting scraping pipeline with dual saving (MongoDB + Local JSON)")
        
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
        all_successful_resumes = []  # All successful resumes for JSON
        saved_to_mongo_count = 0     # Track actual MongoDB saves
        
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
                        all_successful_resumes.append(result["resume"])
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

        # Save ALL successful resumes to JSON ONCE at the end
        if all_successful_resumes:
            self.save_to_json_local(all_successful_resumes, mode="append")

        # --- Step 6: Save failed URLs for debugging ---
        if failed_entries:
            self.save_failed_urls(failed_entries)

        # --- Step 7: Create a summary file ---
        self.save_summary_report(len(urls), saved_to_mongo_count, len(failed_entries))

        # --- Step 8: Return statistics ---
        stats = {
            "success": True,
            "total_urls": len(urls),
            "processed": processed_count,
            "successful": success_count,
            "failed": failed_count,
            "saved_to_mongodb": saved_to_mongo_count,  # Use actual MongoDB count
            "saved_to_json": len(all_successful_resumes),  # Use actual JSON count
            "json_output_file": str(self.json_output_file),
            "failed_urls_file": str(self.failed_urls_file),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Pipeline complete! Statistics: {stats}")
        return stats

    def save_summary_report(self, total_urls: int, saved_count: int, failed_count: int):
        """Save a summary report of the scraping session."""
        summary = {
            "session_timestamp": datetime.now(timezone.utc).isoformat(),
            "total_urls_processed": total_urls,
            "successfully_saved": saved_count,
            "failed_urls": failed_count,
            "success_rate": f"{(saved_count/total_urls)*100:.1f}%" if total_urls > 0 else "0%",
            "output_files": {
                "successful_resumes": str(self.json_output_file),
                "failed_urls": str(self.failed_urls_file),
                "log_file": "logs/scrape_pipeline.log"
            },
            "next_steps": [
                "Check failed_urls.json for URLs that need manual review",
                "Use main.py --mode single to process individual batches for Qdrant",
                "Verify data in MongoDB using your database client"
            ]
        }
        
        summary_file = self.output_dir / "scraping_session_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Session summary saved to: {summary_file}")

    def compare_mongo_json(self) -> dict:
        """Compare MongoDB records with local JSON for verification."""
        try:
            # Count in MongoDB
            mongo_count = self.mongo_manager.collection.count_documents({})
            
            # Count in local JSON
            json_count = 0
            if self.json_output_file.exists():
                with open(self.json_output_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                    json_count = len(json_data)
            
            comparison = {
                "mongodb_count": mongo_count,
                "json_count": json_count,
                "match": mongo_count == json_count,
                "difference": mongo_count - json_count,
                "comparison_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Data comparison: MongoDB={mongo_count}, JSON={json_count}, Match={comparison['match']}")
            return comparison
            
        except Exception as e:
            logger.error(f"Error comparing MongoDB and JSON data: {e}")
            return {"error": str(e)}

    def close(self):
        """Close MongoDB connection."""
        try:
            self.mongo_manager.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.warning(f"Warning during shutdown: {e}")


def main():
    """Main function with dual saving and verification."""
    pipeline = ScrapePipeline(batch_size=20)
    
    try:
        # Run the complete pipeline
        result = pipeline.run_pipeline()
        
        # Compare data for verification
        comparison = pipeline.compare_mongo_json()
        
        # Log comprehensive summary
        logger.info("\n" + "="*60)
        logger.info("SCRAPING PIPELINE SUMMARY - DUAL SAVING")
        logger.info("="*60)
        
        if result["success"]:
            logger.info(f"Success: {result['successful']} resumes")
            logger.info(f"Failed:  {result['failed']} URLs")
            logger.info(f"MongoDB: {result['saved_to_mongodb']} saved")
            logger.info(f"Local:   {result['saved_to_json']} saved to JSON")
            logger.info(f"Total:   {result['total_urls']} URLs processed")
            logger.info("\nDATA VERIFICATION:")
            logger.info(f"   MongoDB count: {comparison['mongodb_count']}")
            logger.info(f"   JSON count:    {comparison['json_count']}")
            logger.info(f"   Data match:    {'YES' if comparison['match'] else 'NO'}")
            logger.info(f"\n Output files:")
            logger.info(f"   Successful: {result['json_output_file']}")
            logger.info(f"   Failed URLs: {result['failed_urls_file']}")
            logger.info(f"   Session summary: output/scraping_session_summary.json")
        else:
            logger.error(f"Pipeline failed: {result.get('error', 'Unknown error')}")
            
        logger.info("="*60)
        
    except Exception as e:
        logger.critical(f"Critical pipeline failure: {e}")
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()