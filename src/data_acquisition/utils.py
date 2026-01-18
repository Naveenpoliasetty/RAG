import re
import time, random
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from bs4 import BeautifulSoup
import requests
from pydantic import BaseModel


class Experience(BaseModel):
    job_role: str
    responsibilities: List[str]
    environment: Optional[str] = None


class Resume(BaseModel):
    job_role: str
    professional_summary: List[str]
    technical_skills: List[str]
    experiences: List[Experience]


class PostExtractionResult(BaseModel):
    """Result model for post extraction step."""
    job_role: Optional[str]
    structured_content: List[dict]
    full_text: str
    container_text: str
    missing_excerpt: str
    skipped_blocks: List[str]
    warnings: List[str]
    
def normalize_breaks(soup):
    """Convert <br> tags to newline text nodes so .get_text() uses them."""
    for br in soup.find_all("br"):
        br.replace_with("\n")

def clean_whitespace(text):
    lines = [ln.strip() for ln in text.splitlines()]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join([re.sub(r'\s+', ' ', ln) for ln in lines])

def extract_job_role(soup):
    media_bodies = soup.find_all("div", class_=re.compile(r"media-body"))
    if media_bodies:
        media_body = media_bodies[0]
        job_title_tag = media_body.find("h3")
        if job_title_tag:
            job_role = job_title_tag.get_text(strip=True)
            if job_role:
                return job_role
    return None

def extract_post_body_safe(
    url: str,
    target_class: Optional[str] = None,
    class_regex: Optional[str] = None,
    allow_fallback: bool = True,
    debug: bool = False,
    min_word_threshold: int = 120,
    retries: int = 3,
) -> PostExtractionResult:
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
    
    for attempt in range(retries):
        try:
            with requests.Session() as session:
                session.headers.update(headers)
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
                if len(resp.text) < 1000:
                    raise ValueError("Response too short.")
                break
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(random.uniform(1, 3))
    soup = BeautifulSoup(resp.text, "html.parser")

    normalize_breaks(soup)

    # Identify container
    container = None
    if target_class:
        container = soup.find("div", class_=target_class)
    if not container and class_regex:
        container = soup.find("div", class_=re.compile(class_regex))
    if not container and allow_fallback:
        divs = soup.find_all("div")
        if divs:
            container = max(divs, key=lambda d: len(d.get_text(strip=True)))
    if not container:
        raise ValueError("Could not find a suitable container.")

    raw_container_text = container.get_text(separator="\n", strip=True)
    container_text = clean_whitespace(raw_container_text)

    structured_content = []
    skipped_blocks = []  # 🔹 Track skipped text blocks

    resume_job_role = extract_job_role(soup)

    # 2️⃣ Handle normal paragraphs and lists not under media-body
    for element in container.find_all(["p", "ul"], recursive=True):
        if element.find_parent("div", class_=re.compile(r"media-body")):
            continue  # already captured above

        if element.name == "p":
            text = clean_whitespace(" ".join(element.stripped_strings))
            # 🚫 Skip overly long text blocks
            if len(text.split()) > min_word_threshold:
                skipped_blocks.append(text[:120] + "...")
                continue
            if text:
                structured_content.append({"type": "p", "text": text})

        elif element.name == "ul":
            items = []
            for li in element.find_all("li", recursive=False):
                li_text = clean_whitespace(" ".join(li.stripped_strings))
                # 🚫 Skip overly long list items
                if len(li_text.split()) > min_word_threshold:
                    skipped_blocks.append(li_text[:120] + "...")
                    continue
                if li_text:
                    items.append(li_text)
            if items:
                structured_content.append({"type": "ul", "items": items})

    # Join all paragraph text for convenience
    joined_p = "\n\n".join(
        [b["text"] for b in structured_content if b.get("type") == "p"]
    )

    container_words = len(container_text.split())
    joined_words = len(joined_p.split()) if joined_p else 0

    warnings = []
    missing_excerpt = ""
    if container_words > joined_words + 20:
        temp = container_text
        for block in structured_content:
            if block.get("type") == "p":
                temp = temp.replace(block["text"], "")
            elif block.get("type") == "ul":
                for item in block["items"]:
                    temp = temp.replace(item, "")
            elif "job_role" in block:
                temp = temp.replace(block["job_role"], "")
                for sub in block.get("content", []):
                    if sub.get("type") == "p":
                        temp = temp.replace(sub["text"], "")
                    elif sub.get("type") == "ul":
                        for item in sub["items"]:
                            temp = temp.replace(item, "")
        missing_excerpt = temp.strip()[:800]
        if missing_excerpt:
            warnings.append("Container has additional text not captured by structured tags.")

    if "<script" in resp.text.lower() and (container_words == 0 or joined_words == 0):
        warnings.append("Page might be JS-rendered.")

    if debug:
        print("===== DEBUG INFO =====")
        print("Container classes:", container.get("class"))
        print("Job roles found:", sum(1 for b in structured_content if "job_role" in b))
        print("Paragraphs:", sum(1 for b in structured_content if b.get("type") == "p"))
        print("Lists:", sum(1 for b in structured_content if b.get("type") == "ul"))
        print("Skipped blocks:", len(skipped_blocks))
        print("Warnings:", warnings)
        print("======================")

    return PostExtractionResult(
        job_role=resume_job_role,
        structured_content=structured_content,
        full_text=joined_p,
        container_text=container_text,
        missing_excerpt=missing_excerpt,
        skipped_blocks=skipped_blocks,
        warnings=warnings,
    )


import re
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from tqdm import tqdm

import re
from typing import Any, Dict, List

def parse_resume(json_data: Dict[str, Any]) -> Dict[str, Any]:
    resume = {
        "job_role": json_data.get("job_role", ""),
        "professional_summary": [],
        "technical_skills": [],
        "experiences": []
    }
    
    structured_content = json_data.get("structured_content", [])
    if not structured_content:
        return resume

    # --- Pre-normalize data for faster lookup ---
    for e in structured_content:
        e["text_norm"] = e.get("text", "").strip()
        e["text_upper"] = e["text_norm"].upper()

    # --- Identify section indices ---
    section_idx = { "SUMMARY": None, "TECHNICAL SKILLS": None, "PROFESSIONAL EXPERIENCE": None }
    for i, e in enumerate(structured_content):
        if e["type"] == "p" and e["text_upper"] in section_idx:
            section_idx[e["text_upper"]] = i

    # --- Extract sections safely ---
    def slice_section(start_key, end_key=None):
        start = section_idx.get(start_key)
        if start is None:
            return []
        end = section_idx.get(end_key)
        return structured_content[start+1:end] if end else structured_content[start+1:]

    summary_section = slice_section("SUMMARY", "TECHNICAL SKILLS")
    skills_section = slice_section("TECHNICAL SKILLS", "PROFESSIONAL EXPERIENCE")
    exp_section = slice_section("PROFESSIONAL EXPERIENCE")

    # --- Parse SUMMARY ---
    for e in summary_section:
        if e["type"] == "ul":
            resume["professional_summary"].extend(e.get("items", []))

    # --- Parse TECHNICAL SKILLS ---
    resume["technical_skills"] = [
        e["text_norm"] for e in skills_section
        if e["type"] == "p" and e["text_upper"] != "TECHNICAL SKILLS"
    ]

    # --- Parse EXPERIENCES (single linear scan, no nested loops) ---
    exp_blocks = []
    exp_data = None
    for e in exp_section:
        txt = e["text_norm"]
        if e["type"] == "p" and txt.startswith("Confidential"):
            # Start new block
            if exp_data and exp_data["job_role"] and exp_data["responsibilities"]:
                exp_blocks.append(exp_data)
            exp_data = {"job_role": "", "responsibilities": [], "environment": None}
            continue

        if exp_data is None:
            continue

        if e["type"] in ["p", "strong"] and not exp_data["job_role"]:
            if not any(k in e["text_upper"] for k in ["SUMMARY", "TECHNICAL SKILLS", "PROFESSIONAL EXPERIENCE", "RESPONSIBILITIES", "ENVIRONMENT"]):
                exp_data["job_role"] = txt
            continue

        if e["type"] == "ul":
            exp_data["responsibilities"].extend(e.get("items", []))
            continue

        if e["type"] == "p" and txt.lower().startswith("environment"):
            exp_data["environment"] = txt.split(":", 1)[-1].strip()
            continue

    if exp_data and exp_data["job_role"] and exp_data["responsibilities"]:
        exp_blocks.append(exp_data)

    resume["experiences"] = exp_blocks
    return resume


def validate_structured_resume(json_data: Dict[str, Any]) -> Dict[str, Any]:
    structured = json_data.get("structured_content", [])
    if not structured:
        return {"is_valid": False, "errors": ["Empty structured_content"], "sections_found": [], "valid_experience_blocks": 0}

    errors, sections, valid_blocks = [], [], 0
    n = len(structured)

    # Pre-normalize once
    for e in structured:
        e["text_norm"] = e.get("text", "").strip()
        e["text_upper"] = e["text_norm"].upper()

    # Fast lookups
    def find_section(name):
        for i, e in enumerate(structured):
            if e["text_upper"] == name and e["type"] == "p":
                return i
        return None

    # --- Check for required sections ---
    summary_i = find_section("SUMMARY")
    skills_i = find_section("TECHNICAL SKILLS")
    exp_i = find_section("PROFESSIONAL EXPERIENCE")

    if summary_i is None:
        errors.append("Missing SUMMARY section")
    else:
        sections.append("SUMMARY")
    if skills_i is None:
        errors.append("Missing TECHNICAL SKILLS section")
    else:
        sections.append("TECHNICAL SKILLS")
    if exp_i is None:
        errors.append("Missing PROFESSIONAL EXPERIENCE section")
    else:
        sections.append("PROFESSIONAL EXPERIENCE")

    if errors:
        return {"is_valid": False, "errors": errors, "sections_found": sections, "valid_experience_blocks": 0}

    # --- Validate experiences in O(n) pass ---
    re_conf = re.compile(r"^Confidential", re.I)
    re_resp = re.compile(r"^responsibilities", re.I)
    re_env = re.compile(r"^environment", re.I)

    i = exp_i + 1
    while i < n:
        e = structured[i]
        if e["type"] == "p" and re_conf.match(e["text_norm"]):
            if i + 1 < n and structured[i + 1]["type"] in ["p", "strong"]:
                valid_blocks += 1
            else:
                errors.append(f"Missing job role after Confidential at index {i}")
        i += 1

    if valid_blocks == 0:
        errors.append("No valid experience blocks found")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "sections_found": sections,
        "valid_experience_blocks": valid_blocks
    }




def parse_resume_to_object(url: str) -> Tuple[Optional[Resume], Optional[str]]:
    """
    Returns (Resume object, failed_url_if_any).
    """
    try:
        scraped_data = extract_post_body_safe(
            url,
            class_regex=r"(single-post-body|post-content|entry-content|article-body)",
            allow_fallback=True
        )

        # Validate structure
        valid_check = validate_structured_resume(scraped_data.model_dump())
        if not valid_check["is_valid"]:
            return None, url  # Invalid resume structure

        parsed_data = parse_resume(scraped_data.model_dump())
        resume_obj = Resume(**parsed_data)
        return resume_obj, None  # success

    except Exception as e:
        # Any parsing/scraping failure
        return None, url



def scrape_and_parse_all(all_resume_links: List[str], max_workers: int = 12, timeout: int = 30, max_retries: int = 2):
    """Scrape and parse resumes concurrently with retry logic."""
    if not all_resume_links:
        return {}, []
    
    org_resume_dict = {}
    failed_urls = []
    
    print(f"[+] Scraping {len(all_resume_links)} resumes with {max_workers} workers, timeout={timeout}s...")
    
    def safe_parse_with_retry(url: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Wrapper with retry logic and exponential backoff."""
        for attempt in range(max_retries + 1):
            try:
                # Assuming parse_resume_to_object is defined elsewhere
                resume_obj, failed_url = parse_resume_to_object(url)
                
                if resume_obj:
                    return resume_obj.model_dump(), None
                elif failed_url:
                    return None, failed_url
                else:
                    # Both None - treat as failure
                    return None, url
                    
            except Exception as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    print(f"[!] Attempt {attempt + 1} failed for {url}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"[!] All {max_retries + 1} attempts failed for {url}: {e}")
                    return None, url
        
        return None, url
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(safe_parse_with_retry, url): url 
            for url in all_resume_links
        }
        
        with tqdm(total=len(future_to_url), desc="Scraping resumes", unit="resume") as pbar:
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result(timeout=timeout * 2)
                    resume_data, failed_url = result
                    
                    if resume_data:
                        org_resume_dict[url] = resume_data
                    if failed_url:
                        failed_urls.append(failed_url)
                        
                except TimeoutError:
                    print(f"[!] Timeout processing {url}")
                    failed_urls.append(url)
                except Exception as e:
                    print(f"[!] Unexpected error processing {url}: {e}")
                    failed_urls.append(url)
                finally:
                    pbar.update(1)
    
    success_rate = (len(org_resume_dict) / len(all_resume_links) * 100) if all_resume_links else 0
    print(f"\n[+] Final: {len(org_resume_dict)} successful, {len(failed_urls)} failed ({success_rate:.1f}% success rate)")
    
    return org_resume_dict, failed_urls