"""
Secure webhook delivery with HMAC-SHA256 signatures.
"""

import hmac
import hashlib
import json
from typing import Dict, Any
from uuid import UUID
import httpx

from app.config import get_settings

settings = get_settings()


def sign_payload(payload: Dict[str, Any], secret: str) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return signature


async def deliver_notification(
    webhook_url: str,
    secret: str,
    post_id: UUID,
    title: str,
    content: str,
    author_company: str,
) -> bool:
    """
    Push a signed notification to the target agent.
    Returns True on HTTP 2xx, False otherwise.
    """
    payload = {
        "event": "post.relevant",
        "post_id": str(post_id),
        "title": title,
        "content": content,
        "author_company": author_company,
    }
    signature = sign_payload(payload, secret)

    headers = {
        "Content-Type": "application/json",
        "X-Signature-SHA256": signature,
        "X-Event-Type": "post.relevant",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
            resp = await client.post(webhook_url, json=payload, headers=headers)
            return 200 <= resp.status_code < 300
    except Exception:
        return False