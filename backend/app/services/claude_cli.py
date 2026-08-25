"""Claude CLI 调用封装。"""
import asyncio
import json
import os

from app.services import settings_service


class ClaudeCliError(RuntimeError):
    pass


async def _claude_env() -> dict[str, str]:
    """面板中配置的认证信息（token/网关/模型）注入子进程环境变量。"""
    env = dict(os.environ)
    token = await settings_service.get_setting("claude.auth_token", "")
    if token:
        env["ANTHROPIC_AUTH_TOKEN"] = token
    base_url = await settings_service.get_setting("claude.base_url", "")
    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url
    model = await settings_service.get_setting("claude.model", "")
    if model:
        env["ANTHROPIC_MODEL"] = model
    return env


async def run_claude(
    prompt: str,
    cwd: str | None = None,
    skip_permissions: bool = False,
    timeout: int | None = None,
) -> str:
    """运行 `claude -p`，返回 result 文本。"""
    claude_path = await settings_service.get_setting("claude.path", "claude")
    if timeout is None:
        timeout = await settings_service.get_int("claude.timeout_sec", 1800)

    cmd = [claude_path, "-p", prompt, "--output-format", "json"]
    if skip_permissions:
        cmd.append("--dangerously-skip-permissions")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        env=await _claude_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise ClaudeCliError(f"claude CLI 超时（{timeout}s）")

    if proc.returncode != 0:
        raise ClaudeCliError(
            f"claude CLI 退出码 {proc.returncode}: {stderr.decode()[:500]}"
        )
    try:
        data = json.loads(stdout.decode())
    except json.JSONDecodeError as e:
        raise ClaudeCliError(f"claude CLI 输出非 JSON: {e}") from e
    return data.get("result", "")


def extract_json(text: str) -> dict | None:
    """从模型输出中提取 JSON 对象（容忍 markdown 代码块包裹）。"""
    text = text.strip()
    if text.startswith("```"):
        text = re_strip_fence(text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def re_strip_fence(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)
