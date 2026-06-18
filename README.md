# 星火智造云打印 (Starfire Print Hub)

扫码即打的云打印系统。手机扫码上传文件 **或直接编辑 Markdown 文本**，云端中转渲染，树莓派边缘节点拉取任务并驱动打印机出纸。支持 **AI 文档摘要**、**打印效果预览**、**LaTeX 数学公式**、**远程 SSH 隧道**、**OTA 在线更新**、**TTS 语音播报**。

采用「**云端中转 + 边缘拉取**」架构：打印机不需要公网 IP，树莓派主动轮询云端拉取任务，绕开内网穿透与防火墙限制。

```
手机端                        云端 (FastAPI)              树莓派 (CUPS)
  │                             │                              │
  ├─ POST /api/upload ────────►│  存文件 + 建任务(pending)      │
  ├─ POST /api/text ──────────►│  MD+LaTeX→PDF + 建任务         │
  ├─ POST /api/preview ───────►│  应用打印参数生成预览 PDF       │
  │                             │◄── GET /api/jobs/next ───────┤  轮询拉取
  │                             │◄── GET /api/files/{id}/download─┤ 下载 PDF
  │                             │◄── POST /api/jobs/update ─────┤  上报状态
  │                             │◄── GET /api/nodes/{id}/cmd ──┤  远程命令
  ├─ GET /api/jobs/{id}/status►│                              │
  ├─ GET /api/jobs ───────────►│  历史打印列表                  │
  │                             │                              │
```

---

## 树莓派 — 一键初始化

> **这是给树莓派运维的主要入口。从零开始，一行克隆，引导式安装。**

### 1. 克隆项目

```bash
git clone https://gitee.com/ZhangliZennon/StarfirePrintHub.git
cd StarfirePrintHub/pi-client
```

### 2. 运行配置向导

```bash
bash setup.sh
```

向导会**自动完成以下 6 步**：

| 步骤 | 内容 | 自动化 |
|------|------|--------|
| 1. 系统依赖 | 检查 Python3 / pip / CUPS / libcups2-dev / lpadmin 组 | 缺啥自动装 |
| 2. Python 包 | 安装 pycups / requests / tenacity / python-dotenv | 自动 |
| 3. CUPS 打印机 | `lpinfo -v` 扫描 USB/IPP → 自动 `lpadmin` 添加 → 设为默认 | 引导选择 |
| 4. .env 配置 | 交互输入云端地址 / 节点ID / 名称 / 打印机名 → 自动生成 | 交互 |
| 5. 云端注册 | `POST /api/nodes/register` 注册节点 | 自动 |
| 6. 启动验证 | CUPS 连接测试 / 打印机就绪检查 / 云端可达性 | 自动 |

```bash
# 快速模式（少交互，自动检测）
bash setup.sh --quick
```

### 3. 安装开机自启动

```bash
sudo bash install-services.sh pi
```

安装后树莓派开机自动启动 `pi_worker.py`，进程崩溃 5 秒后自动拉起。

```bash
# 日常管理
sudo systemctl status starfire-pi      # 查看状态
sudo systemctl restart starfire-pi     # 重启守护
journalctl -u starfire-pi -f           # 实时日志
sudo bash install-services.sh remove   # 卸载
```

### 4. 可选: 安装 TTS 语音播报

```bash
# 离线方案 (秒级响应)
sudo apt install -y espeak-ng

# 在线高质量方案
pip3 install edge-tts --break-system-packages
```

打印完成后树莓派通过扬声器中文播报"打印完成"或"打印失败，请检查打印机"。

### 5. 可选: 启用 DOC 文件转换

```bash
sudo apt install -y libreoffice-impress
```

旧版 `.doc` (Word 97-2003) 文件自动通过 LibreOffice 转为 PDF。

---

## 项目结构

| 目录 | 角色 | 技术栈 |
|------|------|--------|
| `cloud/` | 云端中转服务 | FastAPI · SQLAlchemy 2.0 (async) · SQLite · OpenAI · weasyprint · pypdf |
| `frontend/` | 手机端网页 | Vue 3 · Vite · Tailwind CSS · vue-pdf-embed · marked · KaTeX |
| `pi-client/` | 树莓派守护进程 | Python · pycups · requests · tenacity · pygame · edge-tts |

---

## 核心功能

### 打印功能

| 功能 | 说明 |
|------|------|
| 文件上传 | PDF / DOCX / DOC / TXT / PNG / JPG，拖拽上传 |
| Markdown 编辑 | 在线编辑器 + LaTeX 数学公式 + 实时预览 |
| 打印参数 | 纸张尺寸 / 纸张类型 / 纸盒来源 / 单双面 / 拼版 (1-16 up) / 方向 / 份数 |
| 效果预览 | 应用打印参数实时渲染预览 PDF，可下载 |
| AI 摘要 | 可选自动生成文档摘要页 |
| 任务历史 | 按节点筛选查看，分页加载 |
| 状态闭环 | pending → printing → completed / failed，失败显示原因 |

### 树莓派管理

| 功能 | 说明 |
|------|------|
| 一键配置 | `setup.sh` 引导式 6 步初始化 |
| 开机自启 | `systemd` 服务，崩溃自动拉起 |
| OTA 更新 | 云端下发 `update` 命令 → git pull + 自重启 |
| 远程 SSH | 反向隧道穿透内网 (`ssh -J serveo.net pi@节点ID`) |
| 远程命令 | ping / restart / exec 自定义 shell |
| TTS 播报 | 打印完成/失败语音播报 (espeak-ng / edge-tts) |
| 心跳保活 | 30s 间隔上报在线状态 |

### 纸张类型

| 选项 | CUPS 值 | 说明 |
|------|---------|------|
| 普通纸 | `stationery` | 默认 |
| 再生纸 | `stationery-recycled` | 环保纸 |
| 薄纸 | `stationery-lightweight` | 轻量纸 |
| 厚纸 | `stationery-heavyweight` | 重型纸/卡纸 |
| 透明胶片 | `transparency` | 投影胶片 |
| 标签纸 | `labels` | 标签贴纸 |

---

## 快速开始 (开发)

### 云端服务

```bash
cd cloud
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 服务器上还需安装 weasyprint 系统依赖
sudo apt install -y libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
  libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info fonts-wqy-microhei

cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
npm run build        # 生产构建 → dist/
```

### 树莓派守护 (手动)

```bash
cd pi-client
pip install -r requirements.txt
sudo apt install libcups2-dev   # pycups 编译依赖

cp .env.example .env    # 修改 CLOUD_BASE_URL / NODE_ID / PRINTER_NAME
python pi_worker.py
```

---

## 测试

| 模块 | 用例数 | 命令 |
|------|--------|------|
| cloud | 29 | `cd cloud && python -m pytest tests/ -v` |
| pi-client | 29 | `cd pi-client && python -m pytest tests/ -v` |

---

## 配置说明

### 树莓派 (pi-client/.env)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CLOUD_BASE_URL` | `http://192.168.1.100:8000` | 云端 API 地址 |
| `NODE_ID` | `pi-default-01` | 节点唯一标识 |
| `NODE_NAME` | `打印机-raspberrypi` | 节点显示名称 |
| `PRINTER_NAME` | `Fuji_Xerox_SC2020` | CUPS 队列中的打印机名 |
| `POLL_INTERVAL_SECONDS` | `5` | 任务轮询间隔 |
| `POLL_LONG_INTERVAL_SECONDS` | `30` | 静默期轮询间隔 |
| `HEARTBEAT_INTERVAL_SECONDS` | `30` | 心跳间隔 |
| `DOWNLOAD_DIR` | `/tmp/starfire-jobs` | PDF 临时下载目录 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `ENABLE_SOUND` | `true` | 打印完成语音播报 |
| `SOUND_VOLUME` | `0.7` | 播报音量 (0.0-1.0) |
| `TTS_SUCCESS` | `打印完成` | 成功播报文本 |
| `TTS_FAILURE` | `打印失败，请检查打印机` | 失败播报文本 |
| `TUNNEL_HOST` | `serveo.net` | SSH 隧道跳板 |
| `TUNNEL_PORT` | `0` | 跳板端口 (0=自动) |
| `TUNNEL_USER` | — | 跳板 SSH 用户名 |
| `TUNNEL_SSH_KEY` | `~/.ssh/id_rsa` | SSH 私钥路径 |

### 云端 (cloud/.env)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` / `PORT` | `0.0.0.0` / `8000` | 服务监听地址 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./starfire.db` | 数据库连接串 |
| `UPLOAD_DIR` | `./uploads` | 上传文件存储目录 |
| `MAX_FILE_SIZE_MB` | `20` | 单文件大小上限 |
| `AI_ENABLED` | `false` | 是否启用 AI 摘要 |
| `OPENAI_API_KEY` | — | LLM API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | 兼容 OpenAI 接口地址 |
| `AI_MODEL` | `gpt-4o-mini` | 摘要模型 |

---

## API 概览

| 方法 | 路径 | 面向 | 说明 |
|------|------|------|------|
| POST | `/api/upload` | 手机端 | 上传文件并创建打印任务 |
| POST | `/api/text` | 手机端 | 提交 Markdown 文本，云端渲染为 PDF |
| POST | `/api/preview` | 手机端 | 预览打印效果 |
| GET | `/api/jobs` | 手机端 | 历史任务列表（分页） |
| GET | `/api/jobs/{id}/status` | 手机端 | 查询任务状态 |
| GET | `/api/jobs/next` | 树莓派 | 拉取下一个 pending 任务 |
| POST | `/api/jobs/update` | 树莓派 | 上报打印状态 |
| GET | `/api/files/{id}/download` | 树莓派 | 下载任务文件 |
| POST | `/api/nodes/register` | 树莓派 | 注册节点 |
| POST | `/api/nodes/{id}/heartbeat` | 树莓派 | 心跳上报 |
| GET | `/api/nodes/` | 管理 | 列出所有节点 |
| POST | `/api/nodes/{id}/command` | 管理 | 下发远程命令 (ping/restart/update/exec/tunnel) |
| GET | `/api/nodes/{id}/command` | 树莓派 | 轮询待执行命令 |
| POST | `/api/nodes/{id}/command/result` | 树莓派 | 上报命令执行结果 |

---

## 打印参数 (cups_options)

```json
{
  "copies": 2,
  "sides": "two-sided-long-edge",
  "media": "A4",
  "media_type": "stationery",
  "media_source": "auto",
  "number_up": 2,
  "page_ranges": "1-5",
  "color_mode": "monochrome",
  "orientation": "portrait"
}
```

支持的取值范围见 `pi-client/printer.py` 的 `CUPS_OPTION_MAP`。

---

## 远程管理

通过云端 API 对树莓派下发命令：

```bash
# 查看树莓派状态 (IP/温度/磁盘/git版本)
curl "http://<云端>:8000/api/nodes/pi-raspberrypi/command?cmd=ping"

# OTA 更新 (git pull + 自动重启)
curl -X POST "http://<云端>:8000/api/nodes/pi-raspberrypi/command?cmd=update"

# 打开 SSH 隧道 (不在同一内网也能 SSH)
curl -X POST "http://<云端>:8000/api/nodes/pi-raspberrypi/command?cmd=tunnel"
# 返回连接方式: ssh -J serveo.net pi@pi-raspberrypi

# 执行自定义命令
curl -X POST "http://<云端>:8000/api/nodes/pi-raspberrypi/command?cmd=exec&exec_cmd=sudo%20apt%20update"

# 关闭隧道
curl -X POST "http://<云端>:8000/api/nodes/pi-raspberrypi/command?cmd=tunnel-close"
```

---

## 安全说明

当前为内网/演示配置，生产部署前请注意：

- 云端 CORS 当前为 `allow_origins=["*"]`，应限定为实际前端域名
- 上传、节点注册、状态上报接口均无鉴权，公网部署需补充 Token / API Key 认证
- 文件下载接口仅凭 `job_id` 即可访问，建议加签名或访问控制
- `.env` 中的 `OPENAI_API_KEY` 等密钥请勿提交到版本库
- `exec` 远程命令请谨慎使用，可执行任意 shell 指令
