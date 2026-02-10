import os
import yaml
from typing import Dict, Any

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
        with open(path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    def load_sources(self, path: str) -> Dict[str, Any]:
        data = self.load_yaml(path)
        sources_list = data.get("sources", [])
        return {src["id"]: src for src in sources_list if src.get("enabled", False)}

config = Config()