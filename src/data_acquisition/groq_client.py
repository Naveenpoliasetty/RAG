"""
Groq LLM client wrapper for resume data extraction.
Uses Groq API with instructor for structured output.
Implements unified RPM + TPM aware retry handling.
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
# Groq client initialization
# ------------------------------------------------------------------

def get_groq_client() -> Groq:
    global _cached_groq_client

    if _cached_groq_client is not None:
        return _cached_groq_client

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables")

    logger.info("Initializing Groq client (first call)")
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
# Rate limit extraction (best effort – SDK may hide headers)
# ------------------------------------------------------------------

def extract_rate_info(response) -> dict:
    rate_info = {
        "remaining_requests": None,
        "remaining_tokens": None,
        "reset": None,
        "is_daily_limit": False,
    }

    try:
        if hasattr(response, "_raw_response"):
            headers = response._raw_response.headers

            rate_info["remaining_requests"] = (
                int(headers["x-ratelimit-remaining-requests"])
                if "x-ratelimit-remaining-requests" in headers else None
            )
            rate_info["remaining_tokens"] = (
                int(headers["x-ratelimit-remaining-tokens"])
                if "x-ratelimit-remaining-tokens" in headers else None
            )
            rate_info["reset"] = headers.get("x-ratelimit-reset-requests")

            if rate_info["reset"] and any(c in rate_info["reset"] for c in ["h", "m", "d"]):
                rate_info["is_daily_limit"] = True

    except Exception as e:
        logger.debug(f"Rate info unavailable: {e}")

    return rate_info


# ------------------------------------------------------------------
# 🔥 SINGLE DECISION FUNCTION (THIS IS THE CORE)
# ------------------------------------------------------------------

def decide_wait_time_on_429(
    attempt: int,
    rate_info: dict,
    prompt_length_chars: int,
) -> tuple[float, bool]:
    """
    Decide how long to wait after a 429 and whether to stop the pipeline.

    Returns:
        (wait_seconds, should_stop)
    """

    remaining_requests = rate_info.get("remaining_requests")
    remaining_tokens = rate_info.get("remaining_tokens")
    is_daily = rate_info.get("is_daily_limit", False)

    # ------------------------------------------------------------
    # Case 1: HARD DAILY EXHAUSTION
    # ------------------------------------------------------------
    if is_daily and (
        remaining_requests == 0 or remaining_tokens == 0
    ):
        logger.error("🛑 DAILY LIMIT EXHAUSTED — stopping pipeline")
        return 0.0, True

    # ------------------------------------------------------------
    # Case 2: TOKEN-PER-MINUTE PRESSURE (MOST COMMON FOR RESUMES)
    # ------------------------------------------------------------
    if (
        remaining_tokens is not None and remaining_tokens <= 1000
    ) or (
        remaining_tokens is None and prompt_length_chars > 8000
    ):
        # Resume workload tuned escalation
        wait_schedule = [15, 30, 45, 60]
        wait_time = wait_schedule[min(attempt, len(wait_schedule) - 1)]

        logger.warning(
            f"⚠️ TPM throttling detected — waiting {wait_time}s "
            f"(attempt={attempt}, remaining_tokens={remaining_tokens})"
        )
        return wait_time, False

    # ------------------------------------------------------------
    # Case 3: REQUEST-PER-MINUTE PRESSURE
    # ------------------------------------------------------------
    if remaining_requests is not None and remaining_requests <= 2:
        wait_schedule = [5, 10, 20, 30]
        wait_time = wait_schedule[min(attempt, len(wait_schedule) - 1)]

        logger.warning(
            f"⚠️ RPM throttling detected — waiting {wait_time}s "
            f"(attempt={attempt}, remaining_requests={remaining_requests})"
        )
        return wait_time, False

    # ------------------------------------------------------------
    # Case 4: UNKNOWN (SDK HID HEADERS) — INFER FROM CONTEXT
    # ------------------------------------------------------------
    if prompt_length_chars > 8000:
        wait_time = 30
        logger.warning(
            f"⚠️ 429 with hidden headers — assuming TPM pressure, waiting {wait_time}s"
        )
        return wait_time, False

    # ------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------
    fallback = min(10 * (attempt + 1), 30)
    logger.warning(f"⚠️ 429 fallback wait {fallback}s")
    return fallback, False


# ------------------------------------------------------------------
# Main synchronous structured output function
# ------------------------------------------------------------------

def groq_structured_output_sync(
    response_model: Type[BaseModel],
    system_prompt: str,
    user_prompt: str,
    model: str = "llama-3.1-8b-instant",
    max_tokens: int = 4000,
    temperature: float = 0.3,
    max_retries: int = 4,
) -> tuple[Optional[BaseModel], dict]:

    client = get_instructor_client()
    prompt_length = len(user_prompt)

    for attempt in range(max_retries):
        try:
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

            logger.info(f"✅ Groq call successful — {response_model.__name__}")
            return response, extract_rate_info(response)

        except Exception as e:
            if "429" not in str(e):
                logger.error(f"❌ Groq call failed: {e}")
                raise

            logger.warning(f"⚠️ 429 encountered (attempt {attempt + 1}/{max_retries})")

            rate_info = {}
            if hasattr(e, "response"):
                try:
                    rate_info = extract_rate_info(e.response)
                except Exception:
                    pass

            wait_time, should_stop = decide_wait_time_on_429(
                attempt=attempt,
                rate_info=rate_info,
                prompt_length_chars=prompt_length,
            )

            if should_stop:
                return None, {
                    "remaining_requests": 0,
                    "remaining_tokens": 0,
                    "limit_exhausted": True,
                    "is_daily_limit": True,
                }

            time.sleep(wait_time)
            continue

    logger.error("❌ Max retries exceeded")
    return None, {
        "remaining_requests": None,
        "remaining_tokens": None,
        "limit_exhausted": False,
        "is_daily_limit": False,
    }