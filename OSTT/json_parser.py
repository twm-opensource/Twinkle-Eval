import pandas as pd
import re


def convert_taigi_data_to_twinkle_format(input_file, output_file):
    """
    將台語試題轉換為 Twinkle-Eval 所需格式

    參數:
        input_file: 原始資料檔案路徑 (CSV/Excel)
        output_file: 輸出檔案路徑 (CSV)
    """

    # 讀取原始資料
    # 根據你的檔案格式選擇適當的讀取方式
    if input_file.endswith('.xlsx') or input_file.endswith('.xls'):
        df = pd.read_excel(input_file)
    else:
        df = pd.read_csv(input_file)

    # 創建新的 DataFrame
    converted_data = []

    for idx, row in df.iterrows():
        # 組合題目:前文 + 試題
        if pd.notna(row['前文(台語能力試題專案507題適用)']):
            full_question = f"{row['前文(台語能力試題專案507題適用)']}\n{row['試題']}"
        else:
            full_question = row['試題']

        # 解析選項
        options_text = row['選項']

        # 使用正則表達式提取選項
        # 格式: (1) 內容 (2) 內容 (3) 內容 (4) 內容
        pattern = r'\((\d+)\)\s*([^()]+?)(?=\s*\(\d+\)|$)'
        matches = re.findall(pattern, options_text)

        # 建立選項字典
        options_dict = {}
        option_labels = ['A', 'B', 'C', 'D']

        for i, (num, content) in enumerate(matches):
            if i < 4:  # 只取前4個選項
                options_dict[option_labels[i]] = content.strip()

        # 將答案數字轉換為字母
        answer_num = int(row['答案'])
        answer_letter = option_labels[answer_num - 1]

        # 組成新的資料行
        converted_row = {
            'question': full_question,
            'A': options_dict.get('A', ''),
            'B': options_dict.get('B', ''),
            'C': options_dict.get('C', ''),
            'D': options_dict.get('D', ''),
            'answer': answer_letter
        }

        converted_data.append(converted_row)

    # 建立新的 DataFrame 並儲存
    result_df = pd.DataFrame(converted_data)
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')

    print(f"✅ 轉換完成!")
    print(f"   原始題數: {len(df)}")
    print(f"   轉換題數: {len(result_df)}")
    print(f"   輸出檔案: {output_file}")

    # 顯示前3題作為範例
    print("\n📝 前3題範例:")
    print(result_df.head(3))

    return result_df


# 使用範例
if __name__ == "__main__":
    # 請修改為你的檔案路徑
    input_file = "你的台語試題.csv"  # 或 .xlsx
    output_file = "taigi_questions_twinkle_format.csv"

    convert_taigi_data_to_twinkle_format(input_file, output_file)