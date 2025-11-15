# src/utils/logger.py
import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

class ProjectLogger:
    def __init__(self, default_pipeline="app"):
        self.base_path = Path(__file__).resolve().parents[2]
        self.default_pipeline = default_pipeline
        self.setup_logging()
    
    def setup_logging(self, pipeline_name=None):
        """Enhanced centralized logging configuration."""
        
        if pipeline_name is None:
            pipeline_name = self.default_pipeline
            
        LOG_DIR = self.base_path / "logs"
        LOG_DIR.mkdir(exist_ok=True)
        
        # Get current date for filename
        current_date = datetime.now().strftime("%Y%m%d")
        
        # Clear existing handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        # Formatters
        detailed_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-25s | %(funcName)-20s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        simple_formatter = logging.Formatter(
            "%(levelname)-8s | %(name)-25s | %(message)s"
        )
        
        # Pipeline-specific file handler WITH DATE
        file_handler = RotatingFileHandler(
            LOG_DIR / f"{pipeline_name}_{current_date}.log",  # Add date to filename
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(detailed_formatter)
        
        # Error file handler WITH DATE
        error_handler = RotatingFileHandler(
            LOG_DIR / f"errors_{current_date}.log",  # Add date to error file
            maxBytes=5*1024*1024,
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        
        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            handlers=[file_handler, error_handler, console_handler],
            force=True
        )
        
        # Reduce noise from external libraries
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("selenium").setLevel(logging.WARNING)
        
        logger = logging.getLogger(__name__)
        logger.info(f"🚀 Logging configured for pipeline: {pipeline_name}")
    
    def get_logger(self, name, pipeline_name=None):
        """Get a logger instance, optionally for specific pipeline."""
        if pipeline_name and pipeline_name != self.default_pipeline:
            self.setup_logging(pipeline_name)
        return logging.getLogger(name)

# Create default instance
project_logger = ProjectLogger()

# Convenience functions
def get_logger(name):
    return project_logger.get_logger(name)

def get_pipeline_logger(name, pipeline_name):
    return project_logger.get_logger(name, pipeline_name)

# Initialize when imported
get_logger(__name__).info("✅ Logger module loaded")