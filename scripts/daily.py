"""
scripts/daily.py

Simplified daily.py
- Fetch data from sources
- Filter based on keywords
- Send results to Slack
"""

from __future__ import annotations

import sys
import os
import argparse

# src 디렉터리를 Python 경로에 추가
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../src'))

from radar.main import run_daily

def main():
    parser = argparse.ArgumentParser(description="Daily radar script for fetching and publishing data")
    parser.add_argument(
        "--publish",
        action="store_true",
        default=True,  # 기본값: Slack 전송 활성화
        help="Enable Slack message publishing (default: enabled)"
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Disable Slack message publishing"
    )
    args = parser.parse_args()
    
    # --no-publish가 지정되면 publish=False
    publish = not args.no_publish
    
    run_daily(publish=publish)

if __name__ == "__main__":
    main()