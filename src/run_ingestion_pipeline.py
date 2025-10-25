from pipelines.ingestion_pipeline import resume_ingestion_pipeline

if __name__ == "__main__":
    pipeline = resume_ingestion_pipeline(resume_folder="resumes", batch_size=50)
    pipeline.run()