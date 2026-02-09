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

# src 디렉터리를 Python 경로에 추가
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../src'))

from radar.main import run_daily

if __name__ == "__main__":
    run_daily(publish=False)  # Slack 전송 비활성화