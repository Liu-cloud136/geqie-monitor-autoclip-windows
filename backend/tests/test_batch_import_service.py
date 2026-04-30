"""
批量导入服务测试
测试并行导入功能和性能
"""

import sys
import os
from pathlib import Path
import time
import tempfile
import threading
from typing import List, Dict, Any

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

import pytest
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

from services.batch_import_service import (
    BatchImportService,
    ImportTask,
    get_batch_import_service
)


class TestImportTask:
    """ImportTask 数据类测试"""
    
    def test_import_task_creation(self):
        """测试导入任务创建"""
        task = ImportTask(
            task_id="test_id_123",
            video_path=Path("/test/video.mp4"),
            project_name="测试项目",
            project_type="knowledge",
            srt_path=Path("/test/subtitle.srt")
        )
        
        assert task.task_id == "test_id_123"
        assert task.video_path == Path("/test/video.mp4")
        assert task.project_name == "测试项目"
        assert task.project_type == "knowledge"
        assert task.srt_path == Path("/test/subtitle.srt")
        assert task.status == "pending"
        assert task.error_message is None
        assert task.project_id is None
        assert task.celery_task_id is None
    
    def test_import_task_defaults(self):
        """测试导入任务默认值"""
        task = ImportTask(
            task_id="test_id",
            video_path=Path("/test/video.mp4"),
            project_name="测试项目"
        )
        
        assert task.project_type == "default"
        assert task.srt_path is None
        assert task.danmaku_path is None
        assert task.status == "pending"


class TestBatchImportService:
    """BatchImportService 测试"""
    
    def test_service_initialization(self):
        """测试服务初始化"""
        service = BatchImportService(max_concurrent=5)
        
        assert service.max_concurrent == 5
        assert service._import_tasks == {}
        assert service._completed_count == 0
        assert service._failed_count == 0
    
    def test_service_default_concurrency(self):
        """测试默认并发数"""
        from config.import_config import MAX_CONCURRENT_IMPORTS
        
        service = BatchImportService()
        assert service.max_concurrent == MAX_CONCURRENT_IMPORTS
    
    def test_create_import_task(self):
        """测试创建导入任务"""
        service = BatchImportService()
        
        video_path = Path("/test/video.mp4")
        task = service.create_import_task(
            video_path=video_path,
            project_name="测试项目",
            project_type="knowledge"
        )
        
        assert task.video_path == video_path
        assert task.project_name == "测试项目"
        assert task.project_type == "knowledge"
        assert task.task_id in service._import_tasks
    
    def test_create_import_task_with_srt(self):
        """测试创建带字幕的导入任务"""
        service = BatchImportService()
        
        video_path = Path("/test/video.mp4")
        srt_path = Path("/test/subtitle.srt")
        
        task = service.create_import_task(
            video_path=video_path,
            project_name="测试项目",
            srt_path=srt_path
        )
        
        assert task.srt_path == srt_path
        assert task.task_id in service._import_tasks
    
    def test_get_task_status(self):
        """测试获取任务状态"""
        service = BatchImportService()
        
        video_path = Path("/test/video.mp4")
        task = service.create_import_task(
            video_path=video_path,
            project_name="测试项目"
        )
        
        status = service.get_task_status(task.task_id)
        
        assert status is not None
        assert status["task_id"] == task.task_id
        assert status["video_path"] == str(video_path)
        assert status["project_name"] == "测试项目"
        assert status["status"] == "pending"
    
    def test_get_task_status_nonexistent(self):
        """测试获取不存在的任务状态"""
        service = BatchImportService()
        
        status = service.get_task_status("non_existent_id")
        assert status is None
    
    def test_get_all_tasks(self):
        """测试获取所有任务"""
        service = BatchImportService()
        
        for i in range(3):
            service.create_import_task(
                video_path=Path(f"/test/video_{i}.mp4"),
                project_name=f"项目 {i}"
            )
        
        all_tasks = service.get_all_tasks()
        
        assert len(all_tasks) == 3
        for task in all_tasks:
            assert "task_id" in task
            assert "video_path" in task
            assert "status" in task
    
    def test_get_statistics_empty(self):
        """测试空统计信息"""
        service = BatchImportService(max_concurrent=5)
        
        stats = service.get_statistics()
        
        assert stats["total"] == 0
        assert stats["pending"] == 0
        assert stats["processing"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0
        assert stats["max_concurrent"] == 5
    
    def test_get_statistics_with_tasks(self):
        """测试有任务的统计信息"""
        service = BatchImportService()
        
        for i in range(5):
            service.create_import_task(
                video_path=Path(f"/test/video_{i}.mp4"),
                project_name=f"项目 {i}"
            )
        
        stats = service.get_statistics()
        
        assert stats["total"] == 5
        assert stats["pending"] == 5
        assert stats["completed"] == 0
        assert stats["failed"] == 0


class TestBatchImportServiceThreadSafety:
    """BatchImportService 线程安全测试"""
    
    def test_concurrent_task_creation(self):
        """测试并发创建任务"""
        service = BatchImportService()
        task_count = 50
        barrier = threading.Barrier(task_count)
        
        def create_task(index: int):
            barrier.wait()
            service.create_import_task(
                video_path=Path(f"/test/video_{index}.mp4"),
                project_name=f"项目 {index}"
            )
        
        threads = []
        for i in range(task_count):
            thread = threading.Thread(target=create_task, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        stats = service.get_statistics()
        assert stats["total"] == task_count
        assert stats["pending"] == task_count
    
    def test_concurrent_status_read(self):
        """测试并发读取任务状态"""
        service = BatchImportService()
        
        for i in range(10):
            service.create_import_task(
                video_path=Path(f"/test/video_{i}.mp4"),
                project_name=f"项目 {i}"
            )
        
        all_tasks = service.get_all_tasks()
        task_ids = [task["task_id"] for task in all_tasks]
        
        read_count = 100
        results = []
        barrier = threading.Barrier(len(task_ids))
        
        def read_task_status(task_id: str):
            barrier.wait()
            for _ in range(read_count):
                status = service.get_task_status(task_id)
                if status:
                    results.append(status["task_id"])
        
        threads = []
        for task_id in task_ids:
            thread = threading.Thread(target=read_task_status, args=(task_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert len(results) == len(task_ids) * read_count


class TestGlobalServiceInstance:
    """全局服务实例测试"""
    
    def test_get_batch_import_service_returns_singleton(self):
        """测试全局服务单例"""
        service1 = get_batch_import_service()
        service2 = get_batch_import_service()
        
        assert service1 is service2
    
    def test_get_batch_import_service_returns_valid_instance(self):
        """测试全局服务实例有效性"""
        service = get_batch_import_service()
        
        assert isinstance(service, BatchImportService)
        assert service.max_concurrent is not None


class TestBatchImportPerformance:
    """批量导入性能测试"""
    
    def test_progress_callback(self):
        """测试进度回调"""
        service = BatchImportService()
        
        progress_updates = []
        
        def mock_progress_callback(completed: int, total: int, task_id: str):
            progress_updates.append({
                "completed": completed,
                "total": total,
                "task_id": task_id
            })
        
        with patch.object(service, '_import_videos_serial') as mock_serial:
            mock_serial.return_value = [
                {"success": True, "task_id": "task1"},
                {"success": True, "task_id": "task2"},
            ]
            
            video_files = [
                {"video_path": Path("/test/v1.mp4"), "project_name": "p1"},
                {"video_path": Path("/test/v2.mp4"), "project_name": "p2"},
            ]
            
            service.import_videos_parallel(video_files, mock_progress_callback)
    
    def test_import_videos_parallel_with_empty_list(self):
        """测试空列表导入"""
        service = BatchImportService()
        
        results = service.import_videos_parallel([])
        
        assert results == []
    
    def test_import_videos_parallel_task_creation(self):
        """测试导入任务创建"""
        service = BatchImportService()
        
        video_files = [
            {"video_path": "/test/v1.mp4", "project_name": "项目1"},
            {"video_path": "/test/v2.mp4", "project_name": "项目2"},
            {"video_path": "/test/v3.mp4", "project_name": "项目3"},
        ]
        
        with patch.object(service, '_import_videos_serial') as mock_serial:
            mock_serial.return_value = []
            
            service.import_videos_parallel(video_files)
        
        stats = service.get_statistics()
        assert stats["total"] == 3


class TestImportTaskEdgeCases:
    """导入任务边缘情况测试"""
    
    def test_import_task_with_none_srt(self):
        """测试 None 字幕路径"""
        task = ImportTask(
            task_id="test",
            video_path=Path("/test/video.mp4"),
            project_name="测试",
            srt_path=None
        )
        
        assert task.srt_path is None
    
    def test_import_task_with_none_danmaku(self):
        """测试 None 弹幕路径"""
        task = ImportTask(
            task_id="test",
            video_path=Path("/test/video.mp4"),
            project_name="测试",
            danmaku_path=None
        )
        
        assert task.danmaku_path is None
    
    def test_import_task_status_transitions(self):
        """测试任务状态转换"""
        task = ImportTask(
            task_id="test",
            video_path=Path("/test/video.mp4"),
            project_name="测试"
        )
        
        assert task.status == "pending"
        
        task.status = "processing"
        assert task.status == "processing"
        
        task.status = "queued"
        assert task.status == "queued"
        
        task.status = "completed"
        assert task.status == "completed"
        
        task.status = "failed"
        assert task.status == "failed"
        
        task.status = "partial"
        assert task.status == "partial"


def run_batch_import_benchmarks():
    """运行批量导入基准测试"""
    print("\n" + "="*70)
    print("批量导入服务基准测试")
    print("="*70)
    
    import time
    
    test_sizes = [5, 10, 20, 50]
    concurrency_levels = [1, 2, 4, 8]
    
    results = {}
    
    for size in test_sizes:
        print(f"\n{'='*70}")
        print(f"测试任务数量: {size}")
        print(f"{'='*70}")
        
        size_results = {}
        
        for concurrency in concurrency_levels:
            service = BatchImportService(max_concurrent=concurrency)
            
            video_files = [
                {
                    "video_path": Path(f"/test/video_{i}.mp4"),
                    "project_name": f"项目 {i}"
                }
                for i in range(size)
            ]
            
            start_time = time.perf_counter()
            
            with patch.object(service, '_execute_single_import') as mock_execute:
                def mock_exec(task):
                    time.sleep(0.01)
                    return {
                        "success": True,
                        "task_id": task.task_id,
                        "project_id": f"proj_{task.task_id}"
                    }
                
                mock_execute.side_effect = mock_exec
                
                with patch.object(service, '_import_videos_serial') as mock_serial:
                    with ThreadPoolExecutor(max_workers=concurrency) as executor:
                        tasks = []
                        for vf in video_files:
                            task = service.create_import_task(
                                video_path=vf["video_path"],
                                project_name=vf["project_name"]
                            )
                            tasks.append(task)
                        
                        start = time.perf_counter()
                        futures = [executor.submit(mock_exec, t) for t in tasks]
                        for f in futures:
                            f.result()
                        elapsed = time.perf_counter() - start
            
            size_results[concurrency] = elapsed
            
            print(f"  并发数 {concurrency}: {elapsed:.4f}s")
        
        results[size] = size_results
    
    print(f"\n{'='*70}")
    print("基准测试结果汇总")
    print(f"{'='*70}")
    
    print(f"\n{'任务数':<10} {'并发=1':<12} {'并发=2':<12} {'并发=4':<12} {'并发=8':<12}")
    print(f"{'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")
    
    for size in test_sizes:
        row = [f"{size}"]
        for concurrency in concurrency_levels:
            if concurrency in results[size]:
                row.append(f"{results[size][concurrency]:.4f}s")
            else:
                row.append("-")
        print(f"{row[0]:<10} {row[1]:<12} {row[2]:<12} {row[3]:<12} {row[4]:<12}")
    
    print("\n" + "="*70)
    print("基准测试完成")
    print("="*70)


if __name__ == "__main__":
    run_batch_import_benchmarks()
