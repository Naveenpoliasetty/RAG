import re
import requests
import json
from bs4 import BeautifulSoup
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

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

def extract_post_body_safe(url,
                           target_class=None,
                           class_regex=None,
                           allow_fallback=True,
                           debug=False):
    """
    Extracts text and structure (<p>, <ul>, <li>) from the main post container.
    """
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    normalize_breaks(soup)

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

    # Preserve structure: paragraphs, unordered lists and list items
    structured_content = []
    for element in container.find_all(["p", "ul"], recursive=True):
        if element.name == "p":
            text = clean_whitespace(" ".join(element.stripped_strings))
            if text:
                structured_content.append({
                    "type": "p",
                    "text": text
                })
        elif element.name == "ul":
            items = []
            for li in element.find_all("li", recursive=False):
                li_text = clean_whitespace(" ".join(li.stripped_strings))
                if li_text:
                    items.append(li_text)
            if items:
                structured_content.append({
                    "type": "ul",
                    "items": items
                })

    # Join paragraphs for convenience
    joined_p = "\n\n".join(
        [block["text"] for block in structured_content if block["type"] == "p"]
    )

    container_words = len(container_text.split())
    joined_words = len(joined_p.split()) if joined_p else 0

    warnings = []
    missing_excerpt = ""
    if container_words > joined_words + 20:
        temp = container_text
        for block in structured_content:
            if block["type"] == "p":
                temp = temp.replace(block["text"], "")
            elif block["type"] == "ul":
                for item in block["items"]:
                    temp = temp.replace(item, "")
        missing_excerpt = temp.strip()[:800]
        if missing_excerpt:
            warnings.append("Container has additional text not captured by structured tags.")
    if "<script" in resp.text.lower() and (container_words == 0 or joined_words == 0):
        warnings.append("Page might be JS-rendered. Try using Playwright or Selenium.")

    if debug:
        print("===== DEBUG INFO =====")
        print("Container:", container.get("class"))
        print("Captured paragraphs:", sum(1 for b in structured_content if b["type"] == "p"))
        print("Captured lists:", sum(1 for b in structured_content if b["type"] == "ul"))
        print("Warnings:", warnings)
        print("======================")

    return {
        "url":url,
        "structured_content": structured_content,
        "full_text": joined_p,
        "container_text": container_text,
        "missing_excerpt": missing_excerpt,
        "warnings": warnings
    }

# Example usage
result = extract_post_body_safe(
    url=all_resume_links[79],
    class_regex=r"(single-post-body|post-content|entry-content|article-body)",
    debug=True
)

# Print preview
for block in result["structured_content"][:5]:
    if block["type"] == "p":
        print(f"PARA: {block['text'][:100]}")
    elif block["type"] == "ul":
        print(f"LIST: {block['items']}")

# Save to JSON
with open("post_content_79.json", "w") as f:
    f.write(json.dumps(result, indent=4, ensure_ascii=False))

class Experience(BaseModel):
    company: str
    job_role: str
    responsibilities: List[str]
    environment: Optional[str] = None

class Resume(BaseModel):
    professional_summary: List[str]
    technical_skills: List[str]
    experiences: List[Experience]

def parse_resume(json_data):
    # Initialize the resume structure
    resume = {
        "professional_summary": [],
        "technical_skills": [],
        "experiences": []
    }
    
    structured_content = json_data.get("structured_content", [])
    
    # Flags to track current section
    in_summary = False
    in_technical_skills = False
    in_professional_experience = False
    
    # Variables for experience parsing
    current_experience = None
    current_job_role = None
    current_responsibilities = []
    current_environment = None
    experience_started = False
    
    # Iterate through each element in structured_content
    i = 0
    while i < len(structured_content):
        element = structured_content[i]
        
        # Check if we're entering SUMMARY section
        if element["type"] == "p" and "SUMMARY" in element["text"]:
            in_summary = True
            in_technical_skills = False
            in_professional_experience = False
            i += 1
            continue
        
        # Check if we're entering TECHNICAL SKILLS section
        elif element["type"] == "p" and "TECHNICAL SKILLS" in element["text"]:
            in_summary = False
            in_technical_skills = True
            in_professional_experience = False
            i += 1
            continue
        
        # Check if we're entering PROFESSIONAL EXPERIENCE section
        elif element["type"] == "p" and "PROFESSIONAL EXPERIENCE" in element["text"]:
            in_summary = False
            in_technical_skills = False
            in_professional_experience = True
            i += 1
            continue
        
        # Process SUMMARY section
        elif in_summary:
            if element["type"] == "ul":
                resume["professional_summary"].extend(element["items"])
            i += 1
            continue
        
        # Process TECHNICAL SKILLS section
        elif in_technical_skills:
            if element["type"] == "p":
                # Skip the "TECHNICAL SKILLS:" header itself
                if "TECHNICAL SKILLS" not in element["text"]:
                    resume["technical_skills"].append(element["text"])
            i += 1
            continue
        
        # Process PROFESSIONAL EXPERIENCE section
        elif in_professional_experience:
            # Check for "Confidential" P tags to identify new experiences
            if element["type"] == "p" and "Confidential" in element["text"]:
                # Save previous experience if it exists and has data
                if experience_started and current_job_role:
                    experience_data = {
                        "job_role": current_job_role,
                        "responsibilities": current_responsibilities.copy()
                    }
                    if current_environment:
                        experience_data["environment"] = current_environment
                    resume["experiences"].append(experience_data)
                
                # Reset for new experience
                current_job_role = None
                current_responsibilities = []
                current_environment = None
                experience_started = True
                
                # The next P tag after "Confidential" should be the job role
                if i + 1 < len(structured_content):
                    next_element = structured_content[i + 1]
                    if next_element["type"] == "p":
                        current_job_role = next_element["text"]
                        i += 2  # Skip both confidential and job role
                    else:
                        i += 1
                else:
                    i += 1
                continue
            
            # Check for UL tags (responsibilities)
            elif element["type"] == "ul" and current_job_role:
                current_responsibilities.extend(element["items"])
                i += 1
                continue
            
            # Check for "Environment" P tags
            elif element["type"] == "p" and "Environment:" in element["text"]:
                current_environment = element["text"].replace("Environment:", "").strip()
                i += 1
                continue
            
            # Check for "Environment" without colon (some entries might have different formatting)
            elif element["type"] == "p" and "Environment" in element["text"] and current_job_role:
                current_environment = element["text"].replace("Environment", "").strip()
                if current_environment.startswith(":"):
                    current_environment = current_environment[1:].strip()
                i += 1
                continue
            
            # Regular P tag in experience section (might be environment or other info)
            elif element["type"] == "p":
                # If we don't have a job role yet but we're in an experience, this might be it
                if not current_job_role and "Confidential" not in element["text"] and "PROFESSIONAL EXPERIENCE" not in element["text"]:
                    current_job_role = element["text"]
                i += 1
                continue
            
            else:
                i += 1
                continue
        
        else:
            i += 1
            continue
    
    # Don't forget to add the last experience if it exists
    if experience_started and current_job_role:
        experience_data = {
            "job_role": current_job_role,
            "responsibilities": current_responsibilities.copy()
        }
        if current_environment:
            experience_data["environment"] = current_environment
        resume["experiences"].append(experience_data)
    
    return resume

# Alternative version that returns a Resume object
def parse_resume_to_object(json_data):
    parsed_data = parse_resume(json_data)
    return Resume(**parsed_data)

# Usage example:
if __name__ == "__main__":
    # Assuming your JSON data is in a variable called 'sample_json'
    resume_data = parse_resume(result)
    with open("structured_resume.json", "w") as f:
        json.dump(resume_data, f, indent=4)
    
    # Print the results to verify
    print("PROFESSIONAL SUMMARY:")
    for item in resume_data["professional_summary"]:
        print(f"- {item}")
    
    print("\nTECHNICAL SKILLS:")
    for skill in resume_data["technical_skills"]:
        print(f"- {skill}")
    
    print("\nEXPERIENCES:")
    for idx, exp in enumerate(resume_data["experiences"]):
        print(f"\n--- Experience {idx + 1} ---")
        print(f"Job Role: {exp['job_role']}")
        if 'environment' in exp:
            print(f"Environment: {exp['environment']}")
        print("Responsibilities:")
        for resp in exp['responsibilities']:
            print(f"- {resp}")