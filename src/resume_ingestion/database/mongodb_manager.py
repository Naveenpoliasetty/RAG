from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError
from bson import ObjectId  
from src.core.settings import config
from src.utils.logger import get_logger
import json

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

    def claim_document(self, doc_id) -> Optional[dict]:
        """
        Atomically claim a document for processing.
        Uses resume_id field for querying.
        """
        try:
            return self.collection.find_one_and_update(
                {"resume_id": doc_id, "qdrant_status": {"$nin": ["processing", "ingested"]}},
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

    def mark_as_ingested(self, doc_id) -> bool:
        """
        Mark document as successfully ingested.
        Uses resume_id field for querying.
        """
        try:
            result = self.collection.update_one(
                {"resume_id": doc_id},
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

    def mark_batch_ingested(self, doc_ids: List) -> bool:
        """
        Mark multiple documents as ingested.
        Uses resume_id field for querying.
        """
        try:
            result = self.collection.update_many(
                {"resume_id": {"$in": doc_ids}},
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

    def mark_as_failed(self, doc_id, error: str) -> bool:
        """
        Mark document as failed.
        Uses resume_id field for querying.
        """
        try:
            result = self.collection.update_one(
                {"resume_id": doc_id},
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

    def mark_batch_processing(self, doc_ids: List) -> bool:
        """
        Atomically mark a batch of documents as processing.
        Uses resume_id field for querying.
        """
        try:
            result = self.collection.update_many(
                {"resume_id": {"$in": doc_ids}, "qdrant_status": {"$nin": ["processing", "ingested"]}},
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

    def get_sections_by_resume_ids(
        self, 
        resume_ids: List[str], 
        section_name: str
    ) -> List[Dict[str, Any]]:
        """
        Fetches only the specified section (e.g., professional_summary)
        for a list of resume IDs.

        Args:
            resume_ids: List of resume IDs as strings (from Qdrant)
            section_name: Name of the section to fetch
            
        Returns a list of dicts:
        [
            { "resume_id": "...", "section": [...] or {...} or None },
            ...
        ]
        """
        try:
            # MongoDB accepts both ObjectId and UUID strings directly
            # So we can use the resume_ids as-is
            query_ids = []
            for rid in resume_ids:
                # Convert to string if needed, but keep as-is for MongoDB query
                if isinstance(rid, ObjectId):
                    query_ids.append(rid)
                else:
                    # MongoDB accepts UUID strings directly
                    query_ids.append(rid)
            
            if not query_ids:
                logger.warning(f"No valid IDs found from {len(resume_ids)} resume IDs")
                return []
            
            # Query MongoDB using resume_id field
            query = {"resume_id": {"$in": query_ids}}
            
            # Only query the resume_id + section_name field
            projection = {
                "resume_id": 1,
                section_name: 1
            }

            docs = list(
                self.collection.find(query, projection)
            )

            logger.info(f"Found {len(docs)} documents for {len(query_ids)} requested resume IDs in section '{section_name}'")
            
            # Create a mapping from resume_id to document
            results: List[Dict[str, Any]] = []
            found_ids = set()
            
            for doc in docs:
                doc_resume_id = doc.get("resume_id")
                if not doc_resume_id:
                    logger.warning("Document missing resume_id field, skipping")
                    continue
                found_ids.add(str(doc_resume_id))
                results.append({
                    "resume_id": str(doc_resume_id),
                    section_name: doc.get(section_name, None)
                })
            
            # Log missing documents
            query_id_strs = set(str(qid) for qid in query_ids)
            missing_ids = query_id_strs - found_ids
            if missing_ids:
                logger.warning(f"Missing {len(missing_ids)} documents in MongoDB for section '{section_name}': {list(missing_ids)[:5]}...")
            
            return results

        except Exception as e:
            logger.error(f"Error fetching sections for resumes: {e}", exc_info=True)
            return []

    def get_resume_by_id(self, resume_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the complete resume document by resume_id.
        
        Args:
            resume_id: Resume ID as string
            
        Returns:
            Complete resume document as dict, or None if not found
        """
        try:
            doc = self.collection.find_one({"resume_id": resume_id})
            if doc:
                logger.info(f"Found resume document for resume_id: {resume_id}")
                return doc
            else:
                logger.warning(f"No resume found for resume_id: {resume_id}")
                return None
        except PyMongoError as e:
            logger.error(f"Error fetching resume {resume_id}: {e}")
            return None