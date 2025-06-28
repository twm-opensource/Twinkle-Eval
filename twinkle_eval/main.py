import argparse
import copy
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from twinkle_eval.exceptions import ConfigurationError

from .config import load_config
from .datasets import find_all_evaluation_files
from .evaluators import Evaluator
from .logger import log_error, log_info
from .results_exporters import ResultsExporterFactory


def create_default_config(output_path: str = "config.yaml") -> int:
    """創建預設配置檔案

    Args:
        output_path: 輸出檔案路徑，預設為 config.yaml

    Returns:
        int: 程式退出代碼（0 表示成功，1 表示失敗）
    """
    import shutil

    try:
        # 檢查檔案是否已存在
        if os.path.exists(output_path):
            response = input(f"⚠️  檔案 '{output_path}' 已存在，是否覆蓋？(y/N): ")
            if response.lower() not in ["y", "yes", "是"]:
                print("❌ 取消創建配置檔案")
                return 1

        # 找到範本檔案
        template_path = os.path.join(os.path.dirname(__file__), "config.template.yaml")

        if not os.path.exists(template_path):
            print(f"❌ 找不到配置範本檔案: {template_path}")
            return 1

        # 複製範本檔案
        shutil.copy2(template_path, output_path)

        print(f"✅ 配置檔案已創建: {output_path}")
        print()
        print("📝 接下來請編輯配置檔案，設定：")
        print("  1. LLM API 設定 (base_url, api_key)")
        print("  2. 模型名稱 (model.name)")
        print("  3. 資料集路徑 (evaluation.dataset_paths)")
        print()
        print("💡 編輯完成後，使用以下命令開始評測：")
        print(f"   twinkle-eval --config {output_path}")

        return 0

    except Exception as e:
        print(f"❌ 創建配置檔案時發生錯誤: {e}")
        return 1


class TwinkleEvalRunner:
    """Twinkle Eval 主要執行器類別 - 負責控制整個評測流程"""

    def __init__(self, config_path: str = "config.yaml"):
        """初始化 Twinkle Eval 執行器

        Args:
            config_path: 配置檔案路徑，預設為 config.yaml
        """
        self.config_path = config_path  # 配置檔案路徑
        self.config = None  # 載入的配置字典
        self.start_time = None  # 執行開始時間標記
        self.start_datetime = None  # 執行開始的 datetime 物件
        self.results_dir = "results"  # 結果輸出目錄

    def initialize(self):
        """初始化評測執行器

        載入配置、設定時間標記、建立結果目錄

        Raises:
            Exception: 初始化過程中發生錯誤
        """
        try:
            self.config = load_config(self.config_path)  # 載入配置
            self.start_time = datetime.now().strftime("%Y%m%d_%H%M")  # 生成時間標記
            self.start_datetime = datetime.now()  # 記錄開始時間

            os.makedirs(self.results_dir, exist_ok=True)  # 建立結果目錄

            log_info(f"Twinkle Eval 初始化完成 - {self.start_time}")

        except Exception as e:
            log_error(f"初始化失敗: {e}")
            raise

    def _prepare_config_for_saving(self) -> Dict[str, Any]:
        """準備用於儲存的配置資料，移除敏感資訊

        在儲存配置到結果檔案前，需要移除 API 金鑰等敏感資訊
        和不可序列化的物件實例

        Returns:
            Dict[str, Any]: 清理後的配置字典
        """
        if self.config is None:
            raise ConfigurationError("配置未載入")

        save_config = copy.deepcopy(self.config)

        # 移除敏感資訊（API 金鑰）
        if "llm_api" in save_config and "api_key" in save_config["llm_api"]:
            del save_config["llm_api"]["api_key"]

        # 移除物件實例（不可序列化）
        if "llm_instance" in save_config:
            del save_config["llm_instance"]
        if "evaluation_strategy_instance" in save_config:
            del save_config["evaluation_strategy_instance"]

        return save_config

    def _get_dataset_paths(self) -> List[str]:
        """從配置中取得資料集路徑清單

        支援單一路徑字串或路徑清單，統一轉換為清單格式

        Returns:
            List[str]: 資料集路徑清單
        """
        if self.config is None:
            raise ConfigurationError("配置未載入")

        dataset_paths = self.config["evaluation"]["dataset_paths"]
        if isinstance(dataset_paths, str):
            dataset_paths = [dataset_paths]
        return dataset_paths

    def _evaluate_dataset(self, dataset_path: str, evaluator: Evaluator) -> Dict[str, Any]:
        """評測單一資料集

        對指定資料集中的所有檔案進行評測，支援多次執行並統計結果

        Args:
            dataset_path: 資料集路徑
            evaluator: 評測器實例

        Returns:
            Dict[str, Any]: 資料集評測結果，包含準確率統計和詳細結果
        """
        if self.config is None:
            raise ConfigurationError("配置未載入")

        log_info(f"開始評測資料集: {dataset_path}")

        all_files = find_all_evaluation_files(dataset_path)  # 尋找所有評測檔案
        repeat_runs = self.config["evaluation"].get("repeat_runs", 1)  # 重複執行次數
        prompt_map = self.config["evaluation"].get("datasets_prompt_map", {})  # 資料集語言對應表
        dataset_lang = prompt_map.get(dataset_path, "zh")  # 當前資料集的語言，預設為中文

        results = []  # 儲存所有檔案的評測結果

        for idx, file_path in enumerate(all_files):
            file_accuracies = []  # 當前檔案的準確率結果
            file_results = []  # 當前檔案的詳細結果

            # 對當前檔案進行多次評測
            for run in range(repeat_runs):
                try:
                    file_path_result, accuracy, result_path = evaluator.evaluate_file(
                        file_path, f"{self.start_time}_run{run}", dataset_lang
                    )
                    file_accuracies.append(accuracy)
                    file_results.append((file_path_result, accuracy, result_path))
                except Exception as e:
                    log_error(f"評測檔案 {file_path} 失敗: {e}")
                    continue

            # 為當前檔案計算統計數據
            if file_accuracies:
                mean_accuracy = np.mean(file_accuracies)  # 平均準確率
                std_accuracy = np.std(file_accuracies) if len(file_accuracies) > 1 else 0  # 標準差

                results.append(
                    {
                        "file": file_path,
                        "accuracy_mean": mean_accuracy,
                        "accuracy_std": std_accuracy,
                        "individual_runs": {
                            "accuracies": file_accuracies,
                            "results": [r[2] for r in file_results],
                        },
                    }
                )

            # 進度指示器
            progress = (idx + 1) / len(all_files) * 100
            print(f"\r已執行 {progress:.1f}% ({idx + 1}/{len(all_files)}) ", end="")

        print()  # 進度完成後換行

        # 計算資料集統計數據
        dataset_avg_accuracy = (
            np.mean([r["accuracy_mean"] for r in results]) if results else 0
        )  # 資料集平均準確率
        dataset_avg_std = (
            np.mean([r["accuracy_std"] for r in results]) if results else 0
        )  # 資料集平均標準差

        return {
            "results": results,
            "average_accuracy": dataset_avg_accuracy,
            "average_std": dataset_avg_std,
        }

    def run_evaluation(self, export_formats: Optional[List[str]] = None) -> str:
        """執行完整的評測流程

        這是主要的評測入口點，包含以下步驟：
        1. 建立評測器
        2. 對所有資料集進行評測
        3. 統計和輸出結果

        Args:
            export_formats: 輸出格式清單，預設為 ["json"]

        Returns:
            str: 主要結果檔案路徑
        """
        if self.config is None:
            raise ConfigurationError("配置未載入")

        if export_formats is None:
            export_formats = ["json"]  # 預設輸出格式

        dataset_paths = self._get_dataset_paths()  # 取得資料集路徑
        dataset_results = {}  # 儲存所有資料集的結果

        # 建立評測器
        llm_instance = self.config["llm_instance"]
        evaluation_strategy_instance = self.config["evaluation_strategy_instance"]
        evaluator = Evaluator(llm_instance, evaluation_strategy_instance, self.config)

        # 逐一評測每個資料集
        for dataset_path in dataset_paths:
            try:
                dataset_result = self._evaluate_dataset(dataset_path, evaluator)
                dataset_results[dataset_path] = dataset_result

                message = (
                    f"資料集 {dataset_path} 評測完成，"
                    f"平均正確率: {dataset_result['average_accuracy']:.2%} "
                    f"(±{dataset_result['average_std']:.2%})"
                )
                print(message)
                log_info(message)

            except Exception as e:
                log_error(f"資料集 {dataset_path} 評測失敗: {e}")
                continue

        # 準備最終結果
        current_duration = (
            (datetime.now() - self.start_datetime).total_seconds() if self.start_datetime else 0
        )  # 計算執行時間
        final_results = {
            "timestamp": self.start_time,  # 執行時間標記
            "config": self._prepare_config_for_saving(),  # 清理後的配置
            "dataset_results": dataset_results,  # 所有資料集結果
            "duration_seconds": current_duration,  # 執行時間（秒）
        }

        # 以多種格式輸出結果
        base_output_path = os.path.join(self.results_dir, f"results_{self.start_time}")
        exported_files = ResultsExporterFactory.export_results(
            final_results, base_output_path, export_formats
        )

        log_info(f"評測完成，結果已匯出至: {', '.join(exported_files)}")
        return exported_files[0] if exported_files else ""


def create_cli_parser() -> argparse.ArgumentParser:
    """建立命令列介面解析器

    定義所有命令列參數和選項，支援多種評測和查詢功能

    Returns:
        argparse.ArgumentParser: 配置完成的命令列解析器
    """
    parser = argparse.ArgumentParser(
        description="🌟 Twinkle Eval - AI 模型評測工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  twinkle-eval                          # 使用預設配置執行
  twinkle-eval --config custom.yaml    # 使用自定義配置檔
  twinkle-eval --export json csv html  # 輸出為多種格式
  twinkle-eval --list-llms             # 列出可用的 LLM 類型
  twinkle-eval --list-strategies       # 列出可用的評測策略
        """,
    )

    parser.add_argument(
        "--config", "-c", default="config.yaml", help="配置檔案路徑 (預設: config.yaml)"
    )

    parser.add_argument(
        "--export",
        "-e",
        nargs="+",
        default=["json"],
        choices=ResultsExporterFactory.get_available_types(),
        help="輸出格式 (預設: json)",
    )

    parser.add_argument("--list-llms", action="store_true", help="列出可用的 LLM 類型")

    parser.add_argument("--list-strategies", action="store_true", help="列出可用的評測策略")

    parser.add_argument("--list-exporters", action="store_true", help="列出可用的輸出格式")

    parser.add_argument("--version", action="store_true", help="顯示版本資訊")

    parser.add_argument("--init", action="store_true", help="創建預設配置檔案")

    return parser


def main() -> int:
    """主程式入口點

    處理命令列參數並執行相應的功能，包括查詢功能和主要評測流程

    Returns:
        int: 程式退出代碼（0 表示成功，1 表示失敗）
    """
    parser = create_cli_parser()
    args = parser.parse_args()

    # 處理查詢命令
    if args.list_llms:
        from .models import LLMFactory

        print("可用的 LLM 類型:")
        for llm_type in LLMFactory.get_available_types():
            print(f"  - {llm_type}")
        return 0

    if args.list_strategies:
        from .evaluation_strategies import EvaluationStrategyFactory

        print("可用的評測策略:")
        for strategy in EvaluationStrategyFactory.get_available_types():
            print(f"  - {strategy}")
        return 0

    if args.list_exporters:
        print("可用的輸出格式:")
        for exporter in ResultsExporterFactory.get_available_types():
            print(f"  - {exporter}")
        return 0

    if args.version:
        from . import get_info

        info = get_info()
        print(f"🌟 {info['name']} v{info['version']}")
        print(f"作者: {info['author']}")
        print(f"授權: {info['license']}")
        print(f"網址: {info['url']}")
        return 0

    if args.init:
        return create_default_config()

    # 執行評測
    try:
        runner = TwinkleEvalRunner(args.config)
        runner.initialize()
        runner.run_evaluation(args.export)
    except Exception as e:
        log_error(f"執行失敗: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
