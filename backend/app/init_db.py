from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Setting

DEFAULT_SETTINGS = {
    "poll.default_interval_sec": ("60", "int"),
    "poll.initial_lookback_sec": ("300", "int"),
    "dedup.cooldown_hours": ("72", "int"),
    "notify.enabled": ("true", "bool"),
    "notify.recipients": ("zkcode@126.com", "str"),
    "smtp.host": ("smtp.126.com", "str"),
    "smtp.port": ("465", "int"),
    "smtp.user": ("", "str"),
    "smtp.pass": ("", "str"),
    "smtp.from": ("", "str"),
    "smtp.secure": ("ssl", "str"),  # ssl|starttls|none
    "claude.path": ("claude", "str"),
    "claude.timeout_sec": ("1800", "int"),
    "claude.auth_token": ("", "str"),
    "claude.base_url": ("", "str"),
    "claude.model": ("", "str"),
    "multica.create_cmd": (
        'multica issue create --title {title} --description {desc}',
        "str",
    ),
    "multica.id_regex": (
        r'([A-Z]{2,6}-\d+)',
        "str",
    ),
    "multica.status_cmd": ("multica issue get {task_id}", "str"),
}


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        for key, (value, vtype) in DEFAULT_SETTINGS.items():
            existing = await session.get(Setting, key)
            if existing is None:
                session.add(Setting(key=key, value=value, value_type=vtype))
        await session.commit()
