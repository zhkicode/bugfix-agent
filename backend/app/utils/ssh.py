import asyncio

import paramiko

from app.models import Server
from app.utils.crypto import decrypt


async def run_remote(
    server: Server, command: str, timeout: int = 60
) -> tuple[int, str]:
    """SSH 到远程服务器执行命令，返回 (exit_code, stdout+stderr)。"""

    def _run() -> tuple[int, str]:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=server.host,
                port=server.port,
                username=server.username,
                password=decrypt(server.password_enc),
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False,
            )
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            code = stdout.channel.recv_exit_status()
            return code, (out + ("\n" + err if err else "")).strip()
        finally:
            client.close()

    return await asyncio.to_thread(_run)


async def test_connection(server: Server) -> tuple[bool, str]:
    code, output = await run_remote(server, "echo ok", timeout=15)
    return code == 0 and "ok" in output, output or f"exit={code}"
