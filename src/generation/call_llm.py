from typing import Type
from pydantic import BaseModel
from openai import OpenAI
import instructor
from dotenv import load_dotenv
from src.utils.logger import get_logger
logger = get_logger(__name__)
load_dotenv()
# Your async LLM JSON generator (Groq, GPT-5.1, Gemini, etc.)
async def llm_json(output_model: Type[BaseModel], system_prompt:str, user_prompt: str):
    logger.info(f"role: system, content: {system_prompt}, role: user, content: {user_prompt}")
    client = instructor.patch(OpenAI())
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_model=output_model,
        messages=[ 
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
            ]
    )

    logger.info(f"Response: {response.model_dump_json(indent=2)}")
    return response.model_dump_json(indent=2)
