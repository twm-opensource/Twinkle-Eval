import os
import re
import json
import time
import random
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from llm_api import call_llm_api
from logger import log_info, log_error
from data_loader import read_evaluation_data


class RateLimiter:
    def __init__(self, calls_per_second):
        self.no_limit = calls_per_second == -1
        self.interval = 1.0 / calls_per_second if not self.no_limit else 0
        self.last_call_time = 0

    def wait(self):
        if self.no_limit:
            return
        current_time = time.time()
        time_to_wait = self.interval - (current_time - self.last_call_time)
        if time_to_wait > 0:
            time.sleep(time_to_wait)
        self.last_call_time = time.time()


# 匹配各種 LLM 輸出格式的正則表達式
ANSWER_PATTERNS = [
    r"correct answer is:\n\n\n([A-D]).",
    r"correct answer is:\n\n([A-D]).",
    r"correct answer is:\n([A-D]).",
    r"正確的答案應該是:.*?\b([A-D])\b",
    r"正确的答案应该是:.*?\b([A-D])\b",
    r"正確的選項應為:.*?\b([A-D])\b",
    r"正确的选项应为:.*?\b([A-D])\b",
    r"正確的答案是（([A-D])）",
    r"正确的答案是（([A-D])）",
    r"答案應該是:\s?選?項?\s?([A-D])",
    r"答案应该是:\s?选?项?\s?([A-D])",
    r"答案是:\s?選?項?\s?([A-D])",
    r"答案是:\s?选?项?\s?([A-D])",
    r"答案應為:\s?選?項?\s?([A-D])",
    r"答案应为:\s?选?项?\s?([A-D])",
    r"答案為:\s?([A-D])",
    r"答案应为：\s?([A-D])",
    r"答案為：\s?([A-D])",
    r"答案應該是:\s?([A-D])",
    r"正確答案為 \*\*([A-D])",
    r"正確答案為\(([A-D])\)",
    r"答案應為:\s?([A-D])",
    r"答案应为:\s?([A-D])",
    r"答案是 \*\*([A-D])",
    r"答案 ([A-D]) 正確",
    r"選項 ([A-D]) 正確",
    r"所以答案為([A-D])",
    r"答案：\(([A-D])\)",
    r"答案:\s?([A-D])",
    r"答案：\s?([A-D])",
    r"答案: ([A-D]) ",
    r"答案([A-D]) ",
    r"^選項([A-D])",
    r"^选项([A-D])",
    r"^選([A-D])",
    r"^选([A-D])",
    r"([A-D]). ",
    r"([A-D]).",
]

BOX_PATTERNS = [r"\\{1,2}box{([A-D])}", r"\\{1,2}boxed{([A-D])}"]


def extract_answer(llm_output, method):
    """解析 LLM 輸出，從提供的 pattern 清單中匹配答案"""
    if not isinstance(llm_output, str) or not llm_output.strip():
        log_info("LLM 回應為 None 或空字串，無法解析答案")
        return None

    if method == "pattern":
        for pattern in ANSWER_PATTERNS:
            match = re.search(pattern, llm_output)
            if match:
                return match.group(1).strip()

    elif method == "box":
        for pattern in BOX_PATTERNS:
            match = re.search(pattern, llm_output)
            if match:
                return match.group(1).strip()
    return None


def shuffle_question_options(question_data):
    """打亂選項 A,B,C,D 的順序，並同時保持正確答案的對應關係"""
    # Extract options
    options = []
    for key in ["A", "B", "C", "D"]:
        if key in question_data:
            options.append((key, question_data[key]))

    if not options:
        return question_data

    # Remember the correct answer
    correct_ans = question_data["answer"]
    correct_option_text = question_data.get(correct_ans)

    # Shuffle options
    random.shuffle(options)

    # Create new question data with shuffled options
    new_data = {"question": question_data["question"]}

    # Rebuild the options
    for (old_key, text), (new_key, _) in zip(
        options, [("A", ""), ("B", ""), ("C", ""), ("D", "")]
    ):
        new_data[new_key] = text
        if text == correct_option_text:
            new_data["answer"] = new_key

    return new_data


def evaluate_file(config, file_path, timestamp, prompt_lang="zh"):
    """評測單一檔案，並輸出詳細結果"""
    data = read_evaluation_data(file_path)
    method = config["evaluation"]["evaluation_method"]
    shuffle_enabled = config["evaluation"].get("shuffle_options", False)

    total_correct = 0
    total_questions = 0
    detailed_results = []

    rate_limiter = RateLimiter(calls_per_second=config["llm_api"]["api_rate_limit"])

    with ThreadPoolExecutor() as executor:
        future_tasks = []
        future_to_data = {}

        # 設置問題題庫進度條
        for idx, q in enumerate(tqdm(data, desc="準備題庫中")):

            if shuffle_enabled:
                q = shuffle_question_options(q)

            question_text = (
                q["question"]
                + "\n"
                + "\n".join(
                    [
                        f"{k}: {v}"
                        for k, v in q.items()
                        if k not in ["question", "answer"]
                    ]
                )
            )

            try:
                correct_answer = q["answer"].strip().upper()
            except (KeyError, AttributeError) as e:
                log_error(f"\n Error processing question {idx + 1}: {str(e)}")
                continue

            # 在發送API請求前等待
            rate_limiter.wait()
            future = executor.submit(call_llm_api, config, question_text, prompt_lang)
            future_tasks.append(future)
            future_to_data[future] = (question_text, correct_answer, idx)

        # 設置回應處理進度條
        for future in tqdm(
            as_completed(future_tasks), total=len(future_tasks), desc="處理回應中"
        ):
            llm_output = future.result()
            question_text, correct_answer, question_id = future_to_data[future]
            predicted_answer = extract_answer(llm_output, method)

            is_correct = (
                False
                if predicted_answer is None
                else predicted_answer.strip().upper() == correct_answer
            )
            if is_correct:
                total_correct += 1
            total_questions += 1

            detailed_results.append(
                {
                    "question_id": question_id,
                    "question": question_text,
                    "correct_answer": correct_answer,
                    "llm_output": llm_output,
                    "predicted_answer": predicted_answer,
                    "is_correct": is_correct,
                }
            )

        accuracy = total_correct / total_questions if total_questions else 0

    # 輸出結果到 `results/`
    results_dir = "results/details"
    os.makedirs(results_dir, exist_ok=True)
    results_path = os.path.join(results_dir, f"eval_results_{timestamp}.jsonl")

    result_data = {
        "timestamp": timestamp,
        "file": file_path,
        "accuracy": accuracy,
        "details": detailed_results,
    }

    # 使用 append mode 寫入 JSONL
    with open(results_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result_data, ensure_ascii=False) + "\n")

    print(f"✅ 評測完成，結果已儲存至 {results_path}")
    return file_path, accuracy, results_path
