"""
星火智造云打印 — 心跳上报模块
定期向云端报告节点在线状态。
"""

import logging
import threading
import time

import requests

from config import config

logger = logging.getLogger(__name__)


class HeartbeatReporter:
    """
    心跳上报器

    独立线程运行，每隔 HEARTBEAT_INTERVAL_SECONDS 秒
    向云端 POST /api/nodes/{node_id}/heartbeat
    """

    def __init__(self):
        self.base_url = config.CLOUD_BASE_URL.rstrip("/")
        self.node_id = config.NODE_ID
        self.interval = config.HEARTBEAT_INTERVAL_SECONDS
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"StarfirePiClient/1.0 (Node: {self.node_id})",
        })

    def start(self):
        """启动心跳线程"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            name="heartbeat-thread",
            daemon=True,  # 主线程退出时自动终止
        )
        self._thread.start()
        logger.info(f"💓 心跳上报已启动 (间隔: {self.interval}s)")

    def stop(self):
        """停止心跳线程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.session.close()
        logger.info("💓 心跳上报已停止")

    def _heartbeat_loop(self):
        """心跳循环 (在独立线程中运行)"""
        while self._running:
            try:
                self._send_heartbeat()
            except Exception as e:
                logger.error(f"心跳上报异常: {e}")

            # 等待下一轮 (使用 sleep 分段以支持快速停止)
            for _ in range(self.interval):
                if not self._running:
                    break
                time.sleep(1)

    def _send_heartbeat(self):
        """发送单次心跳"""
        url = f"{self.base_url}/api/nodes/{self.node_id}/heartbeat"
        try:
            resp = self.session.post(url, timeout=10)
            if resp.status_code == 200:
                logger.debug(f"💓 心跳成功: {resp.json()}")
            elif resp.status_code == 404:
                logger.warning(
                    "⚠️ 节点未注册，请先调用 /api/nodes/register 注册节点"
                )
            else:
                logger.warning(f"💓 心跳返回: HTTP {resp.status_code}")
        except requests.exceptions.ConnectionError:
            logger.debug(f"💓 心跳失败: 云端不可达 ({self.base_url})")
        except Exception as e:
            logger.debug(f"💓 心跳异常: {type(e).__name__}")
