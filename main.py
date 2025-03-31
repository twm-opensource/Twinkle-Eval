import os
import json
import copy
import numpy as np
from datetime import datetime
from config import load_config
from data_loader import find_all_evaluation_files
from evaluator import evaluate_file
from logger import log_info

if __name__ == "__main__":
    start_time = datetime.now().strftime("%Y%m%d_%H%M")
    start_datetime = datetime.now()  # 記錄實際開始時間
    config = load_config()
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)
    output_path = os.path.join(results_dir, f"results_{start_time}.json")

    # 確保 dataset_path 為列表
    dataset_paths = config["evaluation"]["dataset_paths"]
    if isinstance(dataset_paths, str):
        dataset_paths = [dataset_paths]

    dataset_results = {}
    # 避免將 API 金鑰存入結果檔案
    save_config = copy.deepcopy(config)
    if "llm_api" in save_config and "api_key" in save_config["llm_api"]:
        del save_config["llm_api"]["api_key"]

    final_results = {
        "timestamp": start_time,
        "config": save_config,
        "dataset_results": dataset_results,
    }

    for dataset_path in dataset_paths:
        all_files = find_all_evaluation_files(dataset_path)
        repeat_runs = config["evaluation"].get("repeat_runs", 1)

        results = []
        for f in all_files:
            file_accuracies = []
            file_results = []
            for run in range(repeat_runs):
                result = evaluate_file(config, f, f"{start_time}_run{run}")
                file_accuracies.append(result[1])
                file_results.append(result)

            progress = (all_files.index(f) + 1) / len(all_files) * 100
            print(
                f"\r已執行 {progress:.1f}% ({all_files.index(f) + 1}/{len(all_files)}) ",
                end="",
            )

            mean_accuracy = np.mean(file_accuracies)
            std_accuracy = np.std(file_accuracies) if len(file_accuracies) > 1 else 0

            results.append(
                {
                    "file": f,
                    "accuracy_mean": mean_accuracy,
                    "accuracy_std": std_accuracy,
                    "individual_runs": {
                        "accuracies": file_accuracies,
                        "results": [r[2] for r in file_results],
                    },
                }
            )

        # 計算此資料集的平均正確率
        dataset_avg_accuracy = (
            np.mean([r["accuracy_mean"] for r in results]) if results else 0
        )
        dataset_avg_std = (
            np.mean([r["accuracy_std"] for r in results]) if results else 0
        )

        dataset_results[dataset_path] = {
            "results": results,
            "average_accuracy": dataset_avg_accuracy,
            "average_std": dataset_avg_std,
        }

        # 即時寫入當前資料集的結果
        current_duration = (datetime.now() - start_datetime).total_seconds()
        final_results["duration_seconds"] = current_duration

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_results, f, indent=4, ensure_ascii=False)

        message = f"資料集 {dataset_path} 評測完成，平均正確率: {dataset_avg_accuracy:.2%} (±{dataset_avg_std:.2%})"
        print(message)
        log_info(message)

    log_info(f"評測完成，結果儲存至 {output_path}")
