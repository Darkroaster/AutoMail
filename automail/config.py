"""AutoMail 配置管理模块，从 .env 文件加载所有配置项。"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


EMAIL_IMAP_HOST: str = os.getenv("EMAIL_IMAP_HOST", "imap.163.com")
EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")
EMAIL_AUTH_CODE: str = os.getenv("EMAIL_AUTH_CODE", "")

LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_API_URL: str = os.getenv(
    "LLM_API_URL", "https://openrouter.ai/api/v1/chat/completions"
)
LLM_MODEL: str = os.getenv("LLM_MODEL", "z-ai/glm-4.5-air:free")

_DEFAULT_SYSTEM_PROMPT = (
    "你是一个AI新闻摘要助手。用户会提供一封来自 DeepLearning.AI DataPoints 的英文邮件原文。\n"
    "邮件中包含多条 AI 相关新闻事件。\n\n"
    "请完成以下任务：\n"
    "1. 识别邮件中的每条独立新闻事件（忽略广告、订阅推广、引言问候等非新闻内容）\n"
    "2. 将每条新闻总结为简体中文，每条不超过2句话\n"
    "3. 保留文中提到的关键公司/产品名称（如 OpenAI、Anthropic 等，不翻译）\n\n"
    "输出格式（严格遵守）：\n"
    "1. **新闻标题中文翻译** - 摘要内容。[来源](url)\n"
    "2. **新闻标题中文翻译** - 摘要内容。[来源](url)\n"
    "...\n\n"
    "注意：\n"
    "- 每条末尾附上原文中对应的来源链接，格式为 [来源](url)\n"
    "- 链接直接从原文中提取，不要编造\n"
    "- 只输出新闻总结，不要加开头语、结尾语或任何额外说明"
)
SYSTEM_PROMPT: str = os.getenv("SYSTEM_PROMPT", _DEFAULT_SYSTEM_PROMPT)

_DEFAULT_FALLBACK_MODELS = (
    "stepfun/step-3.5-flash:free,"
    "nvidia/nemotron-3-nano-30b-a3b:free,"
    "meta-llama/llama-3.3-70b-instruct:free"
)
_raw_fallback = os.getenv("LLM_FALLBACK_MODELS", _DEFAULT_FALLBACK_MODELS)
LLM_FALLBACK_MODELS: list[str] = [
    m.strip() for m in _raw_fallback.split(",") if m.strip()
]

FEISHU_WEBHOOK_URL: str = os.getenv("FEISHU_WEBHOOK_URL", "")

SCHEDULE_HOUR: int = int(os.getenv("SCHEDULE_HOUR", "7"))
SCHEDULE_MINUTE: int = int(os.getenv("SCHEDULE_MINUTE", "30"))

PROCESSED_FILE: Path = PROJECT_ROOT / "processed.json"

TARGET_SENDER: str = os.getenv("TARGET_SENDER", "datapoints@deeplearning.ai")

IMAP_TIMEOUT: int = int(os.getenv("IMAP_TIMEOUT", "30"))

FIRST_RUN_LIMIT: int = int(os.getenv("FIRST_RUN_LIMIT", "1"))

