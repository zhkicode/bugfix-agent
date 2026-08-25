from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import Container, Server
from app.schemas import ServerCreate, ServerOut, ServerUpdate
from app.utils import ssh
from app.utils.crypto import encrypt, mask

router = APIRouter(prefix="/api/servers", tags=["servers"])


@router.get("", response_model=list[ServerOut])
async def list_servers():
    async with SessionLocal() as session:
        rows = (await session.execute(select(Server).order_by(Server.id))).scalars().all()
    return [
        ServerOut(
            id=r.id, name=r.name, host=r.host, port=r.port, username=r.username,
            password=mask(r.password_enc), enabled=r.enabled, created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("", response_model=ServerOut)
async def create_server(body: ServerCreate):
    async with SessionLocal() as session:
        server = Server(
            name=body.name, host=body.host, port=body.port, username=body.username,
            password_enc=encrypt(body.password), enabled=body.enabled,
        )
        session.add(server)
        await session.commit()
        await session.refresh(server)
    return ServerOut(
        id=server.id, name=server.name, host=server.host, port=server.port,
        username=server.username, password=mask(server.password_enc),
        enabled=server.enabled, created_at=server.created_at,
    )


@router.put("/{server_id}", response_model=ServerOut)
async def update_server(server_id: int, body: ServerUpdate):
    async with SessionLocal() as session:
        server = await session.get(Server, server_id)
        if server is None:
            raise HTTPException(404, "服务器不存在")
        if body.name is not None:
            server.name = body.name
        if body.host is not None:
            server.host = body.host
        if body.port is not None:
            server.port = body.port
        if body.username is not None:
            server.username = body.username
        if body.password:
            server.password_enc = encrypt(body.password)
        if body.enabled is not None:
            server.enabled = body.enabled
        await session.commit()
        await session.refresh(server)
    return ServerOut(
        id=server.id, name=server.name, host=server.host, port=server.port,
        username=server.username, password=mask(server.password_enc),
        enabled=server.enabled, created_at=server.created_at,
    )


@router.delete("/{server_id}")
async def delete_server(server_id: int):
    async with SessionLocal() as session:
        server = await session.get(Server, server_id)
        if server is None:
            raise HTTPException(404, "服务器不存在")
        used = (
            await session.execute(
                select(Container.id).where(Container.server_id == server_id)
            )
        ).first()
        if used:
            raise HTTPException(400, "该服务器下还有容器，请先删除容器")
        await session.execute(delete(Server).where(Server.id == server_id))
        await session.commit()
    return {"ok": True}


@router.post("/{server_id}/test")
async def test_server(server_id: int):
    async with SessionLocal() as session:
        server = await session.get(Server, server_id)
        if server is None:
            raise HTTPException(404, "服务器不存在")
        session.expunge(server)
    ok, output = await ssh.test_connection(server)
    return {"ok": ok, "output": output}


@router.get("/{server_id}/docker-containers")
async def list_docker_containers(server_id: int):
    """列出服务器上正在运行的 Docker 容器，供面板直接选择。"""
    async with SessionLocal() as session:
        server = await session.get(Server, server_id)
        if server is None:
            raise HTTPException(404, "服务器不存在")
        session.expunge(server)

    code, output = await ssh.run_remote(
        server,
        "docker ps --format '{{.Names}}\\t{{.Image}}\\t{{.Status}}'",
        timeout=30,
    )
    if code != 0:
        return {
            "ok": False,
            "output": output[:300] or f"exit={code}",
            "items": [],
        }
    return {"ok": True, "output": "", "items": parse_docker_ps(output)}


def parse_docker_ps(output: str) -> list[dict]:
    items = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        items.append(
            {
                "name": parts[0],
                "image": parts[1] if len(parts) > 1 else "",
                "status": parts[2] if len(parts) > 2 else "",
            }
        )
    return items
