"""
星火智造云打印 — 任务轮询模块
负责:
  1. 定期 GET /api/jobs/next 拉取任务
  2. 下载 PDF 文件到本地
  3. 将原始任务封装为可处理的结构
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

import requests

from config import config

logger = logging.getLogger(__name__)


class JobPoller:
    """
    云端任务轮询器

    工作流程:
      while True:
        1. GET /api/jobs/next?node_id=xxx
        2. 若有任务 → 下载 PDF → 返回任务数据
        3. 若无任务 → 等待 poll_interval 秒后重试
    """

    def __init__(self):
        self.base_url = config.CLOUD_BASE_URL.rstrip("/")
        self.node_id = config.NODE_ID
        self.download_dir = Path(config.DOWNLOAD_DIR)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # HTTP 会话复用 (连接池)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"StarfirePiClient/1.0 (Node: {self.node_id})",
            "Accept": "application/json",
        })

    # ── 拉取下一个任务 ────────────────────────

    def fetch_next_job(self) -> Optional[Dict[str, Any]]:
        """
        从云端拉取下一个待处理任务

        Returns:
            {
                "job_id": "abc123",
                "file_name": "report.pdf",
                "download_url": "/api/files/abc123/download",
                "cups_options": {"copies": 2, "sides": "two-sided-long-edge"},
                "ai_summary": true,
                "summary_text": "## 摘要\n..."
            }
            如果没有任务，返回 None
        """
        url = f"{self.base_url}/api/jobs/next"
        params = {"node_id": self.node_id}

        try:
            resp = self.session.get(
                url,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()

            # 如果云端返回 null (JSON null)，说明没有待处理任务
            if resp.text.strip() == "null" or not resp.text.strip():
                return None

            job_data = resp.json()
            if job_data is None:
                return None

            logger.info(f"📥 拉取到任务: {job_data.get('job_id')} ({job_data.get('file_name')})")
            return job_data

        except requests.exceptions.ConnectionError:
            logger.error(f"❌ 连接云端失败: {self.base_url} 无法访问")
            return None
        except requests.exceptions.Timeout:
            logger.error(f"⏰ 请求超时: GET {url}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"⚠️ HTTP 错误: {e}")
            return None
        except Exception as e:
            logger.error(f"拉取任务异常: {type(e).__name__}: {e}")
            return None

    # ── 下载 PDF 文件 ─────────────────────────

    def download_pdf(self, download_url: str, job_id: str) -> Optional[str]:
        """
        从云端下载任务对应的 PDF 文件

        Args:
            download_url: 完整下载链接 (如 /api/files/abc123/download)
            job_id: 任务 ID

        Returns:
            本地文件路径，失败返回 None
        """
        # 拼接完整 URL
        if download_url.startswith("http"):
            full_url = download_url
        else:
            full_url = f"{self.base_url}{download_url}"

        local_path = self.download_dir / f"{job_id}.pdf"

        try:
            logger.info(f"⬇️ 开始下载: {full_url}")

            resp = self.session.get(
                full_url,
                timeout=60,  # 大文件需要更长超时
                stream=True,  # 流式下载，支持断点 & 大文件
            )
            resp.raise_for_status()

            # 检查 Content-Type
            content_type = resp.headers.get("Content-Type", "")
            if "application/pdf" not in content_type and "application/octet-stream" not in content_type:
                logger.warning(f"⚠️ 非预期 Content-Type: {content_type}")

            # 流式写入磁盘
            total_bytes = 0
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_bytes += len(chunk)

            file_size_mb = total_bytes / (1024 * 1024)
            logger.info(f"✅ 下载完成: {local_path} ({file_size_mb:.2f} MB)")
            return str(local_path)

        except requests.exceptions.ConnectionError:
            logger.error(f"❌ 下载失败: 无法连接 {full_url}")
            return None
        except requests.exceptions.Timeout:
            logger.error(f"⏰ 下载超时: {full_url}")
            return None
        except Exception as e:
            logger.error(f"下载异常: {type(e).__name__}: {e}")
            return None

    # ── 清理本地文件 ──────────────────────────

    def cleanup_local_file(self, job_id: str):
        """删除本地的任务 PDF 文件"""
        local_path = self.download_dir / f"{job_id}.pdf"
        try:
            if local_path.exists():
                local_path.unlink()
                logger.debug(f"🗑️ 已清理: {local_path}")
        except Exception as e:
            logger.warning(f"清理文件失败: {e}")

    # ── 关闭 ──────────────────────────────────

    def close(self):
        """关闭 HTTP 会话"""
        self.session.close()
