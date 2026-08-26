import datetime as dt

from pydantic import BaseModel, Field


# ---------- Server ----------
class ServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1)
    port: int = 22
    username: str = "root"
    password: str = ""
    enabled: bool = True


class ServerUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None  # 为空或 "******" 表示不修改
    enabled: bool | None = None


class ServerOut(BaseModel):
    id: int
    name: str
    host: str
    port: int
    username: str
    password: str  # 脱敏
    enabled: bool
    created_at: dt.datetime


# ---------- Container ----------
class ContainerCreate(BaseModel):
    server_id: int
    name: str = Field(min_length=1, max_length=200)
    repo_provider: str = "gitlab"  # gitlab|github
    repo_url: str = ""
    repo_token: str = ""
    repo_default_branch: str = "main"
    poll_interval_sec: int = 60
    enabled: bool = True


class ContainerUpdate(BaseModel):
    server_id: int | None = None
    name: str | None = None
    repo_provider: str | None = None
    repo_url: str | None = None
    repo_token: str | None = None  # 为空或 "******" 表示不修改
    repo_default_branch: str | None = None
    poll_interval_sec: int | None = None
    enabled: bool | None = None


class ContainerOut(BaseModel):
    id: int
    server_id: int
    server_name: str
    name: str
    repo_provider: str
    repo_url: str
    repo_token: str  # 脱敏
    repo_default_branch: str
    poll_interval_sec: int
    enabled: bool
    last_log_ts: float | None
    created_at: dt.datetime


# ---------- Task ----------
class TaskBrief(BaseModel):
    id: int
    container_id: int
    container_name: str
    error_type: str
    message: str
    status: str
    branch_name: str
    mr_url: str
    retry_count: int
    fingerprint: str
    created_at: dt.datetime
    updated_at: dt.datetime


class FixLogOut(BaseModel):
    id: int
    stage: str
    level: str
    message: str
    created_at: dt.datetime


class TaskDetail(TaskBrief):
    stack_summary: str
    suspect_files: list[str]
    log_excerpt: str
    error_detail: str
    claude_output: str
    ts_detected: dt.datetime | None
    ts_cloned: dt.datetime | None
    ts_fixed: dt.datetime | None
    ts_pushed: dt.datetime | None
    ts_mr: dt.datetime | None
    ts_notified: dt.datetime | None
    logs: list[FixLogOut]


class TaskPage(BaseModel):
    total: int
    items: list[TaskBrief]


# ---------- Settings ----------
class SettingsUpdate(BaseModel):
    values: dict[str, str]
