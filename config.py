import os
import yaml


def load_config(config_path="config.yaml"):
    """讀取並解析 config.yaml，確保所有必要欄位都存在"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"設定檔 {config_path} 不存在")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    required_keys = ["llm_api", "model", "evaluation"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"設定檔缺少必要欄位: {key}")

    return config
