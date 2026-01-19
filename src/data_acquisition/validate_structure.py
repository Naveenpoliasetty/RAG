from typing import Dict, Any
import re

def validate_structured_resume(json_data: Dict[str, Any]) -> Dict[str, Any]:
    structured = json_data.get("structured_content", [])
    if not structured:
        return {"is_valid": False, "errors": ["Empty structured_content"], "sections_found": [], "valid_experience_blocks": 0}

    # --- Pre-normalize data for faster lookup (logic from parser.py) ---
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
            # Check if this line IS a merged header line
            match = pattern.match(text)
            
            if match:
                header_part = match.group(1).strip()
                rest_part = match.group(2).strip()
                
                # Create two separate items
                # 1. The Header
                new_content.append({
                    "type": "p",
                    "text": header_part,
                })
                # 2. The Rest (only if not empty)
                if rest_part:
                    new_content.append({
                        "type": "p",
                        "text": rest_part
                    })
            else:
                new_content.append(item)
        return new_content

    structured = preprocess_structured_content(structured)

    errors, sections, valid_blocks = [], [], 0
    n = len(structured)

    # Pre-normalize once
    for e in structured:
        e["text_norm"] = e.get("text", "").strip()
        e["text_upper"] = e["text_norm"].upper()

    # --- Identify section indices using regex ---
    found_sections_indices = {}
    
    # regex patterns for section headers
    # We strip trailing colons before matching, so the patterns don't need to handle them
    SECTION_PATTERNS = [
        (re.compile(r"^(?:PROFESSIONAL\s+)?SUMMARY$", re.IGNORECASE), "SUMMARY"),
        (re.compile(r"^TECHNICAL\s+SKILLS$", re.IGNORECASE), "TECHNICAL SKILLS"),
        (re.compile(r"^PROFESSIONAL\s+EXPERIENCE$", re.IGNORECASE), "PROFESSIONAL EXPERIENCE")
    ]

    for i, e in enumerate(structured):
        if e["type"] == "p":
             curr_text = re.sub(r"\s*:\s*$", "", e["text_norm"])
             for pattern, section_key in SECTION_PATTERNS:
                 if pattern.match(curr_text):
                     # Store first occurrence
                     if section_key not in found_sections_indices:
                         found_sections_indices[section_key] = i
                     break
   
    # --- Check for required sections ---
    if "SUMMARY" not in found_sections_indices:
        errors.append("Missing SUMMARY section")
    else:
        sections.append("SUMMARY")

    if "TECHNICAL SKILLS" not in found_sections_indices:
        errors.append("Missing TECHNICAL SKILLS section")
    else:
        sections.append("TECHNICAL SKILLS")

    if "PROFESSIONAL EXPERIENCE" not in found_sections_indices:
        errors.append("Missing PROFESSIONAL EXPERIENCE section")
    else:
        sections.append("PROFESSIONAL EXPERIENCE")

    if errors:
        return {"is_valid": False, "errors": errors, "sections_found": sections, "valid_experience_blocks": 0}

    # --- Validate experiences in O(n) pass ---
    re_conf = re.compile(r"^Confidential", re.I)

    # Start checking from after the Professional Experience header
    exp_i = found_sections_indices["PROFESSIONAL EXPERIENCE"]
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
