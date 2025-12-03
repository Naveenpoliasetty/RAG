import time
from typing import Dict, Any
from bson import ObjectId
from resume_ingestion.vector_store.qdrant_manager import QdrantManager
from resume_ingestion.database.mongodb_manager import MongoDBManager
from src.utils.logger import get_logger

logger = get_logger("BatchIngestionProcessor")

class BatchIngestionProcessor:
    """
    Processes batches of MongoDB documents and ingests them into Qdrant.
    """
    
    def __init__(self, batch_size: int = 50, max_retries: int = 3):
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.mongo_manager = MongoDBManager()
        self.qdrant_manager = QdrantManager()
        
    def process_single_document(self, document: Dict[str, Any]) -> bool:
        """
        Process a single MongoDB document and ingest into Qdrant.
        Uses resume_id field as the primary identifier.
        """
        # Get resume_id
        resume_id = document.get("resume_id")
        if not resume_id:
            logger.error("Document missing resume_id field")
            return False
        
        try:
            # Convert resume_id to string for Qdrant
            resume_id_str = str(resume_id) if not isinstance(resume_id, str) else resume_id
            
            # Ensure document has resume_id field
            document["resume_id"] = resume_id_str
            
            # Prepare document for Qdrant processing
            processed_doc = self._prepare_document(document)
            
            # Ensure resume_id is consistent
            processed_doc["resume_id"] = resume_id_str
            
            logger.debug(f"Processing document: resume_id={resume_id_str}")
            
            # Prepare points for Qdrant
            collection_points = self.qdrant_manager.prepare_points_for_resume(processed_doc)
            
            if not collection_points:
                logger.warning(f"No collection points generated for document {resume_id_str}")
                self.mongo_manager.mark_as_failed(resume_id_str, "No embeddings generated")
                return False
            
            # Validate that resume_id is consistent in all points
            total_points = sum(len(points) for points in collection_points.values())
            logger.info(f"Generated {total_points} points for resume_id={resume_id_str}")
            
            # Upsert to Qdrant
            self.qdrant_manager.upsert_to_qdrant(collection_points)
            
            # Mark as successful in MongoDB using resume_id
            success = self.mongo_manager.mark_as_ingested(resume_id_str)
            if success:
                logger.info(f"Successfully processed document resume_id={resume_id_str}")
            else:
                logger.warning(f"Document {resume_id_str} processed but couldn't update MongoDB status")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing document {resume_id}: {e}", exc_info=True)
            # Mark as failed using resume_id
            try:
                self.mongo_manager.mark_as_failed(resume_id_str, str(e))
            except Exception as e2:
                logger.error(f"Failed to mark document as failed: {e2}")
            return False
    
    def process_batch(self) -> Dict[str, Any]:
        """
        Process a batch of documents from MongoDB.
        Returns statistics about the batch processing.
        """
        logger.info(f"Starting batch processing with size {self.batch_size}")
        
        # Get pending documents
        documents = self.mongo_manager.get_pending_documents_batch(self.batch_size)
        
        if not documents:
            logger.info("No pending documents found")
            return {"processed": 0, "successful": 0, "failed": 0}
        
        # Extract resume_id from documents
        doc_ids = [doc.get("resume_id") for doc in documents if doc.get("resume_id")]
        logger.info(f"Found {len(documents)} pending documents")
        
        # Mark batch as processing
        if not self.mongo_manager.mark_batch_processing(doc_ids):
            logger.error("Failed to mark batch as processing")
            return {"processed": 0, "successful": 0, "failed": 0}
        
        successful = 0
        failed = 0
        
        # Process each document
        for document in documents:
            if self.process_single_document(document):
                successful += 1
            else:
                failed += 1
        
        logger.info(f"Batch processing complete: {successful} successful, {failed} failed")
        return {
            "processed": len(documents),
            "successful": successful,
            "failed": failed
        }
    
    def continuous_processing(self, interval_seconds: int = 60, max_iterations: int = None):
        """
        Continuously process documents until no more pending documents or max iterations.
        """
        iteration = 0
        total_processed = 0
        total_successful = 0
        
        try:
            while True:
                if max_iterations and iteration >= max_iterations:
                    logger.info(f"Reached maximum iterations ({max_iterations})")
                    break
                
                iteration += 1
                logger.info(f"Starting processing iteration {iteration}")
                
                # Reset stuck documents first
                reset_count = self.mongo_manager.reset_stuck_documents()
                if reset_count > 0:
                    logger.info(f"Reset {reset_count} stuck documents")
                
                # Process batch
                batch_stats = self.process_batch()
                total_processed += batch_stats["processed"]
                total_successful += batch_stats["successful"]
                
                # If no documents were processed, wait before next check
                if batch_stats["processed"] == 0:
                    logger.info(f"No documents to process. Waiting {interval_seconds} seconds...")
                    time.sleep(interval_seconds)
                    continue
                
                # Small delay between batches to prevent overwhelming the system
                time.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("Processing interrupted by user")
        except Exception as e:
            logger.error(f"Unexpected error during continuous processing: {e}")
        finally:
            logger.info(f"Processing completed. Total: {total_processed} processed, {total_successful} successful")
    
    def _prepare_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare MongoDB document for Qdrant processing.
        Ensures resume_id field exists and is a string.
        Also normalizes job_role for consistency.
        """
        # Create a copy to avoid modifying the original
        processed = document.copy()
        
        # Get resume_id
        resume_id = processed.get("resume_id")
        if not resume_id:
            logger.error("Document missing resume_id field")
            raise ValueError("Document must have resume_id field")
        
        # Ensure resume_id is a string
        resume_id_str = str(resume_id)
        processed["resume_id"] = resume_id_str
        
        # Remove _id if present - Qdrant uses resume_id from payload, not _id
        processed.pop("_id", None)
        
        # Normalize job_role using the same function used elsewhere
        from src.data_acquisition.parser import normalize_job_role
        raw_job_role = processed.get("job_role", "").strip()
        if raw_job_role:
            processed["job_role"] = normalize_job_role(raw_job_role)
        else:
            processed["job_role"] = ""
        
        # Ensure required fields exist
        processed.setdefault("category", "")
        processed.setdefault("experiences", [])
        processed.setdefault("professional_summary", [])
        processed.setdefault("technical_skills", [])
        
        return processed
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get overall processing statistics."""
        mongo_stats = self.mongo_manager.get_ingestion_stats()
        qdrant_health = self.qdrant_manager.health_check()
        mongo_health = self.mongo_manager.health_check()
        
        return {
            "mongodb_health": mongo_health,
            "qdrant_health": qdrant_health,
            "ingestion_stats": mongo_stats
        }

    
    def close(self):
        """Clean up resources."""
        try:
            self.mongo_manager.close()
            self.qdrant_manager.close()
            logger.info("Batch processor resources closed")
        except Exception as e:
            logger.error(f"Error closing batch processor: {e}")

# Convenience function for one-time batch processing
def run_batch_ingestion(batch_size: int = 50):
    """Run a single batch ingestion process."""
    processor = BatchIngestionProcessor(batch_size=batch_size)
    try:
        stats = processor.process_batch()
        logger.info(f"Batch ingestion completed: {stats}")
        return stats
    finally:
        processor.close()

# Convenience function for continuous processing
def run_continuous_ingestion(batch_size: int = 50, interval_seconds: int = 60):
    """Run continuous ingestion until interrupted."""
    processor = BatchIngestionProcessor(batch_size=batch_size)
    try:
        processor.continuous_processing(interval_seconds=interval_seconds)
    finally:
        processor.close()