from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import Container, Server
from app.schemas import ContainerCreate, ContainerOut, ContainerUpdate
from app.services import gitops
from app.services.scheduler import scheduler
from app.utils.crypto import decrypt, encrypt, mask

router = APIRouter(prefix="/api/containers", tags=["containers"])


async def _to_out(c: Container, server_name: str) -> ContainerOut:
    return ContainerOut(
        id=c.id, server_id=c.server_id, server_name=server_name, name=c.name,
        repo_provider=c.repo_provider, repo_url=c.repo_url,
        repo_token=mask(c.repo_token_enc), repo_default_branch=c.repo_default_branch,
        poll_interval_sec=c.poll_interval_sec, enabled=c.enabled,
        last_log_ts=c.last_log_ts, created_at=c.created_at,
    )


async def _get_container(session, container_id: int) -> Container:
    container = await session.get(Container, container_id)
    if container is None:
        raise HTTPException(404, "容器不存在")
    return container


@router.get("", response_model=list[ContainerOut])
async def list_containers():
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Container, Server.name).join(
                    Server, Container.server_id == Server.id
                ).order_by(Container.id)
            )
        ).all()
    return [await _to_out(c, name) for c, name in rows]


@router.post("", response_model=ContainerOut)
async def create_container(body: ContainerCreate):
    if body.repo_provider not in ("gitlab", "github"):
        raise HTTPException(400, "repo_provider 必须是 gitlab 或 github")
    async with SessionLocal() as session:
        if await session.get(Server, body.server_id) is None:
            raise HTTPException(400, "关联的服务器不存在")
        container = Container(
            server_id=body.server_id, name=body.name,
            repo_provider=body.repo_provider, repo_url=body.repo_url,
            repo_token_enc=encrypt(body.repo_token),
            repo_default_branch=body.repo_default_branch,
            poll_interval_sec=body.poll_interval_sec, enabled=body.enabled,
        )
        session.add(container)
        await session.commit()
        await session.refresh(container)
        server_name = (await session.get(Server, container.server_id)).name
        out = await _to_out(container, server_name)
    if container.enabled:
        scheduler.start_container(container.id)
    return out


@router.put("/{container_id}", response_model=ContainerOut)
async def update_container(container_id: int, body: ContainerUpdate):
    async with SessionLocal() as session:
        container = await _get_container(session, container_id)
        if body.server_id is not None:
            if await session.get(Server, body.server_id) is None:
                raise HTTPException(400, "关联的服务器不存在")
            container.server_id = body.server_id
        if body.name is not None:
            container.name = body.name
        if body.repo_provider is not None:
            if body.repo_provider not in ("gitlab", "github"):
                raise HTTPException(400, "repo_provider 必须是 gitlab 或 github")
            container.repo_provider = body.repo_provider
        if body.repo_url is not None:
            container.repo_url = body.repo_url
        if body.repo_token:
            container.repo_token_enc = encrypt(body.repo_token)
        if body.repo_default_branch is not None:
            container.repo_default_branch = body.repo_default_branch
        if body.poll_interval_sec is not None:
            container.poll_interval_sec = body.poll_interval_sec
        if body.enabled is not None:
            container.enabled = body.enabled
        await session.commit()
        await session.refresh(container)
        server_name = (await session.get(Server, container.server_id)).name
        out = await _to_out(container, server_name)
    await scheduler.reload_container(container_id)
    return out


@router.delete("/{container_id}")
async def delete_container(container_id: int):
    async with SessionLocal() as session:
        await _get_container(session, container_id)
        from app.models import FixLog, Task

        task_ids = (
            await session.execute(select(Task.id).where(Task.container_id == container_id))
        ).scalars().all()
        if task_ids:
            await session.execute(
                delete(FixLog).where(FixLog.task_id.in_(task_ids))
            )
            await session.execute(
                delete(Task).where(Task.container_id == container_id)
            )
        await session.execute(delete(Container).where(Container.id == container_id))
        await session.commit()
    await scheduler.stop_container(container_id)
    return {"ok": True}


@router.post("/{container_id}/poll-now")
async def poll_now(container_id: int):
    result = await scheduler.poll_once(container_id)
    return result


@router.post("/{container_id}/test-repo")
async def test_repo(container_id: int):
    async with SessionLocal() as session:
        container = await _get_container(session, container_id)
        session.expunge(container)
    if not container.repo_url:
        return {"ok": False, "output": "未配置仓库地址"}
    ok, output = await gitops.ls_remote_ok(
        container.repo_url, container.repo_provider, decrypt(container.repo_token_enc)
    )
    return {"ok": ok, "output": output}
