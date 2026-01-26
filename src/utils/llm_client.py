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

# Cache the OpenAI client to avoid reinitializing connection on every call
_cached_openai_client: Optional[OpenAI] = None


def load_llm_config() -> dict:
    """Load the raw llm_config from config.yaml"""
    config_path = Path(__file__).parent.parent / "core" / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("llm_config", {})


def get_current_provider() -> str:
    """Determine the current LLM provider from environment or config."""
    llm_config = load_llm_config()
    # Priority: Environment variable > config.yaml > default "runpod"
    provider = os.getenv("LLM_PROVIDER") or llm_config.get("provider", "runpod")
    return provider.lower()


def get_provider_config(provider: Optional[str] = None) -> dict:
    """
    Get the configuration for a specific provider, or the current one if not specified.
    Returns a merged dictionary with global settings and provider-specific overrides.
    """
    llm_config = load_llm_config()
    if provider is None:
        provider = get_current_provider()
    
    provider_settings = llm_config.get(provider, {})
    
    # Create a merged config so top-level settings like SUMMARY_MAX_TOKENS are available
    merged_config = llm_config.copy()
    # Remove the provider sections from the top level to avoid confusion
    if "runpod" in merged_config: del merged_config["runpod"]
    if "groq" in merged_config: del merged_config["groq"]
    
    # Update with provider-specific overrides
    merged_config.update(provider_settings)
    return merged_config


def get_openai_client() -> OpenAI:
    """
    Create or return cached OpenAI client configured for the selected provider (RunPod or Groq).
    """
    global _cached_openai_client
    
    # Return cached client if it exists
    if _cached_openai_client is not None:
        return _cached_openai_client
    
    provider = get_current_provider()
    logger.info(f"Initializing OpenAI client for provider: {provider}")
    
    config = get_provider_config(provider)

    # Determine Base URL
    # Priority: LLM_BASE_URL (env) -> Provider-specific env -> config.yaml
    base_url = (
        os.getenv("LLM_BASE_URL") or 
        os.getenv(f"{provider.upper()}_BASE_URL") or 
        config.get("base_url")
    )
    
    # Determine API Key
    # Priority: LLM_API_KEY (env) -> Provider-specific env -> config.yaml
    api_key = (
        os.getenv("LLM_API_KEY") 
        or os.getenv(f"{provider.upper()}_API_KEY")
        or config.get("api_key")
        or "dummy-key"
    )
    
    if not base_url:
        raise ValueError(f"Base URL not configured for provider '{provider}'")
    
    # Ensure base_url doesn't have trailing slash
    base_url = base_url.rstrip('/')
    
    logger.info(f"Using {provider} endpoint: {base_url}")
    
    _cached_openai_client = OpenAI(
        base_url=base_url,
        api_key=api_key
    )
    
    return _cached_openai_client


def get_llm_model() -> str:
    """
    Get the LLM model name for the current provider.
    """
    provider = get_current_provider()
    config = get_provider_config(provider)
    
    # Priority: LLM_MODEL (env) -> Provider-specific env -> config.yaml
    model = (
        os.getenv("LLM_MODEL") or
        os.getenv(f"{provider.upper()}_MODEL") or
        config.get("model")
    )
    
    if not model:
        # Defaults based on provider
        if provider == "runpod":
            return "meta-llama/llama-3.1-8b-instruct"
        elif provider == "groq":
            return "llama-3-70b-8192"
        return "meta-llama/llama-3.1-8b-instruct"
        
    return model

