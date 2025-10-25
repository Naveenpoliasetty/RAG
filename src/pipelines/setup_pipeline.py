from zenml import pipeline
from steps import load_config_step, init_qdrant_step

@pipeline
def qdrant_setup_pipeline():
    config = load_config_step()
    init_qdrant_step(config)  # creates client + collections