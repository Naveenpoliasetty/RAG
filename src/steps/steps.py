import glob, json, uuid, logging #noqa
from zenml import step
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

# ---------------------------
# Step 1: Load config
# ---------------------------
@step
def load_config_step(config_path: str = "config.yaml") -> dict:
    import yaml
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    logging.info(f"Config loaded from {config_path}")
    return config

# ---------------------------
# Step 2: Initialize Qdrant (setup pipeline)
# ---------------------------
@step(enable_cache=True)  # run only once if config unchanged
def init_qdrant_step(config: dict) -> tuple:
    qdrant = QdrantClient(config["Qdrant_Client"])
    model = SentenceTransformer(config["Embedder"])
    vector_size = model.get_sentence_embedding_dimension()
    
    # Ensure collections exist
    collections = ["professional_summaries", "technical_skills", "education", "experience"]
    existing = [c.name for c in qdrant.get_collections().collections]
    for name in collections:
        if name not in existing:
            qdrant.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            logging.info(f"Collection '{name}' created.")
        else:
            logging.info(f"Collection '{name}' already exists. Skipping.")
    return qdrant, model

# ---------------------------
# Step 3: Resume ingestion
# ---------------------------
@step
def ingest_resumes_step(
    qdrant: QdrantClient,
    model: SentenceTransformer,
    resume_folder: str = "resumes",
    batch_size: int = 50
):
    section_mapping = {
        "Professional_summary": "professional_summaries",
        "Techinical_skills": "technical_skills",
        "education": "education",
        "experience": "experience"
    }

    collections_points = {col: [] for col in section_mapping.values()}
    resume_files = glob.glob(f"{resume_folder}/*.json")

    for file_path in resume_files:
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            logging.warning(f"Failed to read {file_path}: {e}")
            continue

        resume_id = str(uuid.uuid4())
        domain = data.get("domain", "")
        job_role = data.get("job_role", "")

        for key, collection in section_mapping.items():
            section_data = data.get(key, "")

            if key == "experience" and isinstance(section_data, dict):
                for sec, exp in section_data.items():
                    exp_text = f"{exp.get('job_role','')}. {exp.get('Responisibliiltes','')}".strip()
                    if exp_text:
                        vector = model.encode(exp_text).tolist()
                        collections_points[collection].append({
                            "id": str(uuid.uuid4()),
                            "vector": vector,
                            "payload": {
                                "resume_id": resume_id,
                                "domain": domain,
                                "job_role": job_role,
                                "section": sec,
                                "text": exp_text
                            }
                        })
            else:
                if section_data:
                    vector = model.encode(section_data).tolist()
                    collections_points[collection].append({
                        "id": str(uuid.uuid4()),
                        "vector": vector,
                        "payload": {
                            "resume_id": resume_id,
                            "domain": domain,
                            "job_role": job_role,
                            "section": key,
                            "text": section_data
                        }
                    })

        # Batch upsert
        for collection, points in collections_points.items():
            if len(points) >= batch_size:
                qdrant.upsert(collection_name=collection, points=points)
                collections_points[collection] = []

    # Upsert remaining points
    for collection, points in collections_points.items():
        if points:
            qdrant.upsert(collection_name=collection, points=points)

    logging.info("Resume ingestion completed")