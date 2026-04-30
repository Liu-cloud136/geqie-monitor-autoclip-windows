"""
视频处理工具
"""
import subprocess
import asyncio.subprocess
import json
import logging
import re
from typing import List, Dict, Optional, Callable
from pathlib import Path

from .common import sanitize_filename, time_str_to_seconds, format_duration_with_ms

from services.concurrency_manager import with_async_concurrency_limit
from services.exceptions import VideoProcessingError, FileOperationError

logger = logging.getLogger(__name__)

class VideoProcessor:
    """视频处理工具类"""
    
    def __init__(self, clips_dir: Optional[str] = None):
        # 强制使用传入的项目特定路径，不使用全局路径作为后备
        if not clips_dir:
            raise ValueError("clips_dir 参数是必需的，不能使用全局路径")
        
        self.clips_dir = Path(clips_dir)
    
    @staticmethod
    def convert_srt_time_to_ffmpeg_time(srt_time: str) -> str:
        """
        将SRT时间格式转换为FFmpeg时间格式
        
        Args:
            srt_time: SRT时间格式 (如 "00:00:06,140" 或 "00:00:06.140")
            
        Returns:
            FFmpeg时间格式 (如 "00:00:06.140")
        """
        # 将逗号替换为点
        return srt_time.replace(',', '.')
    
    @staticmethod
    def convert_seconds_to_ffmpeg_time(seconds: float) -> str:
        """
        将秒数转换为FFmpeg时间格式
        
        Args:
            seconds: 秒数
            
        Returns:
            FFmpeg时间格式 (如 "00:00:06.140")
        """
        # FFmpeg格式使用点分隔秒和毫秒
        return format_duration_with_ms(seconds, separator='.')
    
    @staticmethod
    def convert_ffmpeg_time_to_seconds(time_str: str) -> float:
        """
        将FFmpeg时间格式转换为秒数
        
        Args:
            time_str: FFmpeg时间格式 (如 "00:00:06.140")
            
        Returns:
            秒数
        """
        try:
            return time_str_to_seconds(time_str)
        except ValueError as e:
            logger.error(f"时间格式转换失败: {time_str}, 错误: {e}")
            raise VideoProcessingError(
                message=f"时间格式转换失败: {time_str}",
                video_path=str(time_str),
                step_name="时间格式转换",
                cause=e
            )
        except Exception as e:
            logger.error(f"时间格式转换异常: {time_str}, 错误: {e}")
            raise VideoProcessingError(
                message=f"时间格式转换异常: {time_str}",
                video_path=str(time_str),
                step_name="时间格式转换",
                cause=e
            )
    
    @with_async_concurrency_limit(max_concurrent=3)
    @staticmethod
    async def extract_clip_async(
        input_video: Path,
        output_path: Path,
        start_time: str,
        end_time: str,
        progress_callback: Optional[Callable[[float], None]] = None,
        use_stream_copy: bool = True,
        use_hardware_accel: bool = True
    ) -> bool:
        """
        异步从视频中提取指定时间段的片段（优化版本，支持流复制和硬件加速）

        Args:
            input_video: 输入视频路径
            output_path: 输出视频路径
            start_time: 开始时间 (格式: "00:01:25,140")
            end_time: 结束时间 (格式: "00:02:53,500")
            progress_callback: 进度回调函数，传入0-100的进度值
            use_stream_copy: 是否使用流复制（默认True，速度最快）
            use_hardware_accel: 是否使用硬件加速（默认True，需要GPU支持）

        Returns:
            是否成功
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            ffmpeg_start_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(start_time)
            ffmpeg_end_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(end_time)

            start_seconds = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_start_time)
            end_seconds = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_end_time)
            duration = end_seconds - start_seconds

            if use_stream_copy:
                cmd = [
                    'ffmpeg',
                    '-ss', ffmpeg_start_time,
                    '-i', str(input_video),
                    '-t', str(duration),
                    '-c', 'copy',
                    '-avoid_negative_ts', 'make_zero',
                    '-y',
                    str(output_path)
                ]
                logger.info(f"使用流复制模式异步提取视频片段（快速模式）")
            else:
                video_encoder = 'libx264'
                if use_hardware_accel:
                    video_encoder = 'h264_nvenc'

                cmd = [
                    'ffmpeg',
                    '-ss', ffmpeg_start_time,
                    '-i', str(input_video),
                    '-t', str(duration),
                    '-c:v', video_encoder,
                    '-preset', 'p6',
                    '-crf', '23',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-movflags', '+faststart',
                    '-avoid_negative_ts', 'make_zero',
                    '-y',
                    str(output_path)
                ]
                logger.info(f"使用编码模式异步提取视频片段（编码器: {video_encoder}）")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            if progress_callback and duration > 0:
                # 异步读取stderr并解析进度
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    line_str = line.decode('utf-8', errors='ignore')
                    time_match = re.search(r'time=(\d+):(\d+):(\d+)\.(\d+)', line_str)
                    if time_match:
                        hours = int(time_match.group(1))
                        minutes = int(time_match.group(2))
                        seconds = int(time_match.group(3))
                        centiseconds = int(time_match.group(4))
                        current_time = hours * 3600 + minutes * 60 + seconds + centiseconds / 100
                        progress = (current_time / duration) * 100
                        progress_callback(progress)

            await process.wait()

            if process.returncode == 0:
                logger.info(f"成功异步提取视频片段: {output_path} ({ffmpeg_start_time} -> {ffmpeg_end_time}, 时长: {duration:.2f}秒)")
                return True
            else:
                logger.error(f"异步提取视频片段失败，返回码: {process.returncode}")
                stderr_data = await process.stderr.read()
                logger.error(f"FFmpeg 错误: {stderr_data.decode('utf-8', errors='ignore')}")
                raise VideoProcessingError(
                    message=f"FFmpeg 异步视频处理失败",
                    video_path=str(input_video),
                    step_name="异步视频处理",
                    details={"stderr": stderr_data.decode('utf-8', errors='ignore')},
                    cause=subprocess.CalledProcessError(process.returncode, cmd)
                )

        except VideoProcessingError:
            raise
        except FileNotFoundError as e:
            logger.error(f"FFmpeg 未找到: {e}")
            raise VideoProcessingError(
                message="FFmpeg 未安装或不在系统PATH中",
                video_path=str(input_video),
                step_name="异步视频处理",
                cause=e
            )
        except subprocess.TimeoutExpired as e:
            logger.error(f"视频处理超时: {e}")
            raise VideoProcessingError(
                message=f"视频处理超时",
                video_path=str(input_video),
                step_name="异步视频处理",
                cause=e
            )
        except Exception as e:
            logger.error(f"异步视频处理异常: {str(e)}")
            raise VideoProcessingError(
                message=f"异步视频处理异常: {str(e)}",
                video_path=str(input_video),
                step_name="异步视频处理",
                cause=e
            )

    @staticmethod
    def extract_clip(input_video: Path, output_path: Path,
                    start_time: str, end_time: str, progress_callback: Optional[Callable[[float], None]] = None,
                    use_stream_copy: bool = True, use_hardware_accel: bool = True) -> bool:
        """
        从视频中提取指定时间段的片段（优化版本，支持流复制和硬件加速）

        Args:
            input_video: 输入视频路径
            output_path: 输出视频路径
            start_time: 开始时间 (格式: "00:01:25,140")
            end_time: 结束时间 (格式: "00:02:53,500")
            progress_callback: 进度回调函数，传入0-100的进度值
            use_stream_copy: 是否使用流复制（默认True，速度最快）
            use_hardware_accel: 是否使用硬件加速（默认True，需要GPU支持）

        Returns:
            是否成功
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            ffmpeg_start_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(start_time)
            ffmpeg_end_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(end_time)

            start_seconds = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_start_time)
            end_seconds = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_end_time)
            duration = end_seconds - start_seconds

            if use_stream_copy:
                cmd = [
                    'ffmpeg',
                    '-ss', ffmpeg_start_time,
                    '-i', str(input_video),
                    '-t', str(duration),
                    '-c', 'copy',
                    '-avoid_negative_ts', 'make_zero',
                    '-y',
                    str(output_path)
                ]
                logger.info(f"使用流复制模式提取视频片段（快速模式）")
            else:
                video_encoder = 'libx264'
                if use_hardware_accel:
                    video_encoder = 'h264_nvenc'
                
                cmd = [
                    'ffmpeg',
                    '-ss', ffmpeg_start_time,
                    '-i', str(input_video),
                    '-t', str(duration),
                    '-c:v', video_encoder,
                    '-preset', 'p6',
                    '-crf', '23',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-movflags', '+faststart',
                    '-avoid_negative_ts', 'make_zero',
                    '-y',
                    str(output_path)
                ]
                logger.info(f"使用编码模式提取视频片段（编码器: {video_encoder}）")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8',
                errors='ignore'
            )

            if progress_callback and duration > 0:
                for line in process.stderr:
                    time_match = re.search(r'time=(\d+):(\d+):(\d+)\.(\d+)', line)
                    if time_match:
                        hours = int(time_match.group(1))
                        minutes = int(time_match.group(2))
                        seconds = int(time_match.group(3))
                        centiseconds = int(time_match.group(4))
                        current_time = hours * 3600 + minutes * 60 + seconds + centiseconds / 100
                        progress = (current_time / duration) * 100
                        progress_callback(progress)

            process.wait()

            if process.returncode == 0:
                logger.info(f"成功提取视频片段: {output_path} ({ffmpeg_start_time} -> {ffmpeg_end_time}, 时长: {duration:.2f}秒)")
                return True
            else:
                logger.error(f"提取视频片段失败，返回码: {process.returncode}")
                _, stderr = process.communicate()
                logger.error(f"FFmpeg 错误: {stderr}")
                raise VideoProcessingError(
                    message=f"FFmpeg 视频处理失败",
                    video_path=str(input_video),
                    step_name="视频处理",
                    details={"stderr": stderr, "returncode": process.returncode},
                    cause=subprocess.CalledProcessError(process.returncode, cmd)
                )

        except VideoProcessingError:
            raise
        except FileNotFoundError as e:
            logger.error(f"FFmpeg 未找到: {e}")
            raise VideoProcessingError(
                message="FFmpeg 未安装或不在系统PATH中",
                video_path=str(input_video),
                step_name="视频处理",
                cause=e
            )
        except subprocess.TimeoutExpired as e:
            logger.error(f"视频处理超时: {e}")
            raise VideoProcessingError(
                message=f"视频处理超时",
                video_path=str(input_video),
                step_name="视频处理",
                cause=e
            )
        except Exception as e:
            logger.error(f"视频处理异常: {str(e)}")
            raise VideoProcessingError(
                message=f"视频处理异常: {str(e)}",
                video_path=str(input_video),
                step_name="视频处理",
                cause=e
            )
    
    @with_async_concurrency_limit(max_concurrent=5)
    @staticmethod
    async def extract_thumbnail_async(video_path: Path, output_path: Path, time_offset: int = 5) -> bool:
        """
        异步从视频中提取缩略图

        Args:
            video_path: 视频文件路径
            output_path: 输出缩略图路径
            time_offset: 提取时间点（秒）

        Returns:
            是否成功
        """
        try:
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 构建FFmpeg命令
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-ss', str(time_offset),
                '-vframes', '1',
                '-q:v', '2',  # 高质量
                '-y',  # 覆盖输出文件
                str(output_path)
            ]

            # 执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            await process.wait()

            if process.returncode == 0 and output_path.exists():
                logger.info(f"成功异步提取缩略图: {output_path}")
                return True
            else:
                stderr_data = await process.stderr.read()
                logger.error(f"异步提取缩略图失败: {stderr_data.decode('utf-8', errors='ignore')}")
                raise VideoProcessingError(
                    message=f"FFmpeg 异步提取缩略图失败",
                    video_path=str(video_path),
                    step_name="异步提取缩略图",
                    details={"stderr": stderr_data.decode('utf-8', errors='ignore')},
                    cause=subprocess.CalledProcessError(process.returncode, cmd)
                )

        except VideoProcessingError:
            raise
        except FileNotFoundError as e:
            logger.error(f"FFmpeg 未找到: {e}")
            raise VideoProcessingError(
                message="FFmpeg 未安装或不在系统PATH中",
                video_path=str(video_path),
                step_name="异步提取缩略图",
                cause=e
            )
        except Exception as e:
            logger.error(f"异步提取缩略图异常: {str(e)}")
            raise VideoProcessingError(
                message=f"异步提取缩略图异常: {str(e)}",
                video_path=str(video_path),
                step_name="异步提取缩略图",
                cause=e
            )

    @staticmethod
    def extract_thumbnail(video_path: Path, output_path: Path, time_offset: int = 5) -> bool:
        """
        从视频中提取缩略图
        
        Args:
            video_path: 视频文件路径
            output_path: 输出缩略图路径
            time_offset: 提取时间点（秒）
            
        Returns:
            是否成功
        """
        try:
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 构建FFmpeg命令
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-ss', str(time_offset),
                '-vframes', '1',
                '-q:v', '2',  # 高质量
                '-y',  # 覆盖输出文件
                str(output_path)
            ]
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0 and output_path.exists():
                logger.info(f"成功提取缩略图: {output_path}")
                return True
            else:
                logger.error(f"提取缩略图失败: {result.stderr}")
                raise VideoProcessingError(
                    message=f"FFmpeg 提取缩略图失败",
                    video_path=str(video_path),
                    step_name="提取缩略图",
                    details={"stderr": result.stderr, "returncode": result.returncode},
                    cause=subprocess.CalledProcessError(result.returncode, cmd)
                )

        except VideoProcessingError:
            raise
        except FileNotFoundError as e:
            logger.error(f"FFmpeg 未找到: {e}")
            raise VideoProcessingError(
                message="FFmpeg 未安装或不在系统PATH中",
                video_path=str(video_path),
                step_name="提取缩略图",
                cause=e
            )
        except Exception as e:
            logger.error(f"提取缩略图异常: {str(e)}")
            raise VideoProcessingError(
                message=f"提取缩略图异常: {str(e)}",
                video_path=str(video_path),
                step_name="提取缩略图",
                cause=e
            )
    
    @staticmethod
    async def get_video_info_async(video_path: Path) -> Dict:
        """
        异步获取视频信息

        Args:
            video_path: 视频文件路径

        Returns:
            视频信息字典
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout_data, _ = await process.communicate()

            if process.returncode == 0:
                info = json.loads(stdout_data.decode('utf-8'))
                return {
                    'duration': float(info['format']['duration']),
                    'size': int(info['format']['size']),
                    'bitrate': int(info['format']['bit_rate']),
                    'streams': info['streams']
                }
            else:
                stderr_data = await process.stderr.read()
                logger.error(f"异步获取视频信息失败: {process.returncode}")
                raise VideoProcessingError(
                    message=f"FFprobe 异步获取视频信息失败",
                    video_path=str(video_path),
                    step_name="异步获取视频信息",
                    details={"stderr": stderr_data.decode('utf-8', errors='ignore'), "returncode": process.returncode},
                    cause=subprocess.CalledProcessError(process.returncode, cmd)
                )

        except VideoProcessingError:
            raise
        except FileNotFoundError as e:
            logger.error(f"FFprobe 未找到: {e}")
            raise VideoProcessingError(
                message="FFprobe 未安装或不在系统PATH中",
                video_path=str(video_path),
                step_name="异步获取视频信息",
                cause=e
            )
        except json.JSONDecodeError as e:
            logger.error(f"解析视频信息JSON失败: {e}")
            raise VideoProcessingError(
                message=f"解析视频信息JSON失败",
                video_path=str(video_path),
                step_name="异步获取视频信息",
                cause=e
            )
        except Exception as e:
            logger.error(f"异步获取视频信息异常: {str(e)}")
            raise VideoProcessingError(
                message=f"异步获取视频信息异常: {str(e)}",
                video_path=str(video_path),
                step_name="异步获取视频信息",
                cause=e
            )

    @staticmethod
    def get_video_info(video_path: Path) -> Dict:
        """
        获取视频信息
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            视频信息字典
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                return {
                    'duration': float(info['format']['duration']),
                    'size': int(info['format']['size']),
                    'bitrate': int(info['format']['bit_rate']),
                    'streams': info['streams']
                }
            else:
                logger.error(f"获取视频信息失败: {result.stderr}")
                raise VideoProcessingError(
                    message=f"FFprobe 获取视频信息失败",
                    video_path=str(video_path),
                    step_name="获取视频信息",
                    details={"stderr": result.stderr, "returncode": result.returncode},
                    cause=subprocess.CalledProcessError(result.returncode, cmd)
                )

        except VideoProcessingError:
            raise
        except FileNotFoundError as e:
            logger.error(f"FFprobe 未找到: {e}")
            raise VideoProcessingError(
                message="FFprobe 未安装或不在系统PATH中",
                video_path=str(video_path),
                step_name="获取视频信息",
                cause=e
            )
        except json.JSONDecodeError as e:
            logger.error(f"解析视频信息JSON失败: {e}")
            raise VideoProcessingError(
                message=f"解析视频信息JSON失败",
                video_path=str(video_path),
                step_name="获取视频信息",
                cause=e
            )
        except Exception as e:
            logger.error(f"获取视频信息异常: {str(e)}")
            raise VideoProcessingError(
                message=f"获取视频信息异常: {str(e)}",
                video_path=str(video_path),
                step_name="获取视频信息",
                cause=e
            )
    
    async def batch_extract_clips_async(
        self,
        input_video: Path,
        clips_data: List[Dict],
        progress_callback: Optional[Callable[[float], None]] = None,
        use_stream_copy: bool = True,
        use_hardware_accel: bool = True,
        max_concurrent: int = 3
    ) -> List[Path]:
        """
        异步批量提取视频片段（优化版本，支持流复制、硬件加速和进度回调）

        Args:
            input_video: 输入视频路径
            clips_data: 片段数据列表，每个元素包含id、title、start_time、end_time
            progress_callback: 总进度回调函数，传入0-100的进度值
            use_stream_copy: 是否使用流复制（默认True，速度最快）
            use_hardware_accel: 是否使用硬件加速（默认True，需要GPU支持）
            max_concurrent: 最大并发数，默认为3

        Returns:
            成功提取的片段路径列表
        """
        successful_clips = []
        total_clips = len(clips_data)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_single_clip(clip_data: Dict, index: int) -> Optional[Path]:
            """提取单个片段"""
            async with semaphore:
                clip_id = clip_data['id']
                title = clip_data.get('title', f"片段_{clip_id}")
                start_time = clip_data['start_time']
                end_time = clip_data['end_time']

                if isinstance(start_time, (int, float)):
                    start_time = VideoProcessor.convert_seconds_to_ffmpeg_time(start_time)
                if isinstance(end_time, (int, float)):
                    end_time = VideoProcessor.convert_seconds_to_ffmpeg_time(end_time)

                output_path = self.clips_dir / f"clip_{clip_id}.mp4"

                logger.info(f"异步提取切片 {index+1}/{total_clips}: {clip_id}: {start_time} -> {end_time}")

                success = await VideoProcessor.extract_clip_async(
                    input_video,
                    output_path,
                    start_time,
                    end_time,
                    use_stream_copy=use_stream_copy,
                    use_hardware_accel=use_hardware_accel
                )

                if success:
                    logger.info(f"切片 {clip_id} 提取成功")
                    return output_path
                else:
                    logger.error(f"切片 {clip_id} 提取失败")
                    return None

        # 创建所有任务
        tasks = [extract_single_clip(clip_data, i) for i, clip_data in enumerate(clips_data)]

        # 执行所有任务并跟踪进度
        completed = 0
        for future in asyncio.as_completed(tasks):
            result = await future
            completed += 1

            if result:
                successful_clips.append(result)

            # 更新总进度
            if progress_callback:
                total_progress = (completed / total_clips) * 100
                progress_callback(total_progress)

        return successful_clips

    def batch_extract_clips(self, input_video: Path, clips_data: List[Dict],
                           progress_callback: Optional[Callable[[float], None]] = None,
                           use_stream_copy: bool = True, use_hardware_accel: bool = True) -> List[Path]:
        """
        批量提取视频片段（优化版本，支持流复制、硬件加速和进度回调）

        Args:
            input_video: 输入视频路径
            clips_data: 片段数据列表，每个元素包含id、title、start_time、end_time
            progress_callback: 总进度回调函数，传入0-100的进度值
            use_stream_copy: 是否使用流复制（默认True，速度最快）
            use_hardware_accel: 是否使用硬件加速（默认True，需要GPU支持）

        Returns:
            成功提取的片段路径列表
        """
        successful_clips = []
        total_clips = len(clips_data)

        for i, clip_data in enumerate(clips_data):
            clip_id = clip_data['id']
            title = clip_data.get('title', f"片段_{clip_id}")
            start_time = clip_data['start_time']
            end_time = clip_data['end_time']

            if isinstance(start_time, (int, float)):
                start_time = VideoProcessor.convert_seconds_to_ffmpeg_time(start_time)
            if isinstance(end_time, (int, float)):
                end_time = VideoProcessor.convert_seconds_to_ffmpeg_time(end_time)

            safe_title = sanitize_filename(title)
            output_path = self.clips_dir / f"clip_{clip_id}.mp4"

            logger.info(f"提取切片 {i+1}/{total_clips}: {clip_id}: {start_time} -> {end_time}")

            def segment_progress(seg_progress: float):
                total_progress = ((i * 100) + seg_progress) / total_clips
                if progress_callback:
                    progress_callback(total_progress)

            if VideoProcessor.extract_clip(
                input_video,
                output_path,
                start_time,
                end_time,
                progress_callback=segment_progress,
                use_stream_copy=use_stream_copy,
                use_hardware_accel=use_hardware_accel
            ):
                successful_clips.append(output_path)
                logger.info(f"切片 {clip_id} 提取成功")
            else:
                logger.error(f"切片 {clip_id} 提取失败")

        return successful_clips
    
    @with_async_concurrency_limit(max_concurrent=2)
    @staticmethod
    async def merge_videos_async(
        video_segments: List[Dict],
        output_path: Path,
        input_video: Optional[Path] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        use_stream_copy: bool = True,
        use_hardware_accel: bool = True
    ) -> bool:
        """
        异步合并多个视频片段
        
        有两种模式：
        1. 使用 input_video 参数：直接从原始视频中提取多个时间段并合并（效率最高）
        2. 使用已存在的视频文件路径列表：合并已存在的视频文件
        
        Args:
            video_segments: 片段数据列表，每个元素包含：
                - start_time: 开始时间（秒或FFmpeg时间格式）
                - end_time: 结束时间（秒或FFmpeg时间格式）
                - 或 video_path: 已存在的视频文件路径
            output_path: 输出视频路径
            input_video: 原始视频路径（可选，如果提供则直接从中提取片段）
            progress_callback: 进度回调函数
            use_stream_copy: 是否使用流复制
            use_hardware_accel: 是否使用硬件加速
            
        Returns:
            是否成功
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if input_video and input_video.exists():
                logger.info(f"从原始视频中提取并合并 {len(video_segments)} 个片段")
                
                filter_parts = []
                concat_inputs = []
                valid_segments = []
                
                for i, segment in enumerate(video_segments):
                    start = segment.get('start_time')
                    end = segment.get('end_time')
                    
                    if start is None or end is None:
                        logger.warning(f"片段 {i} 缺少时间信息，跳过")
                        continue
                    
                    if isinstance(start, (int, float)):
                        start_sec = float(start)
                    else:
                        start_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(
                            VideoProcessor.convert_srt_time_to_ffmpeg_time(start)
                        )
                    
                    if isinstance(end, (int, float)):
                        end_sec = float(end)
                    else:
                        end_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(
                            VideoProcessor.convert_srt_time_to_ffmpeg_time(end)
                        )
                    
                    duration = end_sec - start_sec
                    if duration <= 0:
                        logger.warning(f"片段 {i} 时长无效，跳过")
                        continue
                    
                    valid_segments.append({
                        'start_sec': start_sec,
                        'end_sec': end_sec,
                        'duration': duration
                    })
                    
                    filter_parts.append(
                        f"[0:v]trim=start={start_sec}:duration={duration},setpts=PTS-STARTPTS[v{i}]; "
                        f"[0:a]atrim=start={start_sec}:duration={duration},asetpts=PTS-STARTPTS[a{i}]"
                    )
                    concat_inputs.append(f"[v{i}][a{i}]")
                
                if not filter_parts:
                    raise VideoProcessingError(
                        message="没有有效的片段可以合并",
                        video_path=str(input_video),
                        step_name="视频合并"
                    )
                
                filter_complex = "; ".join(filter_parts)
                concat_filter = f"{''.join(concat_inputs)}concat=n={len(filter_parts)}:v=1:a=1[outv][outa]"
                full_filter = f"{filter_complex}; {concat_filter}"
                
                if use_stream_copy:
                    video_encoder = 'copy'
                    audio_encoder = 'copy'
                else:
                    video_encoder = 'h264_nvenc' if use_hardware_accel else 'libx264'
                    audio_encoder = 'aac'
                
                cmd = [
                    'ffmpeg',
                    '-i', str(input_video),
                    '-filter_complex', full_filter,
                    '-map', '[outv]',
                    '-map', '[outa]',
                    '-c:v', video_encoder,
                    '-c:a', audio_encoder,
                    '-movflags', '+faststart',
                    '-y',
                    str(output_path)
                ]
                
                if not use_stream_copy:
                    if not use_hardware_accel:
                        cmd.extend(['-preset', 'p6', '-crf', '23'])
                    cmd.extend(['-b:a', '128k'])
                
                logger.info(f"执行视频合并命令: {' '.join(cmd)}")
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                if progress_callback and valid_segments:
                    total_duration = sum(seg['duration'] for seg in valid_segments)
                    
                    while True:
                        line = await process.stderr.readline()
                        if not line:
                            break
                        line_str = line.decode('utf-8', errors='ignore')
                        time_match = re.search(r'time=(\d+):(\d+):(\d+)\.(\d+)', line_str)
                        if time_match and total_duration > 0:
                            hours = int(time_match.group(1))
                            minutes = int(time_match.group(2))
                            seconds = int(time_match.group(3))
                            centiseconds = int(time_match.group(4))
                            current_time = hours * 3600 + minutes * 60 + seconds + centiseconds / 100
                            progress = min(100, (current_time / total_duration) * 100)
                            progress_callback(progress)
                
                await process.wait()
                
                if process.returncode == 0 and output_path.exists():
                    logger.info(f"视频合并成功: {output_path}")
                    return True
                else:
                    stderr_data = await process.stderr.read()
                    logger.error(f"视频合并失败: {stderr_data.decode('utf-8', errors='ignore')}")
                    raise VideoProcessingError(
                        message="FFmpeg 视频合并失败",
                        video_path=str(input_video),
                        step_name="视频合并",
                        details={"stderr": stderr_data.decode('utf-8', errors='ignore')},
                        cause=subprocess.CalledProcessError(process.returncode, cmd)
                    )
            
            else:
                logger.info(f"合并 {len(video_segments)} 个已存在的视频文件")
                
                existing_videos = []
                for segment in video_segments:
                    video_path = segment.get('video_path')
                    if video_path:
                        path = Path(video_path)
                        if path.exists():
                            existing_videos.append(path)
                        else:
                            logger.warning(f"视频文件不存在: {video_path}")
                
                if not existing_videos:
                    raise VideoProcessingError(
                        message="没有有效的视频文件可以合并",
                        video_path="",
                        step_name="视频合并"
                    )
                
                concat_file = output_path.parent / f"concat_{output_path.stem}.txt"
                try:
                    with open(concat_file, 'w', encoding='utf-8') as f:
                        for video_path in existing_videos:
                            f.write(f"file '{video_path.absolute()}'\n")
                    
                    if use_stream_copy:
                        cmd = [
                            'ffmpeg',
                            '-f', 'concat',
                            '-safe', '0',
                            '-i', str(concat_file),
                            '-c', 'copy',
                            '-movflags', '+faststart',
                            '-y',
                            str(output_path)
                        ]
                    else:
                        video_encoder = 'h264_nvenc' if use_hardware_accel else 'libx264'
                        
                        inputs = []
                        filter_parts = []
                        concat_inputs = []
                        
                        for i, video_path in enumerate(existing_videos):
                            inputs.extend(['-i', str(video_path)])
                            filter_parts.append(f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]; [{i}:a]asetpts=PTS-STARTPTS[a{i}]")
                            concat_inputs.append(f"[v{i}][a{i}]")
                        
                        filter_complex = "; ".join(filter_parts)
                        concat_filter = f"{''.join(concat_inputs)}concat=n={len(existing_videos)}:v=1:a=1[outv][outa]"
                        full_filter = f"{filter_complex}; {concat_filter}"
                        
                        cmd = [
                            'ffmpeg',
                            *inputs,
                            '-filter_complex', full_filter,
                            '-map', '[outv]',
                            '-map', '[outa]',
                            '-c:v', video_encoder,
                            '-preset', 'p6',
                            '-crf', '23',
                            '-c:a', 'aac',
                            '-b:a', '128k',
                            '-movflags', '+faststart',
                            '-y',
                            str(output_path)
                        ]
                    
                    logger.info(f"执行视频合并命令: {' '.join(cmd)}")
                    
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    await process.wait()
                    
                    if process.returncode == 0 and output_path.exists():
                        logger.info(f"视频合并成功: {output_path}")
                        return True
                    else:
                        stderr_data = await process.stderr.read()
                        logger.error(f"视频合并失败: {stderr_data.decode('utf-8', errors='ignore')}")
                        raise VideoProcessingError(
                            message="FFmpeg 视频合并失败",
                            video_path="",
                            step_name="视频合并",
                            details={"stderr": stderr_data.decode('utf-8', errors='ignore')},
                            cause=subprocess.CalledProcessError(process.returncode, cmd)
                        )
                finally:
                    if concat_file.exists():
                        concat_file.unlink()
        
        except VideoProcessingError:
            raise
        except Exception as e:
            logger.error(f"视频合并异常: {str(e)}")
            raise VideoProcessingError(
                message=f"视频合并异常: {str(e)}",
                video_path="",
                step_name="视频合并",
                cause=e
            )
    
    @staticmethod
    def merge_videos(
        video_segments: List[Dict],
        output_path: Path,
        input_video: Optional[Path] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        use_stream_copy: bool = True,
        use_hardware_accel: bool = True
    ) -> bool:
        """
        合并多个视频片段（同步版本）
        
        Args:
            video_segments: 片段数据列表
            output_path: 输出视频路径
            input_video: 原始视频路径（可选）
            progress_callback: 进度回调函数
            use_stream_copy: 是否使用流复制
            use_hardware_accel: 是否使用硬件加速
            
        Returns:
            是否成功
        """
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                VideoProcessor.merge_videos_async(
                    video_segments,
                    output_path,
                    input_video,
                    progress_callback,
                    use_stream_copy,
                    use_hardware_accel
                )
            )
        except RuntimeError:
            import asyncio
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(
                    VideoProcessor.merge_videos_async(
                        video_segments,
                        output_path,
                        input_video,
                        progress_callback,
                        use_stream_copy,
                        use_hardware_accel
                    )
                )
            finally:
                new_loop.close()
    
    @with_async_concurrency_limit(max_concurrent=3)
    @staticmethod
    async def extract_clip_precise_async(
        input_video: Path,
        output_path: Path,
        start_time: float,
        end_time: float,
        progress_callback: Optional[Callable[[float], None]] = None,
        use_hardware_accel: bool = True
    ) -> bool:
        """
        精准提取视频片段（使用编码模式，确保帧级精确）
        
        与 extract_clip 不同，此方法总是使用编码模式（不使用流复制），
        这样可以确保在任意时间点精确切割，而不受关键帧限制。
        
        Args:
            input_video: 输入视频路径
            output_path: 输出视频路径
            start_time: 开始时间（秒，可以是浮点数如 10.5）
            end_time: 结束时间（秒，可以是浮点数如 20.3）
            progress_callback: 进度回调函数
            use_hardware_accel: 是否使用硬件加速
            
        Returns:
            是否成功
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            duration = end_time - start_time
            if duration <= 0:
                raise VideoProcessingError(
                    message="片段时长必须大于0",
                    video_path=str(input_video),
                    step_name="精准视频提取"
                )
            
            video_encoder = 'h264_nvenc' if use_hardware_accel else 'libx264'
            
            filter_complex = (
                f"[0:v]trim=start={start_time}:duration={duration},setpts=PTS-STARTPTS[outv]; "
                f"[0:a]atrim=start={start_time}:duration={duration},asetpts=PTS-STARTPTS[outa]"
            )
            
            cmd = [
                'ffmpeg',
                '-i', str(input_video),
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-map', '[outa]',
                '-c:v', video_encoder,
                '-preset', 'p6',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',
                str(output_path)
            ]
            
            logger.info(f"精准提取视频片段: start={start_time}s, end={end_time}s, 时长={duration:.3f}s")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            if progress_callback and duration > 0:
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    line_str = line.decode('utf-8', errors='ignore')
                    time_match = re.search(r'time=(\d+):(\d+):(\d+)\.(\d+)', line_str)
                    if time_match:
                        hours = int(time_match.group(1))
                        minutes = int(time_match.group(2))
                        seconds = int(time_match.group(3))
                        centiseconds = int(time_match.group(4))
                        current_time = hours * 3600 + minutes * 60 + seconds + centiseconds / 100
                        progress = min(100, (current_time / duration) * 100)
                        progress_callback(progress)
            
            await process.wait()
            
            if process.returncode == 0 and output_path.exists():
                logger.info(f"精准提取视频片段成功: {output_path}")
                return True
            else:
                stderr_data = await process.stderr.read()
                logger.error(f"精准提取视频片段失败: {stderr_data.decode('utf-8', errors='ignore')}")
                raise VideoProcessingError(
                    message="FFmpeg 精准视频提取失败",
                    video_path=str(input_video),
                    step_name="精准视频提取",
                    details={"stderr": stderr_data.decode('utf-8', errors='ignore')},
                    cause=subprocess.CalledProcessError(process.returncode, cmd)
                )
        
        except VideoProcessingError:
            raise
        except Exception as e:
            logger.error(f"精准视频提取异常: {str(e)}")
            raise VideoProcessingError(
                message=f"精准视频提取异常: {str(e)}",
                video_path=str(input_video),
                step_name="精准视频提取",
                cause=e
            )
    
    @staticmethod
    def extract_clip_precise(
        input_video: Path,
        output_path: Path,
        start_time: float,
        end_time: float,
        progress_callback: Optional[Callable[[float], None]] = None,
        use_hardware_accel: bool = True
    ) -> bool:
        """
        精准提取视频片段（同步版本）
        
        Args:
            input_video: 输入视频路径
            output_path: 输出视频路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            progress_callback: 进度回调函数
            use_hardware_accel: 是否使用硬件加速
            
        Returns:
            是否成功
        """
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                VideoProcessor.extract_clip_precise_async(
                    input_video,
                    output_path,
                    start_time,
                    end_time,
                    progress_callback,
                    use_hardware_accel
                )
            )
        except RuntimeError:
            import asyncio
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(
                    VideoProcessor.extract_clip_precise_async(
                        input_video,
                        output_path,
                        start_time,
                        end_time,
                        progress_callback,
                        use_hardware_accel
                    )
                )
            finally:
                new_loop.close()