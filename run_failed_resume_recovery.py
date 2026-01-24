"""
Failed Resume Recovery Pipeline Runner

Entry point script to run the failed resume recovery pipeline.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_acquisition.failed_resume_pipeline import main

if __name__ == "__main__":
    exit(main())
