"""
星火智造云打印 — 打印任务数据模型
字段说明:
  - id:           任务唯一标识 (UUID 字符串)
  - file_path:    原始 PDF 文件在服务器上的路径
  - status:       任务状态 (pending / printing / completed / failed)
  - cups_options: 打印参数 (JSON 字符串), 例如:
      {
        "copies": 1,
        "sides": "one-sided",      # one-sided | two-sided-long-edge
        "media": "A4",
        "page_ranges": "1-5",
        "n_up": 2                  # 拼版: 每张纸放几页
      }
  - ai_summary:   是否启用 AI 摘要
  - summary_text: AI 生成的摘要文本 (可为空)
  - node_id:      处理该任务的边缘节点 ID (可为空)
  - error_msg:    错误信息 (失败时记录)
  - created_at:   创建时间
  - updated_at:   最后更新时间
"""

import uuid
import json
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class PrintTask(Base):
    __tablename__ = "print_tasks"

    # ── 主键 ──────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: uuid.uuid4().hex
    )

    # ── 文件路径 ──────────────────────────────
    file_path: Mapped[str] = mapped_column(
        String(512), nullable=False,
        comment="服务器上的 PDF 文件路径"
    )

    # ── 任务状态 ──────────────────────────────
    # pending: 等待拉取
    # printing: 边缘节点正在打印
    # completed: 打印完成
    # failed: 打印失败
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending | printing | completed | failed"
    )

    # ── CUPS 打印选项 ─────────────────────────
    cups_options: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}",
        comment="JSON 格式的 CUPS 打印参数"
    )

    # ── AI 摘要 ───────────────────────────────
    ai_summary: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="是否需要生成 AI 摘要"
    )
    summary_text: Mapped[str] = mapped_column(
        Text, nullable=True, default=None,
        comment="AI 生成的摘要文本"
    )

    # ── 关联节点 ──────────────────────────────
    node_id: Mapped[str] = mapped_column(
        String(64), nullable=True, default=None,
        comment="处理该任务的边缘节点 ID"
    )

    # ── 错误信息 ──────────────────────────────
    error_msg: Mapped[str] = mapped_column(
        Text, nullable=True, default=None,
        comment="失败时的错误详情"
    )

    # ── 重试计数 ──────────────────────────────
    retry_count: Mapped[int] = mapped_column(
        default=0,
        comment="已重试次数"
    )

    # ── 时间戳 ────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="最后更新时间"
    )

    def set_cups_options(self, options: dict):
        """将 dict 序列化为 JSON 存入 cups_options 字段"""
        self.cups_options = json.dumps(options, ensure_ascii=False)

    def get_cups_options(self) -> dict:
        """将 cups_options JSON 字符串反序列化为 dict"""
        return json.loads(self.cups_options) if self.cups_options else {}

    def to_dict(self) -> dict:
        """转为字典，方便序列化响应"""
        return {
            "id": self.id,
            "file_name": self.file_path.split("/")[-1] if self.file_path else "",
            "status": self.status,
            "cups_options": self.get_cups_options(),
            "ai_summary": self.ai_summary,
            "summary_text": self.summary_text,
            "node_id": self.node_id,
            "error_msg": self.error_msg,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<PrintTask {self.id[:8]}... [{self.status}]>"
