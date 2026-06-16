"""
星火智造云打印 — 边缘节点数据模型
记录每个树莓派打印机节点的注册信息和健康状态。
"""

from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class PrintNode(Base):
    __tablename__ = "print_nodes"

    # ── 主键: 使用树莓派自定义 node_id (如 pi-3f-a01) ──
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        comment="节点唯一标识 (由树莓派 .env 中的 NODE_ID 指定)"
    )

    # ── 节点标识 ──────────────────────────────
    name: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="节点名称 (如 '3楼A区打印机')"
    )
    mac_address: Mapped[str] = mapped_column(
        String(17), unique=True, nullable=True,
        comment="树莓派 MAC 地址, 用于唯一识别"
    )

    # ── 状态 ──────────────────────────────────
    is_online: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="是否在线"
    )
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime, nullable=True,
        comment="最后一次心跳时间"
    )

    # ── 打印机能力 ────────────────────────────
    printer_name: Mapped[str] = mapped_column(
        String(256), nullable=True,
        comment="CUPS 打印机名称"
    )
    supported_media: Mapped[str] = mapped_column(
        String(256), nullable=True, default="A4",
        comment="支持的纸张尺寸, 逗号分隔"
    )

    # ── 时间戳 ────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<PrintNode {self.name} [{'ON' if self.is_online else 'OFF'}]>"
