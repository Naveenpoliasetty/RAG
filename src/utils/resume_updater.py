import json
from copy import deepcopy

def update_resume_sections(original_resume: dict, updated_sections: dict) -> dict:
    """
    Replaces professional_summary, technical_skills, and updates only
    responsibilities + environment inside experiences.

    Environment rules:
    - If updated has environment → insert/replace it.
    - If updated does NOT have environment → REMOVE it from original.
    """
    new_resume = deepcopy(original_resume)

    # 1. Replace professional summary
    if "professional_summary" in updated_sections:
        new_resume["professional_summary"] = updated_sections["professional_summary"]["summaries"]

    # 2. Replace technical skills
    if "technical_skills" in updated_sections:
        new_resume["technical_skills"] = updated_sections["technical_skills"]["skills"]

    # 3. Update experiences safely
    updated_exps = updated_sections.get("experience", [])
    original_exps = new_resume.get("experiences", [])

    for i in range(min(len(original_exps), len(updated_exps))):
        updated_exp = updated_exps[i]
        original_exp = new_resume["experiences"][i]

        # Update job_role if provided in updated experience
        if "job_role" in updated_exp:
            original_exp["job_role"] = updated_exp["job_role"]

        # Replace responsibilities
        original_exp["responsibilities"] = updated_exp["responsibilities"]

        # Handle environment field
        if "environment" in updated_exp:
            # Insert or replace environment
            original_exp["environment"] = updated_exp["environment"]
        else:
            # Updated does NOT have environment → remove from original if exists
            original_exp.pop("environment", None)

    return new_resume


# ---------------- SAMPLE USAGE ----------------

# final_resume = update_resume_sections(old_resume_json, updated_sections_json)
# print(json.dumps(final_resume, indent=4))