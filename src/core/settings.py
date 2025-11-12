import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from src.utils.logger import get_logger
logger = get_logger("Config")
class Config:
    def __init__(self, config_path: Optional[str] = 'config.yaml'):
        self.base_path = Path(__file__).resolve().parents[2]
        logger.info(f"Base path to find the config file: {self.base_path}")
        self.config_path = self.base_path /"src" / "core" / config_path
        self._config = self._load_config()
        self._override_with_env_vars()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as file:
                logger.info(f"Loading config file: {self.config_path}")
                return yaml.safe_load(file)
        except FileNotFoundError:
            raise Exception(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise Exception(f"Error parsing YAML configuration: {e}")
    
    def _override_with_env_vars(self):
        """Override configuration with environment variables."""
        # MongoDB
        if os.getenv("MONGO_URI"):
            self._config['mongodb']['uri'] = os.getenv("MONGO_URI")
        if os.getenv("MONGO_DB"):
            self._config['mongodb']['database'] = os.getenv("MONGO_DB")
        if os.getenv("MONGO_COLLECTION"):
            self._config['mongodb']['collection'] = os.getenv("MONGO_COLLECTION")
        
        # Qdrant
        if os.getenv("QDRANT_HOST"):
            self._config['qdrant']['host'] = os.getenv("QDRANT_HOST")
        if os.getenv("QDRANT_PORT"):
            self._config['qdrant']['port'] = int(os.getenv("QDRANT_PORT"))
        
        # Embeddings
        if os.getenv("EMBED_MODEL"):
            self._config['embeddings']['model'] = os.getenv("EMBED_MODEL")
        
        # Processing
        if os.getenv("BATCH_SIZE"):
            self._config['processing']['batch_size'] = int(os.getenv("BATCH_SIZE"))
        if os.getenv("BATCH_TIMEOUT"):
            self._config['processing']['batch_timeout'] = float(os.getenv("BATCH_TIMEOUT"))

        if os.getenv("RETRY_LIMIT"):
            self._config['processing']['retry_limit'] = int(os.getenv("RETRY_LIMIT"))
        if os.getenv("RESET_AFTER_MINUTES"):
            self._config['processing']['reset_after_minutes'] = int(os.getenv("RESET_AFTER_MINUTES"))
    
    @property
    def mongodb_uri(self) -> str:
        return self._config['mongodb']['uri']
    
    @property
    def mongodb_database(self) -> str:
        return self._config['mongodb']['database']
    
    @property
    def mongodb_collection(self) -> str:
        return self._config['mongodb']['collection']
    
    @property
    def qdrant_host(self) -> str:
        return self._config['qdrant']['host']
    
    @property
    def qdrant_port(self) -> int:
        return self._config['qdrant']['port']
    
    @property
    def embed_model(self) -> str:
        return self._config['embeddings']['model']
    
    @property
    def embed_batch_size(self) -> int:
        return self._config['embeddings']['batch_size']
    
    @property
    def embed_device(self) -> str:
        return self._config['embeddings']['device']
    
    @property
    def batch_size(self) -> int:
        return self._config['processing']['batch_size']
    
    @property
    def batch_timeout(self) -> float:
        return self._config['processing']['batch_timeout']
    
    
    @property
    def retry_limit(self) -> int:
        return self._config['processing']['retry_limit']
    
    @property
    def reset_after_minutes(self) -> int:
        return self._config['processing']['reset_after_minutes']

    @property
    def poll_interval(self) -> float:
        return self._config['processing'].get('poll_interval', 10.0)
    
    @property
    def collections(self) -> Dict[str, str]:
        return self._config['collections']
    
    @property
    def retry_max_delay(self) -> int:
        return self._config['retry']['max_delay']
    
    @property
    def retry_base_delay(self) -> int:
        return self._config['retry']['base_delay']
    
    @property
    def retry_backoff_factor(self) -> int:
        return self._config['retry']['backoff_factor']
    
    @property
    def log_level(self) -> str:
        return self._config['app']['log_level']
    
    def get(self, key: str, default=None):
        """Get configuration value by dot notation key."""
        keys = key.split('.')
        value = self._config
        for k in keys:
            value = value.get(k, {})
        return value if value != {} else default

# Global configuration instance
config = Config()