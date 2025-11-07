"""
analysis_pipeline.py
整合性 LLM 評測結果分析腳本
---------------------------------------------------------
步驟：
1. 掃描 summary.csv 並繪製總準確率圖
2. 讀取所有 eval_results_*.jsonl 檔案
3. 錯誤選項偏好分析
4. 題目長度錯誤率分析
5. 各輪抽樣下長度穩定性分析 (FacetGrid)
輸出：
01_overall_accuracy.png
02_choice_bias.png
03_length_error_rate.png
04_length_stability_by_round.png
---------------------------------------------------------
"""

import os
import json
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# -----------------------------------------------------
# 設定 Matplotlib 中文字體（根據系統調整）
# -----------------------------------------------------
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# -----------------------------------------------------
# 顯示當前工作資料夾
# -----------------------------------------------------
CWD = os.getcwd()
print(f"📂 當前工作目錄: {CWD}")

# -----------------------------------------------------
# 模式定義
# -----------------------------------------------------
JSONL_PATTERN = "**/eval_results_*.jsonl"
CSV_PATTERN = "**/summary.csv"

# -----------------------------------------------------
# 輔助函式
# -----------------------------------------------------
def find_correctness_column(df):
    """找出正確性欄位 (True/False 或 1.0/0.0)"""
    possible_keys = ['is_correct', 'correct', 'accuracy']
    for key in possible_keys:
        if key in df.columns:
            if df[key].dtype == bool:
                print(f"✅ 找到正確性欄位: '{key}' (布林)")
                return key
            elif df[key].isin([0.0, 1.0]).all():
                df['is_correct_flag'] = df[key].astype(bool)
                print(f"✅ 找到正確性欄位: '{key}' (0/1 轉布林)")
                return 'is_correct_flag'
    print("❌ 找不到標準正確性欄位，請檢查 JSONL。")
    return None

# -----------------------------------------------------
# 步驟 1: 總體結果分析
# -----------------------------------------------------
print("\n--- Step 1: Summary 分析 ---")

summary_files = glob.glob(CSV_PATTERN, recursive=True)
df_summary = None

if summary_files:
    summary_path = summary_files[0]
    print(f"✅ 找到 Summary 檔案: {summary_path}")
    df_summary = pd.read_csv(summary_path)

    if df_summary['accuracy'].max() > 1.0:
        df_summary['accuracy'] /= 100

    mean_acc = df_summary['accuracy'].mean()
    std_acc = df_summary['accuracy'].std()

    print(f"平均準確率: {mean_acc:.2%} ± {std_acc:.2%}")

    plt.figure(figsize=(8, 5))
    sns.barplot(x='round', y='accuracy', data=df_summary, color='skyblue')
    plt.axhline(mean_acc, color='red', linestyle='--', label=f'平均: {mean_acc:.2%}')
    plt.title('各輪隨機抽樣準確率比較')
    plt.xlabel('評測輪次 (Round)')
    plt.ylabel('準確率')
    plt.legend()
    plt.tight_layout()
    plt.savefig('01_overall_accuracy.png', dpi=300)
    print("📊 已輸出圖檔: 01_overall_accuracy.png")
else:
    print("⚠️ 未找到 summary.csv，跳過步驟 1。")

# -----------------------------------------------------
# 步驟 2: 讀取逐題 JSONL
# -----------------------------------------------------
print("\n--- Step 2: 讀取 JSONL ---")

jsonl_files = glob.glob(JSONL_PATTERN, recursive=True)
print(f"找到 {len(jsonl_files)} 個 JSONL 檔案。")

all_records = []
for f in jsonl_files:
    if os.path.getsize(f) == 0:
        continue
    with open(f, 'r', encoding='utf-8') as file:
        for line in file:
            try:
                record = json.loads(line)
                if 'question' in record and 'llm_output' in record:
                    all_records.append(record)
            except json.JSONDecodeError:
                continue

df_all = pd.DataFrame(all_records)
print(f"✅ 成功讀取 {len(df_all)} 筆資料")

if df_all.empty:
    print("❌ 無資料，停止後續分析。")
    exit()

# -----------------------------------------------------
# 步驟 3: 錯誤答案偏好
# -----------------------------------------------------
print("\n--- Step 3: 錯誤答案偏好分析 ---")

CORRECTNESS_COLUMN = find_correctness_column(df_all)
if CORRECTNESS_COLUMN is None:
    print("❌ 無法進行後續分析。")
    exit()

df_errors = df_all[df_all[CORRECTNESS_COLUMN] == False].copy()
print(f"錯誤答案筆數: {len(df_errors)}")

df_errors['model_choice'] = (
    df_errors['llm_output'].astype(str)
    .str.replace(r'[\s\n\\]', '', regex=True)
    .str.extract(r'\{([A-D])\}')
    .fillna('')
)

valid_choices = ['A', 'B', 'C', 'D']
df_valid_errors = df_errors[df_errors['model_choice'].isin(valid_choices)]

if df_valid_errors.empty:
    print("⚠️ 無有效 A/B/C/D 格式答案。")
else:
    counts = df_valid_errors['model_choice'].value_counts(normalize=True).sort_index()
    print("錯誤選項分佈：")
    print(counts.map('{:.2%}'.format))

    plt.figure(figsize=(6, 6))
    plt.pie(counts, labels=counts.index, autopct='%1.1f%%', startangle=90,
            colors=sns.color_palette('pastel'))
    plt.title('錯誤答案中模型選擇的選項位置分佈')
    plt.savefig('02_choice_bias.png', dpi=300)
    print("📊 已輸出圖檔: 02_choice_bias.png")

# -----------------------------------------------------
# 步驟 4: 題目長度錯誤率
# -----------------------------------------------------
print("\n--- Step 4: 題目長度錯誤率 ---")

df_all['prompt_length'] = df_all['question'].astype(str).str.len()
median_len = df_all['prompt_length'].median()
df_all['length_group'] = np.where(
    df_all['prompt_length'] > median_len,
    f'長題目 (>{median_len:.0f}字)',
    f'短題目 (≤{median_len:.0f}字)'
)

error_rate_by_length = (
    df_all.groupby('length_group')[CORRECTNESS_COLUMN]
    .agg(total='count', errors=lambda x: (x == False).sum())
    .reset_index()
)
error_rate_by_length['error_rate'] = (
    error_rate_by_length['errors'] / error_rate_by_length['total']
)

print(error_rate_by_length)

plt.figure(figsize=(7, 5))
sns.barplot(x='length_group', y='error_rate', data=error_rate_by_length, palette='viridis')
plt.title('長短題目錯誤率比較')
plt.xlabel(f'題目長度分組 (中位數: {median_len:.0f}字)')
plt.ylabel('錯誤率')
plt.tight_layout()
plt.savefig('03_length_error_rate.png', dpi=300)
print("📊 已輸出圖檔: 03_length_error_rate.png")

# -----------------------------------------------------
# 步驟 5: 長度穩定性分析 (分面圖)
# -----------------------------------------------------
print("\n--- Step 5: 長度 vs. Round 穩定性 ---")

df_all['length_group_4q'] = pd.qcut(
    df_all['prompt_length'],
    q=4,
    labels=['Q1 (最短)', 'Q2 (較短)', 'Q3 (較長)', 'Q4 (最長)'],
    duplicates='drop'
)

try:
    df_summary = pd.read_csv('summary.csv')
    round_counts = [444, 445, 444, 444, 445]
except Exception:
    round_counts = [int(len(df_all) / 5)] * 5

round_ids = np.concatenate([np.repeat(i + 1, c) for i, c in enumerate(round_counts)])
if len(round_ids) > len(df_all):
    round_ids = round_ids[:len(df_all)]
elif len(round_ids) < len(df_all):
    round_ids = np.concatenate([round_ids, np.repeat(len(round_counts), len(df_all) - len(round_ids))])

df_all['round_id'] = 'Round ' + pd.Series(round_ids, index=df_all.index).astype(str)

error_rate_by_round_length = df_all.groupby(
    ['round_id', 'length_group_4q']
)[CORRECTNESS_COLUMN].agg(
    total='count',
    errors=lambda x: (x == False).sum()
).reset_index()

error_rate_by_round_length['error_rate'] = (
    error_rate_by_round_length['errors'] / error_rate_by_round_length['total']
)

g = sns.FacetGrid(
    error_rate_by_round_length,
    col='round_id',
    col_wrap=3,
    height=4,
    sharey=True
)

g.map_dataframe(
    sns.barplot,
    x='length_group_4q',
    y='error_rate',
    order=['Q1 (最短)', 'Q2 (較短)', 'Q3 (較長)', 'Q4 (最長)'],
    palette='Spectral'
)

g.set_axis_labels("題目長度分組", "錯誤率")
g.set_titles(col_template="{col_name}")
g.fig.suptitle("不同抽樣輪次下的長度錯誤率趨勢 (穩定性分析)", fontsize=16, y=1.05)

for ax in g.axes.flat:
    ax.set_ylim(0, 1.0)
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f'{h:.2f}', (p.get_x() + p.get_width()/2., h),
                        ha='center', va='center',
                        xytext=(0, 9), textcoords='offset points', fontsize=8)

plt.tight_layout(rect=[0, 0, 1, 0.98])
plt.savefig('04_length_stability_by_round.png', dpi=300)
print("📊 已輸出圖檔: 04_length_stability_by_round.png")

print("\n✅ 分析流程完成！所有輸出已存於：")
print(CWD)
