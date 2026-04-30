"""
大文件处理性能测试
测试大视频文件和多文件导入的处理性能
"""

import sys
import os
from pathlib import Path
import time
import tempfile
import shutil
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import statistics

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

import pytest


@dataclass
class FileProcessingResult:
    """文件处理结果"""
    file_name: str
    file_size: int
    file_size_mb: float
    duration: float
    success: bool
    error: Optional[str] = None


class LargeFileProcessingTests:
    """大文件处理测试类"""
    
    def __init__(self):
        self.results: List[FileProcessingResult] = []
        self.temp_dir: Optional[Path] = None
    
    def create_test_file(self, size_mb: float, name: str = "test_video.mp4") -> Path:
        """
        创建测试文件（模拟视频文件）
        
        Args:
            size_mb: 文件大小（MB）
            name: 文件名
            
        Returns:
            文件路径
        """
        if not self.temp_dir:
            self.temp_dir = Path(tempfile.mkdtemp())
        
        file_path = self.temp_dir / name
        size_bytes = int(size_mb * 1024 * 1024)
        
        with open(file_path, 'wb') as f:
            chunk_size = 1024 * 1024
            chunks = size_bytes // chunk_size
            remainder = size_bytes % chunk_size
            
            for _ in range(chunks):
                f.write(os.urandom(chunk_size))
            
            if remainder > 0:
                f.write(os.urandom(remainder))
        
        return file_path
    
    def create_test_srt_file(self, duration_seconds: int = 3600) -> Path:
        """
        创建测试字幕文件
        
        Args:
            duration_seconds: 视频时长（秒）
            
        Returns:
            字幕文件路径
        """
        if not self.temp_dir:
            self.temp_dir = Path(tempfile.mkdtemp())
        
        srt_path = self.temp_dir / "test_subtitle.srt"
        
        with open(srt_path, 'w', encoding='utf-8') as f:
            subtitle_count = min(duration_seconds // 10, 1000)
            for i in range(subtitle_count):
                start_sec = i * 10
                end_sec = start_sec + 8
                
                start_time = self._format_srt_time(start_sec)
                end_time = self._format_srt_time(end_sec)
                
                f.write(f"{i+1}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"这是第 {i+1} 条字幕内容\n\n")
        
        return srt_path
    
    def _format_srt_time(self, seconds: int) -> str:
        """格式化 SRT 时间戳"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},000"
    
    def simulate_file_copy(self, source_path: Path, dest_path: Path) -> float:
        """
        模拟文件复制操作
        
        Args:
            source_path: 源文件路径
            dest_path: 目标文件路径
            
        Returns:
            耗时（秒）
        """
        start_time = time.perf_counter()
        shutil.copy2(source_path, dest_path)
        return time.perf_counter() - start_time
    
    def simulate_file_read(self, file_path: Path, chunk_size: int = 1024 * 1024) -> float:
        """
        模拟文件读取操作
        
        Args:
            file_path: 文件路径
            chunk_size: 块大小
            
        Returns:
            耗时（秒）
        """
        start_time = time.perf_counter()
        file_size = file_path.stat().st_size
        
        with open(file_path, 'rb') as f:
            bytes_read = 0
            while bytes_read < file_size:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                bytes_read += len(chunk)
        
        return time.perf_counter() - start_time
    
    def test_single_large_file(self, size_mb: float = 100) -> FileProcessingResult:
        """
        测试单个大文件处理
        
        Args:
            size_mb: 文件大小（MB）
            
        Returns:
            处理结果
        """
        print(f"\n{'='*60}")
        print(f"测试单个大文件: {size_mb} MB")
        print(f"{'='*60}")
        
        try:
            file_path = self.create_test_file(size_mb, f"large_{size_mb}mb.mp4")
            file_size = file_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            print(f"文件创建完成: {file_size_mb:.2f} MB")
            
            read_time = self.simulate_file_read(file_path)
            print(f"文件读取耗时: {read_time:.4f} 秒")
            print(f"读取速度: {file_size_mb / read_time:.2f} MB/s")
            
            dest_path = file_path.parent / f"copy_{file_path.name}"
            copy_time = self.simulate_file_copy(file_path, dest_path)
            print(f"文件复制耗时: {copy_time:.4f} 秒")
            print(f"复制速度: {file_size_mb / copy_time:.2f} MB/s")
            
            total_time = read_time + copy_time
            
            result = FileProcessingResult(
                file_name=file_path.name,
                file_size=file_size,
                file_size_mb=file_size_mb,
                duration=total_time,
                success=True
            )
            self.results.append(result)
            
            print(f"\n总耗时: {total_time:.4f} 秒")
            
            return result
            
        except Exception as e:
            result = FileProcessingResult(
                file_name=f"large_{size_mb}mb.mp4",
                file_size=int(size_mb * 1024 * 1024),
                file_size_mb=size_mb,
                duration=0,
                success=False,
                error=str(e)
            )
            self.results.append(result)
            print(f"❌ 测试失败: {e}")
            return result
    
    def test_multiple_files(self, file_count: int = 5, size_mb_per_file: float = 50) -> List[FileProcessingResult]:
        """
        测试多文件处理
        
        Args:
            file_count: 文件数量
            size_mb_per_file: 每个文件大小（MB）
            
        Returns:
            处理结果列表
        """
        print(f"\n{'='*60}")
        print(f"测试多文件处理: {file_count} 个文件，每个 {size_mb_per_file} MB")
        print(f"{'='*60}")
        
        total_size_mb = file_count * size_mb_per_file
        print(f"总大小: {total_size_mb} MB")
        
        start_time = time.perf_counter()
        
        results = []
        for i in range(file_count):
            print(f"\n处理文件 {i+1}/{file_count}...")
            result = self.test_single_large_file(size_mb_per_file)
            results.append(result)
        
        total_time = time.perf_counter() - start_time
        successful = sum(1 for r in results if r.success)
        
        print(f"\n{'='*60}")
        print("多文件处理结果汇总")
        print(f"{'='*60}")
        print(f"文件数量: {file_count}")
        print(f"成功处理: {successful}/{file_count}")
        print(f"总大小: {total_size_mb:.2f} MB")
        print(f"总耗时: {total_time:.4f} 秒")
        print(f"平均速度: {total_size_mb / total_time:.2f} MB/s")
        
        return results
    
    def test_different_file_sizes(self) -> Dict[float, FileProcessingResult]:
        """
        测试不同大小文件的处理性能
        
        Returns:
            测试结果字典
        """
        print(f"\n{'='*60}")
        print("测试不同大小文件的处理性能")
        print(f"{'='*60}")
        
        test_sizes = [10, 50, 100, 200, 500]
        results = {}
        
        for size in test_sizes:
            result = self.test_single_large_file(size)
            results[size] = result
        
        print(f"\n{'='*60}")
        print("不同大小文件处理结果汇总")
        print(f"{'='*60}")
        print(f"\n{'大小(MB)':<12} {'耗时(s)':<12} {'速度(MB/s)':<15} {'状态'}")
        print(f"{'-'*12} {'-'*12} {'-'*15} {'-'*10}")
        
        for size, result in results.items():
            if result.success:
                speed = result.file_size_mb / result.duration if result.duration > 0 else 0
                status = "✅ 成功"
            else:
                speed = 0
                status = f"❌ 失败: {result.error}"
            
            print(f"{size:<12} {result.duration:<12.4f} {speed:<15.2f} {status}")
        
        return results
    
    def test_srt_file_performance(self, duration_seconds: int = 3600) -> Dict[str, Any]:
        """
        测试字幕文件处理性能
        
        Args:
            duration_seconds: 视频时长（秒）
            
        Returns:
            测试结果
        """
        print(f"\n{'='*60}")
        print(f"测试字幕文件处理性能（{duration_seconds/3600:.1f} 小时视频）")
        print(f"{'='*60}")
        
        start_time = time.perf_counter()
        srt_path = self.create_test_srt_file(duration_seconds)
        create_time = time.perf_counter() - start_time
        
        file_size = srt_path.stat().st_size
        file_size_kb = file_size / 1024
        
        print(f"字幕文件创建完成: {file_size_kb:.2f} KB")
        print(f"创建耗时: {create_time:.4f} 秒")
        
        start_time = time.perf_counter()
        subtitle_count = 0
        with open(srt_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '-->' in line:
                    subtitle_count += 1
        parse_time = time.perf_counter() - start_time
        
        print(f"字幕条数: {subtitle_count}")
        print(f"解析耗时: {parse_time:.4f} 秒")
        
        return {
            "file_path": str(srt_path),
            "file_size_bytes": file_size,
            "file_size_kb": file_size_kb,
            "subtitle_count": subtitle_count,
            "create_time": create_time,
            "parse_time": parse_time,
            "total_time": create_time + parse_time
        }
    
    def run_benchmark_suite(self):
        """运行完整的基准测试套件"""
        print(f"\n{'='*70}")
        print("大文件处理性能基准测试套件")
        print(f"{'='*70}")
        
        try:
            print("\n1. 测试不同大小的单个文件...")
            size_results = self.test_different_file_sizes()
            
            print("\n2. 测试多文件处理...")
            multi_results = self.test_multiple_files(file_count=5, size_mb_per_file=20)
            
            print("\n3. 测试字幕文件处理...")
            srt_results = self.test_srt_file_performance(duration_seconds=7200)
            
            print(f"\n{'='*70}")
            print("基准测试完成")
            print(f"{'='*70}")
            
            return {
                "single_file_tests": size_results,
                "multi_file_tests": multi_results,
                "srt_test": srt_results
            }
            
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                print(f"\n已清理临时目录: {self.temp_dir}")
            except Exception as e:
                print(f"清理临时目录失败: {e}")


def run_large_file_benchmarks():
    """运行大文件处理基准测试"""
    import argparse
    
    parser = argparse.ArgumentParser(description='大文件处理性能基准测试')
    parser.add_argument('--single', type=float, default=None, help='测试单个文件大小（MB）')
    parser.add_argument('--multi-count', type=int, default=5, help='多文件测试的文件数量')
    parser.add_argument('--multi-size', type=float, default=50, help='多文件测试每个文件大小（MB）')
    parser.add_argument('--srt-duration', type=int, default=3600, help='字幕文件测试时长（秒）')
    parser.add_argument('--full-suite', action='store_true', help='运行完整测试套件')
    
    args = parser.parse_args()
    
    tester = LargeFileProcessingTests()
    
    try:
        if args.full_suite:
            return tester.run_benchmark_suite()
        
        if args.single:
            return tester.test_single_large_file(args.single)
        
        if args.multi_count and args.multi_size:
            return tester.test_multiple_files(args.multi_count, args.multi_size)
        
        if args.srt_duration:
            return tester.test_srt_file_performance(args.srt_duration)
        
        print("请指定测试参数，使用 --help 查看帮助")
        return None
        
    finally:
        tester.cleanup()


if __name__ == "__main__":
    run_large_file_benchmarks()
