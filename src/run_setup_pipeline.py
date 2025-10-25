# run_setup_pipeline.py
from pipelines.setup_pipeline import qdrant_setup_pipeline

if __name__ == "__main__":
    pipeline = qdrant_setup_pipeline()
    pipeline.run()