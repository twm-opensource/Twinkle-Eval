from twinkle_eval import TwinkleEvalRunner
import json


def run_taigi_evaluation():
    """執行台語試題評測"""

    # 建立評測執行器
    runner = TwinkleEvalRunner("config.yaml")

    # 初始化
    print("🔧 初始化評測環境...")
    runner.initialize()

    # 執行評測
    print("🚀 開始評測...")
    results = runner.run_evaluation(export_formats=["json", "csv", "html"])

    print(f"\n✅ 評測完成!")
    print(f"📁 結果已儲存至: {results}")

    return results


def analyze_results(result_file):
    """分析評測結果"""

    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("\n" + "=" * 50)
    print("📊 評測結果分析")
    print("=" * 50)

    # 總體準確率
    print(f"\n總體準確率: {data['accuracy']:.2%}")

    # 統計各題答題狀況
    details = data['details']
    total_questions = len(details)
    correct_count = sum(1 for item in details if item['is_correct'])

    print(f"總題數: {total_questions}")
    print(f"答對題數: {correct_count}")
    print(f"答錯題數: {total_questions - correct_count}")

    # 錯誤分析
    print("\n❌ 答錯的題目:")
    wrong_questions = [item for item in details if not item['is_correct']]

    for item in wrong_questions[:5]:  # 顯示前5題
        print(f"\n題號 {item['question_id']}:")
        print(f"  正確答案: {item['correct_answer']}")
        print(f"  模型預測: {item['predicted_answer']}")
        print(f"  題目: {item['question'][:100]}...")  # 只顯示前100字

    if len(wrong_questions) > 5:
        print(f"\n... 還有 {len(wrong_questions) - 5} 題答錯")

    # 選項分布分析
    from collections import Counter
    predicted_answers = [item['predicted_answer'] for item in details]
    correct_answers = [item['correct_answer'] for item in details]

    print("\n📈 模型預測選項分布:")
    pred_counter = Counter(predicted_answers)
    for option, count in sorted(pred_counter.items()):
        print(f"  {option}: {count} 次 ({count / total_questions:.1%})")

    print("\n📈 正確答案選項分布:")
    correct_counter = Counter(correct_answers)
    for option, count in sorted(correct_counter.items()):
        print(f"  {option}: {count} 次 ({count / total_questions:.1%})")


if __name__ == "__main__":
    # 執行評測
    result_files = run_taigi_evaluation()

    # 分析結果 (找到詳細結果檔案)
    import glob

    eval_result_files = glob.glob("results/eval_results_*.json")
    if eval_result_files:
        latest_file = max(eval_result_files)  # 取最新的檔案
        analyze_results(latest_file)