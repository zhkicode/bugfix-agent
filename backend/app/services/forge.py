"""通过仓库 API 创建 MR（GitLab/极狐）或 PR（GitHub）。"""
from urllib.parse import quote

import httpx

from app.services import gitops


class ForgeError(RuntimeError):
    pass


async def create_merge_request(
    repo_url: str, token: str,
    source_branch: str, target_branch: str,
    title: str, description: str,
) -> str:
    """GitLab（含极狐 jihulab.com / 自建实例），返回 MR web_url。"""
    host, path = gitops.parse_repo_url(repo_url)
    project_id = quote(path, safe="")
    base = f"https://{host}/api/v4/projects/{project_id}/merge_requests"
    body = {
        "source_branch": source_branch,
        "target_branch": target_branch,
        "title": title,
        "description": description,
        "remove_source_branch": True,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            base, json=body, headers={"PRIVATE-TOKEN": token}
        )
    if resp.status_code not in (200, 201):
        raise ForgeError(f"GitLab 创建 MR 失败 [{resp.status_code}]: {resp.text[:300]}")
    return resp.json().get("web_url", "")


async def create_pull_request(
    repo_url: str, token: str,
    source_branch: str, target_branch: str,
    title: str, description: str,
) -> str:
    """GitHub，返回 PR html_url。"""
    host, path = gitops.parse_repo_url(repo_url)
    if host != "github.com":
        raise ForgeError(f"GitHub PR 仅支持 github.com，当前 host: {host}")
    url = f"https://api.github.com/repos/{path}/pulls"
    body = {
        "title": title,
        "head": source_branch,
        "base": target_branch,
        "body": description,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url, json=body, headers={"Authorization": f"Bearer {token}"}
        )
    if resp.status_code not in (200, 201):
        raise ForgeError(f"GitHub 创建 PR 失败 [{resp.status_code}]: {resp.text[:300]}")
    return resp.json().get("html_url", "")


async def create_mr_or_pr(provider: str, repo_url: str, token: str, **kwargs) -> str:
    if provider == "github":
        return await create_pull_request(repo_url, token, **kwargs)
    return await create_merge_request(repo_url, token, **kwargs)
