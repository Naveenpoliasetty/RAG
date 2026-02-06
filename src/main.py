import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from fastapi import FastAPI, Request, File, Form, UploadFile, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List
import json

from src.api import parser_resume, resume_chat, webhook, user_resumes
from src.api.parser_resume import parse_resume, router
from src.api.get_unique_job_roles import get_unique_job_roles
from src.core.config import settings
from src.core.db_manager import get_qdrant_manager, get_mongodb_manager
from src.generation.resume_generator import orchestrate_resume_generation_individual_experiences
from src.utils.logger import get_logger
from src.middleware.auth import get_current_user
from src.generation.resume_writer import generate_and_upload_resume
from src.utils.resume_updater import update_resume_sections
from datetime import datetime, timezone
from uuid import uuid4
logger = get_logger(__name__)


# -----------------------------
# Lifespan
# -----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.qdrant = get_qdrant_manager()
    app.state.mongodb = get_mongodb_manager()
    logger.info("Qdrant & MongoDB connections initialized")

    yield

    # Shutdown: Only close MongoDB
    if hasattr(app.state.mongodb, "close"):
        app.state.mongodb.close()
        logger.info("MongoDB connection closed")
    else:
        logger.warning("MongoDB client has no close() method")


# -----------------------------
# App Init
# -----------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan
)


# -----------------------------
# Dependencies
# -----------------------------
def get_qdrant(request: Request):
    return request.app.state.qdrant

def get_mongodb(request: Request):
    return request.app.state.mongodb


# -----------------------------
# CORS Config
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(parser_resume.router, prefix="/api/v1", tags=["Parser Resume"])
app.include_router(resume_chat.router, prefix="/api/v1", tags=["Resume Chat Editor"])
app.include_router(webhook.router, prefix="/api/v1", tags=["Webhooks"])
app.include_router(user_resumes.router, prefix="/api/v1", tags=["User Resumes"])

# -----------------------------
# Endpoints
# -----------------------------
@app.get("/")
async def root():
    return {"message": "Resume API Service"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Resume API"}


@app.post("/api/v1/generate_resume")
async def generate_resume_endpoint(
    file: UploadFile = File(...),
    job_description: str = Form(...),
    related_jobs: str = Form(...),
    qdrant_manager=Depends(get_qdrant),
    mongodb_manager=Depends(get_mongodb),
    current_user=Depends(get_current_user),
    semantic_weight: float = Form(0.7),
    keyword_weight: float = Form(0.3)
):
    try:
        # Save uploaded file
        os.makedirs("uploads", exist_ok=True)
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Extract resume text
        resume_data = await parse_resume(file_path)
        logger.info(f"Resume data: {resume_data}")
        resume_dict = json.loads(resume_data)
        experience_count = len(resume_dict["experiences"])

        # Delete uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)

        # Parse related jobs JSON
        try:
            parsed_related_jobs = json.loads(related_jobs)
            if not isinstance(parsed_related_jobs, list) or not all(isinstance(i, str) for i in parsed_related_jobs):
                return JSONResponse({"error": "related_jobs must be a list of strings"}, 400)
        except Exception as e:
            return JSONResponse({"error": f"Invalid related_jobs JSON: {e}"}, 400)

        # Generate resume
        result = await orchestrate_resume_generation_individual_experiences(
            job_description=job_description,
            job_roles=parsed_related_jobs,
            num_experiences=experience_count,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
            qdrant_manager=qdrant_manager,
            mongodb_manager=mongodb_manager
        )

        # Check if we received a data error response
        if isinstance(result, dict) and "data_error" in result:
            logger.warning(f"Insufficient data found. Resume IDs attempted: {result.get('resume_ids', [])}")
            return JSONResponse(content={
                "data_error": result["data_error"],
                "error_code":420,
                "resume_ids": result.get("resume_ids", [])
            })

        final_result = update_resume_sections(resume_dict, result)
        urls = generate_and_upload_resume(final_result)

        # Save resume to MongoDB with user_id
        try:
            resume_doc = {
                "resume_id": str(uuid4()),
                "user_id": current_user.get("_id") or current_user.get("clerk_id"),
                "clerk_id": current_user.get("clerk_id"),
                "job_description": job_description,
                "related_jobs": parsed_related_jobs,
                "resume_data": final_result,
                "gcs_url": urls.get("gcs_url"),
                "local_file": urls.get("local_file"),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "status": "generated"
            }
            
            resumes_collection = mongodb_manager.db["user_resumes"]
            insert_result = resumes_collection.insert_one(resume_doc)
            logger.info(f"Saved resume to MongoDB: resume_id={resume_doc['resume_id']}, user_id={resume_doc['user_id']}")
            
        except Exception as e:
            logger.error(f"Error saving resume to MongoDB: {e}")
            # Don't fail the request if saving fails, just log it

        # Cleanup the generated local file
        if "local_file" in urls:
            local_resume_file = urls["local_file"]
            if os.path.exists(local_resume_file):
                os.remove(local_resume_file)
                logger.info(f"Cleaned up generated resume file: {local_resume_file}")

        return JSONResponse(content=urls)

    except Exception as e:
        logger.error(f"Error generating resume: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/v1/get_job_roles")
async def get_job_roles_endpoint(data: List[str] = Depends(get_unique_job_roles)):
    return {"job_roles": data}