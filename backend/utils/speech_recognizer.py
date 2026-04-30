"""
语音识别工具 - 使用 bcut-asr
"""
import logging
import sys
from pathlib import Path
from typing import Optional
import os
import subprocess
import tempfile

from .common import format_duration_with_ms

from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

logger = logging.getLogger(__name__)

def _add_bcut_asr_to_path():
    """将本地 bcut-asr 目录添加到 Python 路径"""
    # 当前文件: backend/utils/speech_recognizer.py
    # bcut-asr 目录: backend/bcut-asr/
    # 实际包在: backend/bcut-asr/bcut_asr/
    bcut_asr_dir = Path(__file__).parent.parent / "bcut-asr"
    bcut_asr_package_dir = bcut_asr_dir / "bcut_asr"
    
    if bcut_asr_dir.exists() and bcut_asr_package_dir.exists():
        # 添加父目录到 sys.path，这样 Python 可以找到 bcut_asr 包
        bcut_asr_dir_str = str(bcut_asr_dir)
        if bcut_asr_dir_str not in sys.path:
            sys.path.insert(0, bcut_asr_dir_str)
            logger.info(f"已将本地 bcut-asr 目录添加到 Python 路径: {bcut_asr_dir}")
        return True
    return False

# 尝试添加本地 bcut-asr 到路径
_add_bcut_asr_to_path()

BCUT_ASR_AVAILABLE = False
BcutASR = None
ResultStateEnum = None

try:
    from bcut_asr import BcutASR
    from bcut_asr.orm import ResultStateEnum
    BCUT_ASR_AVAILABLE = True
    logger.info("bcut-asr 已成功加载")
except ImportError as e:
    BCUT_ASR_AVAILABLE = False
    logger.warning(f"bcut-asr 未安装或无法加载: {e}")
    logger.warning("请确保 bcut-asr 目录存在，或运行: pip install bcut-asr")


def generate_subtitle_for_video(
    video_path: Path,
    output_path: Optional[Path] = None,
    method: str = "auto",
    model: str = "base",
    language: str = "auto",
    enable_fallback: bool = True
) -> Optional[Path]:
    """
    为视频生成字幕
    
    Args:
        video_path: 视频文件路径
        output_path: 输出字幕文件路径，默认为视频同名.srt
        
    Returns:
        生成的字幕文件路径，失败返回None
    """
    video_path = Path(video_path)
    
    if not video_path.exists():
        logger.error(f"视频文件不存在: {video_path}")
        return None
    
    if not BCUT_ASR_AVAILABLE:
        logger.error("bcut-asr未安装，无法生成字幕")
        return None
    
    cookie = os.getenv("BILIBILI_COOKIE")
    if not cookie:
        logger.error("未设置BILIBILI_COOKIE环境变量，无法使用bcut-asr")
        logger.error("请登录B站后，从浏览器获取Cookie并设置环境变量:")
        logger.error("  1. 登录 bilibili.com")
        logger.error("  2. 打开浏览器开发者工具 (F12)")
        logger.error("  3. 在 Network 标签页找到任意请求")
        logger.error("  4. 复制请求头中的 Cookie 值")
        logger.error("  5. 设置环境变量: set BILIBILI_COOKIE=你的cookie值")
        return None
    
    if output_path is None:
        output_path = video_path.with_suffix(".srt")
    else:
        output_path = Path(output_path)
    
    try:
        return _generate_with_bcut(video_path, output_path)
    except Exception as e:
        logger.error(f"生成字幕失败: {e}")
        return None


def _generate_with_bcut(video_path: Path, output_path: Path) -> Optional[Path]:
    """使用bcut-asr生成字幕"""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        audio_path = Path(tmp.name)
    
    try:
        logger.info(f"从视频提取音频: {video_path}")
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-vn", "-acodec", "libmp3lame",
            "-ar", "16000", "-ac", "1",
            "-y", str(audio_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True, encoding='utf-8', errors='ignore')
        
        logger.info("使用bcut-asr识别音频")
        asr = BcutASR(str(audio_path))
        
        cookie = os.getenv("BILIBILI_COOKIE")
        for item in cookie.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                asr.session.cookies.set(k.strip(), v.strip())
        
        asr.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://member.bilibili.com/",
            "Origin": "https://member.bilibili.com"
        })
        
        asr.upload()
        asr.create_task()
        
        import time
        max_wait = 1800  # 增加到30分钟，支持1小时视频
        waited = 0
        while waited < max_wait:
            result = asr.result()
            if result.state == ResultStateEnum.COMPLETE:
                break
            elif result.state == ResultStateEnum.ERROR:
                raise Exception("bcut-asr识别出错")
            time.sleep(2)
            waited += 2
            logger.info(f"等待识别完成... ({waited}s)")
        else:
            raise Exception("bcut-asr识别超时")
        
        if result.state != ResultStateEnum.COMPLETE:
            raise Exception(f"bcut-asr识别失败: {result.state}")
        
        asr_data = result.parse()
        
        with open(output_path, "w", encoding="utf-8") as f:
            for i, u in enumerate(asr_data.utterances, 1):
                start = _format_time(u.start_time / 1000)
                end = _format_time(u.end_time / 1000)
                f.write(f"{i}\n{start} --> {end}\n{u.transcript}\n\n")
        
        logger.info(f"字幕生成成功: {output_path}")
        return output_path
        
    finally:
        if audio_path.exists():
            audio_path.unlink()


def _format_time(seconds: float) -> str:
    """格式化时间为SRT格式"""
    return format_duration_with_ms(seconds, separator=',')
