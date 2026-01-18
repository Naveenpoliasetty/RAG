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
