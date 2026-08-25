#!/bin/sh
set -e

# multica 认证：服务器 .env 提供 MULTICA_TOKEN（https://multica.ai/settings?tab=tokens 生成）
# 每次启动幂等登录，凭据持久化在 /home/agent/.multica（volume）
if [ -n "${MULTICA_TOKEN:-}" ]; then
  timeout 60 multica login --token "$MULTICA_TOKEN" \
    && echo "[entrypoint] multica 登录成功" \
    || echo "[entrypoint] multica 登录失败（继续启动，可稍后在面板测试）"
fi

# claude headless 运行需要的最小状态文件（认证令牌等在面板设置后经环境变量注入）
[ -f "$HOME/.claude.json" ] || echo '{"hasCompletedOnboarding":true}' > "$HOME/.claude.json"

exec "$@"
