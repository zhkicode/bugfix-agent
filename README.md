# BugfixAgent — 容器报错自动修复系统

监听远程服务器 Docker 容器的报错日志（如后端 500），自动完成：**AI 识别错误 → multica 创建修复任务 → 拉取代码仓库 → Claude CLI 自动修复 → 推送分支并创建 MR/PR → 邮件通知**，并提供 Web 面板跟踪任务状态。

## 功能亮点

- 🔍 **自动巡检**：轮询远程服务器 `docker logs` 增量日志，Claude CLI 智能识别需要修复的服务端错误（自动忽略 4xx、噪音日志）
- 🧠 **AI 自动修复**：按容器绑定的仓库（极狐 GitLab / GitHub）克隆代码，Claude CLI 最小化修改并验证，推送 `bugfix/agent-*` 分支后自动创建 MR/PR
- 🔁 **指纹去重**：错误签名规范化 + 冷却期机制，同一报错不会反复触发修复；同容器串行执行避免冲突
- 📋 **multica 任务联动**：识别到错误自动在 multica 创建 Issue 并追踪，CLI 命令模板化适配、Web 可改
- 📊 **Web 面板**：任务看板 + 各阶段执行时间线（识别→建任务→克隆→修复→推送→MR→通知）、一键重试、服务器/容器/设置全图形化管理
- 📧 **邮件通知**：修复结果（含 MR 链接）自动推送邮箱，开关与收件人可配置
- 🐳 **一键部署**：所有依赖（Python/Node/git/Claude CLI/multica CLI）打包进单个 Docker 镜像，SQLite 零外部依赖，本地构建 tar 传输即可上线

## 技术栈

Python (FastAPI + SQLAlchemy + SQLite + paramiko) · Vue 3 (Vite + TypeScript + Element Plus) · Claude CLI · multica CLI（模板化适配）

## 快速开始

### 1. 后端

```bash
# 使用项目自带 .venv（或自建虚拟环境）
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8787
```

首次启动会自动建表（`data/bugfix_agent.db`）并写入默认配置。

### 2. 前端

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173（/api 已代理到 8787）
```

生产部署可 `npm run build`，后端会自动托管 `frontend/dist`，单端口访问。

### 3. 配置向导（Web 面板操作）

1. **服务器** 页：添加目标服务器（SSH IP/端口/用户名/密码），点"测试连接"验证。
2. **容器监控** 页：添加容器 —— 选择服务器、填容器名（`docker ps` 中的名字）、
   代码托管类型（极狐 GitLab / GitHub）、仓库 URL、访问 Token、默认分支、轮询间隔。
   "测试仓库"验证 token 可用，"立即轮询"手动触发一次采集分析。
3. **系统设置** 页：配置邮件通知（SMTP 授权码，126 邮箱示例默认值）、去重冷却时间、
   multica 命令模板、Claude CLI 路径等。

### 4. 邮件通知（以 126 邮箱为例）

设置页填：`smtp.host=smtp.126.com`、`smtp.port=465`、`smtp.secure=ssl`、
`smtp.user=你的邮箱`、`smtp.pass=SMTP 授权码`（非登录密码，需在邮箱后台开启 SMTP 并生成）、
`notify.recipients=zkcode@126.com`。`notify.enabled` 控制是否通知，可点"发送测试邮件"验证。

## 工作流程

```
轮询 docker logs --since <锚点> --timestamps（增量，锚点存库，重启不丢）
  → Claude CLI 分析该时段日志，识别需修复的错误并生成规范化指纹
  → 指纹去重（同指纹存在进行中任务 或 完成未过冷却期 → 跳过）
  → multica CLI 创建修复任务
  → clone 仓库 → bugfix/agent-<id> 分支 → Claude CLI 修复（无 diff 视为失败）
  → commit + push → 调 API 建 MR（GitLab）/ PR（GitHub）→ 邮件通知 → done
```

任务状态机：`detected → multica_created → cloning → fixing → pushing → mr_created → notified → done`，任一阶段失败进入 `failed`，面板上一键重试（保留 multica ID，避免重复建任务）。

## 防止同一报错反复修复

- AI 输出的错误指纹（错误类型+关键消息+文件:行，已去除时间戳/请求ID/动态数值）经后端再规范化后 sha256 入库。
- 新错误命中以下任一条件即跳过：同指纹任务**进行中**；同指纹任务已结束但仍在**冷却期**内（默认 72 小时，设置页可调）。
- 同一容器同时只允许一个进行中的任务，避免并发修复冲突。

## multica CLI 适配

multica 命令以模板形式存于设置页，占位符 `{title}` `{desc}` `{task_id}`：

- 创建任务（默认）：`multica task create --title {title} --desc {desc}`
- ID 提取正则（默认）：`(?:id|ID|编号)\s*[:#=]?\s*([A-Za-z0-9\-]+)`
- 查询状态（默认）：`multica task show {task_id}`

拿到真实 CLI 的命令格式后，在设置页直接改模板与正则即可，无需改代码。
multica 创建失败不会阻塞修复流程（记为 warn 日志）。

## 安全说明

- SSH 密码 / 仓库 Token / SMTP 授权码使用 Fernet 加密落库；密钥来自环境变量
  `BUGFIX_AGENT_SECRET_KEY`，未设置时自动生成 `data/secret.key`（权限 600）。API 返回一律脱敏。
- Claude 修复使用 `--dangerously-skip-permissions`，仅在 `workspace/task_<id>/`
  一次性克隆副本内执行，修复失败/重试会重置该目录；请知悉此取舍。
- multica 模板经 shell 执行，标题/描述均做 shlex 转义防注入；日志嵌入 prompt 前截断。

## 目录结构

```
backend/   FastAPI 服务（routers / services / models / tests）
frontend/  Vue3 面板（Dashboard / 服务器 / 容器监控 / 设置）
data/      SQLite 数据库与密钥文件
workspace/ 修复用临时克隆目录
```

## 测试

```bash
cd backend
python -m pytest tests/ -q                 # 单元测试（指纹/JSON 解析/URL 解析）
python tests/integration_check.py          # 真实调用 claude CLI 的分析冒烟测试
python tests/fixer_pipeline_check.py       # 修复管线失败/重试路径测试
```

## Docker 部署（本地构建 → tar 传输 → 服务器运行）

镜像内置全部依赖：Python 后端、Vue 前端、git、Node、Claude CLI、multica CLI。
所有资源都在容器内，服务器只需 Docker。

### 1. 本地构建镜像并导出 tar（Mac 为 ARM 时用 buildx 交叉构建 amd64）

```bash
cd BugfixAgent
docker buildx build --platform linux/amd64 -t bugfixagent:latest --load .
docker save bugfixagent:latest | gzip > ~/Desktop/bugfixagent-image.tar.gz
```

### 2. 传输到服务器并启动

```bash
rsync -azP ~/Desktop/bugfixagent-image.tar.gz docker-compose.yml ecs:~/BugfixAgent/
ssh ecs 'cd ~/BugfixAgent && docker load < bugfixagent-image.tar.gz && docker compose up -d'
```

### 3. 配置认证（部署后一次性）

- **Claude CLI**：打开 `http://<服务器IP>:8787` → 系统设置 → 「Claude CLI 认证」，
  填入 `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_BASE_URL` / 模型名，保存后点「测试 Claude」验证。
  （令牌加密存库，界面不回显）
- **multica CLI**：在 https://multica.ai/settings?tab=tokens 创建 Token，写入服务器
  `~/BugfixAgent/.env`：`MULTICA_TOKEN=mul_...`，然后 `docker compose restart`。
  面板「测试 multica」可验证认证。
- **SMTP**：设置页配置后「测试邮件」。

### 说明

- 访问 `http://<服务器IP>:8787`（安全组需放行 8787；面板暂无鉴权，也可用
  `ssh -L 8787:localhost:8787 ecs` 隧道访问，不对外暴露端口）
- 数据持久化：named volumes —— `bugfix_data`（数据库+密钥+面板配置）、
  `bugfix_workspace`（修复克隆副本）、`agent_home`（claude/multica 凭据与状态）
- 更新版本：本地重新构建导出 tar → 传输 → `docker load` → `docker compose up -d`
  （同名镜像替换，卷数据保留）
