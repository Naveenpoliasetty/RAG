import yaml, logging #noqa
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer
import uuid

# ---------------------------
# Logging setup
# ---------------------------
logging.basicConfig(
    filename="pipeline.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------------------------
# Load YAML Config
# ---------------------------
def load_config(path="config.yaml"):
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        raise

# ---------------------------
# Qdrant init
# ---------------------------
def init_qdrant(config):
    try:
        client = QdrantClient(config["Qdrant_Client"])
        logging.info("Connected to Qdrant successfully.")
        return client
    except Exception as e:
        logging.error(f"Failed to connect to Qdrant: {e}")
        raise

# ---------------------------
# Embedder init
# ---------------------------
def init_embedder(config):
    try:
        model = SentenceTransformer(config["Embedder"])
        dim = model.get_sentence_embedding_dimension()
        logging.info(f"Loaded embedder: {config['Embedder']} (dim={dim})")
        return model, dim
    except Exception as e:
        logging.error(f"Failed to load embedder: {e}")
        raise

# ---------------------------
# Collection management
# ---------------------------
def create_collections(client, collection_names, vector_size):
    try:
        existing = [c.name for c in client.get_collections().collections]
    except Exception as e:
        logging.error(f"Failed to fetch existing collections: {e}")
        existing = []

    for name in collection_names:
        if name not in existing:
            try:
                client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
                )
                logging.info(f"Collection '{name}' created.")
            except Exception as e:
                logging.error(f"Failed to create collection '{name}': {e}")
        else:
            logging.info(f"Collection '{name}' already exists. Skipping.")

# ---------------------------
# Upsert helper
# ---------------------------
def upsert_point(client, collection, vector, payload):
    try:
        point = PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload)
        client.upsert(collection, points=[point])
    except Exception as e:
        logging.warning(f"Failed to upsert point into {collection}: {e}")