import argparse
from twinkle_eval import TwinkleEvalRunner
import json, pandas as pd, os, random, glob, yaml, tempfile, numpy as np
from collections import Counter
from datetime import datetime


# === 🧩 抽樣功能 ===
def prepare_sample_dataset(src_path, sample_path, n=50, seed=42):
    """從原始資料集中抽樣 N 題，輸出到暫存資料夾"""
    os.makedirs(sample_path, exist_ok=True)
    random.seed(seed)
    for file in glob.glob(os.path.join(src_path, "*.csv")):
        df = pd.read_csv(file)
        if len(df) > n:
            df = df.sample(n=n, random_state=seed)
        dst_file = os.path.join(sample_path, os.path.basename(file))
        df.to_csv(dst_file, index=False, encoding="utf-8-sig")
        print(f"📁 已抽樣 {len(df)} 題 -> {dst_file}")
    return sample_path


# === 🚀 跑 Twinkle-Eval ===
def run_taigi_evaluation(config_path="config.yaml", sample_path=None):
    """執行台語試題評測，允許動態指定抽樣資料夾"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if sample_path:
        config["evaluation"]["dataset_paths"] = [sample_path]
        print(f"📂 使用抽樣後資料集: {sample_path}")

    # 建立暫存 YAML 檔給 Twinkle-Eval
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml", encoding="utf-8") as tmp:
        yaml.dump(config, tmp, allow_unicode=True)
        tmp_path = tmp.name

    runner = TwinkleEvalRunner(tmp_path)
    print("🔧 初始化評測環境...")
    runner.initialize()
    print("🚀 開始評測...")
    results = runner.run_evaluation(export_formats=["json", "csv", "html"])
    print(f"\n✅ 評測完成! 📁 結果已儲存至: {results}")
    return results


# === 📊 結果分析 ===
def analyze_results(result_file):
    """分析評測結果：自動偵測 Twinkle-Eval 結構"""
    import json

    if result_file.endswith(".json"):
        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        print("\n" + "=" * 50)
        print("📊 評測結果分析 (Summary)")
        print("=" * 50)

        acc, std = 0, 0

        # ✅ 支援多種版本結構
        if "dataset_results" in data:
            dataset_dict = next(iter(data["dataset_results"].values()))
            acc = dataset_dict.get("average_accuracy", 0)
            std = dataset_dict.get("average_std", 0)
        elif "datasets" in data:
            first = data["datasets"][0]
            acc = first.get("avg_accuracy", 0)
            std = first.get("std_accuracy", 0)
        else:
            acc = (
                data.get("overall_accuracy")
                or data.get("average_accuracy")
                or data.get("accuracy")
                or 0
            )
            std = (
                data.get("overall_std")
                or data.get("std_accuracy")
                or 0
            )

        print(f"\n平均準確率: {acc:.2%}")
        print(f"標準差: {std:.2%}")
        return acc

    # === 逐題 jsonl ===
    with open(result_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    if not lines:
        print("⚠️ 檔案為空，無法分析。")
        return 0

    total = len(lines)
    correct = sum(1 for x in lines if x.get("is_correct"))
    acc = correct / total if total > 0 else 0

    print("\n" + "=" * 50)
    print("📊 評測結果分析 (逐題)")
    print("=" * 50)
    print(f"總題數: {total}")
    print(f"答對題數: {correct}")
    print(f"答錯題數: {total - correct}")
    print(f"推算準確率: {acc:.2%}")
    return acc


# === 🧮 主流程 ===
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="執行 Twinkle-Eval 隨機抽樣評測.")
    parser.add_argument(
        "--src_dir", 
        type=str, 
        default="dataset", # 預設值改為相對路徑，較通用
        help="原始資料集 (.csv) 所在的路徑。"
    )
    parser.add_argument(
        "--sample_dir", 
        type=str, 
        default="dataset_sampled", # 預設值改為相對路徑
        help="暫存抽樣資料集要輸出的路徑。"
    )
    parser.add_argument(
        "--num_rounds", 
        type=int, 
        default=5, 
        help="執行抽樣評測的輪數 (迴圈次數)。"
    )
    parser.add_argument(
        "--sample_n", 
        type=int, 
        default=50, 
        help="每輪抽樣的題目數量 (n)。"
    )
    args = parser.parse_args()

    # 使用傳入的參數
    SRC = args.src_dir
    SAMPLE = args.sample_dir

    os.makedirs("results", exist_ok=True)
    summary_records = []

    for i in range(5):
        print(f"\n==============================")
        print(f"🔁 第 {i+1} 次抽樣與評測")
        print(f"==============================")

        seed = random.randint(1, 9999)
        prepare_sample_dataset(SRC, SAMPLE, n=args.sample_n, seed=seed)

        # === 記錄舊檔，避免多重附加 ===
        existing_files = set(glob.glob("results/*.json*"))
        run_taigi_evaluation("config.yaml", sample_path=SAMPLE)

        # === 找出新檔並改名 ===
        new_files = set(glob.glob("results/*.json*")) - existing_files
        renamed_files = []
        for f in new_files:
            if f.endswith(".jsonl"):
                new_name = f.replace(".jsonl", f"_round{i+1}.jsonl")
            elif f.endswith(".json"):
                new_name = f.replace(".json", f"_round{i+1}.json")
            else:
                continue
            os.rename(f, new_name)
            renamed_files.append(new_name)

        # === 找出 summary 分析 ===
        json_summaries = [f for f in renamed_files if f.endswith(".json")]
        acc = 0
        if json_summaries:
            acc = analyze_results(json_summaries[0])
        summary_records.append({"round": i + 1, "seed": seed, "accuracy": acc})

    # === 🧾 輸出五輪總結 ===
    if summary_records:
        df = pd.DataFrame(summary_records)
        mean_acc = df["accuracy"].mean()
        std_acc = df["accuracy"].std()
        df.to_csv("results/summary.csv", index=False, encoding="utf-8-sig")

        print("\n" + "=" * 50)
        print(f"🏁 五輪平均準確率: {mean_acc:.2%} (±{std_acc:.2%})")
        print(f"📊 詳細結果已輸出: results/summary.csv")
        print("=" * 50)