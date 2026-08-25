from fastapi import APIRouter
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Container, Server, Task

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def stats():
    async with SessionLocal() as session:
        server_count = (await session.execute(select(func.count(Server.id)))).scalar_one()
        container_count = (
            await session.execute(select(func.count(Container.id)))
        ).scalar_one()
        task_rows = (
            await session.execute(
                select(Task.status, func.count(Task.id)).group_by(Task.status)
            )
        ).all()
    by_status = {status: count for status, count in task_rows}
    return {
        "servers": server_count,
        "containers": container_count,
        "tasks_total": sum(by_status.values()),
        "tasks_active": sum(
            c for s, c in task_rows if s not in ("done", "failed")
        ),
        "tasks_done": by_status.get("done", 0),
        "tasks_failed": by_status.get("failed", 0),
        "by_status": by_status,
    }
