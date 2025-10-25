import glob, json, uuid, logging #noqa
from tqdm import tqdm

BATCH_SIZE = 50  # can be configurable

section_mapping = {
    "Professional_summary": "professional_summaries",
    "Techinical_skills": "technical_skills",
    "education": "education",
    "experience": "experience"
}

def run_ingestion(qdrant, model, resume_folder="resumes"):
    logging.info("Starting batched resume ingestion")

    collections_points = {col: [] for col in section_mapping.values()}
    resume_files = glob.glob(f"{resume_folder}/*.json")

    for file_path in tqdm(resume_files, desc="Processing resumes"):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            logging.warning(f"Failed to read JSON file {file_path}: {e}")
            continue

        resume_id = str(uuid.uuid4())
        domain = data.get("domain", "")
        job_role = data.get("job_role", "")

        for key, collection in section_mapping.items():
            section_data = data.get(key, "")

            # Handle experience dict specially
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
            if len(points) >= BATCH_SIZE:
                try:
                    qdrant.upsert(collection_name=collection, points=points)
                    collections_points[collection] = []
                except Exception as e:
                    logging.warning(f"Failed batch upsert for {collection}: {e}")

    # Upsert remaining points
    for collection, points in collections_points.items():
        if points:
            try:
                qdrant.upsert(collection_name=collection, points=points)
            except Exception as e:
                logging.warning(f"Failed final upsert for {collection}: {e}")

    logging.info("Batched resume ingestion completed")
    logging.info("Done")