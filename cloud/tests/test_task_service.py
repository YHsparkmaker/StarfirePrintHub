"""
test_task_service.py — 任务服务层单元测试
覆盖: 创建 / 拉取(FIFO) / 状态更新 / 查询 / 边界条件
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from models.task import PrintTask
from services.task_service import TaskService


# ═══════════════════════════════════════════════════════════════════
# create_task
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_task_creates_pending_task(db_session):
    task = await TaskService.create_task(
        db=db_session,
        file_path="/uploads/test.pdf",
        original_name="report.pdf",
        cups_options={"copies": 2, "sides": "one-sided"},
        ai_summary=False,
    )

    assert task.id is not None
    assert len(task.id) == 32  # UUID hex
    assert task.status == "pending"
    assert task.file_path == "/uploads/test.pdf"
    assert task.ai_summary is False
    assert task.get_cups_options() == {"copies": 2, "sides": "one-sided"}
    assert task.retry_count == 0
    assert task.node_id is None
    assert task.error_msg is None


@pytest.mark.asyncio
async def test_create_task_with_ai_summary(db_session):
    task = await TaskService.create_task(
        db=db_session,
        file_path="/uploads/doc.pdf",
        original_name="doc.pdf",
        cups_options={},
        ai_summary=True,
    )

    assert task.ai_summary is True
    assert task.summary_text is None


@pytest.mark.asyncio
async def test_create_task_is_persisted_in_db(db_session):
    task = await TaskService.create_task(
        db=db_session,
        file_path="/uploads/a.pdf",
        original_name="a.pdf",
        cups_options={"media": "A4"},
    )

    stmt = select(PrintTask).where(PrintTask.id == task.id)
    result = await db_session.execute(stmt)
    persisted = result.scalar_one()

    assert persisted.id == task.id
    assert persisted.status == "pending"


# ═══════════════════════════════════════════════════════════════════
# get_next_pending
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_next_pending_returns_none_when_empty(db_session):
    result = await TaskService.get_next_pending(db_session, node_id="pi-01")
    assert result is None


@pytest.mark.asyncio
async def test_get_next_pending_returns_fifo_order(db_session):
    t1 = await TaskService.create_task(db_session, "/f/1.pdf", "1.pdf", {})
    t2 = await TaskService.create_task(db_session, "/f/2.pdf", "2.pdf", {})
    t3 = await TaskService.create_task(db_session, "/f/3.pdf", "3.pdf", {})

    task = await TaskService.get_next_pending(db_session, node_id="pi-01")

    assert task is not None
    assert task.id == t1.id  # 最早创建的


@pytest.mark.asyncio
async def test_get_next_pending_marks_printing_and_binds_node(db_session):
    await TaskService.create_task(db_session, "/f/1.pdf", "1.pdf", {})

    task = await TaskService.get_next_pending(db_session, node_id="pi-01")

    assert task.status == "printing"
    assert task.node_id == "pi-01"


@pytest.mark.asyncio
async def test_get_next_pending_skips_non_pending_tasks(db_session):
    t1 = await TaskService.create_task(db_session, "/f/1.pdf", "1.pdf", {})
    await TaskService.get_next_pending(db_session, node_id="pi-01")  # t1 → printing

    t2 = await TaskService.create_task(db_session, "/f/2.pdf", "2.pdf", {})
    await TaskService.update_status(db_session, t2.id, "printing")

    t3 = await TaskService.create_task(db_session, "/f/3.pdf", "3.pdf", {})

    task = await TaskService.get_next_pending(db_session, node_id="pi-02")
    assert task is not None
    assert task.id == t3.id  # 跳过 t1(printing) 和 t2(printing), 拿到 t3(pending)


# ═══════════════════════════════════════════════════════════════════
# update_status
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_update_status_to_completed(db_session):
    task = await TaskService.create_task(db_session, "/f/1.pdf", "1.pdf", {})

    updated = await TaskService.update_status(
        db_session, task.id, "completed", node_id="pi-01"
    )

    assert updated.status == "completed"
    assert updated.node_id == "pi-01"
    assert updated.retry_count == 0


@pytest.mark.asyncio
async def test_update_status_to_failed_increments_retry(db_session):
    task = await TaskService.create_task(db_session, "/f/1.pdf", "1.pdf", {})

    await TaskService.update_status(db_session, task.id, "failed", error_msg="timeout")
    updated = await TaskService.update_status(db_session, task.id, "failed", error_msg="retry")

    assert updated.status == "failed"
    assert updated.retry_count == 2
    assert updated.error_msg == "retry"


@pytest.mark.asyncio
async def test_update_status_sets_summary_text(db_session):
    task = await TaskService.create_task(db_session, "/f/1.pdf", "1.pdf", {})

    updated = await TaskService.update_status(
        db_session, task.id, "pending", summary_text="## 摘要\n内容..."
    )

    assert updated.summary_text == "## 摘要\n内容..."
    assert updated.status == "pending"  # 状态不变


@pytest.mark.asyncio
async def test_update_status_not_found_returns_none(db_session):
    result = await TaskService.update_status(db_session, "nonexistent", "completed")
    assert result is None


# ═══════════════════════════════════════════════════════════════════
# get_by_id
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_by_id_found(db_session):
    task = await TaskService.create_task(db_session, "/f/1.pdf", "1.pdf", {})

    result = await TaskService.get_by_id(db_session, task.id)
    assert result is not None
    assert result.id == task.id


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session):
    result = await TaskService.get_by_id(db_session, "nonexistent")
    assert result is None
