######## 阶段一：前端构建 ########
# 基础镜像默认走国内镜像源（Docker Hub 直连不可达时）；网络通畅可 build-arg 覆盖回官方
ARG NODE_IMAGE=docker.1panel.live/library/node:22-slim
ARG PYTHON_IMAGE=docker.1panel.live/library/python:3.12-slim
FROM ${NODE_IMAGE} AS frontend-build
ARG NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry=$NPM_REGISTRY
COPY frontend/ ./
RUN npm run build

######## 阶段二：运行时 ########
FROM ${PYTHON_IMAGE}
ARG PIP_INDEX=https://mirrors.cloud.tencent.com/pypi/simple
ARG NPM_REGISTRY=https://registry.npmmirror.com

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl tzdata \
    && rm -rf /var/lib/apt/lists/*

# node/npm 直接取自前端构建阶段（node:22-slim，同为 Debian bookworm，二进制兼容）
COPY --from=frontend-build /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend-build /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm config set registry $NPM_REGISTRY --location=global \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force

# multica CLI（Go 二进制，GitHub Releases 分发）
ARG MULTICA_VERSION=
ARG TARGETARCH
RUN set -eux; \
    arch="${TARGETARCH:-amd64}"; \
    if [ -n "$MULTICA_VERSION" ]; then tag="$MULTICA_VERSION"; else \
      url=$(curl -fsSL -o /dev/null -w '%{url_effective}' https://github.com/multica-ai/multica/releases/latest); \
      tag="${url##*/}"; \
    fi; \
    ver="${tag#v}"; \
    curl -fsSL --retry 3 "https://github.com/multica-ai/multica/releases/download/${tag}/multica-cli-${ver}-linux-${arch}.tar.gz" -o /tmp/multica.tar.gz; \
    tar -xzf /tmp/multica.tar.gz -C /tmp multica; \
    install -m 0755 /tmp/multica /usr/local/bin/multica; \
    rm -f /tmp/multica.tar.gz; \
    multica --version

# 非 root 运行（claude CLI 拒绝以 root 常规运行）
RUN useradd -m -u 1000 agent

ENV TZ=Asia/Shanghai \
    HOME=/home/agent \
    BUGFIX_AGENT_DATA_DIR=/app/data \
    BUGFIX_AGENT_WORKSPACE=/app/workspace

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i $PIP_INDEX
COPY backend/ .
COPY --from=frontend-build /build/dist /app/frontend/dist
COPY docker/entrypoint.sh /entrypoint.sh

RUN mkdir -p /app/data /app/workspace \
    && chmod +x /entrypoint.sh \
    && chown -R agent:agent /app

USER agent
EXPOSE 8787
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787"]
