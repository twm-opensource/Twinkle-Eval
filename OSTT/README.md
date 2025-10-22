# 使用 Twinkle-Eval 評測你的台語試題

根據你提供的題目格式和 Twinkle-Eval 的要求,以下是詳細步驟:

### 📋 **步驟一:資料格式轉換**

Twinkle-Eval 需要 CSV、JSON、JSONL 或 Parquet 格式,必須包含以下欄位:`question`、`A`、`B`、`C`、`D`、`answer`

你需要將你的資料轉換成這個格式。我為你準備一個轉換腳本:[json_parser.py](OSTT/json_parser.py)

### 📦 **步驟二:安裝 Twinkle-Eval**

```bash
# 從 PyPI 安裝
pip install twinkle-eval

# 或從 GitHub 安裝最新版本
pip install git+https://github.com/twm-opensource/Twinkle-Eval.git
```

### ⚙️ **步驟三:建立配置檔案**：[config.yaml](OSTT/config.yaml)

### 🚀 **步驟四:執行評測**

建立以下資料夾結構:

```
your_project/
├── config.yaml
├── datasets/
│   └── taigi/
│       └── taigi_questions_twinkle_format.csv
└── results/  (自動建立)
```

執行評測:

```bash
# 使用配置檔案執行
twinkle-eval --config config.yaml

# 或者同時輸出多種格式
twinkle-eval --config config.yaml --export json csv html
```

### 📊 **步驟五:查看結果**

評測完成後,會在 `results/` 資料夾中產生兩個檔案:

1. **`results_{timestamp}.json`** - 總體摘要
    - 平均正確率
    - 各資料集表現
    - 配置資訊

2. **`eval_results_{timestamp}.json`** - 詳細結果
    - 每題的答題情況
    - 模型預測答案 vs 正確答案
    - 可用於錯誤分析

### 隨機抽樣評估

由於資料集可能很大，此腳本專門用於進行多輪隨機抽樣，以取得更具統計意義的平均準確率和穩定性。
如果你想在 Python 程式中使用:[run.py](OSTT/run.py)

執行指令：
你需要透過參數指定原始資料集路徑 (--src_dir)。程式會自動創建或使用 dataset_sampled 作為暫存目錄。
### 範例：每輪抽樣 50 題(預設)
```bash
python run.py \
    --src_dir "/path/to/your/raw/dataset/csvs" \
```

### 範例:每輪抽樣 15 題
```bash
python run.py \
    --src_dir "/path/to/your/raw/dataset/csvs" \
    --sample_n 15
```

#### 執行範例與結果 (Example Run)

以下是執行五輪抽樣評估的**精簡日誌範例**，用於展示流程。

**執行指令：**

```bash
python run.py --src_dir "/path/to/your/raw/dataset/csvs"
```

### 終端機日誌輸出 (節錄)：
```bash
==============================
🔁 第 1 次抽樣與評測
==============================
📁 已抽樣 50 題 -> dataset_sampled/taigi_questions_twinkle_format.csv
📂 使用抽樣後資料集: dataset_sampled
... (評測細節省略) ...
平均準確率: 84.35%
標準差: 0.96%

... (中間輪次省略) ...

==============================
🔁 第 5 次抽樣與評測
==============================
📁 已抽樣 50 題 -> dataset_sampled/taigi_questions_twinkle_format.csv
... (評測細節省略) ...
平均準確率: 89.33%
標準差: 1.89%

==================================================
🏁 五輪平均準確率: 87.54% (±2.04%)
📊 詳細結果已輸出: results/summary.csv
==================================================
```

**結論：**

該範例顯示模型在五次隨機抽樣下的平均準確率為 **87.54%**，標準差 **±2.04%**，表明其性能在隨機抽樣測試集下具有穩定性。

### 500 筆測評結果展示

### 每輪抽樣 150 題
```bash
python run.py \
    --src_dir "/path/to/your/raw/dataset/csvs" \
    --sample_n 150
```
對於500筆資料使用每次150筆抽樣評測，模型在五次隨機抽樣下的平均準確率為 53.35%，標準差 ±3.92%。



### 🎯 **重點提醒**

1. **選項隨機化**: Twinkle-Eval 會自動隨機排列選項,避免模型對特定位置有偏好,這能更準確評估模型的理解能力。

2. **多次測試**: 建議設定 `repeat_runs: 5`,進行5次測試並取平均,可以觀察模型的穩定性。

3. **評測方法選擇**:
    - **Box 模式** (推薦): 要求模型輸出 `\box{A}` 格式,更嚴格
    - **Pattern 模式**: 使用正則表達式匹配答案

4. **台語特性考量**: 在系統提示詞中明確說明這是台語試題,幫助模型理解題目語境。

5. **API 設定**:
    - 如果使用本地模型,確保 API 服務已啟動
    - 調整 `api_rate_limit` 避免超過 API 限制
    - 如果模型回應較慢,可增加 `timeout` 時間

### 📈 **效能優勢**

根據文件說明,Twinkle-Eval 比其他評測工具快 **9-17 倍**,對於你的 125 題測試集來說,評測時間會大幅縮短。
