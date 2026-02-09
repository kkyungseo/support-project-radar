import os
import yaml

class Config:
    def __init__(self):
        self.env = self.load_env()
        self.rules = self.load_yaml("rules/rules.yaml")
        self.sources = self.load_yaml("rules/sources.yaml")

    def load_env(self):
        return {
            "SLACK_TOKEN": os.getenv("SLACK_TOKEN"),
            "KSTARTUP_API_KEY": os.getenv("KSTARTUP_API_KEY"),
        }

    def load_yaml(self, path):
        with open(path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)

config = Config()