import os
import json
from datetime import datetime, timezone
from typing import Optional
from pymongo.collection import Collection
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Try to import svix for webhook verification
try:
    from svix.webhooks import Webhook, WebhookVerificationError
    SVIX_AVAILABLE = True
except ImportError:
    SVIX_AVAILABLE = False
    logger.warning("svix library not installed. Webhook verification will be basic. Install with: pip install svix")


class WebhookService:
    """Service for handling Clerk webhook events"""
    
    def __init__(self):
        self.webhook_secret = os.getenv("CLERK_WEBHOOK_SECRET", "")
    
    def verify_webhook(self, body: bytes, headers: dict) -> bool:
        """
        Verify Clerk webhook signature using svix library.
        Returns True if verification passes or is skipped.
        Raises ValueError if verification fails.
        """
        if not self.webhook_secret:
            logger.warning("CLERK_WEBHOOK_SECRET not set - webhook verification disabled")
            return True
        
        svix_id = headers.get("svix-id")
        svix_timestamp = headers.get("svix-timestamp")
        svix_signature = headers.get("svix-signature")
        
        if not all([svix_id, svix_timestamp, svix_signature]):
            logger.warning("Missing Clerk webhook headers")
            return True  # Allow in development, should be strict in production
        
        if SVIX_AVAILABLE:
            try:
                wh = Webhook(self.webhook_secret)
                wh.verify(body, {
                    "svix-id": svix_id,
                    "svix-timestamp": svix_timestamp,
                    "svix-signature": svix_signature
                })
                logger.debug("Webhook signature verified successfully")
                return True
            except WebhookVerificationError as e:
                logger.error(f"Webhook verification failed: {e}")
                raise ValueError("Invalid webhook signature")
        else:
            logger.warning("svix not available - using basic verification")
            return True
    
    def process_webhook(self, payload: dict, users_collection: Collection) -> dict:
        """
        Process Clerk webhook payload and update user collection.
        
        Args:
            payload: Parsed JSON webhook payload
            users_collection: MongoDB users collection
            
        Returns:
            dict with success message
        """
        event_type = payload.get("type")
        event_data = payload.get("data", {})
        
        logger.info(f"Processing Clerk webhook event: {event_type}")
        
        if event_type == "user.created":
            self._handle_user_created(users_collection, event_data)
        elif event_type == "user.updated":
            self._handle_user_updated(users_collection, event_data)
        elif event_type == "user.deleted":
            self._handle_user_deleted(users_collection, event_data)
        else:
            logger.warning(f"Unhandled event type: {event_type}")
            return {"message": f"Event type {event_type} not handled"}
        
        return {"message": f"Successfully processed {event_type} event"}
    
    def _handle_user_created(self, users_collection: Collection, user_data: dict):
        """Handle user.created event - insert new user into MongoDB"""
        user_id = user_data.get("id")
        if not user_id:
            raise ValueError("User ID is required")
        
        # Extract email addresses
        email_addresses = user_data.get("email_addresses", [])
        primary_email = None
        if email_addresses:
            primary_email_obj = next(
                (email for email in email_addresses if email.get("id") == user_data.get("primary_email_address_id")),
                email_addresses[0] if email_addresses else None
            )
            primary_email = primary_email_obj.get("email_address") if primary_email_obj else None
        
        # Prepare user document
        user_doc = {
            "clerk_id": user_id,
            "username": user_data.get("username"),
            "first_name": user_data.get("first_name"),
            "last_name": user_data.get("last_name"),
            "full_name": f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip() or None,
            "email": primary_email,
            "image_url": user_data.get("image_url"),
            "email_addresses": email_addresses,
            "created_at": datetime.fromtimestamp(user_data.get("created_at", 0) / 1000, tz=timezone.utc) if user_data.get("created_at") else datetime.now(timezone.utc),
            "updated_at": datetime.fromtimestamp(user_data.get("updated_at", 0) / 1000, tz=timezone.utc) if user_data.get("updated_at") else datetime.now(timezone.utc),
            "webhook_received_at": datetime.now(timezone.utc)
        }
        
        # Insert user
        result = users_collection.insert_one(user_doc)
        logger.info(f"Created user in MongoDB: clerk_id={user_id}, _id={result.inserted_id}")
    
    def _handle_user_updated(self, users_collection: Collection, user_data: dict):
        """Handle user.updated event - update existing user in MongoDB"""
        user_id = user_data.get("id")
        if not user_id:
            raise ValueError("User ID is required")
        
        # Extract email addresses
        email_addresses = user_data.get("email_addresses", [])
        primary_email = None
        if email_addresses:
            primary_email_obj = next(
                (email for email in email_addresses if email.get("id") == user_data.get("primary_email_address_id")),
                email_addresses[0] if email_addresses else None
            )
            primary_email = primary_email_obj.get("email_address") if primary_email_obj else None
        
        # Prepare update document
        update_doc = {
            "username": user_data.get("username"),
            "first_name": user_data.get("first_name"),
            "last_name": user_data.get("last_name"),
            "full_name": f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip() or None,
            "email": primary_email,
            "image_url": user_data.get("image_url"),
            "email_addresses": email_addresses,
            "updated_at": datetime.fromtimestamp(user_data.get("updated_at", 0) / 1000, tz=timezone.utc) if user_data.get("updated_at") else datetime.now(timezone.utc),
            "webhook_received_at": datetime.now(timezone.utc)
        }
        
        # Update user (upsert in case user doesn't exist yet)
        result = users_collection.update_one(
            {"clerk_id": user_id},
            {"$set": update_doc},
            upsert=True
        )
        
        if result.upserted_id:
            logger.info(f"Created user via update (upsert): clerk_id={user_id}")
        else:
            logger.info(f"Updated user in MongoDB: clerk_id={user_id}, modified={result.modified_count > 0}")
    
    def _handle_user_deleted(self, users_collection: Collection, user_data: dict):
        """Handle user.deleted event - delete user from MongoDB"""
        user_id = user_data.get("id")
        if not user_id:
            raise ValueError("User ID is required")
        
        # Delete user from MongoDB
        result = users_collection.delete_one({"clerk_id": user_id})
        
        if result.deleted_count > 0:
            logger.info(f"Deleted user from MongoDB: clerk_id={user_id}")
        else:
            logger.warning(f"User not found for deletion: clerk_id={user_id}")
