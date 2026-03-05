"""通过 IMAP 连接 163 邮箱，抓取来自 DataPoints 的邮件。"""

import email
import imaplib
import json
import logging
import re
from email.header import decode_header
from email.message import Message
from typing import Optional

from . import config

logger = logging.getLogger(__name__)

_UID_RE = re.compile(rb"UID\s+(\d+)")


# ---------------------------------------------------------------------------
# processed.json 持久化
# ---------------------------------------------------------------------------

def _load_processed_uids() -> set[str]:
    """加载已处理的邮件 UID 集合，文件损坏时安全降级为空集合。"""
    if not config.PROCESSED_FILE.exists():
        return set()
    try:
        data = json.loads(config.PROCESSED_FILE.read_text(encoding="utf-8"))
        uids = set(data.get("uids", []))
        logger.debug("已加载 %d 个已处理 UID。", len(uids))
        return uids
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("processed.json 损坏，将视为空记录重新开始。")
        return set()


def _save_processed_uids(uids: set[str]) -> None:
    """保存已处理的邮件 UID 集合。"""
    config.PROCESSED_FILE.write_text(
        json.dumps({"uids": sorted(uids, key=int)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.debug("已保存 %d 个已处理 UID。", len(uids))


def is_first_run() -> bool:
    """检测是否为首次运行（processed.json 不存在）。"""
    return not config.PROCESSED_FILE.exists()


def mark_as_processed(uid: str) -> None:
    """将指定 UID 标记为已处理。"""
    uids = _load_processed_uids()
    uids.add(uid)
    _save_processed_uids(uids)
    logger.debug("UID %s 已标记为已处理。", uid)


# ---------------------------------------------------------------------------
# 邮件解码辅助
# ---------------------------------------------------------------------------

def _decode_subject(msg: Message) -> str:
    """解码邮件主题。"""
    raw_subject = msg.get("Subject", "")
    parts = decode_header(raw_subject)
    decoded_parts: list[str] = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)


def _get_html_body(msg: Message) -> Optional[str]:
    """从邮件中提取 HTML 正文。"""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
    else:
        if msg.get_content_type() == "text/html":
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
    return None


# ---------------------------------------------------------------------------
# IMAP 操作
# ---------------------------------------------------------------------------

def _send_imap_id(conn: imaplib.IMAP4_SSL) -> None:
    """发送 IMAP ID 命令，163 邮箱要求此步骤才允许操作邮箱。"""
    imaplib.Commands["ID"] = ("AUTH",)
    args = '("name" "AutoMail" "contact" "automail@local" "version" "1.0")'
    typ, _ = conn._simple_command("ID", args)
    conn._untagged_response(typ, _, "ID")
    logger.debug("IMAP ID 命令已发送。")


def _find_target_uids(conn: imaplib.IMAP4_SSL) -> list[str]:
    """
    查找来自目标发件人的真实 IMAP UID 列表。

    使用 UID FETCH 1:* 批量获取所有邮件的 FROM 头，在客户端过滤。
    返回 UID 字符串列表，按 UID 升序排列（旧 -> 新）。
    """
    status, data = conn.uid("search", None, "ALL")
    if status != "OK" or not data[0]:
        logger.info("邮箱为空或 SEARCH 失败。")
        return []

    all_uids = data[0].split()
    total = len(all_uids)
    logger.info("邮箱共 %d 封邮件，批量获取 FROM 头并过滤...", total)

    if not all_uids:
        return []

    uid_range = f"{all_uids[0].decode()}:{all_uids[-1].decode()}"
    status, fetch_data = conn.uid(
        "fetch", uid_range, "(UID BODY[HEADER.FIELDS (FROM)])"
    )
    if status != "OK":
        logger.error("批量 FETCH FROM 头失败: status=%s", status)
        return []

    target = config.TARGET_SENDER.lower()
    matched: list[str] = []

    for item in fetch_data:
        if not isinstance(item, tuple) or len(item) < 2:
            continue

        uid_match = _UID_RE.search(item[0])
        if not uid_match:
            continue
        uid_str = uid_match.group(1).decode()

        from_text = (
            item[1].decode("utf-8", errors="replace").lower()
            if isinstance(item[1], bytes)
            else str(item[1]).lower()
        )
        if target in from_text:
            matched.append(uid_str)

    matched.sort(key=int)
    logger.info("找到 %d 封来自 %s 的邮件。", len(matched), config.TARGET_SENDER)
    return matched


def fetch_new_emails() -> list[dict]:
    """
    抓取来自目标发件人的未处理邮件。

    首次运行时只返回最新的 FIRST_RUN_LIMIT 封邮件（并将更旧的标记为已处理），
    后续运行返回所有未处理邮件。

    Returns:
        包含 uid, subject, html_body, date 的字典列表（按时间升序）。
    """
    first_run = is_first_run()
    processed_uids = _load_processed_uids()
    results: list[dict] = []

    logger.info("连接 %s（超时 %ds）...", config.EMAIL_IMAP_HOST, config.IMAP_TIMEOUT)
    conn = imaplib.IMAP4_SSL(config.EMAIL_IMAP_HOST, timeout=config.IMAP_TIMEOUT)

    try:
        conn.login(config.EMAIL_ADDRESS, config.EMAIL_AUTH_CODE)
        logger.debug("IMAP 登录成功: %s", config.EMAIL_ADDRESS)
        _send_imap_id(conn)
        conn.select("INBOX")

        matched_uids = _find_target_uids(conn)
        if not matched_uids:
            logger.info("未找到来自 %s 的邮件。", config.TARGET_SENDER)
            return results

        new_uids = [u for u in matched_uids if u not in processed_uids]
        if not new_uids:
            logger.info("所有匹配邮件均已处理（共 %d 封）。", len(matched_uids))
            return results

        if first_run:
            limit = config.FIRST_RUN_LIMIT
            logger.info(
                "首次运行，共 %d 封未处理，仅处理最新 %d 封。",
                len(new_uids),
                limit,
            )
            uids_to_process = new_uids[-limit:]
            skipped = [u for u in new_uids if u not in uids_to_process]
            if skipped:
                for uid in skipped:
                    processed_uids.add(uid)
                _save_processed_uids(processed_uids)
                logger.info("已将 %d 封旧邮件标记为已处理。", len(skipped))
        else:
            uids_to_process = new_uids
            logger.info("发现 %d 封新邮件待处理。", len(uids_to_process))

        for uid_str in uids_to_process:
            status, data = conn.uid("fetch", uid_str, "(RFC822)")
            if status != "OK" or not data[0]:
                logger.warning("UID %s 邮件内容获取失败，跳过。", uid_str)
                continue

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _decode_subject(msg)
            html_body = _get_html_body(msg)
            date_str = msg.get("Date", "")

            if html_body:
                results.append(
                    {
                        "uid": uid_str,
                        "subject": subject,
                        "html_body": html_body,
                        "date": date_str,
                    }
                )
                logger.info("新邮件: [UID %s] %s", uid_str, subject)
            else:
                logger.warning("邮件 UID %s 无 HTML 正文，跳过。", uid_str)

    finally:
        try:
            conn.logout()
        except Exception:
            logger.debug("IMAP 连接关闭时出现异常（已忽略）。", exc_info=True)

    return results
