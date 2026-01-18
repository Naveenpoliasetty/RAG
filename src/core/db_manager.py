"""
Centralized database connection manager with singleton pattern.
Ensures MongoDB and Qdrant connections are created once and reused.
"""
from typing import Optional
from src.utils.logger import get_logger
from src.resume_ingestion.database.mongodb_manager import MongoDBManager
from src.resume_ingestion.vector_store.qdrant_manager import QdrantManager

logger = get_logger(__name__)

# Singleton instances
_mongodb_manager: Optional['MongoDBManager'] = None
_qdrant_manager: Optional['QdrantManager'] = None


def get_mongodb_manager():
    """Get or create singleton MongoDB manager instance."""
    global _mongodb_manager
    if _mongodb_manager is None:
        logger.info("Initializing MongoDB connection...")
        _mongodb_manager = MongoDBManager()
        logger.info(" MongoDB connection established")
    return _mongodb_manager


def get_qdrant_manager():
    """Get or create singleton Qdrant manager instance."""
    global _qdrant_manager
    if _qdrant_manager is None:
        logger.info("Initializing Qdrant connection...")
        _qdrant_manager = QdrantManager()
        logger.info(" Qdrant connection established")
    return _qdrant_manager


def close_connections():
    """Close all database connections gracefully."""
    global _mongodb_manager, _qdrant_manager
    
    if _mongodb_manager is not None:
        try:
            _mongodb_manager.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.warning(f"Error closing MongoDB: {e}")
        _mongodb_manager = None
    
    if _qdrant_manager is not None:
        try:
            # Qdrant client doesn't need explicit close, but we can reset it
            _qdrant_manager = None
            logger.info("Qdrant connection released")
        except Exception as e:
            logger.warning(f"Error releasing Qdrant: {e}")


async def initialize_connections():
    """Initialize all database connections at startup."""
    logger.info("Initializing database connections...")
    
    # Initialize both managers (will create singleton instances)
    get_mongodb_manager()
    get_qdrant_manager()
    
    logger.info(" All database connections initialized")
