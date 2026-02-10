import logging
import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from radar.config import config
from radar.connectors.knowhow_feed import _parse_rss_with_feedparser
from radar.connectors.kstartup_api import fetch as fetch_kstartup
from radar.integrations.slack import send_rich_message

# 설정값
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "7"))  # 게시일 기준 며칠 이내인지 설정하여 최신 항복 필터링 
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./data/output")


def get_db_connection():
    """SQLite DB 연결 (없으면 생성)"""
    db_path = os.getenv("SQLITE_PATH", "./data/radar.sqlite3")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    
    # 테이블 생성 (없으면)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_items (
            source_id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            url TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    return conn


def parse_date(date_str: str) -> Optional[datetime]:
    """다양한 날짜 형식을 파싱 (timezone 제거, naive datetime 반환)"""
    if not date_str:
        return None
    
    # timezone 정보 제거
    date_str_clean = date_str.split("+")[0].split("Z")[0]
    
    # YYYYMMDD 형식 (K-Startup)
    if len(date_str) == 8 and date_str.isdigit():
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            pass
    
    # ISO 형식에서 날짜만 추출
    if "T" in date_str_clean:
        date_str_clean = date_str_clean.split("T")[0]
    
    # 다양한 형식 시도
    formats = [
        "%Y-%m-%d",     # Simple date
        "%Y/%m/%d",     # Slash format
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str_clean[:10], fmt)
        except (ValueError, TypeError):
            continue
    
    return None


def is_within_date_range(item: Dict[str, Any], lookback_days: int) -> bool:
    """
    아이템이 날짜 범위 내에 있는지 확인
    
    조건:
    1. 접수 시작일(apply_start 또는 published_at)이 lookback_days 일 이내
    2. AND 마감일(apply_end)이 아직 지나지 않음
    
    둘 다 만족해야 True 반환
    """
    today = datetime.now()
    cutoff_date = today - timedelta(days=lookback_days)
    
    # 접수 시작일 확인 (apply_start 우선, 없으면 published_at)
    start_date_str = item.get("apply_start", "") or item.get("published_at", "")
    start_date = parse_date(start_date_str)
    
    # 마감일 확인
    apply_end = parse_date(item.get("apply_end", ""))
    
    # 조건 1: 접수 시작일이 최근 N일 이내
    is_recent = start_date and start_date >= cutoff_date
    
    # 조건 2: 마감일이 오늘 이후 (아직 마감 안됨)
    is_not_expired = apply_end and apply_end >= today
    
    # 둘 다 만족해야 함
    return is_recent and is_not_expired


def filter_new_items(items: List[Dict[str, Any]], conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """이미 본 항목을 제외하고 새로운 항목만 반환"""
    new_items = []
    cursor = conn.cursor()
    
    for item in items:
        source_id = item.get("source_id", "")
        if not source_id:
            continue
            
        # 이미 존재하는지 확인
        cursor.execute("SELECT 1 FROM seen_items WHERE source_id = ?", (source_id,))
        if cursor.fetchone() is None:
            new_items.append(item)
            # 새 항목을 DB에 저장
            cursor.execute(
                "INSERT INTO seen_items (source_id, source, title, url, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    source_id,
                    item.get("source", ""),
                    item.get("title", ""),
                    item.get("url", ""),
                    datetime.now().isoformat()
                )
            )
    
    conn.commit()
    return new_items


def save_results_to_file(items: List[Dict[str, Any]], filename: str = None):
    """결과를 JSON 파일로 저장"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if filename is None:
        filename = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_count": len(items),
            "items": items
        }, f, ensure_ascii=False, indent=2)
    
    logging.info(f"Results saved to: {filepath}")
    return filepath


def format_results_for_console(results: List[Dict[str, Any]]):
    print("\n=== 수집 결과 ===")
    if not results:
        print("새로운 항목이 없습니다.")
        return
    
    print(f"총 {len(results)}건의 매칭 항목:\n")
    for i, item in enumerate(results[:10], 1):  # 콘솔에는 최대 10개만 출력
        title = item.get("title") or "제목 없음"
        link = item.get("link") or item.get("url") or "N/A"
        apply_start = item.get("apply_start", "")
        apply_end = item.get("apply_end", "")
        keywords = item.get("keywords", [])
        
        print(f"{i}. {title}")
        print(f"   출처: {item.get('source', 'N/A')}")
        if apply_start and apply_end:
            print(f"   신청기간: {apply_start} ~ {apply_end}")
        print(f"   링크: {link}")
        print(f"   키워드: {', '.join(keywords)}")
        print()
    
    if len(results) > 10:
        print(f"... 외 {len(results) - 10}건")


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """다양한 소스의 아이템을 통일된 형식으로 변환"""
    return {
        "source": item.get("source", ""),
        "source_id": item.get("source_id", ""),
        "title": item.get("title", ""),
        "link": item.get("url", "") or item.get("link", ""),
        "date": item.get("published_at", "") or item.get("date", ""),
        "apply_start": item.get("apply_start", ""),
        "apply_end": item.get("apply_end", ""),
        "summary": item.get("summary", ""),
        "content": item.get("content", ""),
        "keywords": item.get("keywords", []),
    }


def run_daily(publish: bool = True):
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting daily execution...")

    # Load configuration
    sources = config.sources
    rules = config.rules

    # DB 연결
    conn = get_db_connection()

    # Collect data from enabled sources
    raw_items = []
    for source_id, source_cfg in sources.items():
        connector = source_cfg.get("connector", "")
        logging.info(f"Processing source: {source_id} (connector: {connector})")
        
        if connector == "knowhow_feed":
            # RSS 피드 URL에서 데이터 수집
            rss_config = source_cfg.get("rss", {})
            feed_url = rss_config.get("feed_url", "")
            if feed_url:
                items = _parse_rss_with_feedparser(feed_url)
                logging.info(f"  -> knowhow: {len(items)}건 수집")
                raw_items.extend(items)
                
        elif connector == "kstartup_api":
            # K-Startup OpenAPI에서 데이터 수집
            items = fetch_kstartup(source_cfg)
            logging.info(f"  -> kstartup: {len(items)}건 수집")
            raw_items.extend(items)
            
        # smtech, bizinfo 등은 추후 구현

    logging.info(f"Collected {len(raw_items)} raw items total")

    # 새로운 항목만 필터링 (이미 본 항목 제외)
    new_items = filter_new_items(raw_items, conn)
    logging.info(f"New items (not seen before): {len(new_items)}")

    # 날짜 필터링: 게시일 기준 LOOKBACK_DAYS 이내 또는 마감일이 지나지 않은 항목만
    date_filtered_items = [
        item for item in new_items 
        if is_within_date_range(item, LOOKBACK_DAYS)
    ]
    logging.info(f"Date filtered (접수시작 {LOOKBACK_DAYS}일 이내 & 마감 전): {len(date_filtered_items)}건")

    # Apply rules to filter/tag items
    filtered_items = []
    
    # rules.yaml에서 필터링 규칙 추출
    policy = rules.get("policy", {})
    always_include = policy.get("always_include_if_any", [])
    must_match_groups = rules.get("must_match_any", [])
    
    for item in date_filtered_items:
        title = item.get("title", "")
        summary = item.get("summary", "")
        content = item.get("content", "")
        search_text = f"{title} {summary} {content}".lower()
        
        matched_keywords = []
        
        # always_include 키워드 체크
        for keyword in always_include:
            if keyword.lower() in search_text:
                matched_keywords.append(keyword)
        
        # must_match_any 그룹 체크
        for group in must_match_groups:
            group_keywords = group.get("any", [])
            for keyword in group_keywords:
                if keyword.lower() in search_text:
                    matched_keywords.append(keyword)
        
        if matched_keywords:
            item["keywords"] = list(set(matched_keywords))
            filtered_items.append(normalize_item(item))

    logging.info(f"Filtered to {len(filtered_items)} items (matching keywords)")
    
    conn.close()

    # 전체 결과를 JSON 파일로 저장 (나머지 항목도 조회 가능)
    if filtered_items:
        result_file = save_results_to_file(filtered_items)
        print(f"\n[FILE] 전체 결과는 다음 파일에서 확인할 수 있습니다: {result_file}")

    # Print results to console for GitHub Actions logs
    format_results_for_console(filtered_items)

    # Send results to Slack
    if publish:
        logging.info("Sending results to Slack...")
        send_rich_message(filtered_items, lookback_days=LOOKBACK_DAYS)
        logging.info("Slack message sent successfully")
    else:
        logging.info("Slack publishing disabled (--no-publish)")

if __name__ == "__main__":
    run_daily()