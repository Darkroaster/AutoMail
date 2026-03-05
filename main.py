"""AutoMail 入口：抓取 DataPoints 邮件 -> 提取文本 -> LLM 中文总结 -> 飞书推送。"""

import argparse
import logging
import sys
import time

from apscheduler.schedulers.blocking import BlockingScheduler

from automail import config
from automail.email_fetcher import fetch_new_emails, mark_as_processed
from automail.email_parser import extract_text_for_llm
from automail.feishu_bot import send_to_feishu
from automail.summarizer import summarize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def process_emails() -> None:
    """执行一次完整的 抓取 -> 提取文本 -> 总结 -> 推送 流程。"""
    logger.info("=" * 50)
    logger.info("开始检查新邮件...")

    try:
        emails = fetch_new_emails()
    except Exception:
        logger.exception("邮件抓取失败。")
        return

    if not emails:
        logger.info("没有新的 DataPoints 邮件。")
        return

    logger.info("发现 %d 封新邮件，开始处理...", len(emails))

    for idx, mail in enumerate(emails, 1):
        t0 = time.monotonic()
        logger.info("[%d/%d] 处理邮件: [UID %s] %s", idx, len(emails), mail["uid"], mail["subject"])

        clean_text = extract_text_for_llm(mail["html_body"])
        if not clean_text:
            logger.warning("[UID %s] 邮件文本提取为空，跳过。", mail["uid"])
            mark_as_processed(mail["uid"])
            continue

        summary = summarize(clean_text)
        if not summary:
            logger.warning("[UID %s] 摘要生成为空，跳过推送。", mail["uid"])
            mark_as_processed(mail["uid"])
            continue

        title = f"AI 速递 | {mail['subject']}"
        success = send_to_feishu(title, summary)

        elapsed = time.monotonic() - t0
        if success:
            mark_as_processed(mail["uid"])
            logger.info("[UID %s] 处理完成并已推送（耗时 %.1fs）。", mail["uid"], elapsed)
        else:
            logger.error("[UID %s] 推送失败，不标记为已处理，下次重试（耗时 %.1fs）。", mail["uid"], elapsed)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AutoMail - DeepLearning.AI DataPoints 邮件摘要飞书推送机器人"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="立即执行一次抓取-总结-推送流程",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="启动定时调度，按配置间隔自动执行",
    )
    args = parser.parse_args()

    if not args.once and not args.schedule:
        parser.print_help()
        sys.exit(1)

    _validate_config()

    if args.once:
        process_emails()

    if args.schedule:
        logger.info(
            "启动定时调度，每天 %02d:%02d 执行...",
            config.SCHEDULE_HOUR,
            config.SCHEDULE_MINUTE,
        )
        scheduler = BlockingScheduler()
        scheduler.add_job(
            process_emails,
            "cron",
            hour=config.SCHEDULE_HOUR,
            minute=config.SCHEDULE_MINUTE,
            id="daily_check",
        )
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("调度器已停止。")


def _validate_config() -> None:
    """校验必要配置项是否已填写。"""
    missing: list[str] = []
    if not config.EMAIL_ADDRESS:
        missing.append("EMAIL_ADDRESS")
    if not config.EMAIL_AUTH_CODE:
        missing.append("EMAIL_AUTH_CODE")
    if not config.LLM_API_KEY:
        missing.append("LLM_API_KEY")
    if not config.FEISHU_WEBHOOK_URL:
        missing.append("FEISHU_WEBHOOK_URL")

    if missing:
        logger.error("以下配置项缺失，请在 .env 文件中填写: %s", ", ".join(missing))
        sys.exit(1)

    logger.info(
        "配置校验通过 | 邮箱: %s | 模型: %s | 调度: 每天 %02d:%02d",
        config.EMAIL_ADDRESS,
        config.LLM_MODEL,
        config.SCHEDULE_HOUR,
        config.SCHEDULE_MINUTE,
    )


if __name__ == "__main__":
    main()
