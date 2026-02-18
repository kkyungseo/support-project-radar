import os
import logging
import yaml
from typing import Dict, Any

# 지원되는 커넥터 목록 (실제 구현 상태)
SUPPORTED_CONNECTORS = {
    "knowhow_feed": True,      # 구현 완료
    "kstartup_api": True,      # 구현 완료
    "smtech_public": False,    # 미완성 (비활성화 권장)
    "bizinfo_public": False,   # 미구현
}

class Config:
    def __init__(self):
        self.env = self.load_env()
        self.rules = self.load_yaml("rules/rules.yaml")
        self.sources = self.load_sources("rules/sources.yaml")

    def load_env(self):
        from dotenv import load_dotenv
        load_dotenv()
        return {
            # Slack 설정
            "SLACK_WEBHOOK_URL": os.getenv("SLACK_WEBHOOK_URL"),
            "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN"),
            "SLACK_POST_CHANNEL_ID": os.getenv("SLACK_POST_CHANNEL_ID"),
            # K-Startup API 설정
            "DATA_GO_KR_SERVICE_KEY": os.getenv("DATA_GO_KR_SERVICE_KEY"),
            "KSTARTUP_BASE_URL": os.getenv("KSTARTUP_BASE_URL"),
        }

    def load_yaml(self, path: str) -> Any:
        # 프로젝트 루트 기준 절대 경로로 변환
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        full_path = os.path.join(base_dir, path)
        with open(full_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    def load_sources(self, path: str) -> Dict[str, Any]:
        data = self.load_yaml(path)
        sources_list = data.get("sources", [])
        
        enabled_sources = {}
        for src in sources_list:
            if not src.get("enabled", False):
                continue
                
            source_id = src["id"]
            connector = src.get("connector", "")
            
            # 커넥터 지원 여부 검증
            if connector not in SUPPORTED_CONNECTORS:
                logging.warning(
                    f"[Config] 소스 '{source_id}': 알 수 없는 커넥터 '{connector}'. 건너뜁니다."
                )
                continue
                
            if not SUPPORTED_CONNECTORS[connector]:
                logging.warning(
                    f"[Config] 소스 '{source_id}': 커넥터 '{connector}'가 아직 구현되지 않았습니다. "
                    f"sources.yaml에서 enabled: false로 설정해주세요."
                )
                continue
            
            enabled_sources[source_id] = src
            
        return enabled_sources

config = Config()