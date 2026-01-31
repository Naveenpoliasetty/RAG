from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse
from src.resume_chat_editor.chat_service import ResumeChatService
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
chat_service = ResumeChatService()

@router.post("/edit_resume_chat")
async def edit_resume_chat_endpoint(
    resume_url: str = Form(...),
    user_instruction: str = Form(...)
):
    """
    Endpoint to edit a resume based on user chat instructions.
    Receives GCS URL and user instruction, returns new GCS URL.
    """
    try:
        logger.info(f"Received resume edit request for URL: {resume_url}")
        result = await chat_service.process_resume_edit(resume_url, user_instruction)
        
        if not result or "gcs_url" not in result:
            raise HTTPException(status_code=500, detail="Failed to generate new resume GCS URL.")
            
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Error in edit_resume_chat_endpoint: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
