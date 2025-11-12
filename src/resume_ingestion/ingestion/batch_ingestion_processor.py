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
        """
        doc_id = document.get("_id")
        if not doc_id:
            logger.error("Document missing _id field")
            return False
        
        try:
            # Convert ObjectId to string for Qdrant
            processed_doc = self._prepare_document(document)
            
            # Prepare points for Qdrant
            collection_points = self.qdrant_manager.prepare_points_for_resume(processed_doc)
            
            if not collection_points:
                logger.warning(f"No collection points generated for document {doc_id}")
                self.mongo_manager.mark_as_failed(doc_id, "No embeddings generated")
                return False
            
            # Upsert to Qdrant
            self.qdrant_manager.upsert_to_qdrant(collection_points)
            
            # Mark as successful in MongoDB
            success = self.mongo_manager.mark_as_ingested(doc_id)
            if success:
                logger.info(f"Successfully processed document {doc_id}")
            else:
                logger.warning(f"Document {doc_id} processed but couldn't update MongoDB status")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}")
            self.mongo_manager.mark_as_failed(doc_id, str(e))
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
        
        doc_ids = [doc["_id"] for doc in documents]
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
        Converts ObjectId to string and ensures required fields.
        """
        # Create a copy to avoid modifying the original
        processed = document.copy()
        
        # Convert ObjectId to string
        if "_id" in processed and isinstance(processed["_id"], ObjectId):
            processed["_id"] = str(processed["_id"])
        
        # Ensure required fields exist
        processed.setdefault("domain", "")
        processed.setdefault("job_role", "")
        processed.setdefault("experiences", [])
        
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