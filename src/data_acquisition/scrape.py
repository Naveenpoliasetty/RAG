import re
from typing import List, Optional
import time, random #noqa
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
            if len(text.split()) > min_word_threshold:
                skipped_blocks.append(text[:120] + "...")
                continue
            if text:
                structured_content.append({"type": "p", "text": text})

        elif element.name == "ul":
            items = []
            for li in element.find_all("li", recursive=False):
                li_text = clean_whitespace(" ".join(li.stripped_strings))
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
