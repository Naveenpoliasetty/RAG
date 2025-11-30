import uuid
import time
import re
import numpy as np
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse, ApiException
from src.core.settings import config
from src.utils.logger import get_logger

# Import your keyword extractor
from src.utils.keyword_extraction import extract_keywords

logger = get_logger("QdrantManager")


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
    QdrantManager with keyword extraction and matching capabilities.
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
                "keywords": qmodels.PayloadSchemaType.KEYWORD,  # For keyword matching
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
            basic_indexes = ["resume_id", "section", "domain", "job_role", "keywords"]
            
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
    # Keyword Extraction Methods
    # ---------------------------------------------------------------------

    def _extract_keywords_from_text(self, text: str, min_score: float = 0.9) -> List[str]:
        """
        Extract keywords from text using your keyword extractor.
        """
        try:
            if not text or not text.strip():
                return []
                
            keywords = extract_keywords(text, min_score=min_score)
            logger.debug(f"Extracted {len(keywords)} keywords from text")
            return keywords
            
        except Exception as e:
            logger.warning(f"Keyword extraction failed: {e}")
            return []

    def _extract_keywords_from_list(self, items: List[str], min_score: float = 0.9) -> List[str]:
        """
        Extract keywords from a list of items (like skills list).
        """
        try:
            if not items:
                return []
                
            # Join items and extract keywords
            combined_text = " ".join([str(item) for item in items if item])
            return self._extract_keywords_from_text(combined_text, min_score)
            
        except Exception as e:
            logger.warning(f"Keyword extraction from list failed: {e}")
            return []

    # ---------------------------------------------------------------------
    # Resume Document Processing
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
        """Process each experience as a cohesive chunk with keyword extraction."""
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

                # Extract keywords from the experience text
                experience_keywords = self._extract_keywords_from_text(full_text)
                
                # Let the embedding service decide if splitting is needed
                text_chunks = self.embedding_service.chunk_text(full_text)
                
                for chunk_idx, chunk in enumerate(text_chunks):
                    if not chunk.strip():
                        continue
                        
                    vector = self._encode_text_safely(chunk, resume_id, f"exp-{exp_idx}-{chunk_idx}")
                    if not vector:
                        continue

                    # Extract keywords for this specific chunk
                    chunk_keywords = self._extract_keywords_from_text(chunk)
                    # Combine with experience-level keywords for broader context
                    all_keywords = list(set(experience_keywords + chunk_keywords))

                    # Create proper payload according to Qdrant schema WITH KEYWORDS
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
                        "text": chunk,
                        "keywords": all_keywords  # Add extracted keywords
                    }
                    
                    # Remove empty fields from payload
                    payload = {k: v for k, v in payload.items() if v not in [None, ""]}

                    point_id = str(uuid.uuid4())
                    collection_points[collection_name].append({
                        "id": point_id,
                        "vector": vector,
                        "payload": payload
                    })
                    
                    logger.debug(f"Created experience chunk {chunk_idx+1}/{len(text_chunks)} for '{exp_job_role}' with {len(all_keywords)} keywords")
                    
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
        """Process standard sections with proper payload structure and keyword extraction."""
        try:
            if isinstance(data, list):
                # Join list items with spaces for embedding
                text_items = [str(item).strip() for item in data if item and str(item).strip()]
                if not text_items:
                    logger.debug(f"Empty text items for section '{section_key}' in resume {resume_id}")
                    return
                full_text = " ".join(text_items)
                
                # Extract keywords from the list data
                section_keywords = self._extract_keywords_from_list(text_items)
            else:
                full_text = str(data).strip() if data else ""
                # Extract keywords from text
                section_keywords = self._extract_keywords_from_text(full_text)
                
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

                # Extract keywords for this specific chunk
                chunk_keywords = self._extract_keywords_from_text(chunk)
                # Combine with section-level keywords for broader context
                all_keywords = list(set(section_keywords + chunk_keywords))

                # Create proper payload according to Qdrant schema WITH KEYWORDS
                payload = {
                    "resume_id": resume_id,
                    "section": section_key,
                    "domain": domain,
                    "job_role": job_role,
                    "chunk_index": chunk_idx,
                    "total_chunks": len(text_chunks),
                    "text": chunk,
                    "keywords": all_keywords  # Add extracted keywords
                }
                
                point_id = str(uuid.uuid4())
                collection_points[collection_name].append({
                    "id": point_id,
                    "vector": vector,
                    "payload": payload
                })
                
                logger.debug(f"Created {section_key} chunk {chunk_idx+1}/{len(text_chunks)} with {len(all_keywords)} keywords")
                
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
    # Simple Keyword Matching
    # ---------------------------------------------------------------------

    def calculate_keyword_match_percentage(
        self,
        job_description: str,
        resume_ids: List[str]
    ) -> Dict[str, float]:
        """
        Simple keyword matching - calculates what percentage of JD keywords 
        are found in each resume.
        
        Args:
            job_description: Job description text
            resume_ids: List of resume IDs to check
            
        Returns:
            Dictionary mapping resume_id -> match_percentage (0.0 to 1.0)
        """
        # Extract keywords from job description
        jd_keywords = set(self._extract_keywords_from_text(job_description))
        
        if not jd_keywords:
            logger.warning("No keywords extracted from job description")
            return {rid: 0.0 for rid in resume_ids}
        
        logger.info(f"Looking for {len(jd_keywords)} JD keywords: {list(jd_keywords)[:10]}...")
        
        # Get all resume payloads
        resume_payloads = self.fetch_all_payloads_for_resume_ids(resume_ids)
        
        match_results = {}
        
        for resume_id in resume_ids:
            # Extract all keywords from this resume
            resume_keywords = set()
            
            # Get keywords from all sections of this resume
            resume_data = resume_payloads.get(resume_id, {})
            for section_name, payloads in resume_data.items():
                for payload in payloads:
                    keywords = payload.get("keywords", [])
                    resume_keywords.update(keywords)
            
            # Calculate match percentage
            if not jd_keywords:
                match_percentage = 0.0
            else:
                matched_keywords = jd_keywords.intersection(resume_keywords)
                match_percentage = len(matched_keywords) / len(jd_keywords)
            
            match_results[resume_id] = match_percentage
            
            logger.info(f"Resume {resume_id}: {match_percentage:.1%} match "
                       f"({len(matched_keywords)}/{len(jd_keywords)} keywords)")
        
        return match_results

    def get_best_keyword_matches(
        self,
        job_description: str,
        resume_ids: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[str, float]]:
        """
        Get resumes sorted by keyword match percentage.
        
        Args:
            job_description: Job description text
            resume_ids: List of resume IDs to check
            top_k: Number of top matches to return (None for all)
            
        Returns:
            List of (resume_id, match_percentage) sorted by best match
        """
        match_percentages = self.calculate_keyword_match_percentage(job_description, resume_ids)
        
        # Sort by match percentage (descending)
        sorted_matches = sorted(
            match_percentages.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Return top_k if specified
        if top_k is not None:
            return sorted_matches[:top_k]
        
        return sorted_matches

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

    # ----------------------------
    # Resume matching & retrieval
    # ----------------------------

    def _search_collection(self, collection_name: str, vector: List[float], top_k: int = 50, resume_ids_filter: Optional[List[str]] = None) -> List[Dict]:
        """
        Search a collection and return list of results with resume_id and score.
        
        Args:
            collection_name: Name of the collection to search
            vector: Query vector for semantic search
            top_k: Number of top results to return
            resume_ids_filter: Optional list of resume_ids to filter results by
        """
        try:
            # Build filter if resume_ids_filter is provided
            search_filter = None
            if resume_ids_filter:
                search_filter = qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="resume_id",
                            match=qmodels.MatchAny(any=resume_ids_filter)
                        )
                    ]
                )
            
            results = self.client.search(
                collection_name=collection_name,
                query_vector=vector,
                limit=top_k,
                with_payload=True,
                with_vectors=False,
                query_filter=search_filter
            )
        except Exception as e:
            logger.error(f"Search failed on {collection_name}: {e}")
            return []

        out = []
        for r in results:
            payload = r.payload or {}
            resume_id = payload.get("resume_id")
            score = float(r.score) if hasattr(r, "score") else None
            out.append({"resume_id": resume_id, "score": score, "payload": payload})
        return out

    def match_resumes_for_job_description(
        self,
        job_description: str,
        per_collection_top_k: int = 100,
        aggregate_top_k: int = 10,
        weights: Optional[Dict[str, float]] = None,
        score_aggregation: str = "max",
        resume_ids_filter: Optional[List[str]] = None,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> Tuple[List[Tuple[str, float]], Dict[str, Dict[str, Any]]]:
        """
        Hybrid resume matching pipeline combining semantic search and keyword matching.
        
        Args:
            job_description: Job description text to match against
            per_collection_top_k: Number of top results per collection
            aggregate_top_k: Number of top resumes to return after aggregation
            weights: Optional weights for different sections (for semantic scoring)
            score_aggregation: How to aggregate scores ("max" or "mean")
            resume_ids_filter: Optional list of resume_ids to filter search results
            semantic_weight: Weight for semantic similarity score (default 0.7)
            keyword_weight: Weight for keyword match score (default 0.3)
        """
        if weights is None:
            weights = {
                "technical_skills": 0.4,
                "experiences": 0.3,
                "professional_summary": 0.3
            }

        # embed job description
        jd_vecs = self.embedding_service.encode_texts([job_description])
        if not jd_vecs or len(jd_vecs) == 0:
            raise QdrantError("Failed to embed job description")
        jd_vector = jd_vecs[0]

        # map of collection_key -> actual collection name in QdrantManager config
        collection_name_map = self.collections_mapping

        # search each collection
        per_collection_results = {}
        for key, collection_name in collection_name_map.items():
            try:
                per_collection_results[key] = self._search_collection(
                    collection_name, 
                    jd_vector, 
                    top_k=per_collection_top_k,
                    resume_ids_filter=resume_ids_filter
                )
            except Exception as e:
                logger.warning(f"Search error for {collection_name}: {e}")
                per_collection_results[key] = []

        # aggregate scores per resume_id
        resume_signals = defaultdict(lambda: {"summary_scores": [], "skills_scores": [], "experience_scores": [], "raw": {}})
        for key, results in per_collection_results.items():
            for r in results:
                rid = r.get("resume_id")
                if not rid:
                    continue
                score = r.get("score", 0.0) or 0.0
                if key == "professional_summary":
                    resume_signals[rid]["summary_scores"].append(score)
                elif key == "technical_skills":
                    resume_signals[rid]["skills_scores"].append(score)
                elif key == "experiences":
                    resume_signals[rid]["experience_scores"].append(score)
                resume_signals[rid]["raw"].setdefault(key, []).append(r)

        # compute aggregated scalar scores for each resume_id
        aggregated = {}
        for rid, s in resume_signals.items():
            def agg(list_scores):
                if not list_scores:
                    return 0.0
                if score_aggregation == "max":
                    return float(np.max(list_scores))
                return float(np.mean(list_scores))

            summary_score = agg(s["summary_scores"])
            skills_score = agg(s["skills_scores"])
            exp_score = agg(s["experience_scores"])

            semantic_score = (
                weights.get("professional_summary", 0.0) * summary_score +
                weights.get("technical_skills", 0.0) * skills_score +
                weights.get("experiences", 0.0) * exp_score
            )

            aggregated[rid] = {
                "semantic_score": float(semantic_score),
                "summary_score": summary_score,
                "skills_score": skills_score,
                "experience_score": exp_score,
                "raw": s["raw"]
            }

        # Extract all resume IDs that were found
        all_resume_ids = list(aggregated.keys())
        
        # Calculate keyword match scores
        logger.info(f"Calculating keyword matches for {len(all_resume_ids)} resumes...")
        keyword_match_scores = self.calculate_keyword_match_percentage(job_description, all_resume_ids)
        
        # Combine semantic and keyword scores
        for rid in all_resume_ids:
            semantic_score = aggregated[rid]["semantic_score"]
            keyword_score = keyword_match_scores.get(rid, 0.0)
            
            # Hybrid score: weighted combination
            hybrid_score = (semantic_weight * semantic_score) + (keyword_weight * keyword_score)
            
            # Store both scores for debugging/analysis
            aggregated[rid]["keyword_score"] = float(keyword_score)
            aggregated[rid]["score"] = float(hybrid_score)
            
            logger.debug(f"Resume {rid}: semantic={semantic_score:.3f}, keyword={keyword_score:.3f}, hybrid={hybrid_score:.3f}")

        # sort by hybrid score descending
        sorted_resumes = sorted([(rid, v["score"]) for rid, v in aggregated.items()], key=lambda x: x[1], reverse=True)

        # return top-k (or all if less)
        top_resumes = sorted_resumes[:aggregate_top_k]
        top_rids = [r for r, _ in top_resumes]

        return top_resumes, {rid: aggregated[rid] for rid in top_rids}

    def match_resumes_by_section(
        self,
        job_description: str,
        section_key: str,
        top_k: int = 10,
        resume_ids_filter: Optional[List[str]] = None,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[Tuple[str, float]]:
        """
        Hybrid search for a specific section (professional_summary, technical_skills, or experiences).
        
        Args:
            job_description: Job description text
            section_key: Section name ('professional_summary', 'technical_skills', 'experiences')
            top_k: Number of top resumes to return
            resume_ids_filter: Optional list of resume_ids to filter results
            semantic_weight: Weight for semantic similarity (default 0.7)
            keyword_weight: Weight for keyword matching (default 0.3)
            
        Returns:
            List of (resume_id, hybrid_score) tuples sorted by score descending
        """
        if section_key not in self.collections_mapping:
            raise ValueError(f"Invalid section_key: {section_key}. Must be one of {list(self.collections_mapping.keys())}")
        
        collection_name = self.collections_mapping[section_key]
        
        # Embed job description
        jd_vecs = self.embedding_service.encode_texts([job_description])
        if not jd_vecs or len(jd_vecs) == 0:
            raise QdrantError("Failed to embed job description")
        jd_vector = jd_vecs[0]
        
        # Semantic search on this collection only
        search_results = self._search_collection(
            collection_name,
            jd_vector,
            top_k=top_k * 5,  # Get more candidates for keyword re-ranking
            resume_ids_filter=resume_ids_filter
        )
        
        if not search_results:
            logger.warning(f"No results found for section '{section_key}'")
            return []
        
        # Extract unique resume IDs and their semantic scores
        resume_semantic_scores = {}
        for result in search_results:
            rid = result.get("resume_id")
            score = result.get("score", 0.0)
            if rid:
                # Take max score if multiple chunks per resume
                if rid not in resume_semantic_scores or score > resume_semantic_scores[rid]:
                    resume_semantic_scores[rid] = score
        
        resume_ids = list(resume_semantic_scores.keys())
        
        # Extract keywords from job description
        jd_keywords = set(self._extract_keywords_from_text(job_description))
        
        if not jd_keywords:
            logger.warning("No keywords extracted from job description")
            # Return semantic-only results
            sorted_results = sorted(
                resume_semantic_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            return sorted_results[:top_k]
        
        logger.info(f"Extracted {len(jd_keywords)} keywords for section '{section_key}'")
        
        # Calculate keyword matches for this section only
        resume_keyword_scores = {}
        for rid in resume_ids:
            # Fetch payloads for this resume and section
            resume_keywords = set()
            
            flt = qmodels.Filter(
                must=[qmodels.FieldCondition(key="resume_id", match=qmodels.MatchValue(value=rid))]
            )
            
            try:
                points, _ = self.client.scroll(
                    collection_name=collection_name,
                    with_payload=True,
                    with_vectors=False,
                    scroll_filter=flt,
                    limit=1000
                )
                
                for point in points:
                    payload = point.payload or {}
                    keywords = payload.get("keywords", [])
                    resume_keywords.update(keywords)
                
                # Calculate match percentage
                if jd_keywords:
                    matched_keywords = jd_keywords.intersection(resume_keywords)
                    match_percentage = len(matched_keywords) / len(jd_keywords)
                else:
                    match_percentage = 0.0
                
                resume_keyword_scores[rid] = match_percentage
                
            except Exception as e:
                logger.warning(f"Failed to fetch keywords for resume {rid} in section '{section_key}': {e}")
                resume_keyword_scores[rid] = 0.0
        
        # Combine semantic and keyword scores
        hybrid_scores = {}
        for rid in resume_ids:
            semantic_score = resume_semantic_scores.get(rid, 0.0)
            keyword_score = resume_keyword_scores.get(rid, 0.0)
            
            hybrid_score = (semantic_weight * semantic_score) + (keyword_weight * keyword_score)
            hybrid_scores[rid] = hybrid_score
            
            logger.debug(f"Section '{section_key}' - Resume {rid}: semantic={semantic_score:.3f}, keyword={keyword_score:.3f}, hybrid={hybrid_score:.3f}")
        
        # Sort by hybrid score and return top_k
        sorted_results = sorted(
            hybrid_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        logger.info(f"Section '{section_key}': Returning top {top_k} from {len(sorted_results)} candidates")
        return sorted_results[:top_k]
    def fetch_all_payloads_for_resume_ids(self, resume_ids: List[str]) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Fetch all payload entries for given resume_ids across all collections.
        Returns dict: resume_id -> { collection_key: [payloads...] }
        """
        out = {rid: {k: [] for k in self.collections_mapping.keys()} for rid in resume_ids}

        for rid in resume_ids:
            flt = qmodels.Filter(
                must=[qmodels.FieldCondition(key="resume_id", match=qmodels.MatchValue(value=rid))]
            )
            for key, collection_name in self.collections_mapping.items():
                try:
                    points, _ = self.client.scroll(
                        collection_name=collection_name,
                        with_payload=True,
                        with_vectors=False,
                        scroll_filter=flt,
                        limit=1000
                    )
                    for p in points:
                        payload = p.payload or {}
                        out[rid][key].append(payload)
                except Exception as e:
                    logger.warning(f"Failed to fetch payloads for resume_id {rid} from {collection_name}: {e}")
                    continue

        return out

    def get_resume_ids_by_job_roles(self, job_roles: List[str]) -> List[str]:
        """
        Get all unique resume_ids that match any of the given job roles.
        
        Args:
            job_roles: List of job role strings to search for (case-sensitive matching)
            
        Returns:
            List of unique resume_ids that have any of the specified job roles
        """
        if not job_roles:
            logger.warning("Empty job_roles list provided")
            return []
        
        # Clean and validate job roles
        cleaned_job_roles = [role.strip() for role in job_roles if role and role.strip()]
        
        if not cleaned_job_roles:
            logger.warning("No valid job roles after cleaning")
            return []
        
        logger.info(f"Searching for resumes with job roles: {cleaned_job_roles}")
        
        # Use MatchAny to find resumes matching any of the job roles
        # We'll search across all collections and collect unique resume_ids
        resume_ids_set = set()
        
        for key, collection_name in self.collections_mapping.items():
            try:
                # Create filter for job_role matching any of the provided roles
                # Note: MatchAny does exact matching, so job_roles should match stored values
                flt = qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="job_role",
                            match=qmodels.MatchAny(any=cleaned_job_roles)
                        )
                    ]
                )
                
                # Scroll through all matching points
                points, _ = self.client.scroll(
                    collection_name=collection_name,
                    with_payload=True,
                    with_vectors=False,
                    scroll_filter=flt,
                    limit=10000  # Adjust if needed
                )
                
                # Extract unique resume_ids
                for point in points:
                    payload = point.payload or {}
                    resume_id = payload.get("resume_id")
                    if resume_id:
                        resume_ids_set.add(resume_id)
                
                logger.debug(f"Found {len(resume_ids_set)} unique resume_ids from '{collection_name}' collection")
                
            except Exception as e:
                logger.warning(f"Failed to query '{collection_name}' for job roles: {e}")
                continue
        
        resume_ids_list = list(resume_ids_set)
        logger.info(f"Found {len(resume_ids_list)} unique resume_ids matching job roles: {cleaned_job_roles}")
        
        return resume_ids_list

    def fetch_text_data_from_qdrant(
        self,
        resume_ids: List[str],
        section: str
    ):
        """Fetch ALL chunks for given resume_ids directly from Qdrant"""
        output_blocks = []  
        logger.info(f"Starting fetch for resume_ids: {resume_ids}, section: {section}")

        for rid in resume_ids:
            logger.info(f"Processing resume_id: {rid}")
            
            # Fetch full payloads for this resume
            data = self.fetch_all_payloads_for_resume_ids([rid])
            logger.info(f"Raw data fetched: {data}")
            
            if rid not in data:
                logger.warning(f"Resume ID {rid} not found in fetched data")
                output_blocks.append("")
                continue
                
            resume_data = data[rid]
            logger.info(f"Resume data keys: {list(resume_data.keys())}")

            # Choose section chunks
            if section == "summary":
                chunks = resume_data.get("professional_summary", [])
            elif section == "skills":
                chunks = resume_data.get("technical_skills", [])
            elif section == "experience":
                chunks = resume_data.get("experiences", [])
            else:
                raise ValueError(f"Unknown section: {section}")
                
            logger.info(f"Found {len(chunks)} chunks for section '{section}'")

            # Join all chunk text
            full_text = " ".join([c.get("text", "") for c in chunks])
            logger.info(f"Concatenated text length: {len(full_text)}")
            
            output_blocks.append(full_text)

        logger.info(f"Final output blocks: {output_blocks}")
        return output_blocks

    def close(self):
        """Close Qdrant connection."""
        try:
            if hasattr(self.client, "close"):
                self.client.close()
                logger.info("Qdrant client closed.")
        except Exception as e:
            logger.warning(f"Error closing Qdrant client: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()