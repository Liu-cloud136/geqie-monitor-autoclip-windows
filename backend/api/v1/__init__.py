from fastapi import APIRouter

# 导入各个API模块
from . import projects, clips, settings, health, files, processing, progress, simple_progress, tasks, websocket, ai_stream, clip_thumbnails, step_config, test_progress, prompt, danmaku, clip_edit, system_config

# 创建主路由器
router = APIRouter()

# 注册各个子路由器
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(clips.router, prefix="/clips", tags=["clips"])
router.include_router(clip_edit.router, prefix="/clip-edit", tags=["clip-edit"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])
router.include_router(step_config.router, prefix="/step-config", tags=["step-config"])
router.include_router(system_config.router, prefix="/system-config", tags=["system-config"])
router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(files.router, tags=["files"])
router.include_router(clip_thumbnails.router, tags=["clip-thumbnails"])
router.include_router(processing.router, prefix="/processing", tags=["processing"])
router.include_router(progress.router, prefix="/progress", tags=["progress"])
router.include_router(simple_progress.router, tags=["simple-progress"])

router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(websocket.router, tags=["websocket"])
router.include_router(ai_stream.router, prefix="/ai_stream", tags=["ai_stream"])
router.include_router(test_progress.router, tags=["test"])
router.include_router(prompt.router, prefix="/prompt", tags=["prompt"])
router.include_router(danmaku.router, tags=["danmaku"])