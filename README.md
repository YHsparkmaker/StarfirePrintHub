# 星火智造云打印 (Starfire Print Hub)

扫码即打的云打印系统。手机扫码上传文件 **或直接编辑 Markdown 文本**，云端中转渲染，树莓派边缘节点拉取任务并驱动打印机出纸。支持 **AI 文档摘要**、**打印效果预览**、**LaTeX 数学公式**。

采用「**云端中转 + 边缘拉取**」架构：打印机不需要公网 IP，树莓派主动轮询云端拉取任务，绕开内网穿透与防火墙限制。

```
📱 手机端                      ☁️ 云端 (FastAPI)              🖨️ 树莓派 (CUPS)
  │                             │                              │
  ├─ POST /api/upload ────────►│  存文件 + 建任务(pending)      │
  ├─ POST /api/text ──────────►│  MD+LaTeX→PDF + 建任务         │
  ├─ POST /api/preview ───────►│  应用打印参数生成预览 PDF       │
  │                             │◄── GET /api/jobs/next ───────┤  轮询拉取
  │                             │◄── GET /api/files/{id}/download  下载 PDF
  │                             │◄── POST /api/jobs/update ─────┤  上报状态
  ├─ GET /api/jobs/{id}/status►│                              │
  ├─ GET /api/jobs ───────────►│  历史打印列表                  │
  │                             │                              │
```

## 项目结构

| 目录 | 角色 | 技术栈 |
|------|------|--------|
| `cloud/` | 云端中转服务：接收上传、文本渲染、打印预览、任务队列、节点心跳、AI 摘要 | FastAPI · SQLAlchemy 2.0 (async) · SQLite · OpenAI · markdown · weasyprint · latex2mathml · pypdf |
| `frontend/` | 手机端网页：扫码进入、文件上传 / **Markdown 编辑**、打印参数、**效果预览**、历史记录 | Vue 3 · Vite · Tailwind CSS · vue-pdf-embed · marked · KaTeX |
| `pi-client/` | 树莓派守护进程：轮询拉取、下载、调用 CUPS 打印、心跳保活 | Python · pycups · requests · tenacity |

## 核心功能

- **扫码绑定节点**：每个打印机节点对应一个二维码，扫码 URL 携带 `?node=pi-xx` 参数，上传时自动绑定目标任务
- **文件上传打印**：支持 PDF、Word、TXT、PNG/JPG，拖拽上传，显示预览、页数、文件大小
- **Markdown 文本编辑**：内置在线编辑器，支持 Markdown 语法 + **LaTeX 数学公式**（`$...$` / `$$...$$`），实时预览，工具栏快捷插入
- **打印参数配置**：纸张尺寸、单双面、拼版 (1/2/4/6/9/16-up)、份数
- **打印效果预览**：提交前可预览当前参数下的真实打印效果（n-up 拼版、双面标注、份数重复）
- **AI 摘要**：可选在 PDF 最前面自动拼接一页 LLM 生成的中文文档摘要（后台异步，不阻塞打印）
- **任务历史**：可按节点筛选查看历史打印记录，支持分页加载
- **边缘拉取**：树莓派主动轮询，打印机无需公网暴露
- **状态闭环**：pending → printing → completed / failed 全程可查
- **上传进度条**：大文件上传实时显示百分比
- **健壮性**：网络断开指数退避重试、打印机离线自动检测恢复、心跳保活
- **移动端优化**：触摸反馈、tap 高亮消除、双击缩放禁用

## 测试

三个模块均已覆盖测试，`cloud/` 和 `pi-client/` 各 **29 个测试用例**，覆盖核心业务逻辑和接口集成。

```bash
cd cloud      && python -m pytest tests/ -v   # 29 passed
cd pi-client  && python -m pytest tests/ -v   # 29 passed
```

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
| POST | `/api/text` | 手机端 | 提交 Markdown 文本，云端渲染为 PDF 并创建任务 |
| POST | `/api/preview` | 手机端 | 预览打印效果（n-up 拼版等参数实时渲染 PDF） |
| GET | `/api/jobs` | 手机端 | 查询历史任务列表（分页，可按节点筛选） |
| GET | `/api/jobs/{job_id}/status` | 手机端 | 查询单个任务状态 |
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

## 文本打印（Markdown + LaTeX）

前端内置 Markdown 编辑器和实时预览，可直接编写带格式的文档并打印。支持：

- **Markdown 全套语法**：标题、粗体斜体、代码块（语法高亮）、表格、引用、列表、分隔线、链接
- **LaTeX 数学公式**：行内 `$E=mc^2$` 和块级 `$$\int_0^\infty e^{-x^2}dx$$`
- **工具栏快捷插入**：粗体/斜体/标题/代码/列表/公式/表格/链接 一键插入
- **实时预览**：侧边预览面板，Markdown 通过 marked 渲染，LaTeX 通过 KaTeX 渲染
- **渲染管线**：LaTeX → latex2mathml → MathML → markdown → HTML → weasyprint → PDF

## 打印效果预览

提交打印前，点击「预览打印效果」按钮可生成当前打印参数下的真实效果 PDF：

| 功能 | 说明 |
|------|------|
| n-up 拼版 | 1/2/4/6/9/16-up 网格布局，页面自动居中缩放 |
| 份数重复 | 按 copies 参数重复全部页面 |
| 双面标注 | 双面模式在每页右上角标注 FRONT / BACK |

实现在 `cloud/services/print_preview_service.py`，基于 pypdf 的 merge_transformed_page 完成页面缩放和排布。

## 安全说明

当前为内网/演示配置，生产部署前请注意：

- 云端 CORS 当前为 `allow_origins=["*"]`，应限定为实际前端域名
- 上传、节点注册、状态上报接口**均无鉴权**，公网部署需补充认证（如 Token / API Key）
- 文件下载接口仅凭 `job_id` 即可访问，建议加签名或访问控制
- `.env` 中的 `OPENAI_API_KEY` 等密钥请勿提交到版本库
