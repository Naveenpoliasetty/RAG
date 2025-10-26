from fastapi import FastAPI, Header, HTTPException, Depends, Request
from pydantic import BaseModel
from prometheus_client import Counter, Histogram
from prometheus_client.exposition import make_asgi_app

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.extension import _rate_limit_exceeded_handler

import time
import logging
import sys
import requests
import httpx
import os

##################################################################################

app = FastAPI(title="vLLM Gateway")

VLLM_URL = "http://vllm:8000/v1/completions"  # Docker network service name
API_KEY = os.getenv("API_KEY", "supersecretapikey")

timeout = 600       # seconds - set to "None" for "no timeout"

logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
        )
logger = logging.getLogger("fastapi-gateway")       # docker logs fastapi-gateway

# metrics
REQUEST_COUNT = Counter(
    "fastapi_requests_total",
    "Total API requests",
    ["endpoint", "method", "status"]
)
REQUEST_LATENCY = Histogram(
    "fastapi_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint", "method"]
)

app.mount("/metrics", make_asgi_app())

##################################################################################

# key authentication
def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True


# rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# data model
class PromptRequest(BaseModel):
    model: str
    prompt: list
    max_tokens: int = 50


# endpoint declaration
@app.post("/api/generate")
@limiter.limit("3/minute")
async def generate(request: Request, body: PromptRequest, api_key: bool = Depends(verify_api_key)):
    endpoint = "/api/generate"
    method = "POST"
    status = "500"

    start = time.time()
    logger.info(f"Received req from model {str(request)}")

    try:     
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(VLLM_URL, json={
                "model": body.model,
                "prompt": body.prompt,
                "max_tokens": body.max_tokens
            })
        logger.info("vllm response success")
        return resp.json()
    
    except httpx.ReadTimeout:
        logger.error("Timeout contacting vLLM", exc_info=True)
        raise HTTPException(status_code=504, detail="Timeout from vLLM")
    
    except httpx.RequestError as e:
        logger.error(f"Request error: {str(e)}")
        raise HTTPException(status_code=502, detail=f"vLLM request failed: {str(e)}")

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

    except Exception as e:
        logger.exception("Unhandled error in generate")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        elapsed = time.time() - start
        REQUEST_COUNT.labels(endpoint=endpoint, method=method, status=status).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint, method=method).observe(elapsed)
        logger.info("Handled request", extra={"endpoint": endpoint, "status": status, "elapsed_s": elapsed})

