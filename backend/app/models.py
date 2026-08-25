import datetime as dt

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> dt.datetime:
    # 用本地时间（容器 TZ=Asia/Shanghai），保证前端 new Date() 解析无时区偏移；
    # 所有比较都在同一时钟内进行，一致性不受影响
    return dt.datetime.now()


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str] = mapped_column(String(100), default="root")
    password_enc: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


class Container(Base):
    __tablename__ = "containers"

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"))
    name: Mapped[str] = mapped_column(String(200))  # docker 容器名
    repo_provider: Mapped[str] = mapped_column(String(20), default="gitlab")  # gitlab|github
    repo_url: Mapped[str] = mapped_column(Text, default="")
    repo_token_enc: Mapped[str] = mapped_column(Text, default="")
    repo_default_branch: Mapped[str] = mapped_column(String(100), default="main")
    poll_interval_sec: Mapped[int] = mapped_column(Integer, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # docker logs --since 的锚点（unix 秒），存库保证重启不丢
    last_log_ts: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


# 任务状态机
TASK_STATUSES = [
    "detected",        # 已识别到错误
    "multica_created", # 已创建 multica 任务
    "cloning",         # 克隆仓库中
    "fixing",          # claude 修复中
    "pushing",         # 推送分支中
    "mr_created",      # MR/PR 已创建
    "notified",        # 已发送邮件通知
    "done",            # 完成（终态）
    "failed",          # 失败（终态，可重试）
]
TERMINAL_STATUSES = {"done", "failed"}


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    container_id: Mapped[int] = mapped_column(ForeignKey("containers.id"))
    fingerprint: Mapped[str] = mapped_column(String(64))  # sha256 hex
    error_type: Mapped[str] = mapped_column(String(200), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    stack_summary: Mapped[str] = mapped_column(Text, default="")
    suspect_files: Mapped[str] = mapped_column(Text, default="")  # JSON array
    log_excerpt: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="detected")
    multica_task_id: Mapped[str] = mapped_column(String(100), default="")
    branch_name: Mapped[str] = mapped_column(String(200), default="")
    mr_url: Mapped[str] = mapped_column(Text, default="")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[str] = mapped_column(Text, default="")
    claude_output: Mapped[str] = mapped_column(Text, default="")
    # 各阶段时间戳
    ts_detected: Mapped[dt.datetime] = mapped_column(default=utcnow)
    ts_multica: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    ts_cloned: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    ts_fixed: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    ts_pushed: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    ts_mr: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    ts_notified: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(default=utcnow, onupdate=utcnow)


Index("ix_tasks_fingerprint", Task.fingerprint)
Index("ix_tasks_container_status", Task.container_id, Task.status)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    value_type: Mapped[str] = mapped_column(String(10), default="str")  # str|int|bool


class FixLog(Base):
    __tablename__ = "fix_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    stage: Mapped[str] = mapped_column(String(30), default="")
    level: Mapped[str] = mapped_column(String(10), default="info")  # info|warn|error
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
