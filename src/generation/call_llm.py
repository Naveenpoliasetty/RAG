from typing import Type
from pydantic import BaseModel
import instructor
from dotenv import load_dotenv
from src.utils.logger import get_logger
from src.utils.llm_client import get_openai_client, get_llm_model, load_llm_config

logger = get_logger(__name__)
load_dotenv()

# Your async LLM JSON generator (RunPod vLLM with OpenAI wrapper)
async def llm_json(output_model: Type[BaseModel], system_prompt:str, user_prompt: str, max_tokens: int = 1000, temperature: float = 0.4):
    logger.info(f"role: system, content: {system_prompt}, role: user, content: {user_prompt}")
    client = instructor.from_openai(
        get_openai_client(),
        mode=instructor.Mode.JSON,
    )
    
    # Build request parameters
    # Note: RunPod server has a hard limit of 3000 tokens for completion
    # Cap max_tokens at 3000 to avoid hitting the server limit
    llm_config = load_llm_config()
    global_max_tokens = llm_config.get("global_max_tokens", 4096)
    effective_max_tokens = min(max_tokens, global_max_tokens)
    
    request_params = {
        "model": get_llm_model(),  # Get model from config or use default
        "response_model": output_model,
        "messages": [ 
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": effective_max_tokens,
        "temperature": temperature,
    }
    
    if effective_max_tokens < max_tokens:
        logger.warning(f"Capping max_tokens from {max_tokens} to {effective_max_tokens} due to server limit")
    
    logger.info(f"Making LLM call with max_tokens={effective_max_tokens} (requested={max_tokens}, model={get_llm_model()})")
    
    response = client.chat.completions.create(**request_params)
    
    # Check if response was truncated due to token limit
    if hasattr(response, 'choices') and response.choices:
        finish_reason = getattr(response.choices[0], 'finish_reason', None)
        if finish_reason == 'length':
            logger.warning(f"Response was truncated due to max_tokens limit ({effective_max_tokens}). "
                         f"Consider reducing prompt size or number of items requested.")

    # The instructor library returns the Pydantic model directly when using response_model
    # Log the response for debugging
    if hasattr(response, 'model_dump_json'):
        logger.info(f"Response: {response.model_dump_json(indent=2)}")
    else:
        logger.info(f"Response: {str(response)}")
    
    # Return the Pydantic model object, not the JSON string
    return response
