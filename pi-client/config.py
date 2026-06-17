"""
星火智造云打印 — 树莓派客户端配置
通过环境变量或 .env 文件读取所有配置项。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class PiConfig:
    """树莓派客户端配置"""

    # ── 云端 API 地址 ────────────────────────
    CLOUD_BASE_URL: str = os.getenv(
        "CLOUD_BASE_URL",
        "http://192.168.1.100:8000"
    )

    # ── 节点标识 ──────────────────────────────
    NODE_ID: str = os.getenv(
        "NODE_ID",
        "pi-default-01"
    )
    NODE_NAME: str = os.getenv(
        "NODE_NAME",
        "默认打印节点"
    )

    # ── 打印机队列名 ──────────────────────────
    PRINTER_NAME: str = os.getenv(
        "PRINTER_NAME",
        "Fuji_Xerox_SC2020"
    )

    # ── 轮询设置 ──────────────────────────────
    POLL_INTERVAL_SECONDS: int = int(
        os.getenv("POLL_INTERVAL_SECONDS", "5")
    )
    POLL_LONG_INTERVAL_SECONDS: int = int(
        os.getenv("POLL_LONG_INTERVAL_SECONDS", "30")
    )

    # ── 心跳 ──────────────────────────────────
    HEARTBEAT_INTERVAL_SECONDS: int = int(
        os.getenv("HEARTBEAT_INTERVAL_SECONDS", "30")
    )

    # ── 下载目录 ──────────────────────────────
    DOWNLOAD_DIR: str = os.getenv(
        "DOWNLOAD_DIR",
        "/tmp/starfire-jobs"
    )

    # ── 重试设置 ──────────────────────────────
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BACKOFF_FACTOR: float = float(
        os.getenv("RETRY_BACKOFF_FACTOR", "2.0")
    )

    # ── 日志级别 ──────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ── 提示音 ────────────────────────────────
    ENABLE_SOUND: bool = os.getenv("ENABLE_SOUND", "true").lower() in (
        "true", "1", "yes", "on",
    )
    SOUND_VOLUME: float = float(os.getenv("SOUND_VOLUME", "0.7"))


config = PiConfig()

# 确保下载目录存在
Path(config.DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
