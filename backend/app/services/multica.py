"""multica CLI 适配器：命令模板与 ID 提取正则均来自 settings，可随时适配真实 CLI。"""
import asyncio
import re
import shlex

from app.services import settings_service


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


async def create_task(title: str, description: str) -> tuple[str | None, str]:
    """执行创建任务命令，返回 (multica 任务 ID 或 None, 命令输出)。"""
    template = await settings_service.get_setting(
        "multica.create_cmd", "multica task create --title {title} --desc {desc}"
    )
    if not template.strip():
        return None, ""

    # title/desc 来自 AI 输出，必须 shell 转义防注入
    cmd = template.format_map(
        _SafeDict(title=shlex.quote(title), desc=shlex.quote(description))
    )
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        proc.kill()
        return None, "命令超时"
    output = (stdout.decode() + stderr.decode()).strip()
    if proc.returncode != 0:
        return None, output or f"exit={proc.returncode}"

    pattern = await settings_service.get_setting("multica.id_regex", "")
    task_id = None
    if pattern:
        m = re.search(pattern, output)
        if m:
            task_id = m.group(1) if m.groups() else m.group(0)
    return task_id, output


async def get_status(task_id: str) -> str:
    template = await settings_service.get_setting("multica.status_cmd", "")
    if not template.strip():
        return ""
    cmd = template.format_map(_SafeDict(task_id=shlex.quote(task_id)))
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        return ""
    return stdout.decode().strip()
