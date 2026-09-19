"""
services/ai_service.py

Thin wrapper around the Gemini API for complaint triage. Kept isolated from
the issues app so the AI provider can be swapped without touching business logic.

Usage:
    from services.ai_service import classify_issue
    result = classify_issue(description="Light has been off for 3 nights",
                             asset_type="Street Light", area_name="Naynapalli")
"""

import json
import logging
import os

from google import genai

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """Lazily creates the Gemini client so the app can start without a
    key set (AI calls will raise AIServiceError instead of crashing the
    whole server on import)."""
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise AIServiceError(
                "GEMINI_API_KEY is not set. Add it to your environment to enable AI triage."
            )
        _client = genai.Client(api_key=api_key)
    return _client


_SYSTEM_PROMPT = """You are the triage assistant for a civic issue reporting platform.
Given a citizen's complaint about a public asset, respond with ONLY a JSON object
(no markdown, no preamble) with these exact keys:

{
  "category": "<short category name, e.g. 'Street Light Outage'>",
  "priority": "<LOW | MEDIUM | HIGH>",
  "summary": "<one-sentence neutral summary of the complaint, under 20 words>"
}

Priority guidance:
- HIGH: safety risk (exposed wiring, traffic signal down, water contamination)
- MEDIUM: functional failure affecting residents but no immediate danger
- LOW: cosmetic or minor issue
"""


class AIServiceError(Exception):
    """Raised when the AI call fails or returns an unparseable response."""


def classify_issue(description: str, asset_type: str, area_name: str) -> dict:
    """
    Calls the LLM to classify a complaint.
    Returns a dict with keys: category, priority, summary.
    Raises AIServiceError on failure — callers should catch this and still
    save the issue with status OPEN and empty AI fields, so a flaky AI call
    never blocks complaint submission (see issues/api.py perform_create).
    """
    user_message = (
        f"Asset type: {asset_type}\n"
        f"Area: {area_name}\n"
        f"Complaint: {description}"
    )

    try:
        response = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config={"system_instruction": _SYSTEM_PROMPT},
        )
        raw_text = response.text.strip()
        raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        result = json.loads(raw_text)

        if result.get("priority") not in ("LOW", "MEDIUM", "HIGH"):
            result["priority"] = "MEDIUM"  # safe fallback

        return result

    except Exception as exc:
        logger.error("AI classification failed: %s", exc)
        raise AIServiceError(str(exc)) from exc


def find_possible_duplicates(new_description: str, open_issues_for_asset) -> list[int]:
    """
    Lightweight duplicate detection for issues on the SAME asset.
    Uses a keyword-overlap heuristic rather than a second LLM call per
    submission (cheaper, fast enough for V1). Returns a list of issue IDs
    that look like they describe the same underlying problem.
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
