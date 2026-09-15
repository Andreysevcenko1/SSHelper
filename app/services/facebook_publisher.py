"""Facebook Page auto-posting via the Meta Graph API.

Facebook does not allow third-party bots to post into regular Groups (the
Groups Feed API was deprecated years ago). The only officially supported
automated posting target is a **Facebook Page**, using a long-lived Page
access token and the ``/{page_id}/feed`` (text) or ``/{page_id}/photos``
(with image) Graph API endpoints.

This module is intentionally independent of aiogram/Telegram — it only
needs a listing's rendered text + optional image URL, and posts them to the
configured Page. It's wired in as an optional side-effect alongside the
existing Telegram notification pipelines (watcher / group_watcher), gated
behind ``Config.facebook_enabled``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from app.config import Config

logger = logging.getLogger(__name__)

_GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)


async def publish_to_facebook_page(
    config: "Config",
    text: str,
    image_url: str | None = None,
    listing_id: str | None = None,
    route_key: str | None = None,
) -> bool:
    """Post *text* (optionally with *image_url*) to the configured Facebook Page.

    When ``Config.facebook_route_targets`` contains *route_key*, that
    category-specific Page is used. Otherwise the default ``FACEBOOK_PAGE_ID``
    and ``FACEBOOK_PAGE_ACCESS_TOKEN`` are used.

    Returns ``True`` on success, ``False`` otherwise (never raises — failures
    are logged and treated as non-fatal, matching the "best effort" policy
    used for image sends in :mod:`app.services.notifier`).
    """
    if not config.facebook_enabled:
        return False

    target = config.facebook_route_targets.get(route_key or "")
    if target:
        page_id = target.page_id
        token = target.access_token
        target_label = f"route:{route_key}"
    elif config.facebook_page_id and config.facebook_page_access_token:
        page_id = config.facebook_page_id
        token = config.facebook_page_access_token
        target_label = "default"
    else:
        logger.warning(
            "Facebook publish skipped for listing=%s route=%s — missing page_id/access_token",
            listing_id, route_key,
        )
        return False

    try:
        async with aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT) as session:
            if image_url:
                url = f"{_GRAPH_API_BASE}/{page_id}/photos"
                payload = {
                    "url": image_url,
                    "caption": text,
                    "access_token": token,
                }
            else:
                url = f"{_GRAPH_API_BASE}/{page_id}/feed"
                payload = {
                    "message": text,
                    "access_token": token,
                }

            async with session.post(url, data=payload) as resp:
                body = await resp.json(content_type=None)
                if resp.status == 200 and "error" not in body:
                    logger.info(
                        "Facebook post ok listing=%s route=%s target=%s page_id=%s post_id=%s has_image=%s",
                        listing_id,
                        route_key,
                        target_label,
                        page_id,
                        body.get("post_id") or body.get("id"),
                        bool(image_url),
                    )
                    return True
                logger.warning(
                    "Facebook post failed listing=%s route=%s target=%s page_id=%s status=%s body=%s",
                    listing_id, route_key, target_label, page_id, resp.status, body,
                )
                return False
    except Exception as exc:
        logger.warning(
            "Facebook post exception listing=%s route=%s target=%s page_id=%s — %s",
            listing_id, route_key, target_label, page_id, exc,
        )
        return False
