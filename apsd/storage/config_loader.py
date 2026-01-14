import yaml
import os
from apsd.models.config import SystemConfig

class ConfigLoader:
    @staticmethod
    def load_config(path: str) -> SystemConfig:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")
            
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        # Pydantic 會自動驗證型別與預設值
        return SystemConfig(**data)
