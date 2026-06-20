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
    node_id: str,
    name: str = "",
    mac_address: str = "",
    printer_name: str = "",
    db: AsyncSession = Depends(get_db),
):
    """
    注册一个新的边缘打印节点

    POST /api/nodes/register?node_id=pi-3f-a01&name=3楼A区
      注: node_id 必须与树莓派 .env 中 NODE_ID 一致
    """
    # 检查节点是否已注册
    existing = await db.execute(
        select(PrintNode).where(PrintNode.id == node_id)
    )
    node = existing.scalar_one_or_none()

    if node:
        # 已存在: 更新信息
        node.name = name or node.name
        node.mac_address = mac_address or node.mac_address
        node.printer_name = printer_name or node.printer_name
        logger.info(f"节点已存在，更新信息: {node_id}")
    else:
        # 新节点
        node = PrintNode(
            id=node_id,
            name=name,
            mac_address=mac_address,
            printer_name=printer_name,
        )
        db.add(node)
        logger.info(f"新节点注册: {node_id} ({name})")

    await db.commit()
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
    await db.commit()

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
            "last_heartbeat": n.last_heartbeat.isoformat() if n.last_heartbeat else None,
            "pending_command": n.pending_command,
            "command_result": n.command_result,
        }
        for n in nodes
    ]


# ═══════════════════════════════════════════════════════════════════
# 远程管理: 下发命令 → 树莓派轮询执行
# ═══════════════════════════════════════════════════════════════════

CMD_PING = "ping"
CMD_RESTART = "restart"
CMD_UPDATE = "update"
CMD_EXEC = "exec"
CMD_TUNNEL = "tunnel"
CMD_TUNNEL_CLOSE = "tunnel-close"
CMD_TUNNEL_STATUS = "tunnel-status"

ALLOWED_COMMANDS = {
    CMD_PING, CMD_RESTART, CMD_UPDATE, CMD_EXEC,
    CMD_TUNNEL, CMD_TUNNEL_CLOSE, CMD_TUNNEL_STATUS,
}


@router.post("/{node_id}/command")
async def send_command(
    node_id: str,
    cmd: str = CMD_PING,
    exec_cmd: str = "",
    db: AsyncSession = Depends(get_db),
):
    """
    向节点下发远程命令。树莓派轮询心跳时自动取走并执行。

    POST /api/nodes/pi-3f-a01/command?cmd=update
    POST /api/nodes/pi-3f-a01/command?cmd=exec&exec_cmd=sudo%20systemctl%20restart%20starfire-pi

    支持的命令:
      ping          — 连通性测试, 返回 Pi 状态信息
      restart       — 重启 pi_worker 守护进程
      update        — git pull + 重启 (OTA 更新)
      exec          — 执行自定义 shell 命令 (需谨慎! exec_cmd 参数)
      tunnel        — 打开反向 SSH 隧道 (Pi→公网跳板, 远程可SSH登录Pi)
      tunnel-close  — 关闭 SSH 隧道
      tunnel-status — 查询隧道状态
    """
    if cmd not in ALLOWED_COMMANDS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的命令: {cmd}。允许: {', '.join(ALLOWED_COMMANDS)}",
        )

    result = await db.execute(
        select(PrintNode).where(PrintNode.id == node_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(status_code=404, detail="节点未注册")

    if cmd == CMD_EXEC and not exec_cmd:
        raise HTTPException(status_code=400, detail="exec 命令需要提供 exec_cmd 参数")

    # 写入命令 (exec 命令附加在 pending_command 中: "exec|实际命令")
    if cmd == CMD_EXEC:
        node.pending_command = f"{CMD_EXEC}|{exec_cmd}"
    else:
        node.pending_command = cmd

    node.command_result = None  # 清除上次结果
    await db.commit()

    logger.info(f"📡 命令已下发 → {node_id}: {node.pending_command}")
    return {
        "node_id": node.id,
        "command": cmd,
        "exec_cmd": exec_cmd if cmd == CMD_EXEC else "",
        "message": f"命令已下发, 等待 {node_id} 执行",
    }


@router.get("/{node_id}/command")
async def fetch_command(
    node_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    树莓派轮询: 获取并清除待执行命令

    GET /api/nodes/pi-3f-a01/command
    返回: { "command": "update" } 或 { "command": null }
    """
    result = await db.execute(
        select(PrintNode).where(PrintNode.id == node_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(status_code=404, detail="节点未注册")

    cmd = node.pending_command
    node.pending_command = None
    await db.commit()

    return {
        "command": cmd,
        "node_id": node.id,
    }


@router.post("/{node_id}/command/result")
async def report_command_result(
    node_id: str,
    cmd: str = "",
    output: str = "",
    success: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    树莓派上报命令执行结果

    POST /api/nodes/pi-3f-a01/command/result?cmd=update&output=OK&success=true
    """
    result = await db.execute(
        select(PrintNode).where(PrintNode.id == node_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(status_code=404, detail="节点未注册")

    status = "OK" if success else "FAIL"
    node.command_result = f"{cmd}:{status} | {output[:400]}"
    await db.commit()

    logger.info(f"📡 {node_id} 命令结果: {node.command_result}")
    return {
        "node_id": node.id,
        "result": node.command_result,
    }
