#!/bin/sh
set -e

# claude headless 运行需要的最小状态文件（认证令牌等在面板设置后经环境变量注入）
[ -f "$HOME/.claude.json" ] || echo '{"hasCompletedOnboarding":true}' > "$HOME/.claude.json"

exec "$@"
