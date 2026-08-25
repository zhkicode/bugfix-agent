import json

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Container, FixLog, Task, TERMINAL_STATUSES
from app.schemas import FixLogOut, TaskBrief, TaskDetail, TaskPage
from app.services import fixer

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _brief(t: Task, container_name: str) -> TaskBrief:
    return TaskBrief(
        id=t.id, container_id=t.container_id, container_name=container_name,
        error_type=t.error_type, message=t.message, status=t.status,
        multica_task_id=t.multica_task_id, branch_name=t.branch_name,
        mr_url=t.mr_url, retry_count=t.retry_count, fingerprint=t.fingerprint,
        created_at=t.created_at, updated_at=t.updated_at,
    )


@router.get("", response_model=TaskPage)
async def list_tasks(
    status: str | None = None,
    container_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
):
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    conditions = []
    if status == "active":
        conditions.append(~Task.status.in_(TERMINAL_STATUSES))
    elif status:
        conditions.append(Task.status == status)
    if container_id:
        conditions.append(Task.container_id == container_id)

    from sqlalchemy import and_

    async with SessionLocal() as session:
        base = select(Task, Container.name).join(
            Container, Task.container_id == Container.id
        )
        count_stmt = select(func.count()).select_from(Task)
        if conditions:
            base = base.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await session.execute(count_stmt)).scalar_one()
        rows = (
            await session.execute(
                base.order_by(Task.id.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
    return TaskPage(
        total=total,
        items=[_brief(t, name) for t, name in rows],
    )


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(task_id: int):
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(Task, Container.name).join(
                    Container, Task.container_id == Container.id
                ).where(Task.id == task_id)
            )
        ).first()
        if row is None:
            raise HTTPException(404, "任务不存在")
        task, container_name = row
        logs = (
            await session.execute(
                select(FixLog).where(FixLog.task_id == task_id).order_by(FixLog.id)
            )
        ).scalars().all()
    return TaskDetail(
        **_brief(task, container_name).model_dump(),
        stack_summary=task.stack_summary,
        suspect_files=json.loads(task.suspect_files or "[]"),
        log_excerpt=task.log_excerpt,
        error_detail=task.error_detail,
        claude_output=task.claude_output,
        ts_detected=task.ts_detected, ts_multica=task.ts_multica,
        ts_cloned=task.ts_cloned, ts_fixed=task.ts_fixed,
        ts_pushed=task.ts_pushed, ts_mr=task.ts_mr, ts_notified=task.ts_notified,
        logs=[FixLogOut(**{k: getattr(l, k) for k in
                           ("id", "stage", "level", "message", "created_at")})
              for l in logs],
    )


@router.post("/{task_id}/retry")
async def retry_task(task_id: int):
    ok = await fixer.retry_task(task_id)
    if not ok:
        raise HTTPException(400, "仅 failed 状态的任务可以重试")
    return {"ok": True}
