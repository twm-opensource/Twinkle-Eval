import httpx
from logger import log_error
from openai import OpenAI


def call_llm_api(config, question_text, prompt_lang="zh"):
    """呼叫 LLM API 進行推論"""

    # 根據評估方法決定 messages 內容
    if config["evaluation"]["evaluation_method"] == "box":
        sys_prompt_cfg = config["evaluation"].get("system_prompt", {})
        if isinstance(sys_prompt_cfg, dict):
            sys_prompt = sys_prompt_cfg.get(prompt_lang, sys_prompt_cfg.get("zh", ""))
        else:
            # 向下相容舊版設定，直接當成字串使用
            sys_prompt = sys_prompt_cfg
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": question_text},
        ]
    else:
        messages = [{"role": "user", "content": question_text}]

    payload = {
        "model": config["model"]["name"],
        "temperature": config["model"]["temperature"],
        "top_p": config["model"]["top_p"],
        "max_tokens": config["model"]["max_tokens"],
        "messages": messages,
    }

    if config["llm_api"]["disable_ssl_verify"]:
        httpx_client = httpx.Client(verify=False)
    else:
        httpx_client = httpx.Client()

    client = OpenAI(
        api_key=config["llm_api"]["api_key"],
        base_url=config["llm_api"]["base_url"],
        http_client=httpx_client,
        max_retries=config["llm_api"]["max_retries"],
        timeout=config["llm_api"]["timeout"],
    )

    try:
        response = client.chat.completions.create(**payload)
        return response.choices[0].message.content

    except Exception as e:
        log_error(f"LLM API 錯誤: {e}")
        raise e
