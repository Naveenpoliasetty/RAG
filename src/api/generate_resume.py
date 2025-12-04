from fastapi import APIRouter, File, Form, UploadFile, Depends
from fastapi.responses import JSONResponse
import json
import os
from src.generation.resume_generator import orchestrate_resume_generation_individual_experiences
from src.utils.logger import get_logger

from src.api.parser_resume import doc_to_text, parse_resume

logger = get_logger(__name__)
router = APIRouter()





@router.post("/generate_resume")
async def generate_resume_endpoint(
    file: UploadFile = File(...),
    job_description: str = Form(...),
    related_jobs: str = Form(...),

    semantic_weight: float = Form(0.7),
    keyword_weight: float = Form(0.3)
):
    """
    Unified API to generate resume with job context using hybrid search.
    Accepts:
    - file: Resume file upload (.docx or .pdf)
    - job_description: Job description (string)
    - related_jobs: JSON string array (e.g., '["Job1", "Job2"]') that will be parsed as a list
    - semantic_weight: Weight for semantic similarity (default 0.7)
    - keyword_weight: Weight for keyword matching (default 0.3)
    """
    try:
        # Extract text from resume file
        os.makedirs("uploads", exist_ok=True)
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as f:
            f.write(await file.read())
        resume_data = await parse_resume(file_path)
        resume_dict = json.loads(resume_data)

        experience_count = len(resume_dict["experiences"])
        
        # Delete the file after extracting text
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Deleted uploaded file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file {file_path}: {str(e)}")
        
        # Parse related_jobs from JSON string to list and validate
        try:
            parsed_related_jobs = json.loads(related_jobs)
            if not isinstance(parsed_related_jobs, list):
                return JSONResponse(
                    content={"error": "related_jobs must be a JSON array (list)"},
                    status_code=400
                )
            # Ensure all items in the list are strings
            if not all(isinstance(item, str) for item in parsed_related_jobs):
                return JSONResponse(
                    content={"error": "All items in related_jobs must be strings"},
                    status_code=400
                )
        except json.JSONDecodeError as e:
            return JSONResponse(
                content={"error": f"Invalid JSON format for related_jobs: {str(e)}"},
                status_code=400
            )
        
        # Generate resume sections using job_roles (related_jobs) with hybrid search
        result = await orchestrate_resume_generation_individual_experiences(
            job_description, 
            job_roles=parsed_related_jobs,
            num_experiences=experience_count,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight
        )
        with open("result.json", "w") as f:
            json.dump(result, f, indent=4)
        with open("resume_text.json", "w") as f:
            json.dump(resume_dict, f, indent=4)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error generating resume: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)