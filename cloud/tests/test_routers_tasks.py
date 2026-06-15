"""
test_routers_tasks.py — 打印任务路由集成测试
覆盖: 文件上传 / 状态查询 / 任务拉取 / 状态更新 / 文件下载

使用 httpx.AsyncClient 搭配 ASGITransport 发起真实 HTTP 请求,
数据库使用内存 SQLite, 文件写入临时目录。
"""

import json
import io
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from main import app
from database import get_db, AsyncSessionLocal
from config import settings as app_settings


# ═══════════════════════════════════════════════════════════════════
# 数据库 override — 每次请求使用测试 DB session
# ═══════════════════════════════════════════════════════════════════

async def override_get_db():
    """为每个请求创建独立的测试数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def upload_dir(tmp_path):
    """临时文件目录, 测试结束后自动清理"""
    d = tmp_path / "test_uploads"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def async_client(async_engine, upload_dir):
    """返回挂载了 FastAPI app 的 httpx AsyncClient"""
    # 1. 绑定测试数据库
    AsyncSessionLocal.configure(bind=async_engine)

    # 2. 覆盖依赖
    app.dependency_overrides[get_db] = override_get_db

    # 3. 覆盖上传目录 (防止污染实际 uploads/)
    original_upload_dir = app_settings.UPLOAD_DIR
    app_settings.UPLOAD_DIR = upload_dir

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # 恢复
    app.dependency_overrides.clear()
    app_settings.UPLOAD_DIR = original_upload_dir


def _make_pdf_file(filename="test.pdf", content=b"%PDF-1.4 fake pdf"):
    """工具函数: 创建内存中的 PDF 文件对象"""
    return io.BytesIO(content)


# ═══════════════════════════════════════════════════════════════════
# POST /api/upload
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_upload_pdf_success(async_client):
    files = {"file": ("report.pdf", _make_pdf_file(), "application/pdf")}
    data = {"cups_options": '{"copies": 2, "sides": "one-sided"}', "ai_summary": "false"}

    resp = await async_client.post("/api/upload", files=files, data=data)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["file_name"] == "report.pdf"
    assert len(body["job_id"]) == 32
    assert "created_at" in body


@pytest.mark.asyncio
async def test_upload_invalid_file_type(async_client):
    files = {"file": ("script.sh", io.BytesIO(b"#!/bin/bash"), "text/x-shellscript")}
    data = {"cups_options": "{}"}

    resp = await async_client.post("/api/upload", files=files, data=data)

    assert resp.status_code == 400
    assert "不支持" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_invalid_json_options(async_client):
    files = {"file": ("doc.pdf", _make_pdf_file(), "application/pdf")}
    data = {"cups_options": "not-valid-json"}

    resp = await async_client.post("/api/upload", files=files, data=data)

    assert resp.status_code == 400
    assert "JSON" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_with_default_options(async_client):
    files = {"file": ("doc.pdf", _make_pdf_file(), "application/pdf")}
    # cups_options 不传时默认为 "{}"
    resp = await async_client.post("/api/upload", files=files)

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_upload_with_ai_summary_enabled(async_client):
    files = {"file": ("doc.pdf", _make_pdf_file(), "application/pdf")}
    data = {"cups_options": "{}", "ai_summary": "true"}

    resp = await async_client.post("/api/upload", files=files, data=data)

    # AI 摘要是后台异步, 但响应应正常返回
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"


# ═══════════════════════════════════════════════════════════════════
# GET /api/jobs/{job_id}/status
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_job_status_success(async_client):
    files = {"file": ("doc.pdf", _make_pdf_file(), "application/pdf")}
    upload_resp = await async_client.post("/api/upload", files=files)
    job_id = upload_resp.json()["job_id"]

    resp = await async_client.get(f"/api/jobs/{job_id}/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == job_id
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_get_job_status_not_found(async_client):
    resp = await async_client.get("/api/jobs/nonexistent-id/status")
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# GET /api/jobs/next
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_next_job_with_pending(async_client):
    files = {"file": ("doc.pdf", _make_pdf_file(), "application/pdf")}
    await async_client.post("/api/upload", files=files)

    resp = await async_client.get("/api/jobs/next?node_id=pi-01")

    assert resp.status_code == 200
    body = resp.json()
    assert body is not None
    assert "job_id" in body
    assert "download_url" in body
    assert "cups_options" in body
    assert body["download_url"].startswith("/api/files/")


@pytest.mark.asyncio
async def test_get_next_job_empty_queue(async_client):
    resp = await async_client.get("/api/jobs/next?node_id=pi-01")

    assert resp.status_code == 200
    # 空队列 → 返回 null (JSON null)
    assert resp.text.strip() == "null"


# ═══════════════════════════════════════════════════════════════════
# POST /api/jobs/update
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_update_job_status_to_completed(async_client):
    files = {"file": ("doc.pdf", _make_pdf_file(), "application/pdf")}
    upload_resp = await async_client.post("/api/upload", files=files)
    job_id = upload_resp.json()["job_id"]

    resp = await async_client.post(
        "/api/jobs/update",
        json={"job_id": job_id, "status": "completed", "node_id": "pi-01"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == job_id
    assert body["status"] == "completed"
    assert body["updated"] is True


@pytest.mark.asyncio
async def test_update_job_status_to_failed_with_error(async_client):
    files = {"file": ("doc.pdf", _make_pdf_file(), "application/pdf")}
    upload_resp = await async_client.post("/api/upload", files=files)
    job_id = upload_resp.json()["job_id"]

    resp = await async_client.post(
        "/api/jobs/update",
        json={"job_id": job_id, "status": "failed", "error_msg": "paper jam"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"

    # 验证错误信息持久化
    status_resp = await async_client.get(f"/api/jobs/{job_id}/status")
    assert status_resp.json()["error_msg"] == "paper jam"


@pytest.mark.asyncio
async def test_update_job_invalid_status(async_client):
    resp = await async_client.post(
        "/api/jobs/update",
        json={"job_id": "xxx", "status": "unknown-status"},
    )
    assert resp.status_code == 400
    assert "无效状态" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_job_not_found(async_client):
    resp = await async_client.post(
        "/api/jobs/update",
        json={"job_id": "nonexistent", "status": "completed"},
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# GET /api/files/{job_id}/download
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_download_file_success(async_client):
    files = {"file": ("doc.pdf", _make_pdf_file(content=b"%PDF-1.4\nhello world"), "application/pdf")}
    upload_resp = await async_client.post("/api/upload", files=files)
    job_id = upload_resp.json()["job_id"]

    resp = await async_client.get(f"/api/files/{job_id}/download")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert b"%PDF-1.4" in resp.content


@pytest.mark.asyncio
async def test_download_file_not_found(async_client):
    resp = await async_client.get("/api/files/nonexistent/download")
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 上传后状态持久化验证 (端到端链路)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_upload_to_status_lifecycle(async_client):
    """完整生命周期: 上传 → 查状态 → 拉取 → 更新完成 → 确认"""
    # 1. 上传
    files = {"file": ("lifecycle.pdf", _make_pdf_file(), "application/pdf")}
    resp = await async_client.post(
        "/api/upload",
        files=files,
        data={"cups_options": '{"copies": 3, "media": "A4"}'},
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    # 2. 查询 → pending
    status = await async_client.get(f"/api/jobs/{job_id}/status")
    assert status.json()["status"] == "pending"

    # 3. 树莓派拉取
    next_job = await async_client.get("/api/jobs/next?node_id=pi-01")
    assert next_job.json()["job_id"] == job_id
    assert next_job.json()["cups_options"] == {"copies": 3, "media": "A4"}

    # 4. 查询 → printing
    status = await async_client.get(f"/api/jobs/{job_id}/status")
    assert status.json()["status"] == "printing"

    # 5. 上报完成
    await async_client.post(
        "/api/jobs/update",
        json={"job_id": job_id, "status": "completed", "node_id": "pi-01"},
    )

    # 6. 最终确认
    status = await async_client.get(f"/api/jobs/{job_id}/status")
    assert status.json()["status"] == "completed"
