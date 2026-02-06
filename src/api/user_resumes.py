from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from src.middleware.auth import get_current_user
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/user/resumes")
async def get_user_resumes(
    request: Request,
    current_user=Depends(get_current_user),
    limit: Optional[int] = 50,
    skip: Optional[int] = 0
):
    """
    Get all resumes for the authenticated user.
    
    Returns:
        List of resumes with metadata (resume_id, job_description, gcs_url, created_at, etc.)
    """
    try:
        # Get MongoDB manager from app state
        mongodb_manager = request.app.state.mongodb
        resumes_collection = mongodb_manager.db["user_resumes"]
        
        # Get user identifiers
        user_id = current_user.get("_id") or current_user.get("clerk_id")
        clerk_id = current_user.get("clerk_id")
        
        # Query resumes for this user (match either user_id or clerk_id)
        query = {
            "$or": [
                {"user_id": user_id},
                {"clerk_id": clerk_id}
            ]
        }
        
        # Fetch resumes with pagination
        cursor = resumes_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        resumes = list(cursor)
        
        # Convert ObjectId to string and remove sensitive/internal fields
        result_resumes = []
        for resume in resumes:
            resume_doc = {
                "resume_id": resume.get("resume_id"),
                "job_description": resume.get("job_description"),
                "related_jobs": resume.get("related_jobs", []),
                "gcs_url": resume.get("gcs_url"),
                "status": resume.get("status", "generated"),
                "created_at": resume.get("created_at").isoformat() if resume.get("created_at") else None,
                "updated_at": resume.get("updated_at").isoformat() if resume.get("updated_at") else None,
            }
            result_resumes.append(resume_doc)
        
        # Get total count for pagination
        total_count = resumes_collection.count_documents(query)
        
        logger.info(f"Retrieved {len(result_resumes)} resumes for user: clerk_id={clerk_id}")
        
        return JSONResponse(content={
            "resumes": result_resumes,
            "total": total_count,
            "limit": limit,
            "skip": skip,
            "has_more": (skip + len(result_resumes)) < total_count
        })
        
    except Exception as e:
        logger.error(f"Error fetching user resumes: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/user/resumes/{resume_id}")
async def get_user_resume(
    request: Request,
    resume_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get a specific resume by ID for the authenticated user.
    
    Args:
        resume_id: The resume ID to fetch
        
    Returns:
        Complete resume document including resume_data
    """
    try:
        # Get MongoDB manager from app state
        mongodb_manager = request.app.state.mongodb
        resumes_collection = mongodb_manager.db["user_resumes"]
        
        # Get user identifiers
        user_id = current_user.get("_id") or current_user.get("clerk_id")
        clerk_id = current_user.get("clerk_id")
        
        # Find resume that belongs to this user
        resume = resumes_collection.find_one({
            "resume_id": resume_id,
            "$or": [
                {"user_id": user_id},
                {"clerk_id": clerk_id}
            ]
        })
        
        if not resume:
            raise HTTPException(
                status_code=404,
                detail=f"Resume not found or you don't have access to it"
            )
        
        # Convert ObjectId to string and format dates
        resume_doc = {
            "resume_id": resume.get("resume_id"),
            "job_description": resume.get("job_description"),
            "related_jobs": resume.get("related_jobs", []),
            "resume_data": resume.get("resume_data"),
            "gcs_url": resume.get("gcs_url"),
            "status": resume.get("status", "generated"),
            "created_at": resume.get("created_at").isoformat() if resume.get("created_at") else None,
            "updated_at": resume.get("updated_at").isoformat() if resume.get("updated_at") else None,
        }
        
        logger.info(f"Retrieved resume {resume_id} for user: clerk_id={clerk_id}")
        
        return JSONResponse(content=resume_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching resume {resume_id}: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)
