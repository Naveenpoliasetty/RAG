from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError
from bson import ObjectId  
from src.core.settings import config
from src.utils.logger import get_logger

logger = get_logger("ReliableBatchWorker")

class MongoDBManager:
    def __init__(self):
        self.client = MongoClient(
            config.mongodb_uri,
            serverSelectionTimeoutMS=config.get('mongodb.timeout_ms', 30000)
        )
        self.db = self.client[config.mongodb_database]
        self.collection = self.db[config.mongodb_collection]
        self.batch_size = config.get('mongodb.batch_size', 50)

    def claim_document(self, doc_id: ObjectId) -> Optional[dict]:
        """Atomically claim a document for processing."""
        try:
            return self.collection.find_one_and_update(
                {"_id": doc_id, "qdrant_status": {"$nin": ["processing", "ingested"]}},
                {"$set": {"qdrant_status": "processing", "processing_started": datetime.now(timezone.utc)}},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as e:
            logger.error(f"Error claiming document {doc_id}: {e}")
            return None

    def get_pending_documents_batch(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get a batch of documents pending ingestion."""
        try:
            batch_size = limit or self.batch_size
            return list(self.collection.find(
                {"qdrant_status": {"$nin": ["processing", "ingested"]}},
                limit=batch_size
            ))
        except PyMongoError as e:
            logger.error(f"Error fetching pending documents: {e}")
            return []

    def mark_as_ingested(self, doc_id: ObjectId) -> bool:
        """Mark document as successfully ingested."""
        try:
            result = self.collection.update_one(
                {"_id": doc_id},
                {"$set": {
                    "qdrant_status": "ingested", 
                    "ingested_at": datetime.now(timezone.utc),
                    "last_processed": datetime.now(timezone.utc)
                }},
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Error marking document {doc_id} as ingested: {e}")
            return False

    def mark_batch_ingested(self, doc_ids: List[ObjectId]) -> bool:
        """Mark multiple documents as ingested."""
        try:
            result = self.collection.update_many(
                {"_id": {"$in": doc_ids}},
                {"$set": {
                    "qdrant_status": "ingested",
                    "ingested_at": datetime.now(timezone.utc),
                    "last_processed": datetime.now(timezone.utc)
                }}
            )
            logger.info(f"Marked {result.modified_count} documents as ingested")
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Error marking batch as ingested: {e}")
            return False

    def mark_as_failed(self, doc_id: ObjectId, error: str) -> bool:
        """Mark document as failed."""
        try:
            result = self.collection.update_one(
                {"_id": doc_id},
                {"$set": {
                    "qdrant_status": "failed", 
                    "error": str(error)[:500],  # Truncate long errors
                    "failed_at": datetime.now(timezone.utc),
                    "last_processed": datetime.now(timezone.utc)
                }},
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Error marking document {doc_id} as failed: {e}")
            return False

    def mark_batch_processing(self, doc_ids: List[ObjectId]) -> bool:
        """Atomically mark a batch of documents as processing."""
        try:
            result = self.collection.update_many(
                {"_id": {"$in": doc_ids}, "qdrant_status": {"$nin": ["processing", "ingested"]}},
                {"$set": {"qdrant_status": "processing", "processing_started": datetime.now(timezone.utc)}}
            )
            logger.info(f"Marked {result.modified_count} documents as processing")
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Error marking batch as processing: {e}")
            return False

    def reset_stuck_documents(self, reset_after_minutes: int = 30) -> int:
        """Reset documents stuck in 'processing' longer than specified minutes."""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=reset_after_minutes)
            result = self.collection.update_many(
                {"qdrant_status": "processing", "processing_started": {"$lt": cutoff}},
                {"$set": {
                    "qdrant_status": "pending", 
                    "reset_at": datetime.now(timezone.utc),
                    "stuck_reset": True
                }},
            )
            if result.modified_count:
                logger.warning(f"Reset {result.modified_count} stuck documents to 'pending'.")
            return result.modified_count
        except PyMongoError as e:
            logger.error(f"Error resetting stuck documents: {e}")
            return 0

    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get statistics about document ingestion status."""
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": "$qdrant_status",
                        "count": {"$sum": 1},
                        "latest": {"$max": "$last_processed"}
                    }
                }
            ]
            stats = list(self.collection.aggregate(pipeline))
            
            result = {}
            for stat in stats:
                result[stat["_id"] or "pending"] = {
                    "count": stat["count"],
                    "latest": stat.get("latest")
                }
            
            return result
        except PyMongoError as e:
            logger.error(f"Error getting ingestion stats: {e}")
            return {}

    def health_check(self) -> bool:
        """Check MongoDB connection."""
        try:
            self.client.admin.command('ping')
            return True
        except PyMongoError as e:
            logger.error(f"MongoDB health check failed: {e}")
            return False

    def close(self):
        """Close MongoDB connection."""
        try:
            self.client.close()
            logger.info("MongoDB connection closed")
        except PyMongoError as e:
            logger.warning(f"Error closing MongoDB connection: {e}")