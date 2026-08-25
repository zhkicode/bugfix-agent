"""全局配置：路径与环境变量。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("BUGFIX_AGENT_DATA_DIR", BASE_DIR.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "bugfix_agent.db"
SECRET_KEY_FILE = DATA_DIR / "secret.key"
WORKSPACE_DIR = Path(
    os.environ.get("BUGFIX_AGENT_WORKSPACE", BASE_DIR.parent / "workspace")
)
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# 凭据加密密钥：优先环境变量（需为合法 Fernet key），否则自动生成文件密钥
SECRET_KEY = os.environ.get("BUGFIX_AGENT_SECRET_KEY", "")

# API 返回时需要脱敏的 settings key
SECRET_SETTING_KEYS = {"smtp.pass", "claude.auth_token"}
