import json
import os
import requests

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")
GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"


def _page_tokens():
    raw = os.getenv("FB_PAGE_TOKENS_JSON", "{}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("FB_PAGE_TOKENS_JSON must be valid JSON mapping Page IDs to Page access tokens.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("FB_PAGE_TOKENS_JSON must be a JSON object.")
    return data


def publish_page_post(page_id: str, message: str):
    """Publish a text post to a Page for which the user has authorized access."""
    token = _page_tokens().get(str(page_id))
    if not token:
        raise RuntimeError(
            f"No Page access token configured for Page ID {page_id}. Add it to FB_PAGE_TOKENS_JSON in .env."
        )
    response = requests.post(
        f"{GRAPH_ROOT}/{page_id}/feed",
        data={"message": message, "access_token": token},
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw_response": response.text[:500]}
    if not response.ok or "error" in payload:
        raise RuntimeError(f"Meta Graph API error: {payload}")
    return payload
