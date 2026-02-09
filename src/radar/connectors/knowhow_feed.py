# src/rader/connectors/knowhow_feed.py
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_text(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x.strip()
    return str(x).strip()


def _parse_rss_with_feedparser(xml_text: str) -> List[Dict[str, Any]]:
    """
    feedparser가 설치되어 있으면 RSS/Atom 파싱을 가장 안정적으로 할 수 있습니다.
    """
    try:
        import feedparser  # type: ignore
    except Exception:
        return []

    parsed = feedparser.parse(xml_text)
    entries = getattr(parsed, "entries", []) or []

    items: List[Dict[str, Any]] = []
    for e in entries:
        title = _safe_text(getattr(e, "title", ""))
        link = _safe_text(getattr(e, "link", ""))

        summary = _safe_text(getattr(e, "summary", ""))

        # 본문(content)은 feed마다 content[0].value 형태일 수 있음
        content_val = ""
        content = getattr(e, "content", None)
        if isinstance(content, list) and content:
            content_val = _safe_text(getattr(content[0], "value", ""))

        published = (
            _safe_text(getattr(e, "published", "")) or _safe_text(getattr(e, "updated", ""))
        )
        if not published:
            published = _now_iso()

        source_id = _safe_text(getattr(e, "id", "")) or _sha1(f"{title}|{link}|{published}")

        items.append(
            {
                "source": "knowhow",
                "source_id": source_id,
                "title": title,
                "url": link,
                "published_at": published,
                "summary": summary,
                "content": content_val,
                "raw": dict(e) if hasattr(e, "keys") else {"entry": str(e)},
            }
        )
    return items


def _parse_rss_minimal(xml_text: str) -> List[Dict[str, Any]]:
    """
    feedparser가 없을 때의 최소 파서(RSS 2.0 기준).
    Atom 등 다양한 피드를 100% 커버하지는 않습니다.
    """
    import xml.etree.ElementTree as ET

    items: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        print(f"[knowhow] RSS 파싱 실패: XML 파싱 에러 - {e}")
        return items

    # RSS 2.0: <rss><channel><item>...</item></channel></rss>
    channel = root.find("channel")
    if channel is None:
        # 일부 feed는 namespace가 존재할 수 있음
        # 여기서는 최소 구현으로 실패 처리
        print("[knowhow] RSS 구조를 인식하지 못했습니다. (feedparser 설치를 권장합니다)")
        return items

    for it in channel.findall("item"):
        title = _safe_text(it.findtext("title"))
        link = _safe_text(it.findtext("link"))
        pub = _safe_text(it.findtext("pubDate")) or _now_iso()
        desc = _safe_text(it.findtext("description"))

        source_id = _sha1(f"{title}|{link}|{pub}")

        items.append(
            {
                "source": "knowhow",
                "source_id": source_id,
                "title": title,
                "url": link,
                "published_at": pub,
                "summary": desc,
                "content": "",
                "raw": {
                    "title": title,
                    "link": link,
                    "pubDate": pub,
                    "description": desc,
                },
            }
        )

    return items


def fetch(source_cfg: Optional[Dict[str, Any]] = None, ctx: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    KNOWHOW RSS에서 글 목록을 가져옵니다.

    반환 형식: raw item list (dict)
    - source: "knowhow"
    - source_id: 고유 ID
    - title, url, published_at, summary, content, raw
    """
    # 설정 읽기
    feed_url = None
    if source_cfg:
        feed_url = (
            source_cfg.get("rss", {}).get("feed_url")
            or source_cfg.get("endpoint")
            or source_cfg.get("url")
        )

    if not feed_url:
        feed_url = "https://knowhow.ceo/feed"

    timeout_sec = 20
    user_agent = os.getenv("HTTP_USER_AGENT", "amously-grant-radar/0.1")
    headers = {"User-Agent": user_agent}

    print(f"[knowhow] RSS 가져오기 시작: {feed_url}")

    try:
        resp = requests.get(feed_url, headers=headers, timeout=timeout_sec)
        resp.raise_for_status()
    except Exception as e:
        print(f"[knowhow] RSS 요청 실패: {e}")
        return []

    xml_text = resp.text

    # 1) feedparser 우선
    items = _parse_rss_with_feedparser(xml_text)
    if items:
        print(f"[knowhow] RSS 파싱 완료(feedparser): {len(items)}건")
        return items

    # 2) 최소 파서 fallback
    items = _parse_rss_minimal(xml_text)
    print(f"[knowhow] RSS 파싱 완료(최소 파서): {len(items)}건")
    return items