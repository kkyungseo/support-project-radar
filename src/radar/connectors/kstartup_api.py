# src/rader/connectors/kstartup_api.py
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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


def _as_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def _resolve_env_placeholder(value: Any, default: Any = None) -> Any:
    """
    ${ENV_VAR:default_value} 형식의 플레이스홀더를 환경변수 값으로 치환합니다.
    """
    if not isinstance(value, str):
        return value if value is not None else default
    
    if value.startswith("${") and value.endswith("}"):
        inner = value[2:-1]  # ENV_VAR:default_value
        if ":" in inner:
            env_name, env_default = inner.split(":", 1)
        else:
            env_name, env_default = inner, ""
        
        resolved = os.getenv(env_name.strip(), env_default.strip())
        return resolved if resolved else default
    
    return value if value else default


def _pick_items_from_json(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """
    data.go.kr OpenAPI JSON 응답에서 item 목록을 최대한 유연하게 추출합니다.
    (가이드/서비스설계서마다 response 구조가 약간씩 다를 수 있어서 방어적으로 처리)

    반환:
      - items: list[dict]
      - total_count: Optional[int]
    """
    # payload가 list인 경우 직접 반환
    if isinstance(payload, list):
        return payload, len(payload)
    
    # 흔한 케이스 1) {"response": {"body": {"items": {"item": [...]}, "totalCount": N}}}
    response = payload.get("response") if isinstance(payload, dict) else payload
    if response is None:
        response = payload
    
    # body 추출
    if isinstance(response, dict):
        body = response.get("body") or response.get("data") or response.get("result") or response
    else:
        body = response
    
    # body가 list인 경우 직접 반환
    if isinstance(body, list):
        return body, len(body)
    
    if not isinstance(body, dict):
        return [], None

    total_count = None
    for k in ("totalCount", "total_count", "total"):
        if k in body:
            try:
                total_count = int(body[k])
            except Exception:
                total_count = None
            break

    items_container = body.get("items") or body.get("item") or body.get("itemsList") or body.get("list") or body.get("data")
    if isinstance(items_container, dict) and "item" in items_container:
        items_container = items_container.get("item")

    items = []
    for it in _as_list(items_container):
        if isinstance(it, dict):
            items.append(it)
        else:
            items.append({"value": it})
    return items, total_count


def _build_headers() -> Dict[str, str]:
    ua = os.getenv("HTTP_USER_AGENT", "amously-grant-radar/0.1 (+contact: dev@amously.ai)")
    return {"User-Agent": ua}


def fetch(
    source_cfg: Optional[Dict[str, Any]] = None,
    ctx: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    K-Startup OpenAPI에서 공고/통합공고(사업소개) 정보를 가져옵니다.

    sources.yaml 예시(핵심):
      api.base_url = https://apis.data.go.kr/B552735/kisedKstartupService01
      api.endpoints.announcements = /getAnnouncementInformation01
      api.endpoints.business = /getBusinessInformation01
      api.enabled_endpoints = ["announcements","business"]
      auth.service_key_param = "ServiceKey"
      auth.service_key_env = "DATA_GO_KR_SERVICE_KEY"
      api.default_params.returnType / page / perPage

    반환 형식(raw item):
      - source: "kstartup"
      - source_id: pbanc_sn(공고일련번호) 등, 없으면 hash
      - title / url / published_at / summary / content / raw / endpoint
    """
    print("[kstartup] K-Startup OpenAPI 호출을 시작합니다.")

    # ---- 설정 로드 (환경변수 기본값)
    base_url = None
    endpoints: Dict[str, str] = {}
    enabled_endpoints: List[str] = []

    return_type = os.getenv("KSTARTUP_RETURN_TYPE", "json")
    per_page = int(os.getenv("KSTARTUP_PER_PAGE", "100"))
    max_pages = int(os.getenv("KSTARTUP_MAX_PAGES_PER_RUN", "30"))

    service_key_env = "DATA_GO_KR_SERVICE_KEY"
    service_key_param = "ServiceKey"

    if source_cfg:
        api_cfg = source_cfg.get("api", {})
        base_url = _resolve_env_placeholder(api_cfg.get("base_url"), None) or source_cfg.get("endpoint")
        endpoints = api_cfg.get("endpoints", {}) or {}
        enabled_endpoints = api_cfg.get("enabled_endpoints", []) or []

        default_params = api_cfg.get("default_params", {}) or {}
        return_type = str(_resolve_env_placeholder(default_params.get("returnType"), return_type))
        per_page = int(_resolve_env_placeholder(default_params.get("perPage"), per_page))

        incremental = api_cfg.get("incremental", {}) or {}
        max_pages = int(_resolve_env_placeholder(incremental.get("max_pages_per_run"), max_pages))

        auth_cfg = source_cfg.get("auth", {}) or {}
        service_key_env = auth_cfg.get("service_key_env", service_key_env)
        service_key_param = auth_cfg.get("service_key_param", service_key_param)

    if not base_url:
        base_url = os.getenv("KSTARTUP_BASE_URL", "https://apis.data.go.kr/B552735/kisedKstartupService01")

    # enabled_endpoints가 비어있으면 기본은 공고+통합공고
    if not enabled_endpoints:
        enabled_endpoints = ["announcements", "business"]

    # endpoints가 비어있으면 기본값 채움(승인 정보 기준)
    if not endpoints:
        endpoints = {
            "announcements": "/getAnnouncementInformation01",
            "business": "/getBusinessInformation01",
            "content": "/getContentInformation01",
            "stats": "/getStatisticalInformation01",
        }

    # 서비스키
    service_key = os.getenv(service_key_env, "").strip()
    if not service_key:
        print(f"[kstartup] 오류: 환경변수 {service_key_env} 값이 없습니다. (.env 설정 필요)")
        return []

    headers = _build_headers()

    all_items: List[Dict[str, Any]] = []

    # ---- 엔드포인트별 호출
    for ep_name in enabled_endpoints:
        path = endpoints.get(ep_name)
        if not path:
            print(f"[kstartup] 경고: 엔드포인트 '{ep_name}' 경로가 설정되어 있지 않아 건너뜁니다.")
            continue

        url = base_url.rstrip("/") + path
        print(f"[kstartup] 호출 대상: {ep_name} -> {url}")

        for page in range(1, max_pages + 1):
            params = {
                service_key_param: service_key,
                "returnType": return_type,
                "page": page,
                "perPage": per_page,
            }

            try:
                resp = requests.get(url, params=params, headers=headers, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                print(f"[kstartup] 요청 실패({ep_name}, page={page}): {e}")
                break

            # JSON 우선
            try:
                payload = resp.json()
            except Exception:
                # XML로 내려오는 경우도 있는데, 현재는 JSON 운영을 전제로 함
                print(f"[kstartup] 경고: JSON 파싱 실패({ep_name}, page={page}). returnType=json 설정을 확인하세요.")
                break

            items, total_count = _pick_items_from_json(payload)
            if not items:
                print(f"[kstartup] {ep_name}: page={page}에서 항목이 없어 종료합니다.")
                break

            # 각 아이템을 raw 표준 형태로 변환
            mapped = _map_kstartup_items(items, ep_name)
            all_items.extend(mapped)

            print(f"[kstartup] {ep_name}: page={page} 수집 {len(mapped)}건 (누적 {len(all_items)}건)")

            # 페이지 끝 조건(가능하면 total_count로 최적화)
            if total_count is not None:
                # 마지막 페이지 계산: ceil(total_count / per_page)
                last_page = (total_count + per_page - 1) // per_page
                if page >= last_page:
                    print(f"[kstartup] {ep_name}: totalCount 기준 마지막 페이지 도달({page}/{last_page}).")
                    break

            # 안전장치: 응답이 per_page보다 작으면 마지막 페이지일 가능성이 큼
            if len(items) < per_page:
                print(f"[kstartup] {ep_name}: page={page}가 마지막 페이지로 추정됩니다(응답 건수 < perPage).")
                break

    print(f"[kstartup] 전체 수집 완료: {len(all_items)}건")
    return all_items


def _map_kstartup_items(items: List[Dict[str, Any]], ep_name: str) -> List[Dict[str, Any]]:
    """
    K-Startup 각 endpoint의 item(dict)을 raw 공통 형태로 매핑합니다.
    - 실제 필드명은 API 응답에 따라 다를 수 있어, 가능한 후보 키들을 폭넓게 처리합니다.
    """
    mapped: List[Dict[str, Any]] = []

    for it in items:
        # 공고 일련번호(있으면 최우선)
        pbanc_sn = _safe_text(it.get("pbanc_sn") or it.get("pbancSn") or it.get("id") or "")
        title = _safe_text(
            it.get("pbanc_titl_nm")
            or it.get("pbancTitlNm")
            or it.get("biz_pbanc_nm")
            or it.get("bizPbancNm")
            or it.get("title")
            or ""
        )

        # 상세 URL(있으면 사용)
        url = _safe_text(it.get("detl_pg_url") or it.get("detlPgUrl") or it.get("url") or "")

        # 접수기간
        bg = _safe_text(it.get("pbanc_rcpt_bgng_dt") or it.get("pbancRcptBgngDt") or "")
        ed = _safe_text(it.get("pbanc_rcpt_end_dt") or it.get("pbancRcptEndDt") or "")

        # 요약/내용 후보
        summary = _safe_text(
            it.get("supt_biz_clsfc")
            or it.get("suptBizClsfc")
            or it.get("biz_supt_ctnt")
            or it.get("bizSuptCtnt")
            or it.get("supt_ctnt")
            or it.get("summary")
            or ""
        )
        content = _safe_text(
            it.get("pbanc_ctnt")
            or it.get("pbancCtnt")
            or it.get("supt_ctnt")
            or it.get("biz_supt_ctnt")
            or it.get("supt_biz_intrd_info")
            or it.get("suptBizIntrdInfo")
            or it.get("content")
            or ""
        )

        # published_at: 접수시작일을 게시일로 사용 (API에 등록일 필드가 없음)
        # 우선순위: 공고등록일 > 접수시작일 > 현재시간
        published_at = _safe_text(
            it.get("pbanc_reg_dt")
            or it.get("pbancRegDt")
            or it.get("reg_dt")
            or it.get("regDt")
            or bg  # 접수 시작일을 대체로 사용
            or ""
        )
        if not published_at:
            published_at = _now_iso()

        # 고유 ID가 없다면 해시로 생성
        source_id = pbanc_sn or _sha1(f"{ep_name}|{title}|{url}|{bg}|{ed}|{published_at}")

        mapped.append(
            {
                "source": "kstartup",
                "endpoint": ep_name,
                "source_id": source_id,
                "title": title,
                "url": url,
                "published_at": published_at,
                "summary": summary,
                "content": content,
                "apply_start": bg,
                "apply_end": ed,
                "raw": it,
            }
        )

    return mapped