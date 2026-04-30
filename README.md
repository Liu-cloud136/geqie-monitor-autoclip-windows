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
├── .env.example               # 环境变量示例
├── .gitignore
├── init.bat                   # 初始化脚本
├── start_all.bat              # 一键启动所有服务
├── start_backend.bat          # 启动后端 API
└── start_celery_enhanced.bat  # 启动 Celery Worker
```

## 快速开始

### 环境要求

- **Python**: 3.9+
- **Node.js**: 18.x+
- **Redis**: 5.0+ (用于 Celery 任务队列)
- **FFmpeg**: 4.0+ (需添加到系统 PATH)

### 安装步骤

#### 1. 克隆仓库

```bash
git clone https://github.com/Liu-cloud136/geqie-monitor-autoclip-windows.git
cd geqie-monitor-autoclip-windows
```

#### 2. 安装依赖

**方式一：使用初始化脚本（Windows）**

```bash
init.bat
```

**方式二：手动安装**

**Python 依赖：**

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python init_db.py
```

**前端依赖：**

```bash
cd frontend
npm install
```

**弹幕监控系统依赖（如需单独运行）：**

```bash
cd monitor
pip install -r requirements.txt
```

#### 3. 配置环境变量

**切片系统配置 (.env)：**

复制 `.env.example` 为 `.env`，并填写以下配置：

```env
# LLM API 配置（必须）
LLM_PROVIDER=dashscope
API_DASHSCOPE_API_KEY=your_dashscope_api_key
API_MODEL_NAME=qwen-plus

# B站 Cookie（必须，用于语音识别）
BILIBILI_COOKIE=your_bilibili_cookie_here

# 数据库配置
DATABASE_URL=sqlite:///./data/autoclip.db

# Redis 配置
REDIS_URL=redis://localhost:6379/0
```

**弹幕监控系统配置 (config.yaml)：**

复制 `monitor/config.yaml.example` 为 `monitor/config.yaml`：

```yaml
app:
  host: "0.0.0.0"
  port: 5000
  admin_password: "your_password_here"

bilibili:
  room_id: 22391541  # 你的直播间 ID

monitor:
  keyword: "鸽切"  # 监控关键词

# 多房间监控（可选）
multi_room:
  enable: false
  rooms:
    - room_id: 22391541
      nickname: "主直播间"
      enabled: true

# 邮件通知（可选）
email:
  smtp_server: "smtp.qq.com"
  smtp_port: 587
  sender: "your_email@qq.com"
  password: "your_smtp_password"
  receiver: "your_email@qq.com"
```

### 启动服务

#### 方式一：一键启动（Windows）

```bash
start_all.bat
```

这将启动三个服务：
1. FastAPI 后端 (端口 8000)
2. Celery Worker (任务队列)
3. 前端开发服务器 (端口 5173)

#### 方式二：分别启动

**启动 Redis：**
```bash
redis-server
```

**启动 FastAPI 后端：**
```bash
start_backend.bat
# 或手动
cd backend
venv\Scripts\activate
python main.py
```

**启动 Celery Worker：**
```bash
start_celery_enhanced.bat
# 或手动
cd backend
venv\Scripts\activate
celery -A tasks worker --loglevel=info -P solo
```

**启动前端开发服务器：**
```bash
cd frontend
npm run dev
```

**启动弹幕监控系统：**
```bash
cd monitor
python jk.py
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 切片系统前端 | http://localhost:5173 |
| 监控系统前端 | http://localhost:5000 |
| FastAPI 文档 | http://localhost:8000/docs |
| FastAPI ReDoc | http://localhost:8000/redoc |

## 使用说明

### 弹幕监控系统

1. **配置直播间**：在 `config.yaml` 中设置 `bilibili.room_id`
2. **设置监控关键词**：在 `monitor.keyword` 中设置要监控的关键词（默认"鸽切"）
3. **启动监控**：运行 `python jk.py`
4. **查看数据**：访问 http://localhost:5000

主要功能页面：
- `/` - 主页（今日数据展示）
- `/analysis` - 弹幕分析页面
- `/history` - 历史数据查询

### AI 视频切片系统

1. **创建项目**：点击首页「新建项目」，填写项目信息并上传视频文件
2. **启动处理**：在项目详情页点击「开始处理」
3. **等待处理**：系统会自动执行以下步骤：
   - Step 1: 字幕提取（语音识别）
   - Step 2: 话题提取（AI 分析）
   - Step 3: 智能评分（多维度评估）
   - Step 4: 切片规划（筛选最佳片段）
   - Step 5: 视频切片（生成最终视频）
4. **查看结果**：在项目详情页查看所有生成的切片，支持预览和导出

### 配置说明

#### LLM 提供商配置

**通义千问（DashScope）推荐：**
```env
LLM_PROVIDER=dashscope
API_DASHSCOPE_API_KEY=sk-xxx
API_MODEL_NAME=qwen-plus
```

**OpenAI：**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
API_MODEL_NAME=gpt-4
```

**自定义 OpenAI 兼容 API：**
```env
LLM_PROVIDER=custom
CUSTOM_API_KEY=your_api_key
CUSTOM_BASE_URL=https://your-api-endpoint.com/v1
CUSTOM_MODEL_NAME=your-model
```

#### 视频处理优化

```env
# 流复制（最快，质量无损）
VIDEO_USE_STREAM_COPY=true

# 硬件加速（需要 NVIDIA GPU）
VIDEO_USE_HARDWARE_ACCEL=true
VIDEO_ENCODER_PRESET=p6
VIDEO_CRF=18
```

#### 话题提取参数

```env
# 话题时长控制（分钟）
MIN_TOPIC_DURATION_MINUTES=2
MAX_TOPIC_DURATION_MINUTES=12
TARGET_TOPIC_DURATION_MINUTES=5

# 话题数量控制
MIN_TOPICS_PER_CHUNK=3
MAX_TOPICS_PER_CHUNK=8
```

## 处理流水线

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

## 常见问题

### 1. Redis 连接失败

**症状**：启动时提示 Redis 连接错误

**解决方案**：
```bash
# 检查 Redis 是否运行
redis-cli ping

# 如果未运行，启动 Redis
redis-server
```

### 2. FFmpeg 未找到

**症状**：视频处理失败

**解决方案**：
1. 下载 FFmpeg: https://ffmpeg.org/download.html
2. 解压并将 bin 目录添加到系统 PATH
3. 验证安装：`ffmpeg -version`

### 3. LLM API 调用失败

**症状**：处理在 Step 2 或 Step 3 失败

**解决方案**：
1. 检查 API Key 是否正确
2. 检查模型名称是否正确
3. 检查网络连接（可能需要代理）
4. 查看日志：`logs/backend.log`

### 4. 弹幕监控无法连接

**症状**：无法获取直播间弹幕

**解决方案**：
1. 检查直播间 ID 是否正确
2. 检查网络连接
3. 如需监控成员专属弹幕，需要配置 B站登录凭证：
   ```yaml
   credential:
     enable: true
     sessdata: "your_sessdata"
     bili_jct: "your_bili_jct"
     buvid3: "your_buvid3"
   ```

### 5. 语音识别失败

**症状**：Step 1 字幕提取失败

**解决方案**：
1. 检查 B站 Cookie 是否有效
2. Cookie 获取方式：登录 B站后，从浏览器开发者工具 → Network → 任意请求 → Headers → Cookie
3. 确保 Cookie 完整复制

## 注意事项

1. **敏感信息保护**：
   - `.env` 文件包含 API Key 等敏感信息，已在 `.gitignore` 中排除
   - `config.yaml` 包含密码和凭证，切勿提交到公开仓库

2. **资源消耗**：
   - 视频处理需要较大的 CPU 和内存资源
   - 建议处理大视频时使用硬件加速
   - 确保有足够的磁盘空间

3. **API 费用**：
   - LLM API 调用会产生费用
   - 建议设置合理的并发数和重试策略
   - 定期检查 API 使用量

4. **数据备份**：
   - 定期备份数据库文件
   - 切片系统数据库：`backend/data/autoclip.db`
   - 监控系统数据库：`monitor/geqie_data.db`

## 未来规划

- [ ] 实现关键词自动触发切片的完整工作流
- [ ] 支持直播流实时录制和切片
- [ ] 增加更多 LLM 提示词模板
- [ ] 优化切片算法，支持自定义评分规则
- [ ] 增加视频编辑功能
- [ ] 支持批量处理多个视频
- [ ] 增加用户权限管理
- [ ] 支持云存储集成

## 相关项目

- [geqie-monitor](https://github.com/Liu-cloud136/geqie-monitor) - 原始弹幕监控系统
- [autoclip](https://github.com/zhouxiaoka/autoclip) - 原始 AI 切片系统
- [bcut-asr](https://github.com/SocialSisterYi/bcut-asr) - 必剪语音识别组件

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

---

**Happy Monitoring & Clipping! 🎬✨**
