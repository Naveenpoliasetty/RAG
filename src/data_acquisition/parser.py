from typing import Dict, Any
from src.utils.logger import get_logger
import re
logger = get_logger("Parser")

# Pre-compile regex patterns for better performance
RESUME_PATTERNS = [
    re.compile(r'\bresume\b', re.IGNORECASE),
    re.compile(r'\brésumé\b', re.IGNORECASE),
    re.compile(r'\bresumes\b', re.IGNORECASE),
    re.compile(r'\brésumés\b', re.IGNORECASE),
    re.compile(r'\bcv\b', re.IGNORECASE),
    re.compile(r'\bcvs\b', re.IGNORECASE),
    re.compile(r'\bcurriculum vitae\b', re.IGNORECASE),
]

JOB_ROLE_REPLACEMENTS = [
    (re.compile(r'\bpl\s*/\s*sql\b', re.IGNORECASE), 'pl/sql'),
    (re.compile(r'\bplsql\b', re.IGNORECASE), 'pl/sql'),
    (re.compile(r'\bdba\b', re.IGNORECASE), 'database administrator'),
    (re.compile(r'\bfi/co\b', re.IGNORECASE), 'fi-co'),
    (re.compile(r'\bfi\s*/\s*co\b', re.IGNORECASE), 'fi-co'),
    (re.compile(r'\bsr\.\b', re.IGNORECASE), 'senior'),
    (re.compile(r'\bsr\b', re.IGNORECASE), 'senior'),
    (re.compile(r'\band\b', re.IGNORECASE), '&'),
    (re.compile(r'\s+'), ' '),  # Normalize multiple spaces
]

PREFIX_REMOVALS = [
    re.compile(r'^senior\s+', re.IGNORECASE),
    re.compile(r'^lead\s+', re.IGNORECASE),
    re.compile(r'^sr\s+', re.IGNORECASE),
]

CLEANUP_PATTERNS = [
    (re.compile(r'\s+'), ' '),
    (re.compile(r'^\s+|\s+$'), ''),
    (re.compile(r'^[,\-\s]+|[,\-\s]+$'), ''),
]


def remove_resume_from_role(role: str) -> str:
    """
    Remove 'Resume' and its variations from job role.

    Args:
        role: Raw job role string

    Returns:
        Job role with Resume keywords removed
    """
    if not role:
        return ""

    cleaned_role = role
    for pattern in RESUME_PATTERNS:
        cleaned_role = pattern.sub('', cleaned_role)

    # Clean up extra spaces and punctuation
    for pattern, replacement in CLEANUP_PATTERNS:
        cleaned_role = pattern.sub(replacement, cleaned_role)

    return cleaned_role


def normalize_job_role(role: str) -> str:
    """
    Normalize job role by standardizing common variations.

    Args:
        role: Raw job role string

    Returns:
        Normalized job role string
    """
    if not role:
        return ""

    # First remove Resume keywords from the role
    role = remove_resume_from_role(role)

    if not role:
        return ""

    # Convert to lowercase for case-insensitive comparison
    normalized = role.lower().strip()

    # Standardize common abbreviations and spellings
    for pattern, replacement in JOB_ROLE_REPLACEMENTS:
        normalized = pattern.sub(replacement, normalized)

    # Remove common prefixes/suffixes that don't change the core role
    for pattern in PREFIX_REMOVALS:
        normalized = pattern.sub('', normalized)

    return normalized.strip()


def parse_resume(json_data: Dict[str, Any]) -> Dict[str, Any]:
    raw_job_role = json_data.get("job_role", "")
    normalized_job_role = normalize_job_role(raw_job_role)
    resume = {
        "job_role": normalized_job_role,
        "professional_summary": [],
        "technical_skills": [],
        "experiences": []
    }

    structured_content = json_data.get("structured_content", [])
    if not structured_content:
        return resume

    # --- Pre-normalize data for faster lookup ---
    def preprocess_structured_content(content: list) -> list:
        """
        Splits merged headers using regex, e.g., 'PROFESSIONAL EXPERIENCECONFIDENTIAL'
        becomes 'PROFESSIONAL EXPERIENCE' and 'CONFIDENTIAL'.
        """
        new_content = []
        # sort headers by length desc to match long ones first (e.g. PROFESSIONAL SUMMARY before SUMMARY)
        headers = ["PROFESSIONAL EXPERIENCE", "TECHNICAL SKILLS", "PROFESSIONAL SUMMARY", "SUMMARY"]
        # Pattern captures: Group 1 = Header, Group 2 = The rest
        # We use strict start ^ and case insensitive flag
        pattern = re.compile(r"^(" + "|".join(map(re.escape, headers)) + r")\s*(.+)$", re.IGNORECASE)

        for item in content:
            if item.get("type") != "p":
                new_content.append(item)
                continue
            
            text = item.get("text", "").strip()
            match = pattern.match(text)
            
            if match:
                header_part = match.group(1).strip()
                rest_part = match.group(2).strip()
                
                # Create two separate items
                # 1. The Header
                new_content.append({
                    "type": "p",
                    "text": header_part,
                    # Copy other props if needed, simpler to just keep minimal for internal logic
                })
                # 2. The Rest (only if not empty)
                if rest_part:
                    new_content.append({
                        "type": "p", # Assuming the rest is also text/paragraph
                        "text": rest_part
                    })
            else:
                new_content.append(item)
        return new_content

    structured_content = preprocess_structured_content(structured_content)

    for e in structured_content:
        e["text_norm"] = e.get("text", "").strip()
        e["text_upper"] = e["text_norm"].upper()

    # --- Identify section indices ---
    section_idx = {"SUMMARY": None, "TECHNICAL SKILLS": None, "PROFESSIONAL EXPERIENCE": None}
    
    # regex patterns for section headers
    # We strip trailing colons before matching, so the patterns don't need to handle them
    SECTION_PATTERNS = [
        (re.compile(r"^(?:PROFESSIONAL\s+)?SUMMARY$", re.IGNORECASE), "SUMMARY"),
        (re.compile(r"^TECHNICAL\s+SKILLS$", re.IGNORECASE), "TECHNICAL SKILLS"),
        (re.compile(r"^PROFESSIONAL\s+EXPERIENCE$", re.IGNORECASE), "PROFESSIONAL EXPERIENCE")
    ]

    for i, e in enumerate(structured_content):
        # Use text_norm (original case, stripped) for regex with IGNORECASE
        curr_text = re.sub(r"\s*:\s*$", "", e["text_norm"])
        
        if e["type"] == "p":
             for pattern, section_key in SECTION_PATTERNS:
                 if pattern.match(curr_text):
                     # Only set if not already set (first match wins, or last? original logic overwrote commonly unique)
                     # Original: section_idx[normalized_text] = i. If multiple appear, last one wins.
                     # Let's keep overwriting to match original behavior, or check? 
                     # Usually Resume headers appear once. 
                     section_idx[section_key] = i
                     break

    # --- Extract sections safely ---
    def slice_section(start_key, end_key=None):
        start = section_idx.get(start_key)
        if start is None:
            return []
        end = section_idx.get(end_key)
        return structured_content[start+1:end] if end else structured_content[start+1:]

    summary_section = slice_section("SUMMARY", "TECHNICAL SKILLS")
    skills_section = slice_section(
        "TECHNICAL SKILLS", "PROFESSIONAL EXPERIENCE")
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
            exp_data = {"job_role": "",
                        "responsibilities": [], "environment": None}
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
