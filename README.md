# 星火智造云打印 (Starfire Print Hub)

扫码即打的云打印系统。手机扫码上传文件，云端中转，树莓派边缘节点拉取任务并驱动打印机出纸，可选 AI 自动生成文档摘要页。

采用「**云端中转 + 边缘拉取**」架构：打印机不需要公网 IP，树莓派主动轮询云端拉取任务，绕开内网穿透与防火墙限制。

```
📱 手机端                      ☁️ 云端 (FastAPI)              🖨️ 树莓派 (CUPS)
  │                             │                              │
  ├─ POST /api/upload ────────►│  存文件 + 建任务(pending)      │
  │  (上传文件 + 打印参数)        │                              │
  │                             │◄── GET /api/jobs/next ───────┤  轮询拉取
  │                             │◄── GET /api/files/{id}/download  下载 PDF
  │                             │◄── POST /api/jobs/update ─────┤  上报状态
  ├─ GET /api/jobs/{id}/status►│                              │
  │  查询打印结果                 │                              │
```

## 项目结构

| 目录 | 角色 | 技术栈 |
|------|------|--------|
| `cloud/` | 云端中转服务：接收上传、管理任务队列、节点心跳、AI 摘要 | FastAPI · SQLAlchemy 2.0 (async) · SQLite · OpenAI |
| `frontend/` | 手机端网页：扫码进入、选文件、配参数、查状态 | Vue 3 · Vite · Tailwind CSS · vue-pdf-embed |
| `pi-client/` | 树莓派守护进程：轮询拉取、下载、调用 CUPS 打印、心跳保活 | Python · pycups · requests · tenacity |

## 核心功能

- **扫码上传**：每个打印机节点对应一个二维码，扫码直达上传页面
- **打印参数**：纸张尺寸、单双面、拼版 (N-up)、份数、彩色/黑白、页面范围
- **AI 摘要**：可选在 PDF 最前面自动拼接一页 LLM 生成的中文文档摘要（后台异步，不阻塞打印）
- **边缘拉取**：树莓派主动轮询，打印机无需公网暴露
- **状态闭环**：pending → printing → completed / failed 全程可查
- **健壮性**：网络断开指数退避重试、打印机离线自动检测恢复、心跳保活

## 快速开始

### 1. 云端服务 (cloud/)

```bash
cd cloud
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # 按需修改配置
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问：
- API 文档 (Swagger)：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 2. 前端 (frontend/)

```bash
cd frontend
npm install
npm run dev      # 开发服务器，默认 http://localhost:3000
```

开发模式下，Vite 会把 `/api` 请求代理到 `http://localhost:8000`（见 `vite.config.js`）。生产构建：

```bash
npm run build    # 产物输出到 dist/
```

### 3. 树莓派客户端 (pi-client/)

需运行在已配置 CUPS 的 Linux 环境（树莓派 OS）。

```bash
cd pi-client
pip install -r requirements.txt

cp .env.example .env        # 修改 CLOUD_BASE_URL / NODE_ID / PRINTER_NAME
python pi_worker.py
```

> `pycups` 依赖系统 CUPS 开发库，安装前需先执行 `sudo apt install libcups2-dev`。

首次接入需先向云端注册节点：

```bash
curl -X POST "http://<云端地址>:8000/api/nodes/register?name=3楼A区&mac_address=AA:BB:CC:DD:EE:FF&printer_name=Fuji_Xerox_SC2020"
```

## 配置说明

### 云端 (cloud/.env)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` / `PORT` | `0.0.0.0` / `8000` | 服务监听地址 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./starfire.db` | 异步数据库连接串 |
| `UPLOAD_DIR` | `./uploads` | 上传文件存储目录 |
| `MAX_FILE_SIZE_MB` | `20` | 单文件大小上限 |
| `AI_ENABLED` | `false` | 是否启用 AI 摘要 |
| `OPENAI_API_KEY` | — | LLM API Key（启用 AI 时必填） |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | 兼容 OpenAI 的接口地址 |
| `AI_MODEL` | `gpt-4o-mini` | 摘要使用的模型 |

### 树莓派 (pi-client/.env)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CLOUD_BASE_URL` | `http://192.168.1.100:8000` | 云端 API 地址 |
| `NODE_ID` | `pi-default-01` | 节点唯一标识 |
| `PRINTER_NAME` | `Fuji_Xerox_SC2020` | CUPS 队列中的打印机名 |
| `POLL_INTERVAL_SECONDS` | `5` | 轮询间隔 |
| `HEARTBEAT_INTERVAL_SECONDS` | `30` | 心跳间隔 |
| `DOWNLOAD_DIR` | `/tmp/starfire-jobs` | PDF 临时下载目录 |

## API 概览

| 方法 | 路径 | 面向 | 说明 |
|------|------|------|------|
| POST | `/api/upload` | 手机端 | 上传文件并创建打印任务 |
| GET | `/api/jobs/{job_id}/status` | 手机端 | 查询任务状态 |
| GET | `/api/jobs/next` | 树莓派 | 拉取下一个 pending 任务（FIFO，原子抢占） |
| POST | `/api/jobs/update` | 树莓派 | 上报 printing / completed / failed |
| GET | `/api/files/{job_id}/download` | 树莓派 | 下载任务对应文件 |
| POST | `/api/nodes/register` | 树莓派 | 注册 / 更新节点 |
| POST | `/api/nodes/{node_id}/heartbeat` | 树莓派 | 心跳上报 |
| GET | `/api/nodes/` | 管理 | 列出所有节点及在线状态 |

完整请求/响应示例见运行后的 `/docs`。

## 打印参数 (cups_options)

上传时以 JSON 字符串传递，树莓派端映射为标准 CUPS 选项：

```json
{
  "copies": 2,
  "sides": "two-sided-long-edge",
  "media": "A4",
  "number_up": 2,
  "page_ranges": "1-5",
  "color_mode": "monochrome"
}
```

支持的取值范围见 `pi-client/printer.py` 中的 `CUPS_OPTION_MAP`，非法值会自动回退到默认值。

## 安全说明

当前为内网/演示配置，生产部署前请注意：

- 云端 CORS 当前为 `allow_origins=["*"]`，应限定为实际前端域名
- 上传、节点注册、状态上报接口**均无鉴权**，公网部署需补充认证（如 Token / API Key）
- 文件下载接口仅凭 `job_id` 即可访问，建议加签名或访问控制
- `.env` 中的 `OPENAI_API_KEY` 等密钥请勿提交到版本库
