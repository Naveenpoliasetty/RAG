from zenml import pipeline
from steps.steps import load_config_step, init_qdrant_step, ingest_resumes_step

@pipeline
def resume_ingestion_pipeline(
    resume_folder: str = "resumes",
    batch_size: int = 50
):
    config = load_config_step()
    qdrant, model = init_qdrant_step(config)  # uses cache; won't rerun if already initialized
    ingest_resumes_step(qdrant=qdrant, model=model, resume_folder=resume_folder, batch_size=batch_size)