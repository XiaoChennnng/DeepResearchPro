# DeepResearch Pro

一个具备多智能体（Multi-Agent）协作能力的研究平台：前端使用 React + Vite（可打包为 Tauri 桌面端），后端使用 FastAPI，支持研究任务创建、执行过程实时推送、报告生成与报告问答。

## 特性

- 研究任务：创建/查询任务、查看执行进度与阶段
- 实时推送：通过 WebSocket 推送 Agent 状态、进度与日志
- 报告查看：渲染研究报告，支持导出
- 报告问答：基于已生成报告追问（支持历史上下文，自动截断避免上下文爆炸）
- LLM 配置：支持多家 OpenAI 兼容与国内模型提供商

## 技术栈

- 前端：React + TypeScript + Vite + TailwindCSS + Radix UI
- 桌面端（可选）：Tauri 2 + Rust
- 后端：FastAPI + SQLAlchemy（Async）+ SQLite

## 目录结构

```text
.
├─ src/                 # 前端（React + Vite）
├─ backend/             # 后端（FastAPI）
│  ├─ app/              # API、服务、Agent、DB
│  ├─ requirements.txt
│  └─ run.py            # 后端启动脚本
├─ src-tauri/           # Tauri 桌面端（可选）
├─ deploy-linux.sh      # Linux 一键部署脚本（Nginx + systemd）
├─ vite.config.ts       # 开发代理：/api -> 127.0.0.1:8000
└─ vercel.json          # SPA 路由重写（可选）
```

## 环境要求

- Node.js：建议 18+（推荐 20+）
- Python：建议 3.10+（本项目可在 3.13 运行）
- （可选）Rust toolchain：仅在需要 `tauri build` 时需要

## 本地开发

### 1) 安装依赖

前端：

```bash
npm install
```

后端：

```bash
cd backend
python -m venv .venv
./.venv/Scripts/python -m pip install -U pip
./.venv/Scripts/pip install -r requirements.txt
```

macOS / Linux（后端 venv 路径不同）：

```bash
cd backend
python3 -m venv .venv
./.venv/bin/python -m pip install -U pip
./.venv/bin/pip install -r requirements.txt
```

### 2) 配置环境变量

后端读取 `backend/.env`（项目内默认通过 `pydantic-settings` 读取）。你需要至少配置 LLM 相关变量：

```dotenv
LLM_PROVIDER=deepseek
LLM_API_KEY=YOUR_KEY
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

DEBUG=false
HOST=127.0.0.1
PORT=8000
```

前端如果启用 Supabase 登录，需要配置 Vite 环境变量（例如根目录 `.env.local`）：

```dotenv
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

### 3) 启动服务

启动后端（默认 `127.0.0.1:8000`）：

```bash
cd backend
python run.py
```

启动前端（默认 `http://localhost:5173`）：

```bash
npm run dev
```

前端已在 `vite.config.ts` 中配置代理：`/api` 会转发到 `http://127.0.0.1:8000`。

## 局域网访问（开发/内网）

默认后端只绑定 `127.0.0.1`，更安全。如果你确实需要局域网设备访问：

1) 修改 `backend/.env`：将 `HOST` 改为 `0.0.0.0`
2) 将 `CORS_ORIGINS` 加入你的前端来源（如 `http://192.168.1.10:5173`）
3) 前端启动时用 `--host 0.0.0.0`，让 Vite 对外监听：

```bash
npm run dev -- --host 0.0.0.0
```

## 构建

构建前端静态资源：

```bash
npm run build
```

构建/打包 Tauri（可选）：

```bash
npm run tauri build
```

## Linux 服务器部署（Nginx + systemd）

仓库提供一键部署脚本 `deploy-linux.sh`（Ubuntu/Debian）：

```bash
sudo bash deploy-linux.sh --repo <你的git仓库地址> --branch main --domain your.domain.com
```

脚本会：

- 安装依赖（node、python、nginx 等）
- 拉取代码到 `/opt/deepresearchpro`
- 构建前端到 `/opt/deepresearchpro/dist`
- 创建后端 systemd 服务 `deepresearchpro-backend`（监听 `127.0.0.1:8000`）
- 配置 Nginx：静态站点 + 反代 `/api/` 到后端（含 WebSocket）

部署后配置文件位置：

- 后端：`/etc/deepresearchpro/backend.env`
- 前端构建：`/etc/deepresearchpro/frontend.env`

## 常见问题

### 1) 8000 端口被占用

- 本地开发：可以把后端改到 8001，并同步修改 `vite.config.ts` 的代理目标
- 生产环境：推荐保持后端绑定 `127.0.0.1:8000`，通过 Nginx 暴露对外端口

### 2) 登录页提示 Supabase 未配置

需要设置 `VITE_SUPABASE_URL` 与 `VITE_SUPABASE_ANON_KEY`（建议放在根目录 `.env.local`）。

### 3) WebSocket 无法连接

- 开发模式下前端会连接 `ws://127.0.0.1:8000/api/ws/research/{taskId}`
- 生产模式下前端会连接当前域名 `wss://<host>/api/ws/research/{taskId}`
- 如果你改了后端端口，请同时调整前端 WebSocket 与代理配置

## 许可

MIT License
