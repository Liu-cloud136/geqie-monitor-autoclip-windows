# 鸽切监控 + AI 视频切片系统

一个集成了 B站直播间弹幕监控与 AI 视频切片处理的完整系统。通过识别弹幕中的关键词，自动触发视频切片工作流。

## 功能特性

### 📺 弹幕监控系统 (geqie-monitor)

- **实时弹幕监控**：基于 bilibili-api-python 实时获取直播间弹幕
- **关键词过滤**：支持自定义关键词（默认"鸽切"）自动记录
- **多房间监控**：可同时监控多个直播间
- **数据统计**：今日数据、历史数据、趋势图表展示
- **WebSocket 实时推送**：无需轮询，实时获取最新数据
- **在线聊天室**：实时消息通信，支持随机用户名、敏感词过滤、管理员禁言
- **留言板功能**：历史消息记录，敏感词过滤
- **邮件通知**：开播/关播/监控启动时自动发送邮件提醒
- **公告系统**：可配置的站点公告
- **音乐播放器**：支持预加载、队列播放的管理端音乐控制
- **数据导出**：支持 Excel、PDF 格式导出

### 🎬 AI 视频切片系统 (autoclip-windows)

- **智能视频分析**：自动识别视频内容和结构
- **字幕提取**：使用 bcut-asr 进行高质量语音识别
- **AI 话题提取**：使用大语言模型（LLM）提取视频中的精彩话题
- **智能评分系统**：多维度评估话题质量（内容质量、娱乐性、信息价值、观众吸引力）
- **自动切片生成**：根据评分筛选最佳片段
- **视频切片**：使用 FFmpeg 提取视频片段，支持硬件加速
- **缩略图生成**：自动为切片生成预览缩略图
- **实时进度反馈**：通过 WebSocket 实时推送处理进度
- **多 LLM 提供商支持**：通义千问、OpenAI、Gemini、SiliconFlow、Claude、自定义 OpenAI 兼容 API

### 🔗 整合功能

- **关键词触发切片**：当弹幕中出现配置的关键词时，自动记录时间点，后续可触发视频切片
- **统一配置管理**：两个系统可共享配置
- **数据互通**：弹幕监控数据可传递给切片系统

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Flask 3.1 (监控系统) + FastAPI 0.115 (切片系统) |
| 前端框架 | Bootstrap 5 (监控) + React 18 + TypeScript (切片) |
| 数据库 | SQLite (连接池) |
| 任务队列 | Celery + Redis |
| 实时通信 | Flask-SocketIO + FastAPI WebSocket |
| 视频处理 | FFmpeg + ffmpeg-python |
| 语音识别 | bcut-asr (必剪 API) |
| AI 模型 | 支持多种 LLM 提供商 |

## 项目结构

```
geqie-monitor-autoclip-windows/
├── monitor/                    # 弹幕监控系统
│   ├── static/                 # 静态资源
│   │   ├── css/               # CSS 样式
│   │   ├── js/                # JavaScript 模块
│   │   └── vendor/            # 第三方库
│   ├── templates/             # HTML 模板
│   ├── jk.py                  # 主程序入口
│   ├── config_manager.py      # 配置管理
│   ├── data_manager.py        # 数据存储与查询
│   ├── cache_manager.py       # 缓存管理
│   ├── db_pool.py             # 数据库连接池
│   ├── http_client.py         # HTTP 客户端
│   ├── live_chatroom.py       # 在线聊天室
│   ├── danmaku_analyzer.py    # 弹幕分析
│   ├── export_manager.py      # 数据导出
│   └── requirements.txt       # Python 依赖
│
├── backend/                    # AI 视频切片后端
│   ├── api/v1/                # API 路由
│   │   ├── clips.py           # 切片管理
│   │   ├── danmaku.py         # 弹幕接口
│   │   ├── projects.py        # 项目管理
│   │   ├── processing.py      # 处理接口
│   │   ├── websocket.py       # WebSocket
│   │   └── ...
│   ├── core/                  # 核心模块
│   │   ├── config.py          # 配置
│   │   ├── database.py        # 数据库
│   │   ├── llm_manager.py     # LLM 管理
│   │   ├── websocket_manager.py
│   │   └── ...
│   ├── models/                # 数据模型
│   ├── pipeline/              # 处理流水线
│   │   ├── step1_outline.py   # 字幕提取
│   │   ├── step2_timeline.py  # 话题提取
│   │   ├── step3_scoring.py   # 智能评分
│   │   ├── step4_title.py     # 标题生成
│   │   └── step5_video.py     # 视频切片
│   ├── services/              # 业务服务
│   ├── tasks/                 # Celery 任务
│   ├── utils/                 # 工具函数
│   ├── bcut-asr/              # 语音识别组件
│   ├── prompt/                # LLM 提示词模板
│   ├── main.py                # FastAPI 入口
│   └── requirements.txt       # Python 依赖
│
├── frontend/                   # 切片系统前端
│   ├── src/
│   │   ├── components/        # React 组件
│   │   ├── pages/             # 页面组件
│   │   ├── services/          # API 服务
│   │   ├── stores/            # 状态管理 (Zustand)
│   │   ├── hooks/             # 自定义 Hooks
│   │   └── utils/             # 工具函数
│   ├── package.json
│   └── vite.config.ts
│
├── venv/                       # 虚拟环境（运行 install.bat 后生成）
├── logs/                       # 日志目录（运行时生成）
├── .env.example               # 环境变量示例
├── .gitignore
├── requirements.txt           # 统一 Python 依赖
├── install.bat                # Windows 安装脚本
├── install.sh                 # Linux/Mac 安装脚本
├── start_all.bat              # 一键启动所有服务
├── start_monitor.bat          # 启动弹幕监控服务
├── start_backend.bat          # 启动后端 API
├── start_celery.bat           # 启动 Celery Worker
├── init.bat                   # 旧初始化脚本（保留兼容）
├── start_celery_enhanced.bat  # 旧 Celery 脚本（保留兼容）
└── README.md                  # 本文档
```

## 快速开始

### 环境要求

| 软件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.9+ | 后端运行环境 |
| Node.js | 18.x+ | 前端运行环境 |
| Redis | 5.0+ | Celery 任务队列 |
| FFmpeg | 4.0+ | 视频处理（需添加到系统 PATH） |

### 安装步骤

#### 1. 克隆仓库

```bash
git clone https://github.com/Liu-cloud136/geqie-monitor-autoclip-windows.git
cd geqie-monitor-autoclip-windows
```

#### 2. 安装依赖（推荐）

**Windows 用户：**

直接双击运行 `install.bat`，或在命令行中执行：

```bash
install.bat
```

脚本将自动完成以下操作：
1. 检查 Python 和 Node.js 环境
2. 创建统一的虚拟环境 `venv/`
3. 升级 pip（使用清华镜像加速）
4. 安装所有 Python 依赖（使用清华镜像加速）
5. 安装 bcut-asr 语音识别组件
6. 初始化切片系统数据库
7. 安装前端依赖（如已安装 Node.js）

**Linux/Mac 用户：**

```bash
chmod +x install.sh
./install.sh
```

#### 3. 手动安装（可选）

如果自动安装脚本失败，可以手动执行以下步骤：

**创建虚拟环境：**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

**安装 Python 依赖：**

```bash
# 使用清华镜像加速（推荐）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或使用官方源
pip install -r requirements.txt
```

**安装 bcut-asr：**

```bash
cd backend/bcut-asr
pip install -e .
cd ../..
```

**初始化数据库：**

```bash
cd backend
python init_db.py
cd ..
```

**安装前端依赖：**

```bash
cd frontend
npm install
cd ..
```

#### 4. 配置环境变量

**切片系统配置 (.env)：**

复制 `.env.example` 为 `.env`，并填写以下配置：

```env
# ========================================
# 必配项
# ========================================

# LLM API 配置（必须）
# 支持的提供商: dashscope, openai, gemini, siliconflow, claude, custom
LLM_PROVIDER=dashscope

# 通义千问（推荐，国内访问快）
API_DASHSCOPE_API_KEY=sk-xxx  # 从 https://dashscope.console.aliyun.com/ 获取
API_MODEL_NAME=qwen-plus

# OpenAI（如需使用）
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-xxx
# OPENAI_BASE_URL=https://api.openai.com/v1  # 如需代理可修改
# API_MODEL_NAME=gpt-4

# B站 Cookie（必须，用于语音识别）
# 获取方式：登录 B站 → F12 → Network → 任意请求 → Headers → Cookie
BILIBILI_COOKIE=your_bilibili_cookie_here

# ========================================
# 可选配置
# ========================================

# 数据库配置
DATABASE_URL=sqlite:///./data/autoclip.db

# Redis 配置
REDIS_URL=redis://localhost:6379/0

# 视频处理优化（可选）
# 流复制（最快，质量无损）
VIDEO_USE_STREAM_COPY=true
# 硬件加速（需要 NVIDIA GPU）
VIDEO_USE_HARDWARE_ACCEL=false
# 视频质量（18-28，越小质量越高）
VIDEO_CRF=23

# 话题提取参数（可选）
# 话题时长控制（分钟）
MIN_TOPIC_DURATION_MINUTES=2
MAX_TOPIC_DURATION_MINUTES=12
TARGET_TOPIC_DURATION_MINUTES=5
# 话题数量控制
MIN_TOPICS_PER_CHUNK=3
MAX_TOPICS_PER_CHUNK=8
```

**弹幕监控系统配置 (config.yaml)：**

复制 `monitor/config.yaml.example` 为 `monitor/config.yaml`：

```yaml
# ========================================
# 基础配置
# ========================================
app:
  host: "0.0.0.0"        # 监听地址（0.0.0.0 允许外部访问）
  port: 5000              # 服务端口
  admin_password: "你的密码"  # 管理员密码（用于管理端操作）

# ========================================
# B站直播间配置
# ========================================
bilibili:
  room_id: 22391541       # 你的直播间 ID（从直播间地址获取）

# ========================================
# 监控配置
# ========================================
monitor:
  keyword: "鸽切"          # 监控关键词（默认"鸽切"）
  save_all_danmaku: false  # 是否保存所有弹幕（false 只保存含有关键词的弹幕）
  refresh_interval: 300    # 状态刷新间隔（秒）
  max_retry: 5             # 最大重试次数
  retry_delay: 10          # 重试延迟（秒）
  log_level: "INFO"        # 日志级别

# ========================================
# 多房间监控（可选）
# ========================================
multi_room:
  enable: false             # 是否启用多房间监控
  rooms:
    - room_id: 22391541
      nickname: "主直播间"
      enabled: true
    - room_id: 其他直播间ID
      nickname: "副直播间"
      enabled: true

# ========================================
# 邮件通知（可选）
# ========================================
email:
  enable: false             # 是否启用邮件通知
  smtp_server: "smtp.qq.com"
  smtp_port: 587
  sender: "your_email@qq.com"
  password: "your_smtp_password"  # QQ邮箱需要授权码，不是密码
  receiver: "your_email@qq.com"
  notify_on_start: true     # 监控启动时通知
  notify_on_live_start: true  # 开播时通知
  notify_on_live_end: true   # 关播时通知
  notify_interval: 3600      # 通知间隔（秒）

# ========================================
# B站登录凭证（可选，用于成员专属弹幕）
# ========================================
credential:
  enable: false             # 是否启用
  sessdata: "your_sessdata"  # 从浏览器 Cookie 中获取
  bili_jct: "your_bili_jct"
  buvid3: "your_buvid3"

# ========================================
# 数据库配置（一般无需修改）
# ========================================
database:
  type: "sqlite"
  path: "geqie_data.db"
  pool_size: 5
  max_overflow: 10
  pool_timeout: 30

# ========================================
# 缓存配置（一般无需修改）
# ========================================
cache:
  default_ttl: 300
  max_size: 1000
  cleanup_interval: 300

# ========================================
# 在线聊天室（可选）
# ========================================
live_chatroom:
  enabled: true             # 是否启用
  message_ttl: 3600         # 消息保留时间（秒）
  max_users: 100            # 最大用户数
  banned_words:             # 敏感词列表
    - "敏感词1"
    - "敏感词2"

# ========================================
# 留言板（可选）
# ========================================
message_board:
  enabled: true             # 是否启用
  max_messages: 1000        # 最大消息数
  auto_approve: true        # 是否自动审核通过
  admin_approval: false     # 是否需要管理员审核
  banned_words:             # 敏感词列表
    - "敏感词1"
    - "敏感词2"

# ========================================
# 公告系统（可选）
# ========================================
announcement:
  enabled: true             # 是否启用
  default_text: "欢迎使用鸽切监控系统！"  # 默认公告

# ========================================
# 音乐播放器（可选）
# ========================================
music:
  enabled: true             # 是否启用
  playlist:                 # 预设播放列表
    - url: "音乐链接1"
      name: "歌曲名1"
    - url: "音乐链接2"
      name: "歌曲名2"
  volume: 0.5               # 默认音量 (0-1)
  auto_play: false          # 是否自动播放

# ========================================
# 开发模式（生产环境设为 false）
# ========================================
dev:
  debug: false              # 是否启用调试模式
  mock_mode: false          # 是否启用模拟模式
```

### 启动服务

#### 方式一：一键启动（Windows 推荐）

确保 Redis 已启动后，直接运行：

```bash
start_all.bat
```

这将同时启动以下四个服务（每个服务在独立窗口运行）：
1. **FastAPI 后端** (端口 8000) - API 服务
2. **Celery Worker** - 任务队列
3. **前端开发服务器** (端口 5173) - 切片系统前端
4. **弹幕监控服务** (端口 5000) - 弹幕监控系统

启动前会自动检查：
- ✅ 虚拟环境是否存在
- ✅ Redis 是否运行
- ✅ FFmpeg 是否安装

启动完成后会自动打开浏览器访问 http://localhost:5173

#### 方式二：分别启动（开发/调试推荐）

**1. 启动 Redis：**

```bash
# Windows（需先安装 Redis）
redis-server

# 或使用 Docker
docker run -p 6379:6379 redis
```

**2. 启动弹幕监控服务：**

```bash
start_monitor.bat

# 或手动
venv\Scripts\activate
cd monitor
python jk.py
```

**3. 启动 FastAPI 后端：**

```bash
start_backend.bat

# 或手动
venv\Scripts\activate
cd backend
python main.py
# 或使用 uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**4. 启动 Celery Worker：**

```bash
start_celery.bat

# 或手动
venv\Scripts\activate
cd backend
set PYTHONPATH=%CD%
celery -A core.celery_app worker --loglevel=info --concurrency=4
```

**5. 启动前端开发服务器：**

```bash
cd frontend
npm run dev
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 弹幕监控系统 | http://localhost:5000 | Flask 前端 |
| 切片系统前端 | http://localhost:5173 | React 前端 |
| FastAPI 后端 | http://localhost:8000 | API 服务 |
| API 文档 (Swagger) | http://localhost:8000/docs | 交互式 API 文档 |
| API 文档 (ReDoc) | http://localhost:8000/redoc | 另一种文档风格 |

## 使用说明

### 弹幕监控系统

1. **配置直播间**：在 `config.yaml` 中设置 `bilibili.room_id`
   - 直播间 ID 可从直播间地址获取：`https://live.bilibili.com/房间号`

2. **设置监控关键词**：在 `monitor.keyword` 中设置要监控的关键词
   - 默认关键词："鸽切"
   - 系统会自动记录包含该关键词的弹幕

3. **启动监控**：运行 `start_monitor.bat` 或 `python monitor/jk.py`

4. **查看数据**：访问 http://localhost:5000

**主要功能页面：**
- `/` - 主页（今日数据展示、在线状态）
- `/analysis` - 弹幕分析页面（统计图表、热门关键词）
- `/history` - 历史数据查询（按日期查询弹幕记录）
- `/chatroom` - 在线聊天室
- `/message_board` - 留言板

**管理员功能：**
- 使用配置的 `admin_password` 登录
- 可管理聊天室用户、禁言、删除留言等

### AI 视频切片系统

1. **访问前端**：打开 http://localhost:5173

2. **创建项目**：
   - 点击首页「新建项目」
   - 填写项目名称和描述
   - 上传视频文件（支持 .mp4, .avi, .mov 等常见格式）

3. **启动处理**：
   - 进入项目详情页
   - 点击「开始处理」按钮
   - 系统会自动执行 6 步处理流水线

4. **等待处理完成**：
   - 通过 WebSocket 实时查看处理进度
   - 每一步都有详细的日志输出
   - 处理时间取决于视频长度和 AI 模型速度

5. **查看结果**：
   - 在项目详情页查看所有生成的切片
   - 支持在线预览
   - 支持下载原始视频和缩略图
   - 可查看 AI 生成的标题和描述

### 处理流水线

系统采用 6 步流水线处理视频：

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Step 1     │───▶│  Step 2     │───▶│  Step 3     │
│  字幕提取   │    │  话题提取   │    │  智能评分   │
│  (bcut-asr)│    │  (LLM)      │    │  (LLM)      │
└─────────────┘    └─────────────┘    └─────────────┘
                                            │
                                            ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Step 6     │◀───│  Step 5     │◀───│  Step 4     │
│  结果整理   │    │  视频切片   │    │  切片规划   │
│             │    │  (FFmpeg)   │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
```

**各步骤详细说明：**

| 步骤 | 名称 | 功能 | 耗时 |
|------|------|------|------|
| Step 1 | 字幕提取 | 使用 bcut-asr 进行语音识别，生成精确字幕 | 取决于视频长度 |
| Step 2 | 话题提取 | 使用 LLM 分析字幕，识别视频中的精彩话题段落 | 取决于字幕长度 |
| Step 3 | 智能评分 | 使用 LLM 多维度评估话题质量，计算综合分数 | 取决于话题数量 |
| Step 4 | 切片规划 | 根据评分筛选最佳片段，规划视频切片时间点 | 很快 |
| Step 5 | 视频切片 | 使用 FFmpeg 提取视频片段，生成缩略图 | 取决于视频长度 |
| Step 6 | 结果整理 | 汇总处理结果，生成最终报告 | 很快 |

## 常见问题

### 1. Redis 连接失败

**症状**：启动时提示 Redis 连接错误

**解决方案**：

```bash
# 检查 Redis 是否运行
redis-cli ping

# 如果返回 PONG 表示正常
# 如果报错，需要启动 Redis

# Windows 启动 Redis（假设已安装）
redis-server

# 或使用 Docker
docker run -d -p 6379:6379 --name redis redis
```

**常见原因：**
- Redis 服务未启动
- Redis 端口被占用
- 防火墙阻止了连接

### 2. FFmpeg 未找到

**症状**：视频处理失败，提示 `ffmpeg not found`

**解决方案**：

**Windows 用户：**
1. 下载 FFmpeg: https://ffmpeg.org/download.html
   - 或直接下载：https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
2. 解压到任意目录（例如 `C:\ffmpeg`）
3. 将 `bin` 目录（例如 `C:\ffmpeg\bin`）添加到系统 PATH
4. 打开新的命令行窗口，验证安装：
   ```bash
   ffmpeg -version
   ```

**Linux/Mac 用户：**
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg

# Mac (Homebrew)
brew install ffmpeg
```

### 3. LLM API 调用失败

**症状**：处理在 Step 2 或 Step 3 失败，日志显示 API 错误

**解决方案**：

**检查 API Key：**
1. 确认 `.env` 中的 API Key 正确
2. 检查是否有拼写错误
3. 确认 Key 没有过期

**检查网络连接：**
- 某些 API（如 OpenAI）在国内访问可能需要代理
- 如使用代理，确保 `OPENAI_BASE_URL` 配置正确

**检查模型名称：**
- 通义千问支持的模型：`qwen-turbo`, `qwen-plus`, `qwen-max`, `qwen-max-1201`
- OpenAI 支持的模型：`gpt-3.5-turbo`, `gpt-4`, `gpt-4-turbo` 等

**查看详细日志：**
```bash
# 后端日志
tail -f logs/backend.log

# Celery 日志
tail -f logs/celery_worker.log
```

### 4. 弹幕监控无法连接

**症状**：无法获取直播间弹幕，日志显示连接错误

**解决方案**：

**检查直播间 ID：**
- 确认 `config.yaml` 中的 `room_id` 正确
- 直播间 ID 是纯数字，从地址栏获取

**检查网络连接：**
- 确认可以正常访问 B站
- 检查是否有防火墙或代理设置

**检查直播间状态：**
- 确认直播间没有被封禁
- 确认直播间不是仅限会员观看（如需监控，需要配置 credential）

**配置登录凭证（如需监控成员专属弹幕）：**
```yaml
credential:
  enable: true
  sessdata: "your_sessdata"      # 从浏览器 Cookie 获取
  bili_jct: "your_bili_jct"       # 从浏览器 Cookie 获取
  buvid3: "your_buvid3"           # 从浏览器 Cookie 获取
```

### 5. 语音识别失败

**症状**：Step 1 字幕提取失败，提示 bcut-asr 错误

**解决方案**：

**检查 B站 Cookie：**
1. 登录 B站后，打开浏览器开发者工具（F12）
2. 切换到 Network 标签
3. 刷新页面，点击任意请求
4. 在 Headers 中找到 Cookie，完整复制

**注意事项：**
- Cookie 包含敏感信息，请勿分享
- Cookie 可能会过期，需要定期更新
- 确保复制完整的 Cookie 字符串

**安装 bcut-asr：**
```bash
cd backend/bcut-asr
pip install -e .
```

### 6. 虚拟环境问题

**症状**：找不到模块、导入错误

**解决方案**：

**重新创建虚拟环境：**
```bash
# 删除旧的虚拟环境
rmdir /s venv  # Windows
rm -rf venv     # Linux/Mac

# 重新创建
install.bat     # Windows
./install.sh    # Linux/Mac
```

**检查虚拟环境是否激活：**
```bash
# 查看 Python 路径
which python    # Linux/Mac
where python    # Windows

# 应该显示项目 venv 目录下的 Python
```

### 7. 前端无法启动

**症状**：`npm run dev` 报错

**解决方案**：

**清除 npm 缓存：**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

**检查 Node.js 版本：**
```bash
node --version
# 需要 v18.0.0 或更高版本
```

## 注意事项

### 1. 敏感信息保护

**⚠️ 重要提示：**
- `.env` 文件包含 API Key 等敏感信息，已在 `.gitignore` 中排除
- `config.yaml` 包含密码和凭证，切勿提交到公开仓库
- `monitor/config.yaml` 包含 B站登录凭证，注意保密

**推荐做法：**
1. 始终从 `.env.example` 复制配置
2. 定期更换 API Key 和密码
3. 不要在代码中硬编码敏感信息
4. 使用环境变量管理敏感配置

### 2. 资源消耗

**视频处理资源需求：**
- **CPU**：视频编码是 CPU 密集型任务，建议使用多核 CPU
- **内存**：处理长视频时需要足够的内存，建议 8GB+
- **磁盘空间**：需要足够的空间存储原始视频和生成的切片
- **GPU**：如有 NVIDIA GPU，可启用硬件加速加速视频处理

**优化建议：**
1. 处理大视频前确保有足够的磁盘空间
2. 启用 `VIDEO_USE_STREAM_COPY=true` 可大幅加速
3. 如有 GPU，启用 `VIDEO_USE_HARDWARE_ACCEL=true`
4. 定期清理不需要的项目和切片

### 3. API 费用

**LLM API 费用说明：**
- 通义千问、OpenAI 等 API 按调用量收费
- 视频越长、话题越多，费用越高
- 建议设置合理的话题数量限制

**费用控制建议：**
1. 从短视频开始测试
2. 调整 `MAX_TOPICS_PER_CHUNK` 限制话题数量
3. 定期检查 API 使用量
4. 考虑设置 API 调用配额

### 4. 数据备份

**重要数据目录：**
- `backend/data/autoclip.db` - 切片系统数据库
- `monitor/geqie_data.db` - 监控系统数据库
- `backend/uploads/` - 上传的视频文件
- `backend/output/` - 生成的切片文件

**备份建议：**
1. 定期备份数据库文件
2. 重要视频可额外备份到其他位置
3. 考虑使用版本控制系统管理配置（排除敏感信息）

## 配置参考

### LLM 提供商配置

**通义千问（DashScope）- 推荐：**
```env
LLM_PROVIDER=dashscope
API_DASHSCOPE_API_KEY=sk-xxx
API_MODEL_NAME=qwen-plus
```
- 优点：国内访问速度快，价格合理
- 获取地址：https://dashscope.console.aliyun.com/
- 推荐模型：`qwen-turbo`（快速）、`qwen-plus`（平衡）、`qwen-max`（高质量）

**OpenAI：**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
API_MODEL_NAME=gpt-4
```
- 优点：模型质量高，效果好
- 缺点：国内访问可能需要代理

**自定义 OpenAI 兼容 API：**
```env
LLM_PROVIDER=custom
CUSTOM_API_KEY=your_api_key
CUSTOM_BASE_URL=https://your-api-endpoint.com/v1
CUSTOM_MODEL_NAME=your-model
```
- 适用于支持 OpenAI 格式的第三方 API

### 视频处理优化配置

**最快处理（质量无损）：**
```env
# 直接复制视频流，不重新编码
VIDEO_USE_STREAM_COPY=true
```
- 优点：处理速度极快，质量 100% 保留
- 缺点：切片时间点可能不够精确

**平衡模式：**
```env
VIDEO_USE_STREAM_COPY=false
VIDEO_CRF=23
```
- 质量和速度的平衡
- CRF 值范围 18-28，越小质量越高

**高质量模式：**
```env
VIDEO_USE_STREAM_COPY=false
VIDEO_CRF=18
```
- 质量最好，但处理时间最长

**硬件加速（需要 NVIDIA GPU）：**
```env
VIDEO_USE_HARDWARE_ACCEL=true
VIDEO_ENCODER_PRESET=p6
VIDEO_CRF=18
```
- 利用 NVIDIA GPU 加速视频编码
- 可大幅减少处理时间

### 话题提取参数配置

```env
# 话题时长控制（分钟）
MIN_TOPIC_DURATION_MINUTES=2      # 最小话题时长
MAX_TOPIC_DURATION_MINUTES=12     # 最大话题时长
TARGET_TOPIC_DURATION_MINUTES=5   # 目标话题时长

# 话题数量控制
MIN_TOPICS_PER_CHUNK=3             # 每段最少话题数
MAX_TOPICS_PER_CHUNK=8             # 每段最多话题数
```

**调整建议：**
- 如果视频内容密集，可增大 `MAX_TOPICS_PER_CHUNK`
- 如果想要更长的切片，可增大 `TARGET_TOPIC_DURATION_MINUTES`
- 如果想要更多的短切片，可减小 `MIN_TOPIC_DURATION_MINUTES`

## 未来规划

- [ ] **实现关键词自动触发切片的完整工作流**
  - 弹幕监控识别关键词
  - 自动记录时间点
  - 触发视频录制和切片
  - 生成切片报告

- [ ] **支持直播流实时录制和切片**
  - 实时录制直播流
  - 边录制边分析
  - 实时生成切片

- [ ] **增加更多 LLM 提示词模板**
  - 不同场景的提示词
  - 可自定义评估标准
  - 支持多语言

- [ ] **优化切片算法**
  - 支持自定义评分规则
  - 智能合并相邻话题
  - 自动检测精彩时刻

- [ ] **增加视频编辑功能**
  - 在线视频剪辑
  - 添加水印和字幕
  - 批量导出

- [ ] **支持批量处理**
  - 批量上传视频
  - 批量处理队列
  - 批量导出结果

- [ ] **增加用户权限管理**
  - 多用户支持
  - 角色权限控制
  - 操作日志审计

- [ ] **支持云存储集成**
  - 阿里云 OSS
  - 腾讯云 COS
  - AWS S3

## 相关项目

- [geqie-monitor](https://github.com/Liu-cloud136/geqie-monitor) - 原始弹幕监控系统
- [autoclip](https://github.com/zhouxiaoka/autoclip) - 原始 AI 切片系统
- [bcut-asr](https://github.com/SocialSisterYi/bcut-asr) - 必剪语音识别组件

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

**提交建议：**
1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

**Happy Monitoring & Clipping! 🎬✨**
