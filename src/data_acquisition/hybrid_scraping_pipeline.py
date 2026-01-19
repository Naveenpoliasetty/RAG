import os
import sys
import re
import time
import asyncio
import requests
from typing import List, Optional, Any
from datetime import datetime
from pymongo import MongoClient
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# LangChain & Pydantic imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

# Project imports
sys.path.append(os.getcwd())
try:
    from src.core.config import settings
    from src.utils.logger import get_logger
except ImportError:
    # Fallback for direct execution
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.core.config import settings
    from src.utils.logger import get_logger

# Load env vars
load_dotenv()

logger = get_logger("HybridScraperAsync")

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
# Async Hybrid Scraper Class
# ----------------------------------------------------------------------

class AsyncHybridScraper:
    def __init__(self):
        # Database setup
        self.client = MongoClient(settings.MONGODB_URI)
        self.db = self.client[settings.MONGODB_DATABASE]
        self.failed_collection = self.db["failed_resumes"]
        self.output_collection = self.db["parsed_resumes_hybrid"]

        # API Keys Setup
        self.api_keys = settings.gemini_api_keys
        
        # Fallback to env var if not in settings, splitting by comma if it's a string
        if not self.api_keys:
            env_keys = os.getenv("GEMINI_API_KEYS")
            if env_keys:
                self.api_keys = [k.strip() for k in env_keys.split(",") if k.strip()]
        
        if not self.api_keys:
            logger.error("No Gemini API keys found in settings or environment variables.")
            raise ValueError("GEMINI_API_KEYS are required.")

        logger.info(f"Loaded {len(self.api_keys)} Gemini API keys.")

        # Initialize Chains (one per key)
        self.chains = []
        for key in self.api_keys:
            llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash", # Efficient model
                temperature=0,
                google_api_key=key,
                convert_system_message_to_human=True 
            )
            structured_llm = llm.with_structured_output(ResumeSections)
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an expert resume parser. Extract the following sections from the resume content: "
                           "Summary, Technical Skills, and Professional Experience. "
                           "Ensure 'Summary' is a list of strings. "
                           "Ensure 'Technical Skills' is a list of strings. "
                           "For 'Professional Experience', extract a list of jobs, where each job has a role, "
                           "a list of responsibilities (bullet points), and an environment string (if available)."),
                ("human", "Resume Content:\n\n{text}")
            ])
            
            chain = prompt | structured_llm
            self.chains.append(chain)

        # Semaphore to limit total concurrency to number of keys * 2 (pipeline depth)
        # However, rate limits are per key. So we simply assign one worker per key.
        self.queue = asyncio.Queue()

    def fetch_content_sync(self, url: str, retries=3) -> Optional[str]:
        """Fetches and cleans text content from the URL (Blocking I/O)."""
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
        """Extracts text from the html content."""
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Try specific container first
        container = soup.find("div", class_="single-post-body")
        if container:
            text = container.get_text(separator="\n", strip=True)
        else:
            text = soup.body.get_text(separator="\n", strip=True) if soup.body else ""
            
        return text

    async def fetch_content(self, url: str) -> Optional[str]:
        """Async wrapper for fetch_content_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.fetch_content_sync, url)

    async def worker(self, chain_index: int):
        """Worker that consumes tasks from the queue and uses a specific API key/chain."""
        chain = self.chains[chain_index]
        worker_id = f"Worker-{chain_index}"
        logger.info(f"{worker_id} started.")

        while True:
            doc = await self.queue.get()
            if doc is None:
                # Sentinel to stop
                self.queue.task_done()
                break

            url = doc.get("source_url")
            doc_id = doc["_id"]
            
            try:
                logger.info(f"[{worker_id}] Processing: {url}")
                
                # 1. Fetch Content
                raw_text = await self.fetch_content(url)
                if not raw_text:
                    logger.warning(f"[{worker_id}] Could not fetch content for {url}")
                    self.queue.task_done()
                    continue

                # 2. Parse with LLM (Async invoke)
                # Truncate to avoid context limit (Gemini has large context but good to be safe/efficient)
                try:
                    parsed_data = await chain.ainvoke({"text": raw_text[:30000]})
                except Exception as e:
                    logger.error(f"[{worker_id}] LLM Error for {url}: {e}")
                    # Simple backoff if rate limited might be handled by langchain, but adding a small sleep here helps avoid rapid loops on errors
                    await asyncio.sleep(2) 
                    parsed_data = None

                if parsed_data:
                    # 3. Prepare Document
                    output_doc = {
                        "original_id": doc_id,
                        "source_url": url,
                        "inconsistent_resume": doc.get("inconsistent_resume"),
                        "parsed_data": parsed_data.dict(),
                        "parsed_at": datetime.now(),
                        "model_used": "gemini-1.5-flash"
                    }

                    # 4. Save to DB (Blocking, so run in executor)
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self._save_to_db, doc_id, output_doc)
                    logger.info(f"[{worker_id}] Success for {doc_id}")
                else:
                    logger.warning(f"[{worker_id}] Failed to parse {url}")

            except Exception as e:
                logger.error(f"[{worker_id}] Unexpected error processing {doc_id}: {e}")
            finally:
                self.queue.task_done()
                # Optional: Add small delay to respect rate limits if needed, 
                # though we have 5 keys so we can likely go full speed.
                # await asyncio.sleep(1) 

    def _save_to_db(self, doc_id, output_doc):
        try:
            self.output_collection.update_one(
                {"original_id": doc_id},
                {"$set": output_doc},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to save to MongoDB: {e}")

    async def run_async(self, dry_run=False):
        # 1. Get IDs of already processed resumes
        existing_ids = self.output_collection.distinct("original_id")
        
        # 2. Query
        query = {
            "inconsistent_resume": False,
            "_id": {"$nin": existing_ids}
        }
        
        # Pull all docs to memory (assuming manageable size, else use cursor with batching)
        # For batching, we would push to queue incrementally.
        cursor = self.failed_collection.find(query)
        # Convert to list to easily count and distribute
        docs = list(cursor)
        total_docs = len(docs)
        
        if total_docs == 0:
            logger.info("No new consistent resumes to process.")
            return

        logger.info(f"Starting async pipeline for {total_docs} resumes with {len(self.chains)} concurrent workers.")
        
        if dry_run:
            docs = docs[:5] # Limit to 5 for dry run
            logger.info("Dry run: Processing subset of 5 resumes.")

        # Fill Queue
        for doc in docs:
            self.queue.put_nowait(doc)

        # Create Workers (one per chain/key)
        tasks = []
        for i in range(len(self.chains)):
            task = asyncio.create_task(self.worker(i))
            tasks.append(task)

        # Wait for queue to process
        await self.queue.join()

        # Stop workers
        for _ in range(len(self.chains)):
            self.queue.put_nowait(None)
        
        await asyncio.gather(*tasks)
        logger.info("All tasks completed.")

    def run(self, dry_run=False):
        asyncio.run(self.run_async(dry_run))

if __name__ == "__main__":
    is_dry_run = "--dry-run" in sys.argv
    scraper = AsyncHybridScraper()
    scraper.run(dry_run=is_dry_run)
