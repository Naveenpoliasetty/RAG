from typing import Dict, Any
import re

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
