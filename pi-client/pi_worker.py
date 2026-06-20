#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
星火智造云打印 (Starfire Print Hub) — 树莓派守护脚本
═══════════════════════════════════════════════════════════════════════════════

工作流程:
  while True:
    1. GET /api/jobs/next?node_id=xxx        拉取下一个 pending 任务
    2. 如果没有任务 → sleep 5s → continue
    3. POST /api/jobs/update (status=printing) 通知云端开始打印
    4. GET /api/files/{job_id}/download       下载 PDF 到 /tmp/starfire-jobs/
    5. 映射 JSON 参数 → CUPS 选项
    6. conn.printFile(pdf, "Fuji_Xerox_SC2020", options)
    7. POST /api/jobs/update (status=completed) 通知云端完成
    8. 清理本地临时文件 → continue

异常处理:
  - 网络断开: 指数退避重试，最长间隔 30s
  - 打印机离线: 上报 failed，等待恢复
  - CUPS 错误: 记录错误详情，上报 failed

启动方式:
  python pi_worker.py

配置方式:
  复制 .env.example 为 .env，修改其中的 CLOUD_BASE_URL 等参数
"""

import logging
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

# ── 启动前诊断 ──────────────────────────────
_DIAG_ERRORS = []

# 0. 检查 cwd 与 .env
_env_path = Path(__file__).resolve().parent / ".env"
if not _env_path.exists():
    _DIAG_ERRORS.append(f".env 文件不存在: {_env_path}")

# 1. 检查关键依赖是否可导入
_critical_imports = {
    "requests": "sudo pip3 install requests --break-system-packages --root-user-action=ignore",
    "dotenv": "sudo pip3 install python-dotenv --break-system-packages --root-user-action=ignore",
    "tenacity": "sudo pip3 install tenacity --break-system-packages --root-user-action=ignore",
    "cups": "sudo apt install libcups2-dev && sudo pip3 install pycups --break-system-packages --root-user-action=ignore",
    "pypdf": "sudo pip3 install pypdf --break-system-packages --root-user-action=ignore",
}
for mod, fix_cmd in _critical_imports.items():
    try:
        __import__(mod)
    except ImportError:
        _DIAG_ERRORS.append(f"缺少 {mod} 模块. 修复: {fix_cmd}")

# 2. 检查 python-dotenv 加载
if "dotenv" not in [e.split()[1] for e in _DIAG_ERRORS if "缺少" in e]:
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except Exception as e:
        _DIAG_ERRORS.append(f".env 加载失败: {e}")

# 3. 打印诊断结果
if _DIAG_ERRORS:
    print("\n" + "=" * 60, flush=True)
    print("[星火] 树莓派守护启动失败 — 诊断报告", flush=True)
    print("=" * 60, flush=True)
    for i, err in enumerate(_DIAG_ERRORS, 1):
        print(f"  [{i}] {err}", flush=True)
    print("=" * 60, flush=True)
    print("\n请先运行一键安装脚本:\n  bash install-deps.sh --all\n", flush=True)
    sys.exit(1)

import requests

from config import config
from poller import JobPoller
from printer import PrinterService
from heartbeat import HeartbeatReporter
from sound_player import get_sound_player
from ota import OTAManager
from _version import __version__

# ── 日志 ──────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pi_worker")


# ═══════════════════════════════════════════════════════════════════
# Pi Worker 主类
# ═══════════════════════════════════════════════════════════════════

class PiWorker:
    """
    树莓派打印守护进程

    职责:
      - 轮询云端任务队列
      - 下载 PDF → 映射参数 → 调用 CUPS 打印
      - 上报任务状态
      - 心跳保活
      - 异常恢复
    """

    def __init__(self):
        # ── 模块初始化 ──
        self.poller = JobPoller()
        self.printer = PrinterService()
        self.heartbeat = HeartbeatReporter()

        # ── 提示音 ──
        self.sound = get_sound_player(
            enabled=config.ENABLE_SOUND,
            volume=config.SOUND_VOLUME,
            tts_success=config.TTS_SUCCESS,
            tts_failure=config.TTS_FAILURE,
        )

        # ── OTA 远程管理 ──
        self.ota = OTAManager(
            base_url=config.CLOUD_BASE_URL,
            node_id=config.NODE_ID,
        )

        # ── 运行时状态 ──
        self._running = False
        self._printer_available = self.printer.is_connected
        if not self._printer_available:
            logger.error("❌ CUPS 连接不可用，打印机功能受限")
        self._consecutive_errors = 0

    # ═══════════════════════════════════════════════════════════════
    # 自动注册 (启动时调用, 幂等)
    # ═══════════════════════════════════════════════════════════════

    def _ensure_registered(self) -> bool:
        """
        启动时自动向云端注册本节点, 已注册则更新信息

        POST /api/nodes/register?node_id=xxx&name=xxx&printer_name=xxx
        """
        url = f"{self.poller.base_url}/api/nodes/register"
        params = {
            "node_id": config.NODE_ID,
            "name": config.NODE_NAME,
            "printer_name": config.PRINTER_NAME,
        }

        try:
            resp = self.poller.session.post(
                url,
                params=params,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"节点已注册: {data.get('node_id')} ({data.get('name')})")
                return True
            else:
                logger.warning(f"节点注册返回 {resp.status_code}: {resp.text[:120]}")
                return False
        except Exception as e:
            logger.warning(f"节点注册网络异常: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    # 云端状态上报
    # ═══════════════════════════════════════════════════════════════

    def _report_status(
        self,
        job_id: str,
        status: str,
        error_msg: Optional[str] = None,
    ) -> bool:
        """
        向云端上报任务状态变更

        Args:
            job_id:   任务 ID
            status:   printing | completed | failed
            error_msg: 失败时的错误信息

        Returns:
            上报是否成功
        """
        url = f"{self.poller.base_url}/api/jobs/update"
        payload = {
            "job_id": job_id,
            "status": status,
            "node_id": config.NODE_ID,
        }
        if error_msg:
            payload["error_msg"] = error_msg

        try:
            resp = self.poller.session.post(
                url,
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            logger.info(f"📡 状态上报成功: {job_id} → {status}")
            return True

        except requests.exceptions.ConnectionError:
            logger.error(f"❌ 状态上报失败: 云端不可达")
            return False
        except requests.exceptions.Timeout:
            logger.error(f"⏰ 状态上报超时")
            return False
        except Exception as e:
            logger.error(f"状态上报异常: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    # 处理单个任务
    # ═══════════════════════════════════════════════════════════════

    def _process_job(self, job_data: dict) -> bool:
        """
        处理单个打印任务 (完整流程)

        Steps:
          1. 上报 printing
          2. 下载 PDF
          3. 提交 CUPS 打印
          4. 上报 completed / failed
          5. 清理本地文件

        Returns:
            是否处理成功
        """
        job_id = job_data.get("job_id", "unknown")
        file_name = job_data.get("file_name", "unknown")
        download_url = job_data.get("download_url", "")
        cups_options = job_data.get("cups_options", {})
        summary_text = job_data.get("summary_text", "")

        logger.info(f"══════════════════════════════════════")
        logger.info(f"📄 处理任务: {job_id}")
        logger.info(f"   文件: {file_name}")
        logger.info(f"   参数: {cups_options}")
        if summary_text:
            logger.info(f"   AI 摘要: {summary_text[:100]}...")
        logger.info(f"══════════════════════════════════════")

        # ── Step 1: 上报 printing ──
        if not self._report_status(job_id, "printing"):
            logger.warning(f"⚠️ 无法上报 printing 状态，但继续处理任务")

        # ── Step 2: 下载 PDF ──
        local_pdf = self.poller.download_pdf(download_url, job_id)
        if local_pdf is None:
            error_msg = "PDF 下载失败"
            self._report_status(job_id, "failed", error_msg)
            return False

        # ── Step 3: 提交 CUPS 打印 ──
        try:
            cups_job_id = self.printer.submit_job(
                pdf_path=local_pdf,
                job_name=f"starfire-{job_id[:12]}-{file_name}",
                options=cups_options,
            )
            logger.info(f"✅ CUPS 作业已提交: #{cups_job_id}")

            # ── Step 4: 上报 completed ──
            #   注意: 这里报告的是"已提交到打印机队列"，
            #   不代表物理纸张已完成打印。
            #   如需确认物理完成，可在这里轮询 CUPS job-state。
            self._report_status(job_id, "completed")

            # 等待一小段时间让 CUPS 完成假脱机 (spooling)
            time.sleep(1)

            # ── 播放提示音 ──
            self.sound.play_success()

            return True

        except RuntimeError as e:
            # ── 打印机不可用 ──
            error_msg = f"打印机错误: {e}"
            logger.error(f"❌ {error_msg}")
            self._printer_available = False
            self._report_status(job_id, "failed", error_msg)
            self.sound.play_error()
            return False

        except Exception as e:
            # ── 未知错误 ──
            error_msg = f"打印异常: {type(e).__name__}: {e}"
            logger.error(f"❌ {error_msg}")
            logger.debug(traceback.format_exc())
            self._report_status(job_id, "failed", error_msg)
            self.sound.play_error()
            return False

        finally:
            # ── Step 5: 清理本地临时文件 ──
            self.poller.cleanup_local_file(job_id)

    # ═══════════════════════════════════════════════════════════════
    # 主循环
    # ═══════════════════════════════════════════════════════════════

    def _should_use_long_poll(self) -> bool:
        """
        判断是否应切换到长轮询间隔

        连续错误次数多 → 切换为长轮询 (30s)，减少无效请求
        """
        return self._consecutive_errors >= config.MAX_RETRIES

    def run(self):
        """
        主循环入口

        while True:
          1. 检查打印机状态 (如果之前标记为不可用)
          2. 拉取任务
          3. 处理任务 (如有)
          4. sleep 后继续
        """
        logger.info("═" * 60)
        logger.info(f"🖨️  星火智造云打印 — Pi Worker 启动 (v{__version__})")
        logger.info(f"   云端地址: {config.CLOUD_BASE_URL}")
        logger.info(f"   节点 ID:  {config.NODE_ID}")
        logger.info(f"   打印机:   {config.PRINTER_NAME}")
        logger.info(f"   轮询间隔: {config.POLL_INTERVAL_SECONDS}s")
        logger.info("═" * 60)

        # ── 信号处理: Ctrl+C 优雅退出 ──
        self._running = True

        def _graceful_shutdown(signum, frame):
            logger.info(f"\n收到信号 {signum}，正在退出...")
            self._running = False

        signal.signal(signal.SIGINT, _graceful_shutdown)
        signal.signal(signal.SIGTERM, _graceful_shutdown)

        # ── 启动心跳线程 ──
        self.heartbeat.start()

        # ── 自动注册 (幂等) ──
        self._ensure_registered()

        try:
            # ═══════════════════════════════════════════════════════
            # 主循环
            # ═══════════════════════════════════════════════════════
            while self._running:
                try:
                    # ── 1. 打印机恢复检测 ──
                    if not self._printer_available:
                        logger.info("🔍 尝试重新检测打印机...")
                        available, msg = self.printer.check_printer()
                        if available:
                            self._printer_available = True
                            logger.info(f"✅ 打印机已恢复: {msg}")
                        else:
                            logger.warning(f"⏳ 打印机仍不可用: {msg}")
                            time.sleep(config.POLL_LONG_INTERVAL_SECONDS)
                            continue

                    # ── 2. OTA 远程命令轮询 ──
                    restart_needed = self.ota.poll_and_execute()
                    if restart_needed == "restart":
                        logger.info("🔄 OTA 更新完成, 正在重启守护进程...")
                        sys.exit(0)

                    # ── 3. 拉取任务 ──
                    job = self.poller.fetch_next_job()

                    if job:
                        # ── 3. 处理任务 ──
                        success = self._process_job(job)

                        if success:
                            self._consecutive_errors = 0
                            # 成功时快速轮询 (可能有连续任务)
                            poll_interval = config.POLL_INTERVAL_SECONDS
                        else:
                            self._consecutive_errors += 1
                            # 失败时逐渐增大间隔
                            poll_interval = min(
                                config.POLL_INTERVAL_SECONDS * (2 ** self._consecutive_errors),
                                config.POLL_LONG_INTERVAL_SECONDS,
                            )
                    else:
                        # ── 无任务 ──
                        self._consecutive_errors = 0
                        poll_interval = config.POLL_INTERVAL_SECONDS

                except requests.exceptions.ConnectionError:
                    # ── 网络断开 ──
                    self._consecutive_errors += 1
                    poll_interval = min(
                        config.POLL_INTERVAL_SECONDS * (2 ** self._consecutive_errors),
                        config.POLL_LONG_INTERVAL_SECONDS,
                    )
                    logger.error(
                        f"❌ 网络不可达 ({self._consecutive_errors} 次连续失败), "
                        f"下次轮询: {poll_interval}s 后"
                    )

                except Exception as e:
                    # ── 未预见的异常 ──
                    self._consecutive_errors += 1
                    poll_interval = config.POLL_LONG_INTERVAL_SECONDS
                    logger.error(f"💥 主循环异常: {type(e).__name__}: {e}")
                    logger.debug(traceback.format_exc())

                # ── 4. 等待下一轮 ──
                # 使用分段 sleep 以便响应 SIGINT
                for _ in range(int(poll_interval)):
                    if not self._running:
                        break
                    time.sleep(1)

        finally:
            # ═══════════════════════════════════════════════════════
            # 清理
            # ═══════════════════════════════════════════════════════
            logger.info("正在关闭 Pi Worker...")
            self.heartbeat.stop()
            self.poller.close()
            self.ota.close()
            logger.info("👋 Pi Worker 已退出")


# ═══════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    worker = PiWorker()
    worker.run()
