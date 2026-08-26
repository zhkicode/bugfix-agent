"""修复编排状态机：clone → claude 修复 → push → MR/PR → 邮件。"""
import asyncio
import json
import shutil
from pathlib import Path

from sqlalchemy import select

from app.config import WORKSPACE_DIR
from app.database import SessionLocal
from app.models import Container, FixLog, Task, utcnow
from app.services import claude_cli, forge, gitops, notifier
from app.utils.crypto import decrypt

FIX_PROMPT = """本仓库对应的线上服务出现了以下错误（来自容器 {container} 的运行日志），请定位并修复：

错误类型: {error_type}
错误信息: {message}

堆栈/日志摘要:
{stack}

可疑文件: {suspects}

要求:
- 优先查看可疑文件与堆栈中提到的文件
- 做最小必要的修改，不要重构无关代码
- 如果仓库有测试，运行相关测试验证修复
- 不要执行任何 git 命令（提交由外部流程处理）

完成后简要总结：修改了哪些文件、为什么这样修复。"""


async def _save(task_id: int, **fields) -> None:
    async with SessionLocal() as session:
        task = await session.get(Task, task_id)
        if task is None:
            return
        for k, v in fields.items():
            setattr(task, k, v)
        task.updated_at = utcnow()
        await session.commit()


async def _log(task_id: int, stage: str, level: str, message: str) -> None:
    async with SessionLocal() as session:
        session.add(
            FixLog(task_id=task_id, stage=stage, level=level, message=message[:4000])
        )
        await session.commit()


async def _load(task_id: int) -> tuple[Task, Container] | None:
    async with SessionLocal() as session:
        task = await session.get(Task, task_id)
        if task is None:
            return None
        container = (
            await session.execute(
                select(Container).where(Container.id == task.container_id)
            )
        ).scalar_one_or_none()
        if container is None:
            return None
        # 立即关闭 session，避免长事务跨整个修复流程
        session.expunge(task)
        session.expunge(container)
        return task, container


def _workspace(task_id: int) -> Path:
    return WORKSPACE_DIR / f"task_{task_id}"


async def _reset_workspace(ws: Path) -> None:
    if ws.exists():
        await asyncio.to_thread(shutil.rmtree, ws)
    ws.parent.mkdir(parents=True, exist_ok=True)


async def run_pipeline(task_id: int) -> None:
    loaded = await _load(task_id)
    if loaded is None:
        return
    task, container = loaded

    try:
        # 1. 克隆仓库并建分支
        await _save(task_id, status="cloning")
        token = decrypt(container.repo_token_enc)
        authed_url = gitops.authed_repo_url(
            container.repo_url, container.repo_provider, token
        )
        ws = _workspace(task_id)
        await _reset_workspace(ws)
        target_branch = container.repo_default_branch or "main"
        await gitops.clone(authed_url, str(ws), target_branch)
        # 重试时换分支名，避免与远端已存在的同名分支产生 non-fast-forward 冲突
        branch = f"bugfix/agent-{task_id}" + (
            f"-r{task.retry_count}" if task.retry_count else ""
        )
        await gitops.create_branch(str(ws), branch)
        await _save(task_id, branch_name=branch, ts_cloned=utcnow())
        await _log(task_id, "cloning", "info", f"已克隆仓库并创建分支 {branch}")

        # 2. claude 修复
        await _save(task_id, status="fixing")
        prompt = FIX_PROMPT.format(
            container=container.name,
            error_type=task.error_type,
            message=task.message,
            stack=(task.stack_summary or task.log_excerpt)[:6000],
            suspects="\n".join(json.loads(task.suspect_files or "[]")),
        )
        output = await claude_cli.run_claude(
            prompt, cwd=str(ws), skip_permissions=True
        )
        await _save(
            task_id, claude_output=output[:8000], ts_fixed=utcnow()
        )
        await _log(task_id, "fixing", "info", f"claude 修复完成:\n{output[:1500]}")

        if not await gitops.has_changes(str(ws)):
            raise RuntimeError("claude 未产生任何代码修改（无 diff），视为修复失败")

        # 3. commit + push
        await _save(task_id, status="pushing")
        commit_msg = (
            f"fix: {task.error_type}: {task.message[:100]}\n\n"
            f"Automated fix by BugfixAgent (task #{task_id}, "
            f"fingerprint {task.fingerprint[:12]})\n\n{output[:500]}"
        )
        await gitops.commit_all(str(ws), commit_msg)
        await gitops.push(str(ws), branch)
        await _save(task_id, ts_pushed=utcnow())
        await _log(task_id, "pushing", "info", f"已提交并推送分支 {branch}")

        # 4. 创建 MR / PR
        if not task.mr_url:
            mr_url = await forge.create_mr_or_pr(
                container.repo_provider,
                container.repo_url,
                token,
                source_branch=branch,
                target_branch=target_branch,
                title=f"fix: {task.error_type}: {task.message[:60]}",
                description=(
                    f"### 自动修复任务 #{task_id}\n\n"
                    f"**容器**: {container.name}\n\n"
                    f"**错误**: {task.error_type}: {task.message}\n\n"
                    f"**堆栈**:\n```\n{task.stack_summary[:1500]}\n```\n\n"

                    f"**AI 修复说明**:\n{output[:2000]}\n\n"
                    f"---\n由 BugfixAgent 自动生成，请人工审核后合并。"
                ),
            )
            await _save(task_id, mr_url=mr_url, status="mr_created", ts_mr=utcnow())
            await _log(task_id, "mr", "info", f"MR/PR 已创建: {mr_url}")
        else:
            await _save(task_id, status="mr_created")

        # 5. 邮件通知（notify.enabled=false 时静默跳过）
        await _save(task_id, status="notified")
        try:
            await notifier.notify_task_result(task, container.name)
            await _save(task_id, ts_notified=utcnow())
            await _log(task_id, "notify", "info", "通知邮件已发送")
        except notifier.NotifyError as e:
            await _log(task_id, "notify", "warn", str(e))

        await _save(task_id, status="done")
        await _log(task_id, "done", "info", "任务完成")

    except Exception as e:  # noqa: BLE001
        await _save(task_id, status="failed", error_detail=str(e)[:2000])
        await _log(task_id, "pipeline", "error", f"任务失败: {e}")
        # 失败也要通知（若开启）
        try:
            loaded2 = await _load(task_id)
            if loaded2:
                t2, c2 = loaded2
                await notifier.notify_task_result(t2, c2.name)
                await _log(task_id, "notify", "info", "失败通知邮件已发送")
        except notifier.NotifyError as ne:
            await _log(task_id, "notify", "warn", str(ne))


async def retry_task(task_id: int) -> bool:
    """重试 failed 任务：保留 MR 链接，从克隆阶段重跑。"""
    async with SessionLocal() as session:
        task = await session.get(Task, task_id)
        if task is None or task.status != "failed":
            return False
        task.status = "detected"
        task.retry_count += 1
        task.error_detail = ""
        task.updated_at = utcnow()
        await session.commit()
    asyncio.create_task(run_pipeline(task_id))
    return True
