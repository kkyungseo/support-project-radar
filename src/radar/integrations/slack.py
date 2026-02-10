import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


def send_to_slack(message: str) -> None:
    """단순 텍스트 메시지 전송"""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("SLACK_WEBHOOK_URL 환경 변수가 설정되지 않았습니다.")

    payload = {"text": message}
    response = requests.post(webhook_url, json=payload)

    if response.status_code != 200:
        raise ValueError(f"Slack 요청 오류: {response.status_code}, 응답 내용: {response.text}")


MAX_SLACK_ITEMS = 10  # Slack 블록 제한으로 최대 10개 항목만 전송


def send_rich_message(
    items: List[Dict[str, Any]], 
    title: Optional[str] = None,
    lookback_days: int = 7
) -> None:
    """
    Block Kit 스타일의 리치 메시지 전송
    
    Args:
        items: 전송할 아이템 목록
        title: 메시지 제목 (선택)
        lookback_days: 조회 기간 (일)
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("SLACK_WEBHOOK_URL 환경 변수가 설정되지 않았습니다.")

    # 날짜 범위 계산
    today = datetime.now()
    start_date = today - timedelta(days=lookback_days)
    date_range_str = f"{start_date.strftime('%m/%d')} ~ {today.strftime('%m/%d')}"
    today_str = today.strftime('%Y-%m-%d')

    # 항목 수 제한
    total_count = len(items)
    display_items = items[:MAX_SLACK_ITEMS]

    if not items:
        # 새로운 항목이 없을 때
        payload = {
            "text": f"[{today_str}] 최근 {lookback_days}일간 새로운 지원사업 공고가 없습니다.",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📋 *[{today_str}] 최근 {lookback_days}일간 ({date_range_str}) 새로운 지원사업 공고가 없습니다.*"
                    }
                }
            ]
        }
    else:
        # 헤더 블록
        # 헤더 텍스트 (날짜 범위 포함)
        if title:
            header_text = title
        elif total_count > MAX_SLACK_ITEMS:
            header_text = f"[{today_str}] {date_range_str} 공고 ({total_count}건 중 {MAX_SLACK_ITEMS}건)"
        else:
            header_text = f"[{today_str}] {date_range_str} 공고 ({total_count}건)"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text,
                    "emoji": True
                }
            },
            {"type": "divider"}
        ]

        # 각 아이템에 대한 블록 생성 (제한된 수만)
        for item in display_items:
            item_title = item.get("title") or "제목 없음"
            item_link = item.get("link") or item.get("url") or ""
            item_date = item.get("date") or item.get("published_at") or ""
            apply_start = item.get("apply_start", "")
            apply_end = item.get("apply_end", "")
            item_keywords = item.get("keywords", [])
            item_summary = (item.get("summary") or item.get("content") or "")[:150]  # 요약은 150자로 제한

            # 키워드 태그 생성
            keywords_text = " ".join([f"`{kw}`" for kw in item_keywords]) if item_keywords else ""

            # 링크가 있으면 클릭 가능하게, 없으면 제목만
            if item_link:
                section_text = f"*<{item_link}|{item_title}>*\n"
            else:
                section_text = f"*{item_title}*\n"
            
            # 신청 기간 표시 (apply_start ~ apply_end)
            if apply_start and apply_end:
                section_text += f"📅 신청기간: {apply_start} ~ {apply_end}\n"
            elif item_date:
                section_text += f"📅 {item_date}\n"
            
            if item_summary:
                section_text += f"{item_summary}\n"
            if keywords_text:
                section_text += f"🏷️ {keywords_text}"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": section_text
                }
            })
            blocks.append({"type": "divider"})

        # 푸터
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "🤖 Support Project Radar에서 자동 발송된 메시지입니다."
                }
            ]
        })

        payload = {
            "text": f"새로운 지원사업 공고 {total_count}건이 도착했습니다.",
            "blocks": blocks
        }

    response = requests.post(webhook_url, json=payload)

    if response.status_code != 200:
        raise ValueError(f"Slack 요청 오류: {response.status_code}, 응답 내용: {response.text}")