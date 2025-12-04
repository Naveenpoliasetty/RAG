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
from src.resume_ingestion.vector_store.embeddings import create_embedding_service

# Import your keyword extractor
from src.utils.keyword_extraction import extract_keywords

logger = get_logger("QdrantManager")


class QdrantError(Exception):
    """Custom exception class for Qdrant operations."""
    pass


class QdrantManager:
    """
    QdrantManager with keyword extraction and matching capabilities.
    """

    def __init__(self):
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
    def _initialize_client(self, max_retries: int = 5) -> QdrantClient:
        """Initialize Qdrant client with retry logic."""
        timeout = self._get_config_timeout()
        
        logger.info(f"Connecting to Qdrant at {config.qdrant_host}:{config.qdrant_port}")

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
            except (UnexpectedResponse, ApiException, ConnectionError, TimeoutError, OSError) as e:
                # OSError catches httpcore.ConnectError and httpx.ConnectError
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

    def _create_collection_with_payload_schema(self, collection_name: str, max_retries: int = 5):
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
            
            logger.info(f" Configured payload schema for '{collection_name}'")
            
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
        
        Ensures resume_id is always stored as a string (converted from ObjectId if needed).
        """
        if not doc:
            logger.warning("Received empty resume document.")
            return {}

        try:
            # Get resume_id field
            resume_id = doc.get("resume_id")
            if resume_id is None:
                resume_id = str(uuid.uuid4())
                logger.warning(f"Document missing resume_id, generated UUID: {resume_id}")
            else:
                # Convert to string (handles ObjectId, str, etc.)
                resume_id = str(resume_id)
            
            # Normalize job_role using the same function used in MongoDB
            from src.data_acquisition.parser import normalize_job_role
            raw_job_role = doc.get("job_role", "").strip()
            job_role = normalize_job_role(raw_job_role) if raw_job_role else ""
            
            domain = doc.get("category", "").lower().strip()
            
            if not resume_id:
                logger.warning("Generated empty resume_id")
                return {}
                
        except Exception as e:
            logger.error(f"Error processing document metadata: {e}", exc_info=True)
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

    def upsert_to_qdrant(self, collection_points: Dict[str, List[Dict]], max_retries: int = 5):
        """Upsert points with proper error handling and batch processing."""
        if not collection_points:
            logger.warning("No points to upsert")
            return

        total_upserted = 0
        total_upserted = 0
        batch_size = config.get("processing.batch_size", 100)

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

        logger.info(f" Upsert completed: {total_upserted} total points across all collections")

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
                    logger.debug(f" Batch of {len(point_structs)} points upserted to '{collection_name}'")
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

    def _check_resume_ids_exist(self, collection_name: str, resume_ids_sample: List[str]) -> bool:
        """
        Check if any of the sample resume IDs exist in the collection.
        
        Args:
            collection_name: Name of the collection to check
            resume_ids_sample: Sample list of resume IDs to check
            
        Returns:
            True if at least one resume ID exists in the collection, False otherwise
        """
        if not resume_ids_sample:
            return False
            
        try:
            # Create filter for the sample resume IDs
            flt = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="resume_id",
                        match=qmodels.MatchAny(any=resume_ids_sample)
                    )
                ]
            )
            
            # Try to scroll with limit 1 to check if any points exist
            points, _ = self.client.scroll(
                collection_name=collection_name,
                with_payload=False,
                with_vectors=False,
                scroll_filter=flt,
                limit=1
            )
            
            found = len(points) > 0
            if found:
                logger.debug(f"At least one resume ID from sample found in collection '{collection_name}'")
            else:
                logger.debug(f"No resume IDs from sample found in collection '{collection_name}'")
            
            return found
            
        except Exception as e:
            logger.error(f"Error checking resume IDs in collection '{collection_name}': {e}")
            return False


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
            
            # Search without score threshold to get all matching results
            # Qdrant by default may filter low-scoring results, so we explicitly set score_threshold=None
            results = self.client.search(
                collection_name=collection_name,
                query_vector=vector,
                limit=top_k,
                with_payload=True,
                with_vectors=False,
                query_filter=search_filter,
                score_threshold=None  # No threshold - get all results even with low scores
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
            # Default weights - distribute evenly if not specified
            num_collections = len(self.collections_mapping)
            default_weight = 1.0 / num_collections if num_collections > 0 else 0.0
            weights = {k: default_weight for k in self.collections_mapping.keys()}
            
            # Apply specific defaults if keys exist
            if "technical_skills" in weights: weights["technical_skills"] = 0.4
            if "experiences" in weights: weights["experiences"] = 0.3
            if "professional_summary" in weights: weights["professional_summary"] = 0.3
            
            # Normalize if we set specific defaults
            total_weight = sum(weights.values())
            if total_weight > 0:
                weights = {k: v / total_weight for k, v in weights.items()}

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

            semantic_score = 0.0
            for key, weight in weights.items():
                if key == "professional_summary":
                    semantic_score += weight * summary_score
                elif key == "technical_skills":
                    semantic_score += weight * skills_score
                elif key == "experiences":
                    semantic_score += weight * exp_score
                else:
                    # Handle custom sections dynamically
                    # For now, we don't have a specific score list for them in resume_signals structure
                    # This would need extending resume_signals to be more dynamic too
                    pass

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
            resume_ids_filter: Optional list of resume_ids to filter results (as strings)
            semantic_weight: Weight for semantic similarity (default 0.7)
            keyword_weight: Weight for keyword matching (default 0.3)
            
        Returns:
            List of (resume_id, hybrid_score) tuples sorted by score descending
        """
        if section_key not in self.collections_mapping:
            raise ValueError(f"Invalid section_key: {section_key}. Must be one of {list(self.collections_mapping.keys())}")
        
        collection_name = self.collections_mapping[section_key]
        
        # Validate and normalize resume_ids_filter
        if resume_ids_filter:
            # Ensure all IDs are strings
            resume_ids_filter = [str(rid) for rid in resume_ids_filter if rid]
            logger.info(f"Filtering section '{section_key}' search to {len(resume_ids_filter)} resume IDs")
            
            # Check if collection has any points with these resume_ids
            if resume_ids_filter:
                sample_check = self._check_resume_ids_exist(collection_name, resume_ids_filter[:10])
                if not sample_check:
                    logger.warning(f"None of the first 10 resume IDs found in collection '{collection_name}'. "
                                 f"This may indicate a mismatch between MongoDB and Qdrant.")
        
        # Embed job description
        jd_vecs = self.embedding_service.encode_texts([job_description])
        if not jd_vecs or len(jd_vecs) == 0:
            raise QdrantError("Failed to embed job description")
        jd_vector = jd_vecs[0]
        
        # Semantic search on this collection only
        # Request more results to ensure we get top_k unique resume IDs
        # (some resumes may have many chunks, so we need a higher multiplier)
        search_limit = max(top_k * 20, 50)  # At least 20x top_k or 50, whichever is higher
        logger.info(f"Section '{section_key}': Requesting {search_limit} search results (top_k={top_k})")
        search_results = self._search_collection(
            collection_name,
            jd_vector,
            top_k=search_limit,
            resume_ids_filter=resume_ids_filter
        )
        
        if not search_results:
            logger.warning(f"No results found for section '{section_key}'")
            if resume_ids_filter:
                logger.warning(f"  Filtered by {len(resume_ids_filter)} resume IDs. "
                             f"Check if these IDs exist in Qdrant collection '{collection_name}'")
            return []
        
        logger.info(f"Section '{section_key}': Found {len(search_results)} search results (requested {search_limit})")
        
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
        logger.info(f"Section '{section_key}': Extracted {len(resume_ids)} unique resume IDs from {len(search_results)} search results")
        
        # If we don't have enough unique resume IDs, try requesting even more results
        if len(resume_ids) < top_k and resume_ids_filter:
            logger.warning(f"Section '{section_key}': Only found {len(resume_ids)} unique resume IDs, need {top_k}. "
                         f"Trying to request more results...")
            # Try requesting even more results (up to the filter size)
            extended_limit = min(len(resume_ids_filter) * 5, 200)  # Request up to 5x filter size or 200
            if extended_limit > search_limit:
                logger.info(f"Section '{section_key}': Requesting {extended_limit} search results (extended)")
                extended_results = self._search_collection(
                    collection_name,
                    jd_vector,
                    top_k=extended_limit,
                    resume_ids_filter=resume_ids_filter
                )
                # Merge results
                for result in extended_results:
                    rid = result.get("resume_id")
                    score = result.get("score", 0.0)
                    if rid:
                        if rid not in resume_semantic_scores or score > resume_semantic_scores[rid]:
                            resume_semantic_scores[rid] = score
                resume_ids = list(resume_semantic_scores.keys())
                logger.info(f"Section '{section_key}': After extended search, extracted {len(resume_ids)} unique resume IDs")
        
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
            job_roles: List of job role strings to search for
            
        Returns:
            List of unique resume_ids that have any of the specified job roles
        """
        if not job_roles:
            logger.warning("Empty job_roles list provided")
            return []
        
        # Import normalize_job_role for consistent normalization
        from src.data_acquisition.parser import normalize_job_role
        
        # Normalize job roles to match how they're stored in Qdrant
        normalized_roles = []
        for role in job_roles:
            if role and role.strip():
                normalized = normalize_job_role(role.strip())
                if normalized:
                    normalized_roles.append(normalized)
        
        # Also include original roles (case-insensitive) for broader matching
        # This handles cases where normalization might differ slightly
        all_search_roles = list(set(normalized_roles + [r.strip().lower() for r in job_roles if r and r.strip()]))
        
        if not all_search_roles:
            logger.warning("No valid job roles after normalization")
            return []
        
        logger.info(f"Searching for resumes with job roles (normalized): {all_search_roles[:5]}...")
        
        # Use MatchAny to find resumes matching any of the job roles
        # We'll search across all collections and collect unique resume_ids
        resume_ids_set = set()
        
        for key, collection_name in self.collections_mapping.items():
            try:
                # Create filter for job_role matching any of the provided roles
                # Use MatchText for case-insensitive matching, or MatchAny for exact
                # Try both approaches to catch all variations
                flt = qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="job_role",
                            match=qmodels.MatchAny(any=all_search_roles)
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
                        # Ensure resume_id is a string
                        resume_ids_set.add(str(resume_id))
                
                logger.debug(f"Found {len(resume_ids_set)} unique resume_ids from '{collection_name}' collection")
                
            except Exception as e:
                logger.warning(f"Failed to query '{collection_name}' for job roles: {e}")
                continue
        
        resume_ids_list = list(resume_ids_set)
        logger.info(f"Found {len(resume_ids_list)} unique resume_ids matching job roles")
        
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


    def _compute_keyword_scores_for_collection(
        self,
        collection_name: str,
        jd_keywords: set,
        resume_ids: List[str],
        max_points_per_resume: int = 1000,
    ) -> Dict[str, float]:
        """
        Compute keyword match scores for a given collection and a list of resume_ids.
        Score = (# of matching keywords) / (# of JD keywords).

        Args:
            collection_name: Qdrant collection name (e.g., summaries, experiences)
            jd_keywords: set of keywords extracted from job description
            resume_ids: list of resume IDs to score
            max_points_per_resume: scroll limit per resume

        Returns:
            Dict[resume_id, keyword_score]
        """
        if not jd_keywords:
            return {rid: 0.0 for rid in resume_ids}
        logger.info(f"Keywords from JD: {jd_keywords}")

        resume_keyword_scores: Dict[str, float] = {}

        for rid in resume_ids:
            # Gather all keywords across chunks for this resume in this collection
            resume_keywords = set()

            flt = qmodels.Filter(
                must=[qmodels.FieldCondition(key="resume_id",
                                            match=qmodels.MatchValue(value=rid))]
            )

            try:
                points, _ = self.client.scroll(
                    collection_name=collection_name,
                    with_payload=True,
                    with_vectors=False,
                    scroll_filter=flt,
                    limit=max_points_per_resume,
                )

                for point in points:
                    payload = point.payload or {}
                    keywords = payload.get("keywords", [])
                    logger.info(f"Keywords for resume {rid}: {keywords}")
                    if isinstance(keywords, list):
                        resume_keywords.update(keywords)

                if jd_keywords:
                    matched = jd_keywords.intersection(resume_keywords)
                    logger.info(f"Matched keywords: {matched}")
                    match_percentage = len(matched) / len(jd_keywords)
                    logger.info(f"Match percentage: {match_percentage}")
                else:
                    match_percentage = 0.0

                resume_keyword_scores[rid] = match_percentage

            except Exception as e:
                logger.warning(
                    f"[Keyword scoring] Failed to fetch keywords for resume {rid} "
                    f"in collection '{collection_name}': {e}"
                )
                resume_keyword_scores[rid] = 0.0

        return resume_keyword_scores
    def match_resumes_keyword_then_semantic(
        self,
        job_description: str,
        resume_ids_filter: Optional[List[str]] = None,
        top_k: int = 3,
    ) -> List[Tuple[str, float]]:
        """
        New pipeline:
        1) Keyword matching on summaries + experiences (within resume_ids_filter).
        2) Merge + sort by keyword score, take unique resume IDs as candidates.
        3) Semantic search on technical_skills, professional_summary, experiences
            but ONLY for those candidate IDs.
        4) Return top_k resumes by final semantic score.

        Args:
            job_description: Raw job description text.
            resume_ids_filter: List of resume_ids (as strings) we care about.
                            If None or empty -> nothing to do, return [].
            top_k: Number of top resumes to return.

        Returns:
            List of (resume_id, final_semantic_score), sorted descending.
        """
        # ---- Guard: need resume_ids to work on ----
        if not resume_ids_filter:
            logger.warning(
                "[Keyword→Semantic] Empty resume_ids_filter provided; "
                "cannot perform restricted search."
            )
            return []

        # Normalize resume IDs to strings
        resume_ids_filter = [str(rid) for rid in resume_ids_filter if rid]
        if not resume_ids_filter:
            logger.warning(
                "[Keyword→Semantic] resume_ids_filter became empty after normalization."
            )
            return []

        logger.info(
            f"[Keyword→Semantic] Starting pipeline for {len(resume_ids_filter)} "
            f"candidate resumes (top_k={top_k})"
        )

        # ---- Step 1: Extract JD keywords ----
        jd_keywords = set(self._extract_keywords_from_text(job_description))
        if not jd_keywords:
            logger.warning(
                "[Keyword→Semantic] No keywords extracted from job description. "
                "Falling back to semantic-only search on filtered resumes."
            )
            # Directly fall back to semantic-only search over 3 sections
            return self._semantic_only_on_filtered_resumes(
                job_description,
                resume_ids_filter,
                top_k=top_k,
            )

        logger.info(f"[Keyword→Semantic] Extracted {len(jd_keywords)} JD keywords")

        # ---- Identify collection names for summary and experiences ----
        summary_collection = self.collections_mapping.get("professional_summary")
        experiences_collection = self.collections_mapping.get("experiences")

        if not summary_collection or not experiences_collection:
            raise ValueError(
                "collections_mapping must define 'professional_summary' and 'experiences' "
                "for this pipeline to work."
            )

        # ---- Step 2: Keyword scores on summaries ----
        logger.info(
            "[Keyword→Semantic] Computing keyword scores for professional_summary collection"
        )
        summary_keyword_scores = self._compute_keyword_scores_for_collection(
            collection_name=summary_collection,
            jd_keywords=jd_keywords,
            resume_ids=resume_ids_filter,
        )

        # ---- Step 3: Keyword scores on experiences ----
        logger.info(
            "[Keyword→Semantic] Computing keyword scores for experiences collection"
        )
        experiences_keyword_scores = self._compute_keyword_scores_for_collection(
            collection_name=experiences_collection,
            jd_keywords=jd_keywords,
            resume_ids=resume_ids_filter,
        )

        # ---- Step 4: Merge & sort candidates by keyword score ----
        # We combine scores from summary + experiences; if a resume appears in both,
        # we take the max keyword score among the two (you could also use average/sum).
        combined_keyword_scores: Dict[str, float] = defaultdict(float)

        for rid, score in summary_keyword_scores.items():
            if score > combined_keyword_scores[rid]:
                combined_keyword_scores[rid] = score

        for rid, score in experiences_keyword_scores.items():
            if score > combined_keyword_scores[rid]:
                combined_keyword_scores[rid] = score

        if not combined_keyword_scores:
            logger.warning(
                "[Keyword→Semantic] No keyword scores computed; "
                "falling back to semantic-only search on filtered resumes."
            )
            return self._semantic_only_on_filtered_resumes(
                job_description,
                resume_ids_filter,
                top_k=top_k,
            )

        # Sort by keyword score, descending
        sorted_by_keyword = sorted(
            combined_keyword_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Unique union of IDs is just keys in combined_keyword_scores; we also keep ordering.
        candidate_resume_ids = [rid for rid, _ in sorted_by_keyword]
        logger.info(
            f"[Keyword→Semantic] Candidate set after keyword phase: "
            f"{len(candidate_resume_ids)} resumes"
        )

        # Optional: You can cap candidate size before semantic to control cost.
        # For example, keep only top N by keyword:
        # candidate_cutoff = max(top_k * 10, 50)
        # candidate_resume_ids = candidate_resume_ids[:candidate_cutoff]

        # ---- Step 5: Embed job description once ----
        jd_vecs = self.embedding_service.encode_texts([job_description])
        if not jd_vecs or len(jd_vecs) == 0:
            raise QdrantError("[Keyword→Semantic] Failed to embed job description")
        jd_vector = jd_vecs[0]

        # ---- Step 6: Semantic search across 3 sections, restricted to candidate IDs ----
        # We'll aggregate semantic scores per resume across:
        #   - technical_skills
        #   - professional_summary
        #   - experiences
        sections_for_semantic = ["technical_skills", "professional_summary", "experiences"]

        semantic_scores: Dict[str, float] = defaultdict(float)

        for section_key in sections_for_semantic:
            collection_name = self.collections_mapping.get(section_key)
            if not collection_name:
                logger.warning(
                    f"[Keyword→Semantic] Section '{section_key}' not in collections_mapping; "
                    f"skipping."
                )
                continue

            # Decide how many results to request per collection
            search_limit = max(top_k * 20, len(candidate_resume_ids) * 5, 50)
            logger.info(
                f"[Keyword→Semantic] Semantic search on section '{section_key}' "
                f"(collection={collection_name}) with limit={search_limit}"
            )

            section_results = self._search_collection(
            collection_name=collection_name,
            vector=jd_vector,
            top_k=search_limit,
            resume_ids_filter=candidate_resume_ids,
        )

            if not section_results:
                logger.warning(
                    f"[Keyword→Semantic] No semantic results for section '{section_key}'"
                )
                continue

            for result in section_results:
                rid = result.get("resume_id")
                score = result.get("score", 0.0)
                if not rid:
                    continue

                # We keep the max semantic score per resume across *all* sections
                if score > semantic_scores[rid]:
                    semantic_scores[rid] = score

        if not semantic_scores:
            logger.warning(
                "[Keyword→Semantic] No semantic scores computed for candidates; "
                "returning empty result."
            )
            return []

        # ---- Step 7: Final ranking by semantic score only ----
        final_sorted = sorted(
            semantic_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        logger.info(
            f"[Keyword→Semantic] Returning top {top_k} resumes from "
            f"{len(final_sorted)} semantic candidates"
        )

        return final_sorted[:top_k]

    def _semantic_only_on_filtered_resumes(
        self,
        job_description: str,
        resume_ids_filter: List[str],
        top_k: int = 3,
    ) -> List[Tuple[str, float]]:
        """
        Fallback: semantic-only search across technical_skills, professional_summary,
        and experiences, restricted to the given resume_ids_filter.
        """
        if not resume_ids_filter:
            return []

        jd_vecs = self.embedding_service.encode_texts([job_description])
        if not jd_vecs or len(jd_vecs) == 0:
            raise QdrantError("[Semantic-only] Failed to embed job description")
        jd_vector = jd_vecs[0]

        sections_for_semantic = ["technical_skills", "professional_summary", "experiences"]
        semantic_scores: Dict[str, float] = defaultdict(float)

        for section_key in sections_for_semantic:
            collection_name = self.collections_mapping.get(section_key)
            if not collection_name:
                logger.warning(
                    f"[Semantic-only] Section '{section_key}' not in collections_mapping; "
                    f"skipping."
                )
                continue

            search_limit = max(top_k * 20, len(resume_ids_filter) * 5, 50)

            section_results = self._search_collection(
                collection_name=collection_name,
                query_vector=jd_vector,
                top_k=search_limit,
                resume_ids_filter=resume_ids_filter,
            )

            if not section_results:
                continue

            for result in section_results:
                rid = result.get("resume_id")
                score = result.get("score", 0.0)
                if not rid:
                    continue

                if score > semantic_scores[rid]:
                    semantic_scores[rid] = score

        if not semantic_scores:
            return []

        final_sorted = sorted(
            semantic_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return final_sorted[:top_k]