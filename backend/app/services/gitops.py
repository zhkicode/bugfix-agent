"""Git 操作：带 token 的 clone、建分支、commit、push。"""
import asyncio
import re
from urllib.parse import urlparse

GIT_USER_NAME = "BugfixAgent"
GIT_USER_EMAIL = "bugfix-agent@localhost"


class GitError(RuntimeError):
    pass


_CRED_RE = re.compile(r"https://([^:\s@]+):[^@\s]+@")


def redact(text: str) -> str:
    """去除输出中带凭据的 URL 明文。"""
    return _CRED_RE.sub(r"https://\1:***@", text)


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """解析 https 仓库地址 → (host, 去掉 .git 的路径)。"""
    url = repo_url.strip()
    if url.startswith("git@"):
        # git@host:ns/repo.git → https
        host, _, path = url[4:].partition(":")
        url = f"https://{host}/{path}"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    return parsed.netloc, path


def authed_repo_url(repo_url: str, provider: str, token: str) -> str:
    host, path = parse_repo_url(repo_url)
    user = "x-access-token" if provider == "github" else "oauth2"
    return f"https://{user}:{token}@{host}/{path}.git"


async def _git(args: list[str], cwd: str | None = None, timeout: int = 300) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise GitError(f"git {' '.join(args[:3])} 超时")
    out = stdout.decode(errors="replace").strip()
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args[:3])} 失败: {redact(out[:500])}")
    return out


async def ls_remote_ok(repo_url: str, provider: str, token: str) -> tuple[bool, str]:
    try:
        url = authed_repo_url(repo_url, provider, token)
        out = await _git(["ls-remote", "--heads", url], timeout=30)
        return True, out[:200]
    except GitError as e:
        return False, str(e)


async def clone(authed_url: str, ws: str, branch: str) -> None:
    await _git(
        ["clone", "--depth", "50", "--branch", branch, authed_url, ws], timeout=600
    )


async def create_branch(ws: str, branch: str) -> None:
    await _git(["checkout", "-b", branch], cwd=ws)


async def has_changes(ws: str) -> bool:
    out = await _git(["status", "--porcelain"], cwd=ws)
    return bool(out)


async def commit_all(ws: str, message: str) -> None:
    await _git(["add", "-A"], cwd=ws)
    await _git(
        [
            "-c", f"user.name={GIT_USER_NAME}",
            "-c", f"user.email={GIT_USER_EMAIL}",
            "commit", "-m", message,
        ],
        cwd=ws,
    )


async def push(ws: str, branch: str) -> None:
    await _git(["push", "-u", "origin", branch], cwd=ws, timeout=300)


async def default_branch_hint(authed_url: str) -> str:
    """克隆前探测默认分支（HEAD 指向）。"""
    proc = await asyncio.create_subprocess_exec(
        "git", "ls-remote", "--symref", authed_url, "HEAD",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
    for line in stdout.decode().splitlines():
        if line.startswith("ref:"):
            _, _, ref = line.partition("ref:")
            ref = ref.split()[0] if ref.split() else ""
            if ref.startswith("refs/heads/"):
                return ref[len("refs/heads/"):]
    return ""
