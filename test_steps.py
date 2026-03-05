"""逐步诊断脚本：依次测试 IMAP -> 文本提取 -> LLM -> 飞书 每个环节。"""

import io
import logging
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)

from automail import config


def banner(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def step1_imap() -> list[dict]:
    """测试 IMAP 连接、登录、搜索邮件。"""
    banner("Step 1: IMAP 连接与邮件抓取")

    from automail.email_fetcher import fetch_new_emails
    try:
        emails = fetch_new_emails()
    except Exception as e:
        print(f"  [FAIL] 邮件抓取异常: {e}")
        import traceback
        traceback.print_exc()
        return []

    print(f"  找到 {len(emails)} 封新邮件。")
    for m in emails:
        print(f"  - [UID {m['uid']}] {m['subject']} ({m['date'][:30]})")
        print(f"    HTML 长度: {len(m['html_body'])} 字符")

    if not emails:
        print("  [INFO] 无新邮件（可能全部已处理，或邮箱中无目标邮件）。")

    return emails


def step2_extract(html_body: str) -> str:
    """测试文本提取。"""
    banner("Step 2: 邮件文本提取")

    from automail.email_parser import extract_text_for_llm
    text = extract_text_for_llm(html_body)

    print(f"  纯文本长度: {len(text)} 字符")
    print(f"  前 600 字符预览:")
    print(f"---\n{text[:600]}\n---")

    if len(text) < 100:
        print("  [WARN] 提取文本过短！")

    return text


def step3_llm(email_text: str) -> str:
    """测试 OpenRouter API 调用。"""
    banner("Step 3: LLM 摘要")

    print(f"  API URL: {config.LLM_API_URL}")
    print(f"  模型: {config.LLM_MODEL}")
    print(f"  API Key: {config.LLM_API_KEY[:10]}...{config.LLM_API_KEY[-4:]}")
    print(f"  文本长度: {len(email_text)} 字符")

    from automail.summarizer import summarize
    summary = summarize(email_text)

    if summary:
        print(f"\n  [OK] 摘要生成成功，长度: {len(summary)} 字符")
        print(f"\n---摘要内容---\n{summary}\n---")
    else:
        print("  [FAIL] 摘要为空！")

    return summary


def step4_feishu(title: str, content: str) -> None:
    """测试飞书 Webhook 推送。"""
    banner("Step 4: 飞书 Webhook 推送")

    print(f"  Webhook URL: {config.FEISHU_WEBHOOK_URL[:60]}...")
    print(f"  标题: {title}")
    print(f"  内容长度: {len(content)} 字符")

    from automail.feishu_bot import send_to_feishu
    success = send_to_feishu(title, content)

    if success:
        print("  [OK] 飞书推送成功！请检查飞书群聊。")
    else:
        print("  [FAIL] 飞书推送失败！")


def main():
    print("AutoMail 逐步诊断工具")
    print(f"配置检查:")
    print(f"  EMAIL_ADDRESS:    {config.EMAIL_ADDRESS}")
    print(f"  EMAIL_IMAP_HOST:  {config.EMAIL_IMAP_HOST}")
    print(f"  TARGET_SENDER:    {config.TARGET_SENDER}")
    print(f"  LLM_MODEL:        {config.LLM_MODEL}")
    print(f"  FEISHU_WEBHOOK:   {config.FEISHU_WEBHOOK_URL[:50]}...")

    # Step 1: IMAP
    emails = step1_imap()
    if not emails:
        print("\n[ABORT] Step 1 未取到新邮件。")
        print("  如果邮件已全部处理过，可删除 processed.json 后重试。")
        sys.exit(1)

    mail = emails[-1]

    # Step 2: 文本提取
    text = step2_extract(mail["html_body"])
    if not text:
        print("\n[ABORT] Step 2 文本提取失败。")
        sys.exit(1)

    # Step 3: LLM 摘要
    summary = step3_llm(text)
    if not summary:
        print("\n[ABORT] Step 3 LLM 总结失败。")
        sys.exit(1)

    # Step 4: 飞书推送
    title = f"AI 速递 | {mail['subject']}"
    step4_feishu(title, summary)

    banner("诊断完成")


if __name__ == "__main__":
    main()
