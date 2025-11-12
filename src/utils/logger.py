# src/utils/logger.py
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

class ProjectLogger:
    def __init__(self):
        self.base_path = Path(__file__).resolve().parents[2]
        self.setup_logging()
    
    def setup_logging(self):
        """Enhanced centralized logging configuration."""
        
        LOG_DIR = self.base_path / "logs"
        LOG_DIR.mkdir(exist_ok=True)
        
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
        
        # Handlers
        # Rotating file handler (max 10MB per file, keep 5 backup files)
        file_handler = RotatingFileHandler(
            LOG_DIR / "scrape_pipeline.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(detailed_formatter)
        
        # Error file handler
        error_handler = RotatingFileHandler(
            LOG_DIR / "errors.log",
            maxBytes=5*1024*1024,  # 5MB
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
        logger.info("🚀 Enhanced centralized logging configured")
    
    def get_logger(self, name):
        """Get a logger instance."""
        return logging.getLogger(name)

# Create singleton instance
project_logger = ProjectLogger()

# Convenience function
def get_logger(name):
    return project_logger.get_logger(name)

# Initialize when imported
get_logger(__name__).info("✅ Logger module loaded")