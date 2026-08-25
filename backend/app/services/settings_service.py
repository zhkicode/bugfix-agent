from sqlalchemy import select

from app.config import SECRET_SETTING_KEYS
from app.database import SessionLocal
from app.models import Setting


async def get_all_settings(masked: bool = False) -> dict[str, str]:
    async with SessionLocal() as session:
        rows = (await session.execute(select(Setting))).scalars().all()
        result = {row.key: row.value for row in rows}
    if masked:
        for key in SECRET_SETTING_KEYS:
            if key in result and result[key]:
                result[key] = "******"
    return result


async def update_settings(values: dict[str, str]) -> None:
    async with SessionLocal() as session:
        for key, value in values.items():
            row = await session.get(Setting, key)
            if row is None:
                row = Setting(key=key, value_type="str")
                session.add(row)
            # 密文字段提交脱敏值时跳过，避免覆盖真实凭据
            if key in SECRET_SETTING_KEYS and value == "******":
                continue
            row.value = str(value)
        await session.commit()


async def get_setting(key: str, default: str = "") -> str:
    async with SessionLocal() as session:
        row = await session.get(Setting, key)
        return row.value if row and row.value != "" else default


async def get_int(key: str, default: int) -> int:
    try:
        return int(await get_setting(key, str(default)))
    except ValueError:
        return default


async def get_bool(key: str, default: bool) -> bool:
    return (await get_setting(key, str(default).lower())).lower() in ("1", "true", "yes")
