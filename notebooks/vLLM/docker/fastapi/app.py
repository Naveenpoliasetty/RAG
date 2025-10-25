from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI(title="vLLM Gateway")

VLLM_URL = "http://vllm:8000/v1/completions"  # Docker network service name

class PromptRequest(BaseModel):
    model: str
    prompt: list  # list of strings for batch inference
    max_tokens: int = 50

@app.post("/api/generate")
def generate(request: PromptRequest):
    payload = {
        "model": request.model,
        "prompt": request.prompt,
        "max_tokens": request.max_tokens
    }
    resp = requests.post(VLLM_URL, json=payload)
    return resp.json()
