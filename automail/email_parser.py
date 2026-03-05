"""从 DataPoints 邮件 HTML 中提取干净的纯文本，供 LLM 直接总结。"""

import logging
import re

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_text_for_llm(html: str) -> str:
    """
    将 HTML 邮件转为干净的纯文本。

    DataPoints 邮件 HTML 结构复杂且不稳定（h2/h3/bold-p 混用），
    直接提取纯文本并交给 LLM 处理内容结构最为可靠。
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["style", "script", "head"]):
        tag.decompose()

    for hidden in soup.find_all(style=re.compile(r"display\s*:\s*none", re.IGNORECASE)):
        hidden.decompose()

    _convert_links_to_markdown(soup)

    text = soup.get_text(separator="\n")

    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        stripped = re.sub(r"[\u200b\u200c\u200d\u034f\u00ad\xa0]+", "", stripped)
        stripped = re.sub(r"\s{3,}", " ", stripped)
        if stripped and len(stripped) > 1:
            lines.append(stripped)

    clean_text = "\n".join(lines)

    for marker in [
        "Unsubscribe",
        "unsubscribe",
        "Update your email preferences",
        "Manage preferences",
    ]:
        idx = clean_text.rfind(marker)
        if idx > len(clean_text) // 2:
            clean_text = clean_text[:idx].rstrip()
            break

    logger.info("提取纯文本 %d 字符。", len(clean_text))
    return clean_text


_SKIP_LINK_KEYWORDS = {"unsubscribe", "preferences", "manage", "mailto:", "privacy"}


def _convert_links_to_markdown(soup: BeautifulSoup) -> None:
    """将 <a> 标签原地替换为 Markdown 格式 [text](url)，保留链接信息。"""
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        text = a_tag.get_text(strip=True)

        if not text or not href:
            continue
        if any(kw in href.lower() for kw in _SKIP_LINK_KEYWORDS):
            continue

        a_tag.replace_with(f"[{text}]({href})")
