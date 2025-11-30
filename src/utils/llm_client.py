"""
Utility module for creating OpenAI-compatible clients for RunPod vLLM servers.
"""
import os
import yaml
from pathlib import Path
from openai import OpenAI
from typing import Optional
from dotenv import load_dotenv
from src.utils.logger import get_logger

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)


def load_llm_config() -> dict:
    """Load LLM configuration from config.yaml"""
    # Path: src/utils/llm_client.py -> src/core/config.yaml
    config_path = Path(__file__).parent.parent / "core" / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("llm_config", {})


def get_openai_client() -> OpenAI:
    """
    Create OpenAI client configured for RunPod vLLM server.
    
    RunPod vLLM servers expose OpenAI-compatible endpoints.
    Get your endpoint URL from RunPod dashboard -> Your Pod -> Endpoints
    
    The endpoint should be in format: https://<pod-id>-<port>.proxy.runpod.net/v1
    """
    llm_config = load_llm_config()
    
    # Get base_url: prioritize environment variable (.env file), then config.yaml
    base_url = os.getenv("RUNPOD_BASE_URL") or llm_config.get("base_url")
    
    # Get API key: prioritize environment variables (.env file), then config.yaml
    # Priority: RUNPOD_API_KEY > OPENAI_API_KEY > config.yaml api_key
    api_key = (
        os.getenv("RUNPOD_API_KEY") 
        or os.getenv("OPENAI_API_KEY")
        or llm_config.get("api_key")
        or "dummy-key"  # Fallback to prevent errors, but will likely fail auth
    )
    
    # Log where configuration is coming from for debugging
    if os.getenv("RUNPOD_BASE_URL"):
        logger.debug("Using base_url from RUNPOD_BASE_URL environment variable")
    elif llm_config.get("base_url"):
        logger.debug("Using base_url from config.yaml")
    
    if os.getenv("RUNPOD_API_KEY"):
        logger.debug("Using API key from RUNPOD_API_KEY environment variable")
    elif os.getenv("OPENAI_API_KEY"):
        logger.debug("Using API key from OPENAI_API_KEY environment variable")
    elif llm_config.get("api_key"):
        logger.debug("Using API key from config.yaml")
    else:
        logger.warning("No API key found in environment variables or config.yaml")
    
    if not base_url:
        raise ValueError(
            "RunPod endpoint not configured. Please set 'base_url' in config.yaml "
            "or set RUNPOD_BASE_URL environment variable.\n"
            "For RunPod vLLM servers, use the OpenAI-compatible endpoint format:\n"
            "Format: https://<pod-id>-<port>.proxy.runpod.net/v1\n"
            "Get your endpoint URL from RunPod dashboard -> Your Pod -> Endpoints"
        )
    
    # Warn if using serverless API endpoint (not OpenAI-compatible)
    # But allow if it has /openai/v1 in the path (RunPod serverless with OpenAI wrapper)
    if "api.runpod.ai/v2" in base_url and "/openai/v1" not in base_url:
        logger.warning(
            "The endpoint URL appears to be a RunPod serverless API endpoint, "
            "which is NOT OpenAI-compatible. For vLLM servers, you need the "
            "OpenAI-compatible endpoint (format: https://<pod-id>-<port>.proxy.runpod.net/v1). "
            "Get it from RunPod dashboard -> Your Pod -> Endpoints"
        )
    
    # Ensure base_url doesn't have trailing slash (OpenAI client adds paths)
    base_url = base_url.rstrip('/')
    
    logger.info(f"Using RunPod endpoint: {base_url}")
    model_name = llm_config.get('model')
    if model_name:
        logger.info(f"Using model: {model_name}")
    else:
        logger.info("No model specified - endpoint will use default model")
    
    return OpenAI(
        base_url=base_url,
        api_key=api_key
    )


def get_llm_model() -> str:
    """
    Get the LLM model name from config.
    Returns the configured model, or a default model name that RunPod endpoints typically use.
    The default is based on what RunPod vLLM servers commonly use.
    """
    llm_config = load_llm_config()
    model = llm_config.get("model")
    
    # If model is not configured, use a default that RunPod endpoints recognize
    # Based on endpoint responses, RunPod often uses: "meta-llama/llama-3.1-8b-instruct"
    if not model or model.strip() == "":
        return "meta-llama/llama-3.1-8b-instruct"
    return model

