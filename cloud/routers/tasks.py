"""
星火智造云打印 — 打印任务路由
面向手机端用户: 文件上传、任务查询
面向树莓派端:  拉取任务、更新状态、文件下载
"""

import json
import logging
from typing import Optional
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.task import PrintTask
from schemas.task import (
    UploadResponse,
    JobNextResponse,
    JobUpdateRequest,
    JobUpdateResponse,
)
from services.task_service import TaskService
from services.file_service import FileService
from services.ai_service import generate_ai_summary_and_prepend
from config import settings

router = APIRouter(prefix="/api", tags=["打印任务"])
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# 1. 文件上传 & 创建打印任务 (面向手机端)
# ═══════════════════════════════════════════════════════════════════

@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    # ── 文件 ──
    file: UploadFile = File(..., description="要打印的 PDF 文件"),
    # ── 打印参数 (JSON 字符串) ──
    #  格式: {"copies":1, "sides":"one-sided", "media":"A4", "n_up":1}
    cups_options: str = Form(
        default="{}",
        description="JSON 格式的 CUPS 打印参数",
    ),
    # ── AI 摘要开关 ──
    ai_summary: bool = Form(
        default=False,
        description="是否生成 AI 摘要并拼接到 PDF 前",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    手机端上传 PDF 文件并提交打印任务

    请求示例 (multipart/form-data):
      file:          resume.pdf
      cups_options:  '{"copies": 2, "sides": "two-sided-long-edge", "media": "A4"}'
      ai_summary:    true

    返回: 任务 ID、状态、文件名、创建时间
    """
    # ── 1. 校验文件类型 ──────────────────────
    if not FileService.is_allowed(file.filename or ""):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型。允许: {FileService.ALLOWED_EXTENSIONS}",
        )

    # ── 2. 解析打印参数 ──────────────────────
    try:
        cups_dict = json.loads(cups_options) if cups_options else {}
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="cups_options 不是合法的 JSON 字符串",
        )

    # ── 3. 保存文件到磁盘 ────────────────────
    try:
        file_path, original_name = await FileService.save(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"文件保存失败: {e}")
        raise HTTPException(status_code=500, detail="文件保存失败")

    # ── 4. 创建任务记录 ──────────────────────
    task = await TaskService.create_task(
        db=db,
        file_path=file_path,
        original_name=original_name,
        cups_options=cups_dict,
        ai_summary=ai_summary,
    )

    # ── 5. 【AI 拦截】如果开启 AI 摘要，异步生成 ──
    #   注意: 使用 BackgroundTasks 不阻塞 HTTP 响应。
    #   摘要生成完成后，summary_text 通过 /jobs/update 回写。
    if ai_summary:
        logger.info(f"任务 {task.id} 已加入 AI 摘要后台队列")
        background_tasks.add_task(
            _ai_summary_with_persist,
            pdf_path=file_path,
            job_id=task.id,
            db_session_factory=db,  # 注意: 这里需要独立的 session
        )

    return UploadResponse(
        job_id=task.id,
        status=task.status,
        file_name=original_name,
        summary_text=None,  # AI 摘要在后台异步生成，响应时不阻塞
        created_at=task.created_at.isoformat(),
    )


async def _ai_summary_with_persist(
    pdf_path: str,
    job_id: str,
    # 注意: BackgroundTasks 中不能直接复用请求的 db session
    # 这里我们使用独立的 session
):
    """
    后台任务: 生成 AI 摘要 → 拼接到 PDF → 写回数据库
    在 BackgroundTasks 中运行，不阻塞上传接口响应。
    """
    from database import AsyncSessionLocal

    # 生成摘要 & 拼接 PDF
    summary = await generate_ai_summary_and_prepend(pdf_path, job_id)

    # 写回数据库
    if summary:
        async with AsyncSessionLocal() as db:
            try:
                await TaskService.update_status(
                    db=db,
                    job_id=job_id,
                    new_status="pending",  # 不改变任务状态
                    summary_text=summary,
                )
                await db.commit()
                logger.info(f"任务 {job_id} AI 摘要已持久化")
            except Exception as e:
                logger.error(f"持久化 AI 摘要失败: {e}")


# ═══════════════════════════════════════════════════════════════════
# 2. 查询任务状态 (面向手机端)
# ═══════════════════════════════════════════════════════════════════

@router.get("/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    手机端查询任务状态

    GET /api/jobs/abc123/status
    → { "job_id": "abc123", "status": "printing", ... }
    """
    task = await TaskService.get_by_id(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task.to_dict()


# ═══════════════════════════════════════════════════════════════════
# 3. 拉取下一个待处理任务 (面向树莓派)
# ═══════════════════════════════════════════════════════════════════

@router.get("/jobs/next", response_model=Optional[JobNextResponse])
async def get_next_job(
    node_id: str = "unknown",
    db: AsyncSession = Depends(get_db),
):
    """
    树莓派轮询拉取下一个 pending 任务

    GET /api/jobs/next?node_id=pi-3f-a01
    → {
        "job_id": "abc123",
        "file_name": "resume.pdf",
        "download_url": "/api/files/abc123/download",
        "cups_options": {"copies": 2, ...},
        "ai_summary": true,
        "summary_text": "## 摘要\n..."
      }
    → 如果没有待处理任务，返回 null
    """
    task = await TaskService.get_next_pending(db, node_id=node_id)

    if not task:
        return None  # FastAPI 返回 null (JSON null)

    return JobNextResponse(
        job_id=task.id,
        file_name=Path(task.file_path).name,
        download_url=f"/api/files/{task.id}/download",
        cups_options=task.get_cups_options(),
        ai_summary=task.ai_summary,
        summary_text=task.summary_text,
    )


# ═══════════════════════════════════════════════════════════════════
# 4. 更新任务状态 (面向树莓派)
# ═══════════════════════════════════════════════════════════════════

@router.post("/jobs/update", response_model=JobUpdateResponse)
async def update_job_status(
    req: JobUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    树莓派上报任务执行状态

    POST /api/jobs/update
    {
      "job_id": "abc123",
      "status": "completed",      // printing | completed | failed
      "node_id": "pi-3f-a01",
      "error_msg": null
    }
    """
    valid_statuses = {"printing", "completed", "failed"}
    if req.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"无效状态 '{req.status}'，合法值: {valid_statuses}",
        )

    task = await TaskService.update_status(
        db=db,
        job_id=req.job_id,
        new_status=req.status,
        node_id=req.node_id,
        error_msg=req.error_msg,
    )

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return JobUpdateResponse(
        job_id=task.id,
        status=task.status,
    )


# ═══════════════════════════════════════════════════════════════════
# 5. 文件下载 (面向树莓派)
# ═══════════════════════════════════════════════════════════════════

@router.get("/files/{job_id}/download")
async def download_file(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    树莓派下载任务对应的 PDF 文件

    GET /api/files/abc123/download
    → 返回 PDF 文件流
    """
    task = await TaskService.get_by_id(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    file_path = Path(task.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件已被清理或不存在")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/pdf",
    )
