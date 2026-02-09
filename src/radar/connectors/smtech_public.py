# src/rader/connectors/smtech_public.py
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
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


class _LinkTitleParser(HTMLParser):
    """
    외부 라이브러리(bs4) 없이 최소한의 링크/텍스트를 뽑기 위한 HTML 파서입니다.
    """
    def __init__(self) -> None:
        super().__init__()
        self.links: List[Dict[str, str]] = []
        self._in_a = False
        self._cur_href = ""
        self._cur_text_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        if tag.lower() == "a":
            self._in_a = True
            self._cur_href = ""
            self._cur_text_parts = []
            for k, v in attrs:
                if k.lower() == "href" and v:
                    self._cur_href = v

    def handle_data(self, data: str) -> None:
        if self._in_a and data:
            t = data.strip()
            if t:
                self._cur_text_parts.append(t)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._in_a:
            text = " ".join(self._cur_text_parts).strip()
            href = self._cur_href.strip()
            if href and text:
                self.links.append({"href": href, "text": text})
            self._in_a = False
            self._cur_href = ""
            self._cur_text_parts = []


def _build_headers() -> Dict[str, str]:
    ua = os.getenv("HTTP_USER_AGENT", "amously-grant-radar/0.1 (+contact: dev@amously.ai)")
    return {"User-Agent": ua}


def fetch(source_cfg: Optional[Dict[str, Any]] = None, ctx: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    SMTECH 공개 페이지에서 '후보 링크'를 최대한 보수적으로 수집합니다.

    운영 권장:
    - sources.yaml에서 enabled=false 기본
    - 실제로 쓰려면 web.list_urls에 "공개 공고 목록" URL을 명시하세요.
      예) web:
            base_url: https://www.smtech.go.kr
            list_urls:
              - https://www.smtech.go.kr/front/... (공개 공고 리스트)
    """
    enabled = False
    base_url = "https://www.smtech.go.kr"
    list_urls: List[str] = []

    if source_cfg:
        enabled = bool(source_cfg.get("enabled", False))
        web_cfg = source_cfg.get("web", {}) or {}
        base_url = web_cfg.get("base_url", base_url) or base_url
        list_urls = web_cfg.get("list_urls", []) or []

    if not enabled:
        print("[smtech] 안내: sources.yaml에서 enabled=false로 설정되어 있어 수집을 건너뜁니다.")
        return []

    if not list_urls:
        print("[smtech] 안내: 공개 공고 목록 URL(web.list_urls)이 없어 수집을 건너뜁니다.")
        print("[smtech] 팁: SMTECH는 로그인/SSO 이슈가 있어 '공개 목록 URL'을 명시하는 방식이 안전합니다.")
        return []

    headers = _build_headers()
    timeout_sec = 20

    results: List[Dict[str, Any]] = []
    print(f"[smtech] 공개 페이지 수집 시작: list_urls={len(list_urls)}개")

    for idx, url in enumerate(list_urls, start=1):
        print(f"[smtech] ({idx}/{len(list_urls)}) 목록 페이지 요청: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=timeout_sec)
            resp.raise_for_status()
        except Exception as e:
            print(f"[smtech] 요청 실패: {e}")
            continue

        html = resp.text

        parser = _LinkTitleParser()
        try:
            parser.feed(html)
        except Exception as e:
            print(f"[smtech] HTML 파싱 실패: {e}")
            continue

        # 후보 링크 필터: 너무 공격적으로 거르지 않되, 의미 없는 링크를 최대한 제외
        # (실제 운영 시 규칙을 좁혀가면 됩니다)
        for a in parser.links:
            text = _safe_text(a.get("text"))
            href = _safe_text(a.get("href"))

            if len(text) < 4:
                continue

            # 공고/모집/지원/사업/프로그램 등 키워드가 포함된 링크만 우선 수집
            if not re.search(r"(공고|모집|지원|사업|프로그램|행사|설명회|세미나|교육)", text):
                continue

            # 상대경로 처리
            if href.startswith("/"):
                full_url = base_url.rstrip("/") + href
            elif href.startswith("http://") or href.startswith("https://"):
                full_url = href
            else:
                # 기타 상대경로
                full_url = base_url.rstrip("/") + "/" + href.lstrip("/")

            source_id = _sha1(f"{text}|{full_url}")

            results.append(
                {
                    "source": "smtech",
                    "source_id": source_id,
                    "title": text,
                    "url": full_url,
                    "published_at": _now_iso(),
                    "summary": "",
                    "content": "",
                    "raw": {"list_url": url, "link": a},
                }
            )

    print(f"[smtech] 수집 완료: {len(results)}건 (주의: 상세 파싱은 별도 구현 필요)")
    return results