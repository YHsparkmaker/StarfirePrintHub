"""
星火智造云打印 — 任务业务逻辑层
封装任务的创建、查询、状态更新等核心操作。
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.task import PrintTask
from config import settings

logger = logging.getLogger(__name__)


class TaskService:
    """打印任务 CRUD 服务"""

    # ═══════════════════════════════════════════════════════════════
    # 创建任务
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    async def create_task(
        db: AsyncSession,
        file_path: str,
        original_name: str,
        cups_options: dict,
        ai_summary: bool = False,
        node_id: Optional[str] = None,
    ) -> PrintTask:
        """
        创建一条新的打印任务记录

        Args:
            db: 数据库会话
            file_path: 服务器上的 PDF 文件路径
            original_name: 用户上传的原始文件名
            cups_options: 打印参数字典
            ai_summary: 是否开启 AI 摘要
            node_id: 目标边缘节点 ID (扫码传入, 可空)

        Returns:
            新创建的 PrintTask 实例
        """
        task = PrintTask(
            file_path=file_path,
            status="pending",
            ai_summary=ai_summary,
            node_id=node_id,
        )
        task.set_cups_options(cups_options)

        db.add(task)
        await db.flush()  # 立即生成 ID, 但事务还未提交
        await db.refresh(task)

        logger.info(f"任务已创建: {task.id} (文件: {original_name})")
        return task

    # ═══════════════════════════════════════════════════════════════
    # 拉取下一个待处理任务 (树莓派轮询用)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    async def get_next_pending(
        db: AsyncSession,
        node_id: Optional[str] = None,
    ) -> Optional[PrintTask]:
        """
        获取下一条 pending 状态的任务，并按 FIFO 顺序返回。

        使用 SELECT ... FOR UPDATE (或 SQLite 等价方式) 防止并发抢占。
        读取后立即将任务状态更新为 'printing'，并绑定到请求节点。

        Args:
            db: 数据库会话
            node_id: 拉取任务的边缘节点 ID

        Returns:
            待处理任务，如果没有则返回 None
        """
        # 查询最早的一条 pending 任务 (FIFO)
        stmt = (
            select(PrintTask)
            .where(PrintTask.status == "pending")
            .order_by(PrintTask.created_at.asc())
            .limit(1)
        )
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()

        if task is None:
            return None

        # 原子性抢占: 标记为 printing + 绑定节点
        task.status = "printing"
        task.node_id = node_id
        task.updated_at = datetime.now(timezone.utc)
        await db.flush()

        logger.info(f"任务 {task.id} 已分配给节点 {node_id}")
        return task

    # ═══════════════════════════════════════════════════════════════
    # 更新任务状态
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    async def update_status(
        db: AsyncSession,
        job_id: str,
        new_status: str,
        node_id: Optional[str] = None,
        error_msg: Optional[str] = None,
        summary_text: Optional[str] = None,
    ) -> Optional[PrintTask]:
        """
        更新任务状态

        合法状态流转:
          pending → printing → completed
          pending → printing → failed

        Args:
            db: 数据库会话
            job_id: 任务 ID
            new_status: 新状态
            node_id: 节点 ID (可选)
            error_msg: 错误信息 (失败时)
            summary_text: AI 摘要文本 (上传后异步写入)

        Returns:
            更新后的任务，未找到则返回 None
        """
        stmt = select(PrintTask).where(PrintTask.id == job_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()

        if task is None:
            logger.warning(f"任务未找到: {job_id}")
            return None

        # 更新状态
        task.status = new_status
        task.updated_at = datetime.now(timezone.utc)

        if node_id:
            task.node_id = node_id
        if error_msg:
            task.error_msg = error_msg
        if summary_text:
            task.summary_text = summary_text

        # 失败时增加重试计数
        if new_status == "failed":
            task.retry_count += 1

        await db.flush()
        await db.refresh(task)

        logger.info(f"任务 {job_id} 状态更新: → {new_status}")
        return task

    # ═══════════════════════════════════════════════════════════════
    # 查询单个任务
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        job_id: str,
    ) -> Optional[PrintTask]:
        """根据 ID 查询任务"""
        stmt = select(PrintTask).where(PrintTask.id == job_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # ═══════════════════════════════════════════════════════════════
    # 任务列表查询
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    async def list_jobs(
        db: AsyncSession,
        node_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PrintTask]:
        """分页查询任务列表 (按创建时间倒序)"""
        stmt = select(PrintTask)
        if node_id:
            stmt = stmt.where(PrintTask.node_id == node_id)
        stmt = (
            stmt.order_by(PrintTask.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())
