# Support Project Radar

정부 지원사업 및 창업 지원 기회를 자동으로 수집하고 필터링하여 Slack으로 알림하는 자동화 도구

## 프로젝트 개요

- **목적**: K-Startup 등 다양한 소스에서 지원사업 정보를 자동 수집하고, 키워드 기반 필터링을 통해 관심 사업만 추출하여 Slack 알림
- **핵심 기능**:
  - 공공 API(K-Startup OpenAPI) 및 RSS 피드에서 자동 데이터 수집
  - YAML 기반 필터링 규칙 적용 (키워드 매칭, 날짜 범위)
  - SQLite를 통한 중복 항목 제거
  - Slack Block Kit 형식의 알림 전송
  - JSON 파일로 전체 결과 저장

## 프로젝트 구조

### 디렉터리 구성

```
support-project-radar/
├── src/radar/               # 메인 애플리케이션 코드
│   ├── config.py           # 설정 로더 (YAML, 환경변수)
│   ├── main.py             # 핵심 로직 (수집, 필터링, 알림)
│   ├── connectors/         # 데이터 소스 커넥터
│   │   ├── knowhow_feed.py    # RSS 피드 파서 (feedparser 기반)
│   │   ├── kstartup_api.py    # K-Startup OpenAPI 연동
│   │   └── smtech_public.py   # (미구현) 중소벤처기업진흥공단 API
│   └── integrations/       # 외부 서비스 연동
│       └── slack.py           # Slack Webhook/Block Kit 메시지 전송
├── rules/                   # 필터링 규칙 설정 (YAML)
│   ├── rules.yaml          # 키워드 매칭 규칙, 카테고리 매핑
│   └── sources.yaml        # 데이터 소스 설정 (API 엔드포인트, 스케줄)
├── scripts/                 # 실행 스크립트
│   └── daily.py            # 일일 실행 진입점 (--publish 옵션)
├── data/                    # 데이터 저장소
│   ├── output/             # 결과 JSON 파일 (타임스탬프별)
│   └── radar.sqlite3       # 중복 제거용 SQLite DB
├── pyproject.toml          # Poetry 프로젝트 설정
└── requirements.txt        # Python 의존성 목록
```

### 주요 모듈 설명

#### 1. `src/radar/config.py`
- **역할**: 설정 로딩 및 검증
- **기능**:
  - `rules/rules.yaml`, `rules/sources.yaml` 로드
  - 환경변수 (`SLACK_WEBHOOK_URL`, `DATA_GO_KR_SERVICE_KEY` 등) 로드
  - 커넥터 지원 여부 검증 (`SUPPORTED_CONNECTORS`)
  - 활성화된 소스만 필터링하여 반환

#### 2. `src/radar/main.py`
- **역할**: 핵심 실행 로직
- **주요 함수**:
  - `run_daily()`: 전체 파이프라인 실행
    1. 설정된 소스에서 데이터 수집 (커넥터 호출)
    2. SQLite DB로 중복 항목 제거 (`filter_new_items`)
    3. 날짜 범위 필터링 (`is_within_date_range`)
    4. 키워드 매칭 규칙 적용
    5. 결과를 JSON 파일로 저장
    6. Slack 메시지 전송 (옵션)
  - `is_within_date_range()`: 접수 시작일/마감일 기준 필터링
  - `parse_date()`: 다양한 날짜 형식 파싱 (YYYYMMDD, ISO 8601)
  - `normalize_item()`: 소스별 데이터를 통일된 형식으로 변환

#### 3. `src/radar/connectors/`
- **knowhow_feed.py**: 
  - RSS/Atom 피드 파싱 (`feedparser` 라이브러리 사용)
  - `_parse_rss_with_feedparser()`: 피드 → 표준 아이템 리스트 변환
- **kstartup_api.py**:
  - K-Startup OpenAPI 연동 (`data.go.kr`)
  - `fetch()`: API 호출, 페이징 처리, 날짜 필터링
  - 지원 엔드포인트: `announcements`, `business`
  - 환경변수 플레이스홀더 처리 (`${ENV_VAR:default}`)

#### 4. `src/radar/integrations/slack.py`
- **역할**: Slack 알림 전송
- **함수**:
  - `send_rich_message()`: Block Kit 형식의 리치 메시지 전송
  - 최대 10개 항목까지 출력 (`MAX_SLACK_ITEMS`)
  - 날짜 범위, 키워드, 링크 등 포함

#### 5. `rules/rules.yaml`
- **설정 내용**:
  - `policy.always_include_if_any`: 항상 포함할 키워드 (바우처, PoC 등)
  - `must_match_any`: 그룹별 필수 매칭 키워드 (사무실, 공간, R&D 등)
  - `kstartup_taxonomy`: K-Startup 사업구분코드 매핑
  - `match_fields_default`: 검색 대상 필드 (title, summary, content 등)

#### 6. `rules/sources.yaml`
- **설정 내용**:
  - 데이터 소스별 활성화 여부 (`enabled`)
  - API 엔드포인트, 요청 파라미터
  - 스케줄 설정 (cron 표현식)
  - HTTP 설정 (타임아웃, 재시도, User-Agent)
  - 날짜 범위 (`lookback_days`)

#### 7. `scripts/daily.py`
- **역할**: CLI 진입점
- **옵션**:
  - `--publish` (기본값): Slack 알림 활성화
  - `--no-publish`: Slack 알림 비활성화 (테스트용)
- **실행 방법**:
  ```bash
  python scripts/daily.py              # Slack 전송
  python scripts/daily.py --no-publish # 로컬 테스트용
  ```

## 작동 흐름

```
1. 설정 로드 (config.py)
   ├─ rules.yaml, sources.yaml 파싱
   └─ 환경변수 검증

2. 데이터 수집 (main.py → connectors/)
   ├─ kstartup_api: OpenAPI 호출 → announcements, business 데이터
   └─ knowhow_feed: RSS 피드 파싱 (활성화 시)

3. 중복 제거 (SQLite)
   └─ seen_items 테이블에서 source_id 기준 필터링

4. 날짜 필터링
   ├─ 접수 시작일: 최근 N일 이내 (LOOKBACK_DAYS)
   └─ 마감일: 오늘 이후 (아직 마감 안 됨)

5. 키워드 매칭
   ├─ always_include_if_any: 필수 키워드
   └─ must_match_any: 그룹별 키워드 (OR 조건)

6. 결과 저장 및 알림
   ├─ data/output/results_YYYYMMDD_HHMMSS.json
   └─ Slack 메시지 전송 (Block Kit)
```

## 환경변수 설정

```.env
# Slack 알림
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# K-Startup API 인증
DATA_GO_KR_SERVICE_KEY=your_api_key_here

# 선택적 설정
LOOKBACK_DAYS=7                # 날짜 필터링 기준 (기본값: 7일)
KSTARTUP_PER_PAGE=100          # API 페이지당 항목 수
SQLITE_PATH=./data/radar.sqlite3
OUTPUT_DIR=./data/output
```

## 의존성

```toml
python = "^3.9"
pydantic = "^1.10.0"
requests = "^2.28.0"
feedparser = "^6.0.10"       # RSS 파싱
sqlite-utils = "^3.31.0"     # SQLite 유틸리티
slack-sdk = "^3.19.0"        # Slack API
pyyaml = "^6.0"              # YAML 파싱
```

## 실행 예시

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정 (.env 파일 생성)

# 3. 일일 실행 (Slack 전송)
python scripts/daily.py

# 4. 테스트 실행 (Slack 전송 안 함)
python scripts/daily.py --no-publish
```

## 출력 결과

### JSON 파일 (`data/output/results_*.json`)
```json
{
  "generated_at": "2026-02-10T09:00:00+00:00",
  "total_count": 5,
  "items": [
    {
      "source": "kstartup",
      "source_id": "abc123...",
      "title": "2026년 창업기업 R&D 지원사업",
      "link": "https://...",
      "apply_start": "20260201",
      "apply_end": "20260228",
      "keywords": ["R&D", "기술개발"]
    }
  ]
}
```

### Slack 메시지
- Block Kit 형식의 리치 메시지
- 최대 10개 항목 표시
- 제목, 링크, 신청기간, 키워드 포함
