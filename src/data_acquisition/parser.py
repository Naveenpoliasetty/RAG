from typing import Dict, Any
from src.utils.logger import get_logger
logger = get_logger("Parser")

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