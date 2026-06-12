"""
星火智造云打印 — 边缘节点管理路由
节点注册、心跳上报、在线状态管理。
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.node import PrintNode

router = APIRouter(prefix="/api/nodes", tags=["边缘节点"])
logger = logging.getLogger(__name__)


@router.post("/register")
async def register_node(
    name: str,
    mac_address: str,
    printer_name: str = "",
    supported_media: str = "A4",
    db: AsyncSession = Depends(get_db),
):
    """
    注册一个新的边缘打印节点

    POST /api/nodes/register?name=3楼A区&mac_address=AA:BB:CC:DD:EE:FF
    """
    # 检查 MAC 是否已注册
    existing = await db.execute(
        select(PrintNode).where(PrintNode.mac_address == mac_address)
    )
    node = existing.scalar_one_or_none()

    if node:
        # 已存在: 更新信息
        node.name = name
        node.printer_name = printer_name
        node.supported_media = supported_media
        logger.info(f"节点已存在，更新信息: {mac_address}")
    else:
        # 新节点
        node = PrintNode(
            name=name,
            mac_address=mac_address,
            printer_name=printer_name,
            supported_media=supported_media,
        )
        db.add(node)
        logger.info(f"新节点注册: {name} ({mac_address})")

    await db.flush()
    await db.refresh(node)

    return {
        "node_id": node.id,
        "name": node.name,
        "mac_address": node.mac_address,
        "message": "节点注册成功",
    }


@router.post("/{node_id}/heartbeat")
async def node_heartbeat(
    node_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    边缘节点心跳上报 (建议每 30 秒发送一次)

    POST /api/nodes/abc123/heartbeat
    """
    result = await db.execute(
        select(PrintNode).where(PrintNode.id == node_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(status_code=404, detail="节点未注册")

    node.is_online = True
    node.last_heartbeat = datetime.now(timezone.utc)
    await db.flush()

    return {
        "node_id": node.id,
        "is_online": node.is_online,
        "last_heartbeat": node.last_heartbeat.isoformat(),
    }


@router.get("/")
async def list_nodes(
    db: AsyncSession = Depends(get_db),
):
    """列出所有已注册的节点及其在线状态"""
    result = await db.execute(select(PrintNode).order_by(PrintNode.name))
    nodes = result.scalars().all()

    return [
        {
            "id": n.id,
            "name": n.name,
            "is_online": n.is_online,
            "printer_name": n.printer_name,
            "supported_media": n.supported_media,
            "last_heartbeat": n.last_heartbeat.isoformat() if n.last_heartbeat else None,
        }
        for n in nodes
    ]
