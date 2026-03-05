"""格式化消息并通过飞书 Webhook 推送（消息卡片，支持 Markdown 加粗与链接）。"""

import logging

import httpx

from . import config

logger = logging.getLogger(__name__)


def send_to_feishu(title: str, content: str) -> bool:
    """
    通过飞书自定义机器人 Webhook 发送消息卡片。

    使用 interactive 消息类型 + lark_md 标签，原生支持 Markdown
    语法（**加粗**、[链接](url) 等）。

    Args:
        title: 消息标题（如邮件主题 + 日期）。
        content: LLM 生成的中文摘要文本（Markdown 格式）。

    Returns:
        是否发送成功。
    """
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"content": title, "tag": "plain_text"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"content": content, "tag": "lark_md"},
                }
            ],
        },
    }

    try:
        logger.info("正在推送消息到飞书: %s", title)
        with httpx.Client(timeout=30) as client:
            resp = client.post(config.FEISHU_WEBHOOK_URL, json=payload)
            resp.raise_for_status()

        result = resp.json()
        if result.get("code") == 0 or result.get("StatusCode") == 0:
            logger.info("飞书推送成功。")
            return True

        logger.error("飞书推送返回异常: %s", result)
        return False

    except Exception:
        logger.exception("飞书推送失败。")
        return False
