"""
Groq LLM client wrapper for resume data extraction.
Uses Groq API with instructor for structured output and tracks rate limits.
"""

import os
import time
import random
from typing import Optional, Type
from dotenv import load_dotenv

import instructor
from groq import Groq
from pydantic import BaseModel

from src.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

# ------------------------------------------------------------------
# Cached clients
# ------------------------------------------------------------------

_cached_groq_client: Optional[Groq] = None
_cached_instructor_client: Optional[instructor.Instructor] = None


# ------------------------------------------------------------------
# Token-aware pacing
# ------------------------------------------------------------------

def compute_token_delay(rate_info: dict, min_delay: float = 2.0) -> float:
    """
    Decide how long to wait before the next request based on token pressure.

    Strategy:
    - High remaining tokens -> normal delay
    - Low remaining tokens -> slow down
    - Zero tokens + daily -> stop pipeline
    """
    remaining_tokens = rate_info.get("remaining_tokens")
    is_daily = rate_info.get("is_daily_limit", False)

    if remaining_tokens is None:
        return min_delay

    # Hard stop on daily exhaustion
    if remaining_tokens <= 0 and is_daily:
        raise RuntimeError("DAILY TOKEN LIMIT EXHAUSTED")

    # Token pressure thresholds (tuned for llama-3.1-8b-instant)
    if remaining_tokens < 1000:
        return max(min_delay, 20.0)
    elif remaining_tokens < 3000:
        return max(min_delay, 10.0)
    elif remaining_tokens < 6000:
        return max(min_delay, 5.0)

    return min_delay


# ------------------------------------------------------------------
# Groq client initialization
# ------------------------------------------------------------------

def get_groq_client() -> Groq:
    global _cached_groq_client

    if _cached_groq_client is not None:
        return _cached_groq_client

    logger.info("Initializing Groq client (first call)")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables")

    _cached_groq_client = Groq(api_key=api_key)
    logger.info("Groq client initialized successfully")
    return _cached_groq_client


def get_instructor_client() -> instructor.Instructor:
    global _cached_instructor_client

    if _cached_instructor_client is not None:
        return _cached_instructor_client

    logger.info("Initializing Groq instructor client (first call)")
    groq_client = get_groq_client()

    _cached_instructor_client = instructor.from_groq(
        groq_client,
        mode=instructor.Mode.JSON
    )

    logger.info("Groq instructor client initialized successfully")
    return _cached_instructor_client


# ------------------------------------------------------------------
# Rate limit extraction
# ------------------------------------------------------------------

def log_rate_limits(response) -> dict:
    rate_info = {
        "remaining_requests": None,
        "remaining_tokens": None,
        "reset_requests": None,
        "limit_exhausted": False,
        "is_daily_limit": False,
    }

    try:
        if hasattr(response, "_raw_response"):
            headers = response._raw_response.headers

            remaining_requests = headers.get("x-ratelimit-remaining-requests")
            remaining_tokens = headers.get("x-ratelimit-remaining-tokens")
            reset_requests = headers.get("x-ratelimit-reset-requests")

            if remaining_requests is not None:
                rate_info["remaining_requests"] = int(remaining_requests)

            if remaining_tokens is not None:
                rate_info["remaining_tokens"] = int(remaining_tokens)

            rate_info["reset_requests"] = reset_requests

            logger.info(
                f"📊 Groq Rate Limits | "
                f"Requests left: {remaining_requests} | "
                f"Tokens left: {remaining_tokens}"
            )

            # Detect daily vs per-minute reset
            if reset_requests and any(c in reset_requests for c in ["h", "m", "d"]):
                rate_info["is_daily_limit"] = True

            if (
                (rate_info["remaining_requests"] is not None and rate_info["remaining_requests"] <= 0)
                or
                (rate_info["remaining_tokens"] is not None and rate_info["remaining_tokens"] <= 0)
            ):
                if rate_info["is_daily_limit"]:
                    rate_info["limit_exhausted"] = True
                    logger.warning("🛑 DAILY RATE LIMIT EXHAUSTED")
                else:
                    logger.warning("⚠️ Per-minute rate limit reached")

            if rate_info["remaining_tokens"] is not None:
                logger.debug(
                    f"🧠 Token pressure check — remaining tokens: "
                    f"{rate_info['remaining_tokens']}"
                )

    except Exception as e:
        logger.warning(f"Could not extract rate limit info: {e}")

    return rate_info


# ------------------------------------------------------------------
# Synchronous structured output (token + request aware)
# ------------------------------------------------------------------

def groq_structured_output_sync(
    response_model: Type[BaseModel],
    system_prompt: str,
    user_prompt: str,
    model: str = "llama-3.1-8b-instant",
    max_tokens: int = 4000,
    temperature: float = 0.3,
    max_retries: int = 3,
) -> tuple[Optional[BaseModel], dict]:
    """
    Synchronous Groq structured output with:
    - RPM control
    - TPM-aware pacing
    - Safe retries
    """

    RATE_LIMIT_DELAY = 2.0  # 30 RPM → 2s baseline

    logger.info(f"Making Groq API call with model: {model}")
    logger.debug(f"User prompt length: {len(user_prompt)} characters")

    client = get_instructor_client()

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                backoff = (2 ** attempt) + random.uniform(0, 1)
                logger.info(f"Retry {attempt}/{max_retries} — waiting {backoff:.1f}s")
                time.sleep(backoff)

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_model=response_model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            rate_info = log_rate_limits(response)

            # Unified pacing for NEXT request
            try:
                token_delay = compute_token_delay(rate_info, min_delay=RATE_LIMIT_DELAY)
                pacing_delay = max(RATE_LIMIT_DELAY, token_delay)

                logger.info(
                    f"⏱️ Pacing next request by {pacing_delay:.1f}s "
                    f"(remaining tokens: {rate_info.get('remaining_tokens')})"
                )

                time.sleep(pacing_delay)

            except RuntimeError as stop_err:
                logger.error(str(stop_err))
                return None, {
                    "remaining_requests": rate_info.get("remaining_requests", 0),
                    "remaining_tokens": 0,
                    "limit_exhausted": True,
                    "is_daily_limit": True,
                }

            logger.info(f"✅ Groq API call successful — {response_model.__name__}")
            return response, rate_info

        except Exception as e:
            if "429" in str(e):
                logger.warning(f"⚠️ 429 Rate limit error: {e}")
                if attempt == max_retries - 1:
                    return None, {
                        "remaining_requests": 0,
                        "remaining_tokens": 0,
                        "limit_exhausted": False,
                        "is_daily_limit": False,
                    }
                continue

            logger.error(f"❌ Groq API call failed: {e}")
            raise

    raise RuntimeError("Groq call failed after max retries")