"""
services/ai_service.py

Thin wrapper around the Gemini API for complaint triage. Kept isolated from
the issues app so the AI provider can be swapped without touching business logic.

Requires: pip install google-genai
Env var:  GEMINI_API_KEY (get one at https://aistudio.google.com/apikey)

Usage:
    from services.ai_service import classify_issue
    result = classify_issue(description="Light has been off for 3 nights",
                             asset_type="Street Light", area_name="Naynapalli")
"""

import json
import logging
import re

from decouple import config
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

logger = logging.getLogger(__name__)

_client = None

_MODEL_NAME = "gemini-3.6-flash"


def _get_client():
    """Lazily creates the Gemini client so the app can start without a
    key set (AI calls will raise AIServiceError instead of crashing the
    whole server on import).

    NOTE: this project loads .env via python-decouple (see config/settings.py),
    which does NOT write values into os.environ — so we must read the key
    with decouple's config(), not os.environ.get(), or it will always come
    back empty even when GEMINI_API_KEY is correctly set in .env.
    """
    global _client
    if _client is None:
        api_key = config("GEMINI_API_KEY", default="")
        if not api_key:
            raise AIServiceError(
                "GEMINI_API_KEY is not set. Add it to your .env file to enable AI triage."
            )
        _client = genai.Client(api_key=api_key)
    return _client


_SYSTEM_PROMPT_TEMPLATE = """You are the triage assistant for a civic issue reporting platform.
Given a citizen's complaint about a public asset, respond with ONLY a JSON object
(no markdown, no preamble) with these exact keys:

{{
  "category": "<short category name, e.g. 'Street Light Outage'>",
  "priority": "<LOW | MEDIUM | HIGH>",
  "summary": "<one-sentence neutral summary of the complaint, under 20 words>",
  "department": "<the single best department from the list below>"
}}

Priority guidance:
- HIGH: safety risk (exposed wiring, traffic signal down, water contamination)
- MEDIUM: functional failure affecting residents but no immediate danger
- LOW: cosmetic or minor issue

Department guidance:
- The complaint is filed against an asset that has its OWN default department,
  but the described problem may actually belong to a different one (e.g. a
  transformer complaint that's really about flooding near it).
- Pick the department whose team should actually handle this problem, based on
  what the citizen described — not just the asset type.
- You MUST choose exactly one department name, copied verbatim, from this list:
{department_list}
"""


class AIServiceError(Exception):
    """Raised when the AI call fails or returns an unparseable response."""


def classify_issue(description: str, asset_type: str, area_name: str, department_names: list[str]) -> dict:
    """
    Calls the LLM to classify a complaint.
    Returns a dict with keys: category, priority, summary, department.
    `department_names` should be the current list of real Department names
    (e.g. Department.objects.values_list("name", flat=True)) so the AI can
    only ever suggest a department that actually exists.
    Raises AIServiceError on failure — callers should catch this and still
    save the issue with status OPEN and empty AI fields, so a flaky AI call
    never blocks complaint submission (see issues/api.py perform_create).
    """
    user_message = (
        f"Asset type: {asset_type}\n"
        f"Area: {area_name}\n"
        f"Complaint: {description}"
    )
    department_list = "\n".join(f"- {name}" for name in department_names) or "- (no departments configured)"
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(department_list=department_list)

    try:
        response = _get_client().models.generate_content(
            model=_MODEL_NAME,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                # Bumped from 300: the department list makes the prompt longer,
                # and a too-tight limit was truncating the JSON mid-response,
                # which surfaced as a confusing JSONDecodeError.
                max_output_tokens=600,
                response_mime_type="application/json",
            ),
        )
        raw_text = (response.text or "").strip()
        raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            # The model occasionally wraps the JSON in stray text even when
            # response_mime_type=application/json is requested. Try to pull
            # out just the {...} object before giving up.
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if not match:
                logger.error("AI classification failed: no JSON object found in response: %r", raw_text[:300])
                raise
            result = json.loads(match.group(0))

        if result.get("priority") not in ("LOW", "MEDIUM", "HIGH"):
            result["priority"] = "MEDIUM"  # safe fallback

        # Guard against the model hallucinating a department that isn't real —
        # fall back to no suggestion rather than trusting free text here.
        suggested_dept = result.get("department", "")
        if suggested_dept not in department_names:
            result["department"] = None

        return result

    except AIServiceError:
        # Raised by _get_client() itself (e.g. missing key) — re-raise as-is,
        # but log it so it's visible in the server console instead of vanishing.
        logger.error("AI classification failed: Gemini client could not be created (check GEMINI_API_KEY).")
        raise
    except (genai_errors.APIError, json.JSONDecodeError, KeyError, IndexError, AttributeError) as exc:
        logger.error("AI classification failed: %s (raw response: %r)", exc, locals().get("raw_text", "")[:300])
        raise AIServiceError(str(exc)) from exc
    except Exception as exc:
        # Catch-all so no failure mode is ever silent — log full details, then
        # convert to AIServiceError so perform_create's existing handling still applies.
        logger.exception("AI classification failed with an unexpected error: %s", exc)
        raise AIServiceError(str(exc)) from exc


def find_possible_duplicates(new_description: str, open_issues_for_asset) -> list[int]:
    """
    Lightweight duplicate detection for issues on the SAME asset.
    Uses a keyword-overlap heuristic rather than a second LLM call per
    submission (cheaper, fast enough for V1). Returns a list of issue IDs
    that look like they describe the same underlying problem.

    For a production upgrade, replace this with embedding similarity
    (e.g. compare against stored embeddings in a vector column).
    """
    new_words = set(new_description.lower().split())
    matches = []
    for issue in open_issues_for_asset:
        existing_words = set(issue.description.lower().split())
        if not existing_words:
            continue
        overlap = len(new_words & existing_words) / max(len(new_words | existing_words), 1)
        if overlap > 0.35:
            matches.append(issue.id)
    return matches
