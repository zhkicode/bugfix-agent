"""轮询调度器：每个启用的容器一个 asyncio 循环（采集→AI 分析→去重→建任务→修复）。"""
import asyncio
import json
import logging

from sqlalchemy import select

from app.database import SessionLocal
from app.models import TERMINAL_STATUSES, Container, Task, utcnow
from app.services import analyzer, fingerprint, fixer, log_collector, settings_service

logger = logging.getLogger("bugfix_agent.scheduler")

# 持有后台任务引用，防止被 GC
_background: set[asyncio.Task] = set()


class Scheduler:
    def __init__(self) -> None:
        self._loops: dict[int, asyncio.Task] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    async def start(self) -> None:
        async with SessionLocal() as session:
            rows = (
                await session.execute(select(Container).where(Container.enabled))
            ).scalars().all()
        for c in rows:
            self.start_container(c.id)
        logger.info("scheduler 已启动，监听 %d 个容器", len(rows))

    async def shutdown(self) -> None:
        for task in self._loops.values():
            task.cancel()
        self._loops.clear()

    def start_container(self, container_id: int) -> None:
        running = self._loops.get(container_id)
        if running and not running.done():
            return
        self._loops[container_id] = asyncio.create_task(self._loop(container_id))

    async def stop_container(self, container_id: int) -> None:
        task = self._loops.pop(container_id, None)
        if task:
            task.cancel()

    async def reload_container(self, container_id: int) -> None:
        await self.stop_container(container_id)
        async with SessionLocal() as session:
            container = await session.get(Container, container_id)
        if container and container.enabled:
            self.start_container(container_id)

    def _lock(self, container_id: int) -> asyncio.Lock:
        if container_id not in self._locks:
            self._locks[container_id] = asyncio.Lock()
        return self._locks[container_id]

    async def _interval(self, container_id: int) -> int | None:
        """返回轮询间隔；容器已删除/停用时返回 None（结束循环）。"""
        async with SessionLocal() as session:
            container = await session.get(Container, container_id)
            if container is None or not container.enabled:
                return None
            if container.poll_interval_sec and container.poll_interval_sec > 0:
                return container.poll_interval_sec
        return await settings_service.get_int("poll.default_interval_sec", 60)

    async def _loop(self, container_id: int) -> None:
        while True:
            interval = await self._interval(container_id)
            if interval is None:
                logger.info("容器 %d 已删除或停用，轮询循环退出", container_id)
                return
            try:
                await self.poll_once(container_id)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.warning("容器 %d 轮询异常: %s", container_id, e)
            await asyncio.sleep(interval)

    async def poll_once(self, container_id: int) -> dict:
        """单次采集+分析。返回结果摘要（poll-now 接口也复用此函数）。"""
        async with self._lock(container_id):
            async with SessionLocal() as session:
                container = await session.get(Container, container_id)
                if container is None:
                    return {"error": "容器不存在"}
                if not container.enabled:
                    return {"error": "容器未启用"}
                session.expunge(container)

            try:
                logs, anchor = await log_collector.collect_incremental(container)
            except Exception as e:  # noqa: BLE001
                logger.warning("容器 %s 日志采集失败: %s", container.name, e)
                return {"error": f"日志采集失败: {e}"}

            if not logs:
                return {"status": "no_new_logs"}

            try:
                result = await analyzer.analyze_logs(
                    logs, container.name, container.repo_url
                )
            except Exception as e:  # noqa: BLE001
                # 分析失败不推进锚点，下轮重试同一片日志
                logger.warning("容器 %s 日志分析失败: %s", container.name, e)
                return {"error": f"日志分析失败: {e}"}

            # 分析成功，推进锚点
            if anchor:
                async with SessionLocal() as session:
                    c = await session.get(Container, container_id)
                    if c:
                        c.last_log_ts = anchor
                        await session.commit()

            if not result.has_error:
                return {"status": "no_error"}

            fp = fingerprint.make_fingerprint(
                result.fingerprint, result.error_type, result.message
            )
            if await fingerprint.is_duplicate(container_id, fp):
                logger.info("容器 %s 错误指纹 %s… 命中去重，跳过", container.name, fp[:12])
                return {"status": "duplicate_skipped", "fingerprint": fp}

            # 同容器同时只允许一个非终态任务
            async with SessionLocal() as session:
                active = (
                    await session.execute(
                        select(Task.id).where(
                            Task.container_id == container_id,
                            ~Task.status.in_(TERMINAL_STATUSES),
                        )
                    )
                ).first()
            if active:
                logger.info("容器 %s 已有进行中的任务，暂缓新任务", container.name)
                return {"status": "busy"}

            async with SessionLocal() as session:
                task = Task(
                    container_id=container_id,
                    fingerprint=fp,
                    error_type=result.error_type,
                    message=result.message,
                    stack_summary=result.stack_summary,
                    suspect_files=json.dumps(result.suspect_files, ensure_ascii=False),
                    log_excerpt=logs[:20000],
                    status="detected",
                    ts_detected=utcnow(),
                )
                session.add(task)
                await session.commit()
                await session.refresh(task)
                task_id = task.id

            t = asyncio.create_task(fixer.run_pipeline(task_id))
            _background.add(t)
            t.add_done_callback(_background.discard)
            logger.info("容器 %s 创建修复任务 #%d（指纹 %s…）", container.name, task_id, fp[:12])
            return {"status": "task_created", "task_id": task_id, "fingerprint": fp}


scheduler = Scheduler()
