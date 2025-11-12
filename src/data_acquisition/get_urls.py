import yaml
import time
import random
import re
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from src.utils.logger import get_logger
logger = get_logger("GetUrls")

def extract_category_from_url(url: str) -> str:
    """
    Extract category name from resume database URL.
    
    Examples:
        https://www.hireitpeople.com/resume-database/77-oracle-resumes/... -> "oracle"
        https://www.hireitpeople.com/resume-database/71-sap-resumes/... -> "sap"
        https://www.hireitpeople.com/resume-database/70-oracle-developers-resumes -> "oracle"
        /resume-database/77-oracle-resumes/627136-oracle-dba-resume-nc-1 -> "oracle"
    
    Args:
        url: The resume database URL (can be absolute or relative)
        
    Returns:
        The extracted category name (e.g., "oracle", "sap")
    """
    # Pattern: /resume-database/\d+-([^-]+)-resumes
    # Matches: number-dash-category-dash-resumes (with optional trailing slash or path)
    # This handles both absolute and relative URLs
    pattern = re.compile(r"resume-database/\d+-([a-z-]+?)(?:s)?-resumes")
    match = re.search(pattern, url)
    if match:
        category = match.group(1).lower()
        return category
    # If no match, try alternative pattern (in case URL format is different)
    # Pattern for URLs like: resume-database/77-oracle-resumes (without leading slash)
    alt_pattern = r'resume-database/\d+-([^-]+)-resumes'
    alt_match = re.search(alt_pattern, url)
    if alt_match:
        return alt_match.group(1).lower()
    # If no match, return empty string
    return ""


# --- Load configuration ---
def load_config():
    # Get the directory where this script is located
    script_dir = Path(__file__).resolve().parents[1]
    logger.info(f"Script directory: {script_dir}")
    config_path = script_dir / "core" / "scrape_config.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found at: {config_path}")
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    if config is None:
        raise ValueError(f"Config file is empty or invalid: {config_path}")

    scraper_cfg = config["scraper"]
    categories = config["categories"]


    # Bundle everything together
    return {
        "MAX_PAGES": scraper_cfg["max_pages"],
        "HEADERS": scraper_cfg["headers"],
        "MIN_DELAY": scraper_cfg["request_delay"]["min"],
        "MAX_DELAY": scraper_cfg["request_delay"]["max"],
        "MAX_WORKERS": scraper_cfg["max_workers"],
        "categories": categories,
    }


# --- Scraper function ---
def scrape_resume_links(category_url, config):
    resume_links = []
    session = requests.Session()
    session.headers.update(config["HEADERS"])

    for page in range(1, config["MAX_PAGES"] + 1):
        url = f"{category_url}/page/{page}"
        print(f"[+] Scraping {url}")

        r = session.get(url)
        if r.status_code != 200:
            print(f"[-] Page {page} returned {r.status_code}, stopping.")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        raw_links = [a["href"] for a in soup.select("table.hit-table h4 a")]
        
        # Convert relative URLs to absolute URLs
        links = [urljoin(r.url, link) if not link.startswith("http") else link for link in raw_links]

        if not links:
            print(f"[-] No resumes found on page {page}, stopping.")
            break

        resume_links.extend(links)
        time.sleep(random.uniform(config["MIN_DELAY"], config["MAX_DELAY"]))

    return resume_links


# --- Master runner ---
def get_urls():
    config = load_config()
    categories = config["categories"]

    all_links = {}

    with ThreadPoolExecutor(max_workers=config["MAX_WORKERS"]) as executor:
        futures = {executor.submit(scrape_resume_links, url, config): url for url in categories}
        for future in as_completed(futures):
            cat_url = futures[future]
            try:
                links = future.result()
                all_links[cat_url] = links
                print(f"[✓] Collected {len(links)} resumes from {cat_url}")
            except Exception as e:
                print(f"[!] Failed to scrape {cat_url}: {e}")

    # Flatten list
    all_resume_links = [link for links in all_links.values() for link in links]

    return all_resume_links
