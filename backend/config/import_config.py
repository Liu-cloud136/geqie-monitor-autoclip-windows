"""
快速导入优化配置
"""

# 是否在导入时生成缩略图（False表示延迟生成，提升导入速度）
GENERATE_THUMBNAIL_ON_IMPORT = False

# 导入时的默认缩略图（base64格式）
DEFAULT_THUMBNAIL = None  # 将使用前端默认占位图

# 缩略图生成策略
# 'immediate': 导入时立即生成
# 'lazy': 在项目列表刷新时按需生成
# 'background': 在后台异步生成
THUMBNAIL_GENERATION_STRATEGY = 'background'

# 并行处理配置
# 最大并发导入任务数
MAX_CONCURRENT_IMPORTS = 4

# 批量导入时的批处理大小
BATCH_IMPORT_SIZE = 10

# 视频处理步骤的并发配置
# 字幕生成并发数（ASR处理）
SUBTITLE_CONCURRENCY = 2

# 缩略图生成并发数
THUMBNAIL_CONCURRENCY = 4

# 是否启用批量导入优化
ENABLE_BATCH_IMPORT_OPTIMIZATION = True
