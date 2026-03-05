"""调用 LLM API 将邮件纯文本总结为简体中文。"""

import logging
import time

import httpx

from . import config

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 5


def summarize(email_text: str) -> str:
    """
    调用 LLM API 对邮件文本生成中文摘要。

    遇到 429 限流时自动重试，所有模型均失败则返回空字符串。
    """
    if not email_text.strip():
        return ""

    logger.info("LLM 输入文本长度: %d 字符。", len(email_text))

    models_to_try = [config.LLM_MODEL] + [
        m for m in config.LLM_FALLBACK_MODELS if m != config.LLM_MODEL
    ]

    for model in models_to_try:
        result = _call_with_retry(model, email_text)
        if result:
            return result
        logger.warning("模型 %s 不可用，尝试下一个...", model)

    logger.error("所有模型均失败。")
    return ""


def _call_with_retry(model: str, email_text: str) -> str:
    """对单个模型调用 API，带重试逻辑。"""
    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": config.SYSTEM_PROMPT},
            {"role": "user", "content": email_text},
        ],
        "temperature": 0.3,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "调用 LLM API（模型: %s，第 %d/%d 次）...",
                model,
                attempt,
                MAX_RETRIES,
            )
            with httpx.Client(timeout=120) as client:
                resp = client.post(config.LLM_API_URL, json=payload, headers=headers)

            if resp.status_code == 429:
                delay = RETRY_BASE_DELAY * attempt
                logger.warning("429 限流，%d 秒后重试...", delay)
                time.sleep(delay)
                continue

            if resp.status_code != 200:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                logger.error("API 错误 %d: %s", resp.status_code, body)
                return ""

            data = resp.json()
            if "choices" not in data or not data["choices"]:
                logger.error("API 响应缺少 choices: %s", data)
                return ""

            usage = data.get("usage", {})
            logger.info(
                "摘要生成成功（模型: %s） | prompt_tokens=%s, completion_tokens=%s, total_tokens=%s",
                model,
                usage.get("prompt_tokens", "N/A"),
                usage.get("completion_tokens", "N/A"),
                usage.get("total_tokens", "N/A"),
            )

            content = data["choices"][0]["message"]["content"]
            return content.strip()

        except httpx.TimeoutException:
            logger.warning("请求超时（第 %d 次），重试...", attempt)
            continue
        except Exception:
            logger.exception("API 调用异常（模型: %s）。", model)
            return ""

    return ""
