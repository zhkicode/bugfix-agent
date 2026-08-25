"""增量采集远程容器日志：docker logs --since <unix_ts> --timestamps。"""
import re

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Container, Server
from app.services import settings_service
from app.utils.ssh import run_remote

# docker logs --timestamps 行首格式：2024-01-02T03:04:05.123456789Z
_TS_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?Z"
)

MAX_LOG_CHARS = 40000  # 送入 AI 分析的最大日志长度


async def collect_incremental(container: Container) -> tuple[str, float | None]:
    """返回 (增量日志文本, 新锚点 unix 秒)。无新日志时文本为空。"""
    async with SessionLocal() as session:
        server = (
            await session.execute(select(Server).where(Server.id == container.server_id))
        ).scalar_one_or_none()
    if server is None:
        raise RuntimeError(f"container {container.id} 关联的 server 不存在")

    if container.last_log_ts:
        since = str(int(container.last_log_ts))
    else:
        lookback = await settings_service.get_int("poll.initial_lookback_sec", 300)
        import time

        since = f"{int(time.time()) - lookback}"

    cmd = (
        f"docker logs --since {since} --timestamps "
        f"--tail 2000 {_shell_quote(container.name)} 2>&1"
    )
    code, output = await run_remote(server, cmd, timeout=90)
    if code != 0:
        raise RuntimeError(f"docker logs 执行失败: {output[:500]}")
    if not output:
        return "", None

    # 从最后一行提取新锚点（纳秒截断为微秒）
    anchor = _last_timestamp(output) or _now_ts()
    text = output[-MAX_LOG_CHARS:]
    return text, anchor


def _shell_quote(s: str) -> str:
    import shlex

    return shlex.quote(s)


def _now_ts() -> float:
    import time

    return time.time()


def _last_timestamp(log_text: str) -> float | None:
    import datetime as dt

    last: float | None = None
    for line in log_text.splitlines():
        m = _TS_RE.match(line)
        if not m:
            continue
        y, mo, d, h, mi, s, frac = m.groups()
        micro = int((frac or "0").ljust(6, "0")[:6])
        try:
            ts = dt.datetime(
                int(y), int(mo), int(d), int(h), int(mi), int(s), micro,
                tzinfo=dt.timezone.utc,
            ).timestamp()
        except ValueError:
            continue
        last = ts
    return last
