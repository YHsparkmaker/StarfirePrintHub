"""
星火智造云打印 — 配置中心
通过环境变量或 .env 文件读取所有配置项。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录 (cloud/)
BASE_DIR = Path(__file__).resolve().parent

# 加载 .env 文件 (如果存在)
load_dotenv(BASE_DIR / ".env")


class Settings:
    """全局配置单例"""

    # ── 服务器 ──────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # ── 数据库 ──────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{BASE_DIR / 'starfire.db'}"
    )

    # ── 文件存储 ────────────────────────────
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "20"))

    # ── AI 摘要 ─────────────────────────────
    AI_ENABLED: bool = os.getenv("AI_ENABLED", "false").lower() == "true"
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    AI_MODEL: str = os.getenv("AI_MODEL", "gpt-4o-mini")

    # ── 边缘节点 ────────────────────────────
    POLL_TIMEOUT_SECONDS: int = int(os.getenv("POLL_TIMEOUT_SECONDS", "30"))
    JOB_MAX_RETRIES: int = int(os.getenv("JOB_MAX_RETRIES", "3"))

    # ── 微信 JS-SDK ─────────────────────────
    WECHAT_APP_ID: str = os.getenv("WECHAT_APP_ID", "")
    WECHAT_APP_SECRET: str = os.getenv("WECHAT_APP_SECRET", "")


settings = Settings()

# 确保上传目录存在
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
