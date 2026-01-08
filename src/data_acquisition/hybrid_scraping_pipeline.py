import os
import sys
import re
import time
import requests
from typing import List, Optional
from datetime import datetime
from pymongo import MongoClient
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# LangChain & Pydantic imports
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

# Project imports
sys.path.append(os.getcwd())
from src.core.settings import config
from src.utils.logger import get_logger

# Load env vars (ensure OPENAI_API_KEY is loaded)
load_dotenv()

logger = get_logger("HybridScraper")

# ----------------------------------------------------------------------
# Pydantic Models for Structured Output
# ----------------------------------------------------------------------

class ExperienceItem(BaseModel):
    """Represents a single professional experience entry."""
    job_role: str = Field(description="The job title or role.")
    responsibilities: List[str] = Field(description="List of responsibilities and achievements as bullet points.")
    environment: Optional[str] = Field(description="The technical environment, tools, or technologies used.", default=None)

class ResumeSections(BaseModel):
    """Structure for the 3 key sections of a resume."""
    summary: List[str] = Field(description="The professional summary or profile section as a list of bullet points or sentences.")
    technical_skills: List[str] = Field(description="List of technical skills, technologies, or competencies.")
    professional_experience: List[ExperienceItem] = Field(description="List of professional experience entries.")

# ----------------------------------------------------------------------
# Hybrid Scraper Class
# ----------------------------------------------------------------------

class HybridScraper:
    def __init__(self):
        # Database setup
        self.client = MongoClient(config.mongodb_uri)
        self.db = self.client[config.mongodb_database]
        self.failed_collection = self.db["failed_resumes"]
        self.output_collection = self.db["parsed_resumes_hybrid"]

        # LLM Setup
        # Using gpt-4o for high quality extraction, or fallback to gpt-3.5-turbo if needed and cheaper
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not found in environment variables.")
            raise ValueError("OPENAI_API_KEY is required.")

        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=api_key)
        self.structured_llm = self.llm.with_structured_output(ResumeSections)

        # Prompt Template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert resume parser. Extract the following sections from the resume content: "
                       "Summary, Technical Skills, and Professional Experience. "
                       "Ensure 'Summary' is a list of strings. "
                       "Ensure 'Technical Skills' is a list of strings. "
                       "For 'Professional Experience', extract a list of jobs, where each job has a role, "
                       "a list of responsibilities (bullet points), and an environment string (if available)."),
            ("human", "Resume Content:\n\n{text}")
        ])
        
        self.chain = self.prompt | self.structured_llm

    def fetch_content(self, url: str, retries=3) -> Optional[str]:
        """Fetches and cleans text content from the URL."""
        headers = {"User-Agent": "Mozilla/5.0"}
        for attempt in range(retries):
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    return self._clean_html(resp.text)
                elif resp.status_code == 429:
                    time.sleep(2 ** attempt)
            except requests.RequestException:
                pass
        return None

    def _clean_html(self, html_content: str) -> str:
        """Extracts text from the 'single-post-body' div or falls back to full body."""
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Try specific container first (based on previous scripts)
        container = soup.find("div", class_="single-post-body")
        if container:
            text = container.get_text(separator="\n", strip=True)
        else:
            # Fallback to body if specific container not found
            text = soup.body.get_text(separator="\n", strip=True) if soup.body else ""
            
        return text

    def parse_resume(self, text: str) -> Optional[ResumeSections]:
        """Invokes the LLM to parse the resume text."""
        try:
            result = self.chain.invoke({"text": text[:20000]}) # Truncate to avoid context limit if extreme
            return result
        except Exception as e:
            logger.error(f"Error parsing resume with LLM: {e}")
            return None

    def run(self, dry_run=False):
        # 1. Get IDs of already processed resumes
        existing_ids = self.output_collection.distinct("original_id")
        
        # 2. Query: Consistent resumes that are NOT in the output collection
        query = {
            "inconsistent_resume": False,
            "_id": {"$nin": existing_ids}
        } 
        
        total_docs = self.failed_collection.count_documents(query)
        if total_docs == 0:
            logger.info("No new consistent resumes to process.")
            return

        cursor = self.failed_collection.find(query)
        
        logger.info(f"Starting hybrid pipeline for {total_docs} NEW consistent resumes.")
        
        processed_count = 0
        success_count = 0

        for doc in cursor:
            if dry_run and processed_count >= 1:
                break

            url = doc.get("source_url")
            doc_id = doc["_id"]
            
            logger.info(f"Processing: {url}")
            
            # 1. Fetch Content
            raw_text = self.fetch_content(url)
            if not raw_text:
                logger.warning(f"Could not fetch content for {url}")
                continue

            # 2. Parse with LLM
            parsed_data = self.parse_resume(raw_text)
            
            if parsed_data:
                # 3. Prepare Document
                output_doc = {
                    "original_id": doc_id,
                    "source_url": url,
                    "inconsistent_resume": doc.get("inconsistent_resume"), # Should be False based on query
                    "parsed_data": parsed_data.dict(),
                    "parsed_at": datetime.now()
                }

                # 4. Save to DB
                try:
                    self.output_collection.update_one(
                        {"original_id": doc_id},
                        {"$set": output_doc},
                        upsert=True
                    )
                    logger.info(f"Successfully saved parsed data for {doc_id}")
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to save to MongoDB: {e}")
            else:
                logger.warning(f"LLM failed to return structured data for {url}")

            processed_count += 1

        logger.info(f"Pipeline finished. Processed: {processed_count}, Success: {success_count}")

if __name__ == "__main__":
    # Check for dry run arg
    is_dry_run = "--dry-run" in sys.argv
    
    scraper = HybridScraper()
    scraper.run(dry_run=is_dry_run)
