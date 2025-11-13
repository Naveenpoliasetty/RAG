from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.core.settings import config
from typing import List, Optional
from resume_ingestion.vector_store.qdrant_manager import needs_splitter
from src.utils.logger import get_logger

logger = get_logger("ReliableBatchWorker")

class EmbeddingService:
    def __init__(self, model_name: Optional[str] = None, chunk_size: int = 1000, chunk_overlap: int = 150):
        # Get model name from config if not provided
        if model_name is None:
            model_name = self._get_model_from_config()
        
        logger.info(f"Loading embedding model: {model_name}")
        
        try:
            self.model = SentenceTransformer(model_name)
            logger.info(f"Successfully loaded embedding model: {model_name}")
            logger.info(f"Model dimension: {self.get_vector_size()}")
        except Exception as e:
            logger.error(f"Failed to load embedding model '{model_name}': {e}")
            raise
        
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""]
        )

    def _get_model_from_config(self) -> str:
        """Extract model name from config with fallback defaults."""
        # Try different possible config locations using the Config class properties
        try:
            # First try the direct embedding model property
            return config.embed_model
        except (KeyError, AttributeError):
            pass
        
        # Try the flexible get method with dot notation
        model = config.get('embeddings.model')
        if model:
            return model
        
        # Fallback to a reliable default model
        logger.warning("No embedding model found in config, using default: 'sentence-transformers/all-MiniLM-L6-v2'")
        return "sentence-transformers/all-MiniLM-L6-v2"

    def get_vector_size(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def encode_texts(self, texts: List[str]) -> List[List[float]]:
        """Encode multiple texts with error handling."""
        if not texts:
            return []
        
        try:
            # Use the model's encode method which handles batching efficiently
            embeddings = self.model.encode(texts, convert_to_tensor=False)
            return embeddings.tolist() if hasattr(embeddings, 'tolist') else embeddings
        except Exception as e:
            logger.error(f"Error encoding texts: {e}")
            raise

    def chunk_text(self, text: str) -> List[str]:
        """Return list of chunks. Skip splitting if short enough."""
        text = text.strip()
        if not text:
            return []

        # Use token-based decision for splitting
        if not needs_splitter(text, model_name=self._get_model_from_config(), embedding_dim=self.get_vector_size()):
            return [text]

        # Otherwise, perform recursive splitting
        try:
            chunks = self.splitter.split_text(text)
            logger.debug(f"Split text into {len(chunks)} chunks")
            return chunks
        except Exception as e:
            logger.error(f"Error during text splitting: {e}")
            return [text]  # Fallback to original text

    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "model_name": self._get_model_from_config(),
            "vector_size": self.get_vector_size(),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap
        }

# Convenience function to create embedding service
def create_embedding_service() -> EmbeddingService:
    """Factory function to create EmbeddingService using config."""
    return EmbeddingService()