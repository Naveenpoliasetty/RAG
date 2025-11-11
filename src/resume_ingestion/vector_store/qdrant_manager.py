import logging
import uuid
import time
import re
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse, ApiException
from resume_ingestion.config.settings import config

logger = logging.getLogger("QdrantManager")


class QdrantError(Exception):
    """Custom exception class for Qdrant operations."""
    pass


def estimate_token_count(text: str) -> int:
    """
    Roughly estimate token count.
    Works well enough for deciding splitting thresholds.
    """
    if not text:
        return 0
    
    # Split on spaces and punctuation as approximate tokenization
    tokens = re.findall(r"\b\w+\b", text)
    return len(tokens)


def needs_splitter(
    text: str,
    model_name: Optional[str] = None,
    embedding_dim: Optional[int] = None,
    safety_margin: float = 0.8
) -> bool:
    """
    Decide whether text should be split based on model token limits.
    """
    text = text.strip()
    if not text:
        return False

    # Define known model token capacities
    model_token_limits = {
        "intfloat/e5-base-v2": 512,
        "sentence-transformers/all-mpnet-base-v2": 512,
        "sentence-transformers/all-MiniLM-L6-v2": 256,
        "e5-large-v2": 512,
        "text-embedding-3-small": 8191,
        "text-embedding-3-large": 8191
    }

    # Get max tokens
    if model_name in model_token_limits:
        max_tokens = model_token_limits[model_name]
    elif embedding_dim == 768:
        max_tokens = 512
    elif embedding_dim == 384:
        max_tokens = 256
    elif embedding_dim == 1536:
        max_tokens = 8191
    else:
        max_tokens = 512  # safe default

    safe_limit = int(max_tokens * safety_margin)
    est_tokens = estimate_token_count(text)

    return est_tokens > safe_limit


class QdrantManager:
    """
    Updated QdrantManager that keeps experiences as cohesive chunks.
    """

    def __init__(self):
        # Lazy import to avoid circular dependency with embeddings module
        from resume_ingestion.vector_store.embeddings import create_embedding_service
        self.embedding_service = create_embedding_service()
        self.collections_mapping = getattr(config, "collections", {})

        if not self.collections_mapping:
            logger.warning("No Qdrant collections mapping found in config.")
            # Default mapping
            self.collections_mapping = {
                "professional_summary": "professional_summaries",
                "technical_skills": "technical_skills", 
                "experiences": "experiences"
            }

        self.client = self._initialize_client()
        self._ensure_collections_exist()

    # ---------------------------------------------------------------------
    # Qdrant Initialization
    # ---------------------------------------------------------------------

    def _initialize_client(self, max_retries: int = 3) -> QdrantClient:
        """Initialize Qdrant client with retry logic."""
        timeout = self._get_config_timeout()

        for attempt in range(max_retries):
            try:
                client = QdrantClient(
                    host=config.qdrant_host,
                    port=config.qdrant_port,
                    timeout=timeout
                )
                client.get_collections()  # Test connection
                logger.info("Successfully connected to Qdrant")
                return client
            except (UnexpectedResponse, ApiException, ConnectionError, TimeoutError) as e:
                logger.warning(f"Qdrant connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    raise QdrantError(f"Failed to connect to Qdrant after {max_retries} attempts: {e}")
                time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Unexpected Qdrant init error: {e}")
                raise QdrantError(f"Unexpected client initialization error: {e}")

    def _get_config_timeout(self) -> int:
        """Safely get timeout from config."""
        if hasattr(config, "qdrant"):
            return getattr(config.qdrant, "timeout", 30)
        if isinstance(config, dict):
            return config.get("qdrant", {}).get("timeout", 30)
        return 30

    def _ensure_collections_exist(self):
        """Ensure all Qdrant collections exist with proper payload indexing."""
        try:
            existing_names = [c.name for c in self.client.get_collections().collections]
        except Exception as e:
            logger.error(f"Failed to retrieve collections list: {e}")
            raise QdrantError(f"Failed to retrieve collections: {e}")

        for key, collection_name in self.collections_mapping.items():
            try:
                if collection_name not in existing_names:
                    self._create_collection_with_payload_schema(collection_name)
                else:
                    logger.info(f"Collection '{collection_name}' already exists.")
                    # Ensure payload schema is set
                    self._ensure_payload_indexing(collection_name)
            except Exception as e:
                logger.error(f"Error with collection '{collection_name}': {e}")
                raise

    def _create_collection_with_payload_schema(self, collection_name: str, max_retries: int = 3):
        """Create a collection with proper payload schema configuration."""
        vector_size = self.embedding_service.get_vector_size()

        for attempt in range(max_retries):
            try:
                self.client.recreate_collection(
                    collection_name=collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=vector_size,
                        distance=qmodels.Distance.COSINE
                    ),
                )
                logger.info(f"🆕 Created Qdrant collection: {collection_name}")
                
                # Configure payload schema after collection creation
                self._configure_payload_schema(collection_name)
                return
                
            except Exception as e:
                logger.warning(f"Collection creation attempt {attempt + 1}/{max_retries} for '{collection_name}' failed: {e}")
                if attempt == max_retries - 1:
                    raise QdrantError(f"Failed to create collection '{collection_name}' after {max_retries} attempts: {e}")
                time.sleep(2 ** attempt)

    def _configure_payload_schema(self, collection_name: str):
        """Configure payload schema for better query performance."""
        try:
            # Define payload schema for indexing
            payload_schema = {
                "resume_id": qmodels.PayloadSchemaType.KEYWORD,
                "section": qmodels.PayloadSchemaType.KEYWORD,
                "domain": qmodels.PayloadSchemaType.KEYWORD,
                "job_role": qmodels.PayloadSchemaType.TEXT,
                "chunk_index": qmodels.PayloadSchemaType.INTEGER,
                "text": qmodels.PayloadSchemaType.TEXT,
            }
            
            # For experiences collection, add additional fields
            if collection_name == "experiences":
                payload_schema.update({
                    "experience_role": qmodels.PayloadSchemaType.TEXT,
                    "company": qmodels.PayloadSchemaType.TEXT,
                    "environment": qmodels.PayloadSchemaType.TEXT,
                    "experience_index": qmodels.PayloadSchemaType.INTEGER,
                })

            # Create payload indexes for better search performance
            for field_name, field_type in payload_schema.items():
                try:
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=field_type
                    )
                except Exception as e:
                    # Index might already exist, which is fine
                    logger.debug(f"Payload index for '{field_name}' might already exist: {e}")
            
            logger.info(f"✅ Configured payload schema for '{collection_name}'")
            
        except Exception as e:
            logger.warning(f"Could not configure payload schema for '{collection_name}': {e}")

    def _ensure_payload_indexing(self, collection_name: str):
        """Ensure payload indexes exist for existing collections."""
        try:
            # Basic payload indexes that should exist
            basic_indexes = ["resume_id", "section", "domain", "job_role"]
            
            for field_name in basic_indexes:
                try:
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=qmodels.PayloadSchemaType.KEYWORD
                    )
                except Exception:
                    # Index might already exist, which is fine
                    pass
                    
        except Exception as e:
            logger.warning(f"Could not ensure payload indexing for '{collection_name}': {e}")

    # ---------------------------------------------------------------------
    # Resume Document Processing (UPDATED - Keep experiences as cohesive chunks)
    # ---------------------------------------------------------------------

    def prepare_points_for_resume(self, doc: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        Convert a structured resume into embedding points with proper payload schema.
        Experiences are kept as cohesive chunks (each experience as one or more chunks).
        """
        if not doc:
            logger.warning("Received empty resume document.")
            return {}

        try:
            resume_id = str(doc.get("_id", uuid.uuid4()))
            domain = doc.get("category", "").lower().strip()
            job_role = doc.get("job_role", "").strip()
            
            if not resume_id:
                logger.warning("Generated empty resume_id")
                return {}
                
        except Exception as e:
            logger.error(f"Error processing document metadata: {e}")
            return {}

        logger.info(f"Processing resume {resume_id} (domain={domain}, role={job_role})")

        collection_points: Dict[str, List[Dict]] = {v: [] for v in self.collections_mapping.values()}

        # Case-insensitive field matching
        doc_lower = {k.lower(): v for k, v in doc.items()}
        
        for section_key, collection_name in self.collections_mapping.items():
            try:
                # Try multiple field name variations
                field_variations = [
                    section_key,
                    section_key.lower(),
                    section_key.replace('_', ' '),
                    section_key.replace(' ', '_')
                ]
                
                section_data = None
                for field_var in field_variations:
                    if field_var in doc:
                        section_data = doc[field_var]
                        break
                    elif field_var in doc_lower:
                        section_data = doc_lower[field_var]
                        break
                
                if section_data is None:
                    logger.debug(f"No data found for section '{section_key}' in resume {resume_id}")
                    continue

                logger.debug(f"Processing section '{section_key}' for collection '{collection_name}'")

                if section_key == "experiences":
                    self._process_experiences_as_chunks(section_data, collection_points, collection_name, resume_id, domain, job_role)
                else:
                    self._process_standard_section(
                        section_data, collection_points, collection_name, 
                        section_key, resume_id, domain, job_role
                    )
                    
            except Exception as e:
                logger.error(f"Error processing section '{section_key}' for resume {resume_id}: {e}")
                continue

        return collection_points

    def _process_experiences_as_chunks(
        self,
        experiences: List[Dict[str, Any]],
        collection_points: Dict[str, List[Dict]],
        collection_name: str,
        resume_id: str,
        domain: str,
        job_role: str
    ):
        """Process each experience as a cohesive chunk (or multiple chunks if very long)."""
        for exp_idx, exp in enumerate(experiences):
            try:
                exp_job_role = exp.get("job_role", "").strip() or job_role
                environment = exp.get("environment", "").strip()
                company = exp.get("company", "").strip()
                responsibilities = exp.get("responsibilities", [])

                if not responsibilities:
                    logger.debug(f"No responsibilities found for {exp_job_role} ({resume_id})")
                    continue

                # Create cohesive experience text
                text_parts = []
                
                # Add role and company context
                if exp_job_role:
                    text_parts.append(f"Role: {exp_job_role}")
                if company:
                    text_parts.append(f"Company: {company}")
                if environment:
                    text_parts.append(f"Environment: {environment}")
                
                # Add all responsibilities as a cohesive block
                responsibilities_text = "\n".join([f"- {resp}" for resp in responsibilities if resp and isinstance(resp, str)])
                if responsibilities_text:
                    text_parts.append(f"Responsibilities:\n{responsibilities_text}")
                
                full_text = "\n".join(text_parts)
                
                if not full_text.strip():
                    continue

                # Let the embedding service decide if splitting is needed
                text_chunks = self.embedding_service.chunk_text(full_text)
                
                for chunk_idx, chunk in enumerate(text_chunks):
                    if not chunk.strip():
                        continue
                        
                    vector = self._encode_text_safely(chunk, resume_id, f"exp-{exp_idx}-{chunk_idx}")
                    if not vector:
                        continue

                    # Create proper payload according to Qdrant schema
                    payload = {
                        "resume_id": resume_id,
                        "section": "experience",
                        "domain": domain,
                        "job_role": job_role,  # Main document job role
                        "experience_role": exp_job_role,  # Specific experience role
                        "company": company,
                        "environment": environment,
                        "chunk_index": chunk_idx,
                        "experience_index": exp_idx,
                        "total_chunks": len(text_chunks),
                        "text": chunk
                    }
                    
                    # Remove empty fields from payload
                    payload = {k: v for k, v in payload.items() if v not in [None, ""]}

                    point_id = str(uuid.uuid4())
                    collection_points[collection_name].append({
                        "id": point_id,
                        "vector": vector,
                        "payload": payload
                    })
                    
                    logger.debug(f"Created experience chunk {chunk_idx+1}/{len(text_chunks)} for '{exp_job_role}'")
                    
            except Exception as e:
                logger.error(f"Error parsing experience {exp_idx} in resume {resume_id}: {e}")
                continue

    def _process_standard_section(
        self,
        data: Any,
        collection_points: Dict[str, List[Dict]],
        collection_name: str,
        section_key: str,
        resume_id: str,
        domain: str,
        job_role: str
    ):
        """Process standard sections with proper payload structure."""
        try:
            if isinstance(data, list):
                # Join list items with spaces for embedding
                text_items = [str(item).strip() for item in data if item and str(item).strip()]
                if not text_items:
                    logger.debug(f"Empty text items for section '{section_key}' in resume {resume_id}")
                    return
                full_text = " ".join(text_items)
            else:
                full_text = str(data).strip() if data else ""
                
            if not full_text:
                logger.debug(f"Empty text for section '{section_key}' in resume {resume_id}")
                return

            # Split text into chunks if needed (let the embedding service decide)
            text_chunks = self.embedding_service.chunk_text(full_text)
            
            for chunk_idx, chunk in enumerate(text_chunks):
                if not chunk.strip():
                    continue
                    
                vector = self._encode_text_safely(chunk, resume_id, f"{section_key}-{chunk_idx}")
                if not vector:
                    continue

                # Create proper payload according to Qdrant schema
                payload = {
                    "resume_id": resume_id,
                    "section": section_key,
                    "domain": domain,
                    "job_role": job_role,
                    "chunk_index": chunk_idx,
                    "total_chunks": len(text_chunks),
                    "text": chunk
                }
                
                point_id = str(uuid.uuid4())
                collection_points[collection_name].append({
                    "id": point_id,
                    "vector": vector,
                    "payload": payload
                })
                
        except Exception as e:
            logger.error(f"Error processing section '{section_key}' for resume {resume_id}: {e}")

    # ---------------------------------------------------------------------
    # Embedding & Validation
    # ---------------------------------------------------------------------

    def _encode_text_safely(self, text: str, resume_id: str, section: str) -> Optional[List[float]]:
        """Safely encode text to vector with error handling."""
        try:
            if not text or not text.strip():
                logger.warning(f"Empty text for {resume_id}:{section}")
                return None
                
            vectors = self.embedding_service.encode_texts([text])
            
            if not vectors or len(vectors) == 0:
                logger.error(f"No vectors returned for {resume_id}:{section}")
                return None
                
            vector = vectors[0]
            
            # Validate vector dimensions
            expected_size = self.embedding_service.get_vector_size()
            if len(vector) != expected_size:
                logger.error(
                    f"Vector dimension mismatch for {resume_id}:{section} - "
                    f"expected {expected_size}, got {len(vector)}"
                )
                return None
                
            return vector
            
        except Exception as e:
            logger.error(f"Embedding failed for {resume_id}:{section}: {e}")
            return None

    # ---------------------------------------------------------------------
    # Upsert Logic
    # ---------------------------------------------------------------------

    def upsert_to_qdrant(self, collection_points: Dict[str, List[Dict]], max_retries: int = 3):
        """Upsert points with proper error handling and batch processing."""
        if not collection_points:
            logger.warning("No points to upsert")
            return

        total_upserted = 0
        batch_size = 100  # Qdrant recommended batch size

        for collection_name, points in collection_points.items():
            if not points:
                logger.debug(f"No points for collection '{collection_name}'")
                continue

            logger.info(f"Upserting {len(points)} points to '{collection_name}'")

            # Process in batches
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                batch_upserted = self._upsert_batch_with_retry(collection_name, batch, max_retries)
                total_upserted += batch_upserted

        logger.info(f"✅ Upsert completed: {total_upserted} total points across all collections")

    def _upsert_batch_with_retry(self, collection_name: str, batch: List[Dict], max_retries: int) -> int:
        """Upsert a single batch with retry logic."""
        point_structs = self._create_point_structs(batch, collection_name)
        if not point_structs:
            return 0

        for attempt in range(max_retries):
            try:
                # Use upsert with wait=True for durability
                result = self.client.upsert(
                    collection_name=collection_name,
                    points=point_structs,
                    wait=True
                )
                
                if result.status == 'completed':
                    logger.debug(f"✅ Batch of {len(point_structs)} points upserted to '{collection_name}'")
                    return len(point_structs)
                else:
                    logger.warning(f"Upsert status not completed: {result.status}")
                    
            except Exception as e:
                logger.warning(f"Upsert attempt {attempt + 1}/{max_retries} failed for '{collection_name}': {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to upsert batch to '{collection_name}' after {max_retries} attempts")
                    return 0
                time.sleep(2 ** attempt)
                
        return 0

    def _create_point_structs(
        self, points: List[Dict], collection_name: str
    ) -> List[qmodels.PointStruct]:
        """Create PointStruct objects with proper Qdrant schema."""
        point_structs = []
        
        for p in points:
            try:
                # Validate required fields
                if not all(k in p for k in ['id', 'vector', 'payload']):
                    logger.warning(f"Missing required fields in point for '{collection_name}'")
                    continue
                    
                if not isinstance(p['vector'], list) or len(p['vector']) != self.embedding_service.get_vector_size():
                    logger.warning(f"Invalid vector in point {p['id']} for '{collection_name}'")
                    continue

                # Create PointStruct with proper typing
                point_struct = qmodels.PointStruct(
                    id=p["id"],
                    vector=p["vector"],
                    payload=p["payload"]
                )
                point_structs.append(point_struct)
                
            except Exception as e:
                logger.error(f"Failed to create PointStruct for point in '{collection_name}': {e}")
                continue
                
        return point_structs

    # ---------------------------------------------------------------------
    # Query and Management Utilities
    # ---------------------------------------------------------------------

    def health_check(self) -> bool:
        """Check Qdrant connection and collection status."""
        try:
            collections = self.client.get_collections()
            logger.info(f"Qdrant health check passed. Collections: {[c.name for c in collections.collections]}")
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False

    def get_collection_info(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """Return detailed collection information."""
        try:
            collection_info = self.client.get_collection(collection_name=collection_name)
            return {
                "points_count": collection_info.points_count,
                "vectors_count": collection_info.vectors_count,
                "status": collection_info.status,
                "vectors_config": str(collection_info.config.params.vectors)
            }
        except Exception as e:
            logger.error(f"Failed to get info for collection '{collection_name}': {e}")
            return None

    def get_payload_sample(self, collection_name: str, limit: int = 5) -> List[Dict]:
        """Get sample payloads from a collection for debugging."""
        try:
            points, _ = self.client.scroll(
                collection_name=collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            return [point.payload for point in points]
        except Exception as e:
            logger.error(f"Failed to get payload sample from '{collection_name}': {e}")
            return []

    def close(self):
        """Close Qdrant connection."""
        try:
            if hasattr(self.client, "close"):
                self.client.close()
                logger.info("🔌 Qdrant client closed.")
        except Exception as e:
            logger.warning(f"Error closing Qdrant client: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()