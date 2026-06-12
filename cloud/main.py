"""
═══════════════════════════════════════════════════════════════════════
星火智造云打印 (Starfire Print Hub) — 云端服务入口
═══════════════════════════════════════════════════════════════════════

启动方式:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload

访问文档:
  Swagger UI:  http://localhost:8000/docs
  ReDoc:       http://localhost:8000/redoc

架构说明:
  本服务是「云端中转 + 边缘拉取」架构中的云端部分:
  - 手机端:  扫码 → 上传文件 → 查询状态
  - 树莓派:  轮询拉取任务 → 下载文件 → 打印 → 上报状态
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routers import tasks_router, nodes_router

# ── 日志配置 ─────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── 应用生命周期 ──────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理:
    - 启动时: 初始化数据库表
    - 关闭时: 清理资源 (TODO)
    """
    logger.info("🚀 星火智造云打印服务启动中...")
    await init_db()
    logger.info("✅ 数据库初始化完成")
    yield
    logger.info("👋 服务关闭")


# ── 创建 FastAPI 应用 ─────────────────────────
app = FastAPI(
    title="星火智造云打印 API",
    description="""
## Starfire Print Hub — Cloud API

### 接口分组

| 分组 | 面向对象 | 说明 |
|------|---------|------|
| **打印任务** | 手机端 + 树莓派 | 上传、拉取、状态更新 |
| **边缘节点** | 树莓派 | 注册、心跳、列表 |

### 数据流

```
📱 手机端                      ☁️ 云端                        🖨️ 树莓派
  │                             │                              │
  ├─ POST /api/upload ────────►│                              │
  │  (上传 PDF + 打印参数)       │  存储文件 + 创建任务(pending)   │
  │                             │                              │
  │                             │◄── GET /api/jobs/next ──────┤
  │                             │   返回最早的 pending 任务      │
  │                             │                              │
  │                             │◄── GET /api/files/{id}/download
  │                             │   返回 PDF 文件               │
  │                             │                              │
  │                             │◄── POST /api/jobs/update ────┤
  │                             │   上报 completed/failed       │
  │                             │                              │
  ├─ GET /api/jobs/{id}/status─►│                              │
  │  查询任务结果                 │                              │
```
    """,
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS 配置 (允许手机网页跨域访问) ──────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ──────────────────────────────────
app.include_router(tasks_router)
app.include_router(nodes_router)


# ── 健康检查 ──────────────────────────────────
@app.get("/health", tags=["系统"])
async def health_check():
    """服务健康检查"""
    return {
        "status": "ok",
        "service": "starfire-print-hub",
        "version": "0.1.0",
    }


# ═══════════════════════════════════════════════════════════════════
# 直接运行入口
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
