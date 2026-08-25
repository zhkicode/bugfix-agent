"""错误指纹：规范化 AI 给出的签名并 sha256，用于去重判断。"""
import datetime as dt
import hashlib
import re

from sqlalchemy import or_, select

from app.database import SessionLocal
from app.models import TERMINAL_STATUSES, Task, utcnow
from app.services import settings_service


def make_fingerprint(raw_signature: str, error_type: str = "", message: str = "") -> str:
    """对 AI 输出的错误签名做轻量规范化后 sha256。

    AI 已被要求去除时间戳/请求ID等易变内容；这里再兜底去掉十六进制串、
    UUID、纯数字、多余空白，防止同一错误因细微噪声生成不同指纹。
    """
    text = raw_signature.strip() or f"{error_type}: {message}".strip()
    # 长十六进制串 / UUID
    text = re.sub(r"\b[0-9a-f]{8,}\b", "", text, flags=re.IGNORECASE)
    # 混合十六进制短 ID（同时含数字与 a-f 字母，如 9c22）
    text = re.sub(
        r"\b(?=[0-9a-f]*[0-9])(?=[0-9a-f]*[a-f])[0-9a-f]{4,}\b",
        "", text, flags=re.IGNORECASE,
    )
    text = re.sub(r"\b\d+\b", "", text)  # 纯数字
    text = re.sub(r"\s+", " ", text)
    text = text.strip().lower()[:500]
    return hashlib.sha256(text.encode()).hexdigest()


async def is_duplicate(container_id: int, fingerprint: str) -> bool:
    """同容器同指纹：存在非终态任务，或终态任务仍在冷却期内 → 判定为重复。"""
    cooldown_hours = await settings_service.get_int("dedup.cooldown_hours", 72)
    cutoff = utcnow() - dt.timedelta(hours=cooldown_hours)
    async with SessionLocal() as session:
        stmt = select(Task.id).where(
            Task.container_id == container_id,
            Task.fingerprint == fingerprint,
            or_(
                ~Task.status.in_(TERMINAL_STATUSES),
                Task.updated_at >= cutoff,
            ),
        )
        return (await session.execute(stmt)).first() is not None
