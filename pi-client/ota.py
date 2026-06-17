"""
星火智造云打印 — 树莓派远程管理 (OTA 更新 / 远程命令执行)

工作流程:
  1. 定期轮询 GET /api/nodes/{node_id}/command
  2. 如果服务端有待执行命令 → 执行
  3. 上报结果 POST /api/nodes/{node_id}/command/result

支持命令:
  ping          — 返回树莓派状态 (IP/磁盘/CPU温度/uptime)
  restart       — sudo systemctl restart starfire-pi
  update        — git pull + sudo systemctl restart starfire-pi
  exec          — 执行自定义 shell 命令
  tunnel        — 打开反向 SSH 隧道 (公网远程 SSH 登录树莓派)
  tunnel-close  — 关闭 SSH 隧道
  tunnel-status — 查询隧道连接信息
"""

import atexit
import logging
import os
import platform
import shutil
import signal
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

        # SSH 隧道状态
        self._tunnel_proc: subprocess.Popen | None = None
        self._tunnel_info: str = ""  # 用户连接信息

        # 退出时自动关闭隧道
        atexit.register(self._cleanup_tunnel)

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

            elif cmd == "tunnel":
                return self._cmd_tunnel_open()

            elif cmd == "tunnel-close":
                return self._cmd_tunnel_close()

            elif cmd == "tunnel-status":
                return self._cmd_tunnel_status()

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
    # SSH 反向隧道 (公网远程 SSH 登录树莓派)
    # ═══════════════════════════════════════════════════════════════

    def _cmd_tunnel_open(self) -> tuple[bool, str]:
        """
        打开反向 SSH 隧道: Pi → 公网跳板 → 用户可以从公网 SSH 到 Pi

        工作原理:
          树莓派主动 ssh -R 连接到公网服务器, 将该服务器的某个端口
          映射到树莓派的 22 端口。用户 SSH 到公网服务器的那个端口
          就等于 SSH 登录到了树莓派。

        零配置方案 (serveo.net):
          ssh -R starfire-pi:22:localhost:22 serveo.net
          → 用户: ssh -J serveo.net pi@starfire-pi

        自定义方案 (.env TUNNEL_HOST):
          配置你自己的公网服务器, Pi 自动开隧道过去。
        """
        if self._tunnel_proc is not None and self._tunnel_proc.poll() is None:
            # 隧道已在运行
            return True, self._tunnel_info or "tunnel-active"

        # 检查 SSH 是否可用
        if not shutil.which("ssh"):
            return False, "SSH 客户端未安装: sudo apt install openssh-client"

        # 读取配置
        tunnel_host = os.getenv("TUNNEL_HOST", "serveo.net")
        tunnel_port = os.getenv("TUNNEL_PORT", "0")      # 0=服务端自动分配
        tunnel_user = os.getenv("TUNNEL_USER", "")
        tunnel_ssh_key = os.getenv("TUNNEL_SSH_KEY", os.path.expanduser("~/.ssh/id_rsa"))
        local_ssh_port = os.getenv("TUNNEL_LOCAL_PORT", "22")

        # 构建目标地址
        if tunnel_user:
            destination = f"{tunnel_user}@{tunnel_host}"
        else:
            destination = tunnel_host

        # 构建 ssh -R 命令
        # -R [bind_address:]port:host:hostport
        # 如果 tunnel_port=0, serveo 会分配随机端口并返回 URL
        if tunnel_port == "0":
            remote_bind = f"0:localhost:{local_ssh_port}"
        else:
            remote_bind = f"{tunnel_port}:localhost:{local_ssh_port}"

        ssh_args = [
            "ssh",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ServerAliveInterval=60",
            "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes",
            "-R", remote_bind,
            "-N",  # 不执行远程命令, 只做端口转发
            "-T",  # 禁用伪终端
        ]

        # SSH 密钥
        if os.path.isfile(tunnel_ssh_key):
            ssh_args.extend(["-i", tunnel_ssh_key])

        ssh_args.append(destination)

        logger.info(f"🔗 打开 SSH 隧道: {' '.join(ssh_args)}")

        try:
            self._tunnel_proc = subprocess.Popen(
                ssh_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,  # 脱离当前进程组, 不会被一起杀掉
            )

            # 等待一小段时间让连接建立
            time.sleep(3)

            # 检查是否仍然存活
            if self._tunnel_proc.poll() is not None:
                stderr_output = self._tunnel_proc.stderr.read() if self._tunnel_proc.stderr else ""
                return False, f"隧道建立失败: {stderr_output[:200]}"

            # 构建连接信息
            if tunnel_host == "serveo.net":
                # serveo.net 分配随机公网地址
                # 模式: ssh -R starfire-pi:22:localhost:22 serveo.net
                # 用户: ssh -J serveo.net pi@starfire-pi
                relay_info = (
                    f"SSH 隧道已建立! 在任意有网络的电脑上执行:\n"
                    f"  ssh -J serveo.net pi@{self.node_id}\n\n"
                    f"首次使用 serveo 可能需确认指纹, 输入 yes 即可。"
                )
                self._tunnel_info = relay_info
            else:
                port_display = tunnel_port if tunnel_port != "0" else "(自动分配)"
                relay_info = (
                    f"SSH 隧道已建立! 连接方式:\n"
                    f"  ssh -p {port_display} pi@{tunnel_host}"
                )
                self._tunnel_info = relay_info

            logger.info(f"✅ {relay_info}")
            return True, relay_info

        except Exception as e:
            self._tunnel_proc = None
            return False, f"隧道打开失败: {e}"

    def _cmd_tunnel_close(self) -> tuple[bool, str]:
        """关闭 SSH 隧道"""
        if self._tunnel_proc is None or self._tunnel_proc.poll() is not None:
            self._tunnel_proc = None
            self._tunnel_info = ""
            return True, "tunnel-already-closed"

        logger.info("🔗 关闭 SSH 隧道...")
        try:
            # 发送 SIGTERM 到进程组
            os.killpg(os.getpgid(self._tunnel_proc.pid), signal.SIGTERM)
            self._tunnel_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(self._tunnel_proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.debug(f"关闭隧道进程异常: {e}")

        self._tunnel_proc = None
        self._tunnel_info = ""
        logger.info("🔗 SSH 隧道已关闭")
        return True, "tunnel-closed"

    def _cmd_tunnel_status(self) -> tuple[bool, str]:
        """查询隧道状态"""
        if self._tunnel_proc is not None and self._tunnel_proc.poll() is None:
            return True, self._tunnel_info or "tunnel-active"
        else:
            self._tunnel_proc = None
            self._tunnel_info = ""
            return True, "tunnel-inactive"

    def _cleanup_tunnel(self):
        """进程退出时自动清理隧道"""
        if self._tunnel_proc is not None:
            try:
                os.killpg(os.getpgid(self._tunnel_proc.pid), signal.SIGTERM)
            except Exception:
                pass
            self._tunnel_proc = None

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
        self._cleanup_tunnel()
        self.session.close()
