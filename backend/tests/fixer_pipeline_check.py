"""修复管线失败路径冒烟测试：无效仓库 → 任务应标记 failed 且可重试。"""
import asyncio
import json
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.database import SessionLocal, engine
from app.init_db import init_db
from app.models import Container, FixLog, Server, Task, utcnow
from app.services import fixer
from app.utils.crypto import encrypt


async def main() -> None:
    await init_db()
    async with SessionLocal() as session:
        server = Server(name="e2e", host="127.0.0.1", username="x",
                        password_enc=encrypt("x"), enabled=True)
        session.add(server)
        await session.flush()
        container = Container(
            server_id=server.id, name="e2e-container",
            repo_provider="gitlab",
            repo_url="https://invalid.invalid/group/repo.git",
            repo_token_enc=encrypt("dummy"), enabled=False,
        )
        session.add(container)
        await session.flush()
        task = Task(
            container_id=container.id, fingerprint="abc",
            error_type="ZeroDivisionError", message="division by zero",
            status="detected", ts_detected=utcnow(),
        )
        session.add(task)
        await session.commit()
        task_id, container_id, server_id = task.id, container.id, server.id

    await fixer.run_pipeline(task_id)

    async with SessionLocal() as session:
        t = await session.get(Task, task_id)
        print(f"status={t.status}")
        print(f"error_detail={t.error_detail[:200]}")
        logs = (
            await session.execute(select(FixLog).where(FixLog.task_id == task_id))
        ).scalars().all()
        for l in logs:
            print(f"  [{l.stage}/{l.level}] {l.message[:100]}")
        assert t.status == "failed", "无效仓库应导致任务 failed"
        assert any("失败" in (l.message or "") for l in logs), "应有失败日志"

        # failed 任务可重试；重试后状态归位并异步重跑
        ok = await fixer.retry_task(task_id)
        assert ok, "failed 任务应可重试"
        session.expire_all()
        t2 = await session.get(Task, task_id)
        assert t2.retry_count == 1
        # 等待重试派生的后台管线结束再清理
        await asyncio.sleep(3)
        # 清理
        for row in logs:
            await session.delete(row)
        await session.delete(t2)
        c = await session.get(Container, container_id)
        s = await session.get(Server, server_id)
        await session.delete(c)
        await session.delete(s)
        await session.commit()

    # 等待重试派生的后台任务结束，避免事件循环警告
    await asyncio.sleep(0.5)
    await engine.dispose()
    print("[done] 修复管线失败/重试路径测试通过")


asyncio.run(main())
