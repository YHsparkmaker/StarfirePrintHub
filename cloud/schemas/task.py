"""
星火智造云打印 — Pydantic 请求/响应 Schema
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════
# POST /api/upload — 响应
# ═══════════════════════════════════════════════════════════════════

class UploadResponse(BaseModel):
    """文件上传成功后的响应"""
    job_id: str = Field(..., description="任务唯一 ID")
    status: str = Field(default="pending", description="任务初始状态")
    file_name: str = Field(..., description="原始文件名")
    summary_text: Optional[str] = Field(None, description="AI 摘要 (若开启)")
    created_at: str = Field(..., description="创建时间 ISO 字符串")

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════
# GET /api/jobs/next — 响应
# ═══════════════════════════════════════════════════════════════════

class JobNextResponse(BaseModel):
    """树莓派拉取的待处理任务"""
    job_id: str
    file_name: str
    download_url: str = Field(..., description="文件下载直链")
    cups_options: dict = Field(default_factory=dict, description="打印参数")
    ai_summary: bool = False
    summary_text: Optional[str] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════
# POST /api/jobs/update — 请求 & 响应
# ═══════════════════════════════════════════════════════════════════

class JobUpdateRequest(BaseModel):
    """树莓派上报任务状态变更"""
    job_id: str = Field(..., description="任务 ID")
    status: str = Field(..., description="新状态: printing | completed | failed")
    node_id: Optional[str] = Field(None, description="节点 ID")
    error_msg: Optional[str] = Field(None, description="错误详情 (失败时)")


class JobUpdateResponse(BaseModel):
    """状态更新确认"""
    job_id: str
    status: str
    updated: bool = True


# ═══════════════════════════════════════════════════════════════════
# GET /api/jobs — 响应
# ═══════════════════════════════════════════════════════════════════

class JobListItem(BaseModel):
    """任务列表项"""
    id: str
    file_name: str
    status: str
    node_id: Optional[str] = None
    ai_summary: bool = False
    summary_text: Optional[str] = None
    error_msg: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════
# POST /api/text — 请求
# ═══════════════════════════════════════════════════════════════════

class TextUploadRequest(BaseModel):
    """Markdown 文本上传请求"""
    content: str = Field(..., min_length=1, description="Markdown 文本内容")
    cups_options: dict = Field(default_factory=dict, description="打印参数")
    ai_summary: bool = Field(default=False, description="是否生成 AI 摘要")
    node_id: Optional[str] = Field(None, description="目标打印机节点 ID")
