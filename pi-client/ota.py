"""
星火智造云打印 — 树莓派远程管理 (OTA 更新 / 远程命令执行)

工作流程:
  1. 定期轮询 GET /api/nodes/{node_id}/command
  2. 如果服务端有待执行命令 → 执行
  3. 上报结果 POST /api/nodes/{node_id}/command/result

支持命令:
  ping     — 返回树莓派状态 (IP/磁盘/CPU温度/uptime)
  restart  — sudo systemctl restart starfire-pi
  update   — git pull + sudo systemctl restart starfire-pi
  exec     — 执行自定义 shell 命令
"""

import logging
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# ── 仓库路径 (git pull 的目标) ──
_REPO_DIR = Path(__file__).resolve().parent.parent  # StarfirePrintHub/
_SERVICE_NAME = "starfire-pi"


class OTAManager:
    """远程管理: 拉取云端命令 → 执行 → 上报结果"""

    def __init__(self, base_url: str, node_id: str):
        self.base_url = base_url.rstrip("/")
        self.node_id = node_id
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "StarfirePrintHub-OTA/1.0"

    def poll_and_execute(self) -> str:
        """
        轮询一次云端命令 (无命令时立即返回)

        Returns:
            "ok" — 命令执行完毕 (或没有命令)
            "restart" — 需要退出进程 (systemd 会重启)
        """
        try:
            resp = self.session.get(
                f"{self.base_url}/api/nodes/{self.node_id}/command",
                timeout=15,
            )
            if resp.status_code != 200:
                return

            data = resp.json()
            cmd = data.get("command")
            if not cmd:
                return "ok"

            logger.info(f"📡 收到远程命令: {cmd}")

            # 解析 exec 命令
            actual_cmd = cmd
            if cmd.startswith("exec|"):
                actual_cmd = "exec"
                exec_cmd = cmd.split("|", 1)[1]
            else:
                exec_cmd = ""

            # 执行
            success, output = self._execute(actual_cmd, exec_cmd)

            # 上报结果
            self._report(actual_cmd, output, success)

            # restart / update 成功后需要重启进程
            if success and actual_cmd in ("restart", "update"):
                logger.info("🔄 准备退出以触发 systemd 重启...")
                return "restart"

            return "ok"

        except requests.exceptions.ConnectionError:
            logger.debug("OTA 轮询: 云端不可达")
            return "ok"
        except Exception as e:
            logger.warning(f"OTA 轮询异常: {e}")
            return "ok"

    def _execute(self, cmd: str, exec_cmd: str = "") -> tuple[bool, str]:
        """执行命令, 返回 (是否成功, 输出文本)"""

        try:
            if cmd == "ping":
                return self._cmd_ping()

            elif cmd == "restart":
                return self._cmd_restart()

            elif cmd == "update":
                return self._cmd_update()

            elif cmd == "exec":
                return self._cmd_exec(exec_cmd)

            else:
                return False, f"未知命令: {cmd}"

        except Exception as e:
            return False, f"执行异常: {e}"

    # ═══════════════════════════════════════════════════════════════
    # 具体命令实现
    # ═══════════════════════════════════════════════════════════════

    def _cmd_ping(self) -> tuple[bool, str]:
        """返回树莓派状态"""
        info = []

        # 主机名 + IP
        hostname = platform.node()
        info.append(f"hostname={hostname}")

        # 获取本机 IP
        try:
            hostname_ip = subprocess.check_output(
                ["hostname", "-I"], text=True, timeout=5
            ).strip()
            info.append(f"ip={hostname_ip or 'unknown'}")
        except Exception:
            info.append("ip=unknown")

        # CPU 温度 (树莓派)
        try:
            temp = Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()
            info.append(f"cpu_temp={int(temp)/1000:.1f}C")
        except Exception:
            pass

        # 磁盘
        try:
            df = shutil.disk_usage("/")
            info.append(f"disk={df.free // (1024*1024)}MB_free")
        except Exception:
            pass

        # uptime
        try:
            up = subprocess.check_output(["uptime", "-p"], text=True, timeout=5).strip()
            info.append(f"uptime={up}")
        except Exception:
            pass

        # git 版本
        try:
            rev = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(_REPO_DIR), text=True, timeout=5,
            ).strip()
            info.append(f"git={rev}")
        except Exception:
            pass

        return True, "; ".join(info)

    def _cmd_restart(self) -> tuple[bool, str]:
        """重启 pi_worker 服务 (自身退出, systemd 自动拉起)"""
        logger.info("🔄 收到远程重启命令, 准备退出...")
        # schedule restart — systemd 的 Restart=always 会自动拉起
        return True, "scheduled-restart"

    def _cmd_update(self) -> tuple[bool, str]:
        """git pull + 重启"""
        logger.info("🔄 OTA 更新: git pull...")

        git = shutil.which("git") or "git"

        try:
            # Step 1: fetch
            result = subprocess.run(
                [git, "fetch", "origin", "main"],
                cwd=str(_REPO_DIR),
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return False, f"git fetch 失败: {result.stderr[:300]}"

            # Step 2: reset --hard (确保本地干净)
            result = subprocess.run(
                [git, "reset", "--hard", "origin/main"],
                cwd=str(_REPO_DIR),
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return False, f"git reset 失败: {result.stderr[:300]}"

            # Step 3: 获取新 commit hash
            rev = subprocess.check_output(
                [git, "rev-parse", "--short", "HEAD"],
                cwd=str(_REPO_DIR), text=True, timeout=5,
            ).strip()

            logger.info(f"✅ OTA 更新完成 → {rev}")
            return True, f"updated-to-{rev}"

        except subprocess.TimeoutExpired:
            return False, "git 命令超时"
        except Exception as e:
            return False, f"更新异常: {e}"

    def _cmd_exec(self, shell_command: str) -> tuple[bool, str]:
        """执行自定义 shell 命令 (有超时限制)"""
        if not shell_command:
            return False, "empty command"

        logger.info(f"⚡ 执行自定义命令: {shell_command}")

        try:
            result = subprocess.run(
                shell_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout.strip() or result.stderr.strip() or "(no output)"
            return result.returncode == 0, output[:400]
        except subprocess.TimeoutExpired:
            return False, "命令超时 (30s)"
        except Exception as e:
            return False, f"命令异常: {e}"

    # ═══════════════════════════════════════════════════════════════
    # 上报结果
    # ═══════════════════════════════════════════════════════════════

    def _report(self, cmd: str, output: str, success: bool):
        """POST /api/nodes/{id}/command/result"""
        try:
            self.session.post(
                f"{self.base_url}/api/nodes/{self.node_id}/command/result",
                params={
                    "cmd": cmd,
                    "output": output,
                    "success": str(success).lower(),
                },
                timeout=15,
            )
        except Exception as e:
            logger.debug(f"命令结果上报失败: {e}")

    def close(self):
        self.session.close()
