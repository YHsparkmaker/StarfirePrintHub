"""
星火智造云打印 — 打印任务路由
面向手机端用户: 文件上传、任务查询
面向树莓派端:  拉取任务、更新状态、文件下载
"""

import io
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
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.task import PrintTask
from schemas.task import (
    UploadResponse,
    JobNextResponse,
    JobUpdateRequest,
    JobUpdateResponse,
    JobListItem,
    TextUploadRequest,
)
from services.task_service import TaskService
from services.file_service import FileService, ALLOWED_EXTENSIONS
from services.ai_service import generate_ai_summary_and_prepend
from services.text_render_service import TextRenderService
from services.print_preview_service import generate_preview_pdf
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
    # ── 目标节点 (扫码自带) ──
    node_id: Optional[str] = Form(
        default=None,
        description="目标打印机节点 ID (扫码传入)",
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
            detail=f"不支持的文件类型。允许: {ALLOWED_EXTENSIONS}",
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
        node_id=node_id,
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


# ═══════════════════════════════════════════════════════════════════
# 6. 任务列表 (面向手机端)
# ═══════════════════════════════════════════════════════════════════

@router.get("/jobs", response_model=list[JobListItem])
async def list_jobs(
    node_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """
    手机端查询历史任务列表

    GET /api/jobs?node_id=xxx&limit=20&offset=0
    → [{ id, file_name, status, ... }, ...]
    """
    tasks = await TaskService.list_jobs(
        db, node_id=node_id, limit=limit, offset=offset
    )
    return [t.to_dict() for t in tasks]


# ═══════════════════════════════════════════════════════════════════
# 7. 文本上传 (Markdown + LaTeX → PDF → 打印任务)
# ═══════════════════════════════════════════════════════════════════

@router.post("/text", response_model=UploadResponse)
async def upload_text(
    req: TextUploadRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    手机端提交 Markdown 文本 → 渲染为 PDF → 创建打印任务

    POST /api/text
    {
      "content": "# 标题\\n\\n内容...",
      "cups_options": {"copies": 2, "media": "A4"},
      "node_id": "pi-3f-a01"
    }

    服务端流程:
      1. LaTeX 公式 → MathML
      2. Markdown → HTML
      3. weasyprint → PDF
      4. 保存 PDF → 创建任务
    """
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="文本内容不能为空")

    # ── 1. Markdown + LaTeX → PDF ───────────
    try:
        header_info = req.cups_options.get("header_info") if req.cups_options else None
        pdf_path = TextRenderService.render_to_pdf(
            markdown_text=req.content,
            filename_prefix="text",
            header_info=header_info,
        )
    except Exception as e:
        logger.error(f"文本 PDF 渲染失败: {e}")
        raise HTTPException(status_code=500, detail=f"文本渲染失败: {e}")

    # ── 2. 创建任务记录 ──────────────────────
    task = await TaskService.create_task(
        db=db,
        file_path=str(pdf_path),
        original_name="文本打印.md",
        cups_options=req.cups_options,
        ai_summary=req.ai_summary,
        node_id=req.node_id,
    )

    return UploadResponse(
        job_id=task.id,
        status=task.status,
        file_name="文本打印",
        summary_text=None,
        created_at=task.created_at.isoformat(),
    )


# ═══════════════════════════════════════════════════════════════════
# 8. 打印预览 (文件/文本 → 应用打印配置 → 返回预览 PDF)
# ═══════════════════════════════════════════════════════════════════

@router.post("/preview")
async def preview_print(
    # ── 文件 (可选) ──
    file: Optional[UploadFile] = File(None),
    # ── 文本 (可选) ──
    text_content: Optional[str] = Form(None),
    # ── 打印参数 ──
    cups_options: str = Form(default="{}"),
):
    """
    预览打印效果 — 将文件或文本按打印参数生成预览 PDF

    POST /api/preview
    Content-Type: multipart/form-data

    file:          (可选) 上传的 PDF 文件
    text_content:  (可选) Markdown 文本内容
    cups_options:  JSON 字符串, 如 {"number_up":4,"copies":2,"sides":"two-sided-long-edge"}

    返回: PDF 文件流 (application/pdf)
    """
    # ── 解析打印参数 ──
    try:
        opts = json.loads(cups_options)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="cups_options 不是合法的 JSON")

    number_up = opts.get("number_up", 1)
    sides = opts.get("sides", "one-sided")
    copies = opts.get("copies", 1)
    orientation = opts.get("orientation", "portrait")
    media = opts.get("media", "A4")
    header_info = opts.get("header_info")  # {subject, class_name, school_label}

    # ── 获取源 PDF ──
    pdf_bytes: bytes

    if file and file.filename:
        # 文件模式
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="上传的文件为空")
    elif text_content and text_content.strip():
        # 文本模式: 先渲染为 PDF
        try:
            pdf_path = TextRenderService.render_to_pdf(
                markdown_text=text_content,
                filename_prefix="preview",
                header_info=header_info,
            )
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
        except Exception as e:
            logger.error(f"文本预览渲染失败: {e}")
            raise HTTPException(status_code=500, detail=f"文本渲染失败: {e}")
    else:
        raise HTTPException(status_code=400, detail="请提供文件或文本内容")

    # ── 应用打印配置 → 生成预览 ──
    try:
        preview_bytes = generate_preview_pdf(
            pdf_bytes=pdf_bytes,
            media=media,
            number_up=number_up,
            sides=sides,
            copies=copies,
            orientation=orientation,
            header_info=header_info,
        )
    except Exception as e:
        logger.error(f"预览生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"预览生成失败: {e}")

    return StreamingResponse(
        io.BytesIO(preview_bytes),
        media_type="application/pdf",
    )
