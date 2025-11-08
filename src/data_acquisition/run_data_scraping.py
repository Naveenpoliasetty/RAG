import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Import pipeline modules
from get_urls import get_urls, extract_category_from_url
from scrape import extract_post_body_safe
from validate_structure import validate_structured_resume
from parser import parse_resume
import json

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
def scrape_single_resume(url: str):
    """Scrape -> Validate -> Parse one resume end-to-end."""
    try:
        logger.info(f"🔍 Scraping: {url}")
        extraction = extract_post_body_safe(url)

        # --- Validate structured content ---
        validation = validate_structured_resume(extraction.model_dump())
        if not validation["is_valid"]:
            logger.warning(f"Validation failed for {url}: {validation['errors']}")
            return None

        # --- Parse into final structured format ---
        parsed_resume = parse_resume(extraction.model_dump())
        
        # --- Extract and add category from URL ---
        category = extract_category_from_url(url)
        if not category:
            logger.warning(f"Could not extract category from URL: {url}")
        parsed_resume["category"] = category
        
        logger.info(f"Parsed successfully: {url} (category: {category})")
        return parsed_resume

    except Exception as e:
        logger.exception(f"Error processing {url}: {e}")
        return None

# --- Clean empty environment ---
def clean_empty_environment(resume: dict) -> dict:
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


def main():
    logger.info("Starting scraping pipeline")

    # --- Step 1: Get URLs ---
    logger.info("Fetching resume URLs...")
    try:
        urls = get_urls()
    except Exception as e:
        logger.critical(f"Failed to retrieve URLs: {e}")
        return

    if not urls:
        logger.warning("No resume URLs found. Exiting.")
        return

    logger.info(f"Collected {len(urls)} URLs to process")

    # --- Step 2–4: Scrape + Validate + Parse ---
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(scrape_single_resume, url): url for url in urls}

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error in future for {url}: {e}")
    
    # --- Clean empty environment ---
    results = [clean_empty_environment(resume) for resume in results]

    # --- Step 5: Save output ---
    output_path = Path("output_resumes.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Pipeline complete! {len(results)} valid resumes saved to {output_path}")


if __name__ == "__main__":
    main()