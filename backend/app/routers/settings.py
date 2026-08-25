import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas import SettingsUpdate
from app.services import notifier, settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings():
    values = await settings_service.get_all_settings(masked=True)
    return {"values": values}


@router.put("")
async def update_settings(body: SettingsUpdate):
    await settings_service.update_settings(body.values)
    return {"ok": True}


class TestSmtpBody(BaseModel):
    recipient: str = ""


@router.post("/test-smtp")
async def test_smtp(body: TestSmtpBody):
    recipients = [body.recipient] if body.recipient else None
    try:
        await notifier.send_email(
            "[BugfixAgent] SMTP 测试邮件", "这是一封 BugfixAgent 的测试邮件，收到即配置成功。",
            recipients=recipients,
        )
        return {"ok": True, "message": "测试邮件已发送"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)}


@router.post("/test-claude")
async def test_claude():
    """用面板配置的认证跑一次最小 claude -p，验证网关/令牌可用。"""
    from app.services import claude_cli

    try:
        result = await claude_cli.run_claude(
            "只回复两个字母：OK", timeout=90
        )
        return {"ok": True, "message": f"claude 可用，回复: {result[:100]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)}


@router.post("/test-multica")
async def test_multica():
    """验证 multica CLI 已安装且已登录（能列出 issue 即认证有效）。"""
    proc = await asyncio.create_subprocess_shell(
        "multica issue list --limit 1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        proc.kill()
        return {"ok": False, "message": "multica 命令超时"}
    output = stdout.decode(errors="replace").strip()
    if proc.returncode != 0:
        return {"ok": False, "message": output[:300] or f"exit={proc.returncode}"}
    return {"ok": True, "message": f"multica 认证有效:\n{output[:300]}"}
