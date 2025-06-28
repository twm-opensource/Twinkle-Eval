"""資料集載入和處理模組

支援多種檔案格式的資料集載入，包括 JSON、JSONL、Parquet、CSV 和 TSV
"""

import json
import os

import pandas as pd

from .logger import log_error, log_info


class Dataset:
    """資料集類別 - 負責載入和管理單一資料集檔案

    支援多種檔案格式：
    - JSON: 單一 JSON 物件
    - JSONL: 每行一個 JSON 物件
    - Parquet: Apache Parquet 格式
    - CSV/TSV: 逗號或制表符分隔的文字檔
    """

    def __init__(self, file_path: str):
        """初始化資料集

        Args:
            file_path: 資料集檔案路徑
        """
        self.file_path = file_path
        self.data = self._load_data()

    def _load_data(self):
        ext = os.path.splitext(self.file_path)[-1].lower()
        print(f"正在讀取: {self.file_path}")
        try:
            if ext == ".json":  # [{}...]
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            elif ext == ".jsonl":
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = [json.loads(line) for line in f]
            elif ext == ".parquet":
                df = pd.read_parquet(self.file_path)
                # 驗證必要欄位
                if "question" not in df.columns:
                    raise ValueError(f"資料格式錯誤，檔案 `{self.file_path}` 缺少 `question` 欄位")
                if "answer" not in df.columns:
                    raise ValueError(f"資料格式錯誤，檔案 `{self.file_path}` 缺少 `answer` 欄位")
                # 處理 answer 欄位
                df["answer"] = df["answer"].astype(str).str.strip().str.upper()
                data = df.to_dict(orient="records")
            elif ext in [".csv", ".tsv"]:
                sep = "," if ext == ".csv" else "\t"
                df = pd.read_csv(self.file_path, sep=sep)
                # 驗證必要欄位
                if "question" not in df.columns:
                    raise ValueError(f"資料格式錯誤，檔案 `{self.file_path}` 缺少 `question` 欄位")
                if "answer" not in df.columns:
                    raise ValueError(f"資料格式錯誤，檔案 `{self.file_path}` 缺少 `answer` 欄位")
                # 處理 answer 欄位
                df["answer"] = df["answer"].astype(str).str.strip().str.upper()
                data = df.to_dict(orient="records")
            else:
                raise ValueError(f"不支援的檔案格式: {ext}")

            log_info(f"成功讀取檔案: {self.file_path}，共 {len(data)} 題")
            return data
        except Exception as e:
            log_error(f"讀取資料錯誤: {e}")
            raise e

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)


def find_all_evaluation_files(dataset_root: str) -> list:
    """在指定目錄中遞迴搜尋所有支援的評測檔案

    支援的檔案格式包括：.json, .jsonl, .parquet, .csv, .tsv
    會自動忽略以點開頭的隱藏目錄

    Args:
        dataset_root: 資料集根目錄路徑

    Returns:
        list: 找到的所有評測檔案路徑列表

    Raises:
        FileNotFoundError: 當指定目錄中找不到任何支援的檔案時
    """
    supported_extensions = {".json", ".jsonl", ".parquet", ".csv", ".tsv"}  # 支援的檔案副檔名
    all_files = []

    print(f"掃描目錄： {dataset_root}")
    for root, dirs, files in os.walk(dataset_root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[-1].lower()
            if ext in supported_extensions:
                all_files.append(file_path)
            else:
                print(f"⚠️ Warning: 跳過不支援的檔案 {file_path} (副檔名: {ext})")
    if not all_files:
        raise FileNotFoundError(f"在 {dataset_root} 下未找到可讀取的評測檔案")
    log_info(f"評測集資料夾： {dataset_root}")
    log_info(f"發現 {len(all_files)} 個評測檔案")
    return all_files
