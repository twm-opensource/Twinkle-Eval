import os
import json
import pandas as pd
from logger import log_error, log_info


def find_all_evaluation_files(dataset_root):
    """遍歷 dataset_root，找到所有可讀取的評測檔案（支援子資料夾）"""
    supported_extensions = {".json", ".jsonl", ".parquet", ".csv", ".tsv"}
    all_files = []

    print(f"掃描目錄： {dataset_root}")

    for root, dirs, files in os.walk(dataset_root):
        # 跳過隱藏目錄（以"."開頭）
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


def read_evaluation_data(file_path):
    """讀取評測檔案"""
    ext = os.path.splitext(file_path)[-1].lower()
    print(f"正在讀取: {file_path}")  # 顯示正在讀取的檔案
    try:
        if ext == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif ext == ".jsonl":
            with open(file_path, "r", encoding="utf-8") as f:
                data = [json.loads(line) for line in f]
        elif ext == ".parquet":
            data = pd.read_parquet(file_path).to_dict(orient="records")
        elif ext in [".csv", ".tsv"]:
            sep = "," if ext == ".csv" else "\t"
            df = pd.read_csv(file_path, sep=sep)

            # **確保 `answer` 欄位名稱正確**
            if "answer" not in df.columns:
                raise ValueError(f"資料格式錯誤，檔案 `{file_path}` 缺少 `answer` 欄位")

            # **確保 `answer` 欄位讀取到的是正確的答案**
            for idx, row in df.iterrows():
                if isinstance(row["answer"], str):
                    row["answer"] = (
                        row["answer"].strip().upper()
                    )  # 確保比對時大小寫一致

            data = df.to_dict(orient="records")
        else:
            raise ValueError(f"不支援的檔案格式: {ext}")

        log_info(f"成功讀取檔案: {file_path}，共 {len(data)} 題")
        return data
    except Exception as e:
        log_error(f"讀取資料錯誤: {e}")
        raise e
