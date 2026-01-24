"""
LLM-based resume scraper using Groq API.
Fetches HTML content and uses Groq LLM to extract structured resume data.
"""
import re
import time
import random
from typing import Tuple, Optional
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from typing import List

from src.data_acquisition.groq_client import groq_structured_output_sync
from src.data_acquisition.scrape import Resume, Experience
from src.utils.logger import get_logger

logger = get_logger(__name__)


def fetch_page_text(url: str, retries: int = 3) -> str:
    """
    Fetch the full text content from a resume URL.
    
    Args:
        url: Resume URL to fetch
        retries: Number of retry attempts on failure
    
    Returns:
        str: Extracted text from the page
    
    Raises:
        Exception: If fetching fails after all retries
    """
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
    
    for attempt in range(retries):
        try:
            logger.info(f"Fetching page content from: {url} (attempt {attempt + 1}/{retries})")
            
            with requests.Session() as session:
                session.headers.update(headers)
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
                
                if len(resp.text) < 1000:
                    raise ValueError(f"Response too short ({len(resp.text)} chars). Possible empty page.")
                
                # Parse HTML and extract text
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer"]):
                    script.decompose()
                
                # Get text
                text = soup.get_text(separator="\n", strip=True)
                
                # Clean up whitespace
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                clean_text = "\n".join(lines)
                
                logger.info(f"✅ Successfully fetched {len(clean_text)} characters from {url}")
                return clean_text
                
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
            
            if attempt == retries - 1:
                logger.error(f"❌ Failed to fetch {url} after {retries} attempts")
                raise
            
            # Exponential backoff
            wait_time = random.uniform(1, 3) * (2 ** attempt)
            logger.debug(f"Waiting {wait_time:.1f}s before retry...")
            time.sleep(wait_time)
    
    raise Exception(f"Failed to fetch page after {retries} attempts")


def extract_resume_with_groq(text: str, url: str) -> Tuple[Optional[Resume], Optional[dict]]:
    """
    Extract structured resume data from page text using Groq LLM.
    
    Args:
        text: Full page text content
        url: Source URL (for logging/debugging)
    
    Returns:
        Tuple[Optional[Resume], Optional[dict]]: (resume_object, rate_limit_info)
            - If successful: (Resume, rate_info_dict)
            - If failed: (None, None)
    
    Raises:
        Exception: If LLM extraction fails or required sections are missing
    """
    logger.info(f"Extracting resume data with Groq LLM for: {url}")
    
    system_prompt = """You are a resume data extraction expert. Extract structured resume information from the provided text.

Your task is to extract:
1. Job role (the main job title this resume is for)
2. Professional summary (list of summary points/highlights)
3. Technical skills (list of technical skills mentioned)
4. Professional experiences (list of work experiences with job_role, responsibilities, and optionally environment)

IMPORTANT RULES:
- Extract ALL available information - be comprehensive
- For professional_summary: Extract all summary/highlights points as separate list items
- For technical_skills: Extract all technical skills mentioned (programming languages, tools, frameworks, etc.)
- For experiences: Extract all work experiences with their job roles, responsibilities, and environment if mentioned
- If a section is not present in the text, return an empty list for that section
- Be thorough and don't skip any details

The resume text may contain:
- Job title/role at the top
- A "SUMMARY" or "PROFESSIONAL SUMMARY" section
- A "TECHNICAL SKILLS" or "SKILLS" section  
- A "PROFESSIONAL EXPERIENCE" or "WORK EXPERIENCE" section with multiple jobs

Extract everything you find!"""

    user_prompt = f"""Extract resume data from the following text:

{text[:8000]}

Return a complete resume with all sections filled out as completely as possible."""

    try:
        # Call Groq LLM with structured output
        resume, rate_info = groq_structured_output_sync(
            response_model=Resume,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="llama-3.1-8b-instant",
            max_tokens=4000,
            temperature=0.3
        )
        
        # Check if Groq returned None due to rate limit exhaustion
        if resume is None:
            logger.error(f"❌ Groq LLM extraction failed for {url}: Rate limits exhausted")
            return None, rate_info
        
        logger.info(
            f"✅ Groq extraction successful - "
            f"job_role: '{resume.job_role}', "
            f"summary: {len(resume.professional_summary)} items, "
            f"skills: {len(resume.technical_skills)} items, "
            f"experiences: {len(resume.experiences)} items"
        )
        
        return resume, rate_info
        
    except Exception as e:
        logger.error(f"❌ Groq LLM extraction failed for {url}: {e}")
        raise



def validate_resume_complete(resume: Resume) -> Tuple[bool, str]:
    """
    Validate that a resume has all required sections with data.
    
    Args:
        resume: Resume object to validate
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
            - is_valid: True if all required sections present and non-empty
            - error_message: Description of what's missing (empty string if valid)
    """
    missing_sections = []
    
    # Check job_role
    if not resume.job_role or not resume.job_role.strip():
        missing_sections.append("job_role")
    
    # Check professional_summary
    if not resume.professional_summary or len(resume.professional_summary) == 0:
        missing_sections.append("professional_summary")
    
    # Check technical_skills
    if not resume.technical_skills or len(resume.technical_skills) == 0:
        missing_sections.append("technical_skills")
    
    # Check experiences
    if not resume.experiences or len(resume.experiences) == 0:
        missing_sections.append("experiences")
    
    if missing_sections:
        error_msg = f"Resume missing required sections: {', '.join(missing_sections)}"
        logger.warning(f"❌ Validation failed: {error_msg}")
        return False, error_msg
    
    logger.info("✅ Resume validation passed - all required sections present")
    return True, ""


def scrape_resume_with_llm(url: str) -> Tuple[Optional[Resume], Optional[str], Optional[dict]]:
    """
    Complete pipeline: Fetch page → Extract with Groq → Validate
    
    Args:
        url: Resume URL to scrape
    
    Returns:
        Tuple[Optional[Resume], Optional[str], Optional[dict]]: (resume_object, error_message, rate_limit_info)
            - If successful: (Resume, None, rate_info)
            - If failed: (None, error_message, rate_info or None)
    """
    try:
        # Step 1: Fetch page text
        logger.info(f"Starting LLM-based scraping for: {url}")
        page_text = fetch_page_text(url)
        
        # Step 2: Extract with Groq
        resume, rate_info = extract_resume_with_groq(page_text, url)
        
        if resume is None:
            return None, "LLM extraction failed", None
        
        # Step 3: Validate completeness
        is_valid, error_msg = validate_resume_complete(resume)
        
        if not is_valid:
            return None, error_msg, rate_info
        
        logger.info(f"✅ Successfully scraped and validated resume from: {url}")
        return resume, None, rate_info
        
    except Exception as e:
        error_msg = f"Failed to scrape resume: {str(e)}"
        logger.error(f"❌ {error_msg} - URL: {url}")
        return None, error_msg, None
