import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from src.api.webhook_service import WebhookService
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
webhook_service = WebhookService()


@router.post("/user/webhook")
async def clerk_webhook_endpoint(request: Request):
    """
    Clerk webhook endpoint for user events (creation, update, deletion).
    
    Handles:
    - user.created: Create new user in MongoDB
    - user.updated: Update existing user in MongoDB
    - user.deleted: Delete user from MongoDB
    """
    try:
        # Get raw body and headers
        body = await request.body()
        headers = {
            "svix-id": request.headers.get("svix-id"),
            "svix-timestamp": request.headers.get("svix-timestamp"),
            "svix-signature": request.headers.get("svix-signature")
        }
        
        # Verify webhook signature
        try:
            webhook_service.verify_webhook(body, headers)
        except ValueError as e:
            logger.error(f"Webhook verification failed: {e}")
            return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
        
        # Parse webhook payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON payload: {e}")
            return JSONResponse(content={"error": "Invalid JSON payload"}, status_code=400)
        
        # Get MongoDB manager from app state
        mongodb_manager = request.app.state.mongodb
        
        # Get users collection
        users_collection = mongodb_manager.db["users"]
        
        # Process webhook
        result = webhook_service.process_webhook(payload, users_collection)
        
        return JSONResponse(content=result, status_code=200)
        
    except Exception as e:
        logger.error(f"Error in clerk_webhook_endpoint: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)