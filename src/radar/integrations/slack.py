import os
import requests

def send_to_slack(message):
    # 환경 변수에서 Webhook URL 읽기
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("SLACK_WEBHOOK_URL 환경 변수가 설정되지 않았습니다. Slack Webhook URL을 환경 변수로 추가하세요.")

    payload = {"text": message}
    response = requests.post(webhook_url, json=payload)

    if response.status_code != 200:
        raise ValueError(f"Slack 요청 오류: {response.status_code}, 응답 내용: {response.text}")