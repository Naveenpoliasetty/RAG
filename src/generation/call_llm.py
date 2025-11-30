from typing import Type
from pydantic import BaseModel
import instructor
from dotenv import load_dotenv
from src.utils.logger import get_logger
from src.utils.llm_client import get_openai_client, get_llm_model

logger = get_logger(__name__)
load_dotenv()

# Your async LLM JSON generator (RunPod vLLM with OpenAI wrapper)
async def llm_json(output_model: Type[BaseModel], system_prompt:str, user_prompt: str):
    logger.info(f"role: system, content: {system_prompt}, role: user, content: {user_prompt}")
    client = instructor.patch(get_openai_client())
    
    # Build request parameters
    request_params = {
        "model": get_llm_model(),  # Get model from config or use default
        "response_model": output_model,
        "messages": [ 
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }
    
    response = client.chat.completions.create(**request_params)

    logger.info(f"Response: {response.model_dump_json(indent=2)}")
    return response.model_dump_json(indent=2)
