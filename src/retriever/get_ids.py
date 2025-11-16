from typing import List
from bson import ObjectId
from pymongo.errors import PyMongoError
from src.utils.logger import get_logger
from src.resume_ingestion.database.mongodb_manager import MongoDBManager

logger = get_logger("DataRetrieverPipeline")

class DataRetrieverPipeline:
    def __init__(self):
        self.mongo_manager = MongoDBManager()
    
    def get_document_ids_by_job_roles(self, job_roles: List[str]) -> List[ObjectId]:
        """
        Retrieve document IDs for given job roles.
        
        Args:
            job_roles: List of job roles to filter by
            
        Returns:
            List of document ObjectIds
        """
        try:
            # Simple query - just get IDs for the job roles
            documents = list(self.mongo_manager.collection.find(
                {"job_role": {"$in": job_roles}},
                {"_id": 1}  # Only return the _id field
            ))
            
            # Extract just the IDs
            document_ids = [doc["_id"] for doc in documents]
            
            logger.info(f"Retrieved {len(document_ids)} document IDs for job roles: {job_roles}")
            return document_ids
            
        except PyMongoError as e:
            logger.error(f"Error retrieving document IDs for job roles {job_roles}: {e}")
            return []

        
if __name__ == "__main__":
    retriever = DataRetrieverPipeline()
    job_roles = ["Sap Modular"]
    document_ids = retriever.get_document_ids_by_job_roles(job_roles)
    print(document_ids)