# setup.py
from setuptools import setup, find_packages

setup(
    name="resume_ingestion",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pymongo",
        "sentence-transformers", 
        "qdrant-client",
        "langchain",
        "pydantic",
    ],
)