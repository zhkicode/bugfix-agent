"""邮件通知（smtplib，同步库放线程池执行）。"""
import asyncio
import smtplib
from email.mime.text import MIMEText

from app.services import settings_service


class NotifyError(RuntimeError):
    pass


async def _load_smtp_config() -> dict:
    return {
        "host": await settings_service.get_setting("smtp.host", ""),
        "port": await settings_service.get_int("smtp.port", 465),
        "user": await settings_service.get_setting("smtp.user", ""),
        "pass": await settings_service.get_setting("smtp.pass", ""),
        "from": await settings_service.get_setting("smtp.from", ""),
        "secure": await settings_service.get_setting("smtp.secure", "ssl"),
    }


def _send_sync(cfg: dict, subject: str, body: str, recipients: list[str]) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    sender = cfg["from"] or cfg["user"]
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    if cfg["secure"] == "ssl":
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30)
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=30)
    try:
        if cfg["secure"] == "starttls":
            server.starttls()
        if cfg["user"]:
            server.login(cfg["user"], cfg["pass"])
        server.sendmail(sender, recipients, msg.as_string())
    finally:
        server.quit()


async def send_email(subject: str, body: str, recipients: list[str] | None = None) -> None:
    cfg = await _load_smtp_config()
    if not cfg["host"] or not cfg["user"] or not cfg["pass"]:
        raise NotifyError("SMTP 未配置完整（服务器/账号/授权码）")
    if recipients is None:
        raw = await settings_service.get_setting("notify.recipients", "")
        recipients = [r.strip() for r in raw.split(",") if r.strip()]
    if not recipients:
        raise NotifyError("未配置收件人")
    await asyncio.to_thread(_send_sync, cfg, subject, body, recipients)


async def notify_task_result(task, container_name: str) -> None:
    """任务完成/失败后的通知邮件。是否发送由 notify.enabled 控制。"""
    enabled = await settings_service.get_bool("notify.enabled", True)
    if not enabled:
        return
    success = task.status in ("done", "notified", "mr_created")
    subject = f"[BugfixAgent] {container_name} {task.error_type or '错误'} 修复{'成功' if success else '失败'}"
    body = (
        f"容器: {container_name}\n"
        f"错误类型: {task.error_type}\n"
        f"错误信息: {task.message}\n\n"
        f"堆栈摘要:\n{task.stack_summary}\n\n"
        f"multica 任务: {task.multica_task_id or '无'}\n"
        f"修复分支: {task.branch_name or '无'}\n"
        f"MR/PR 链接: {task.mr_url or '无'}\n"
        f"任务状态: {task.status}\n"
    )
    if task.error_detail:
        body += f"\n失败原因:\n{task.error_detail[:1000]}\n"
    try:
        await send_email(subject, body)
    except Exception as e:  # noqa: BLE001
        raise NotifyError(f"邮件发送失败: {e}") from e
