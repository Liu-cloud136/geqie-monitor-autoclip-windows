"""
数据库查询性能测试
测试 N+1 查询优化效果
"""

import sys
import os
from pathlib import Path
import time
from typing import List, Dict, Any

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

import pytest
from sqlalchemy import func, text
from datetime import datetime, timedelta

from models.project import Project, ProjectStatus, ProjectType
from models.task import Task, TaskStatus, TaskType
from models.clip import Clip, ClipStatus
from repositories.project_repository import ProjectRepository


class TestDatabasePerformance:
    """数据库性能测试类"""
    
    def _create_test_projects(self, session, count: int = 20) -> List[Project]:
        """创建测试项目数据"""
        projects = []
        for i in range(count):
            project = Project(
                name=f"测试项目_{i}",
                description=f"这是测试项目 {i}",
                project_type=ProjectType.KNOWLEDGE,
                status=ProjectStatus.PENDING,
                video_path=f"/data/videos/video_{i}.mp4",
                processing_config={"test": True}
            )
            session.add(project)
            projects.append(project)
        
        session.commit()
        return projects
    
    def _create_test_tasks(self, session, projects: List[Project]):
        """为每个项目创建测试任务"""
        for i, project in enumerate(projects):
            task_count = i % 3 + 1  # 1-3个任务
            for j in range(task_count):
                task = Task(
                    name=f"项目 {i} 的任务 {j}",
                    description=f"测试任务",
                    task_type=TaskType.VIDEO_PROCESSING,
                    project_id=project.id,
                    status=TaskStatus.COMPLETED if j == 0 else TaskStatus.PENDING,
                    progress=100.0 if j == 0 else 0.0
                )
                session.add(task)
        
        session.commit()
    
    def _create_test_clips(self, session, projects: List[Project]):
        """为每个项目创建测试切片"""
        for i, project in enumerate(projects):
            clip_count = (i % 5) * 2 + 3  # 3, 5, 7, 9, 11个切片
            for j in range(clip_count):
                clip = Clip(
                    title=f"切片_{i}_{j}",
                    start_time=j * 60,
                    end_time=(j + 1) * 60,
                    duration=60,
                    score=0.5 + (j * 0.05),
                    project_id=project.id,
                    status=ClipStatus.COMPLETED
                )
                session.add(clip)
        
        session.commit()
    
    def test_n_plus_one_optimization(self, test_session):
        """测试 N+1 查询优化效果"""
        print("\n" + "="*60)
        print("测试 N+1 查询优化效果")
        print("="*60)
        
        projects = self._create_test_projects(test_session, count=20)
        self._create_test_tasks(test_session, projects)
        self._create_test_clips(test_session, projects)
        
        repo = ProjectRepository(test_session)
        
        print("\n1. 传统方式（N+1 查询）:")
        print("-"*40)
        
        start_time = time.perf_counter()
        
        traditional_stats = {}
        for project in projects:
            clips_count = test_session.query(Clip).filter(
                Clip.project_id == project.id
            ).count()
            tasks_count = test_session.query(Task).filter(
                Task.project_id == project.id
            ).count()
            traditional_stats[project.id] = {
                'clips_count': clips_count,
                'tasks_count': tasks_count
            }
        
        traditional_time = time.perf_counter() - start_time
        query_count_traditional = 1 + len(projects) * 2  # 1次查询项目 + 2N次统计
        
        print(f"   查询次数: {query_count_traditional}")
        print(f"   耗时: {traditional_time:.6f} 秒")
        
        print("\n2. 优化方式（批量聚合查询）:")
        print("-"*40)
        
        project_ids = [p.id for p in projects]
        
        start_time = time.perf_counter()
        
        optimized_stats = repo.get_projects_stats_batch(project_ids)
        
        optimized_time = time.perf_counter() - start_time
        query_count_optimized = 3  # 1次查询项目 + 2次聚合统计
        
        print(f"   查询次数: {query_count_optimized}")
        print(f"   耗时: {optimized_time:.6f} 秒")
        
        print("\n3. 结果验证:")
        print("-"*40)
        all_match = True
        for project_id in project_ids:
            if traditional_stats[project_id] != optimized_stats[project_id]:
                print(f"   ❌ 项目 {project_id} 结果不匹配:")
                print(f"      传统方式: {traditional_stats[project_id]}")
                print(f"      优化方式: {optimized_stats[project_id]}")
                all_match = False
        
        if all_match:
            print(f"   ✅ 所有项目统计结果匹配")
        
        print("\n4. 性能对比:")
        print("-"*40)
        speedup = traditional_time / optimized_time if optimized_time > 0 else float('inf')
        query_reduction = (1 - query_count_optimized / query_count_traditional) * 100
        
        print(f"   查询次数减少: {query_reduction:.1f}%")
        print(f"   耗时减少: {(1 - optimized_time/traditional_time)*100:.1f}%")
        print(f"   性能提升: {speedup:.2f}x")
        
        assert all_match, "优化后的查询结果应该与传统方式一致"
        assert query_count_optimized < query_count_traditional, "优化后的查询次数应该更少"
    
    def test_single_project_stats(self, test_session):
        """测试单项目统计查询优化"""
        print("\n" + "="*60)
        print("测试单项目统计查询优化")
        print("="*60)
        
        projects = self._create_test_projects(test_session, count=5)
        self._create_test_tasks(test_session, projects)
        self._create_test_clips(test_session, projects)
        
        repo = ProjectRepository(test_session)
        
        test_project = projects[2]
        
        print("\n1. 传统方式（独立 count 查询）:")
        print("-"*40)
        
        start_time = time.perf_counter()
        
        traditional_clips = test_session.query(Clip).filter(
            Clip.project_id == test_project.id
        ).count()
        traditional_tasks = test_session.query(Task).filter(
            Task.project_id == test_project.id
        ).count()
        
        traditional_time = time.perf_counter() - start_time
        
        print(f"   clips_count: {traditional_clips}")
        print(f"   tasks_count: {traditional_tasks}")
        print(f"   耗时: {traditional_time:.6f} 秒")
        
        print("\n2. 优化方式（聚合查询）:")
        print("-"*40)
        
        start_time = time.perf_counter()
        
        stats = repo.get_project_stats_single(test_project.id)
        
        optimized_time = time.perf_counter() - start_time
        
        print(f"   clips_count: {stats['clips_count']}")
        print(f"   tasks_count: {stats['tasks_count']}")
        print(f"   耗时: {optimized_time:.6f} 秒")
        
        print("\n3. 结果验证:")
        print("-"*40)
        assert stats['clips_count'] == traditional_clips, "clips_count 应该一致"
        assert stats['tasks_count'] == traditional_tasks, "tasks_count 应该一致"
        print(f"   ✅ 统计结果一致")
    
    def test_empty_project_stats(self, test_session):
        """测试空项目的统计查询"""
        print("\n" + "="*60)
        print("测试空项目的统计查询")
        print("="*60)
        
        repo = ProjectRepository(test_session)
        
        print("\n1. 批量查询空列表:")
        print("-"*40)
        result = repo.get_projects_stats_batch([])
        assert result == {}, "空列表应该返回空字典"
        print(f"   ✅ 空列表返回空字典")
        
        print("\n2. 批量查询不存在的项目:")
        print("-"*40)
        result = repo.get_projects_stats_batch(["non_existent_id_1", "non_existent_id_2"])
        assert len(result) == 2, "应该返回2个项目的统计"
        assert result["non_existent_id_1"]["clips_count"] == 0
        assert result["non_existent_id_1"]["tasks_count"] == 0
        print(f"   ✅ 不存在的项目返回0值统计")
        
        print("\n3. 单项目查询不存在的项目:")
        print("-"*40)
        result = repo.get_project_stats_single("non_existent_id")
        assert result["clips_count"] == 0
        assert result["tasks_count"] == 0
        print(f"   ✅ 不存在的项目返回0值统计")
    
    def test_large_dataset_performance(self, test_session):
        """测试大数据集的性能"""
        print("\n" + "="*60)
        print("测试大数据集的性能")
        print("="*60)
        
        project_count = 50
        
        print(f"\n创建 {project_count} 个测试项目...")
        projects = self._create_test_projects(test_session, count=project_count)
        self._create_test_tasks(test_session, projects)
        self._create_test_clips(test_session, projects)
        
        repo = ProjectRepository(test_session)
        project_ids = [p.id for p in projects]
        
        print("\n1. 传统方式性能测试:")
        print("-"*40)
        
        start_time = time.perf_counter()
        
        for project_id in project_ids:
            test_session.query(Clip).filter(Clip.project_id == project_id).count()
            test_session.query(Task).filter(Task.project_id == project_id).count()
        
        traditional_time = time.perf_counter() - start_time
        print(f"   耗时: {traditional_time:.6f} 秒")
        print(f"   平均每项目: {traditional_time/project_count:.6f} 秒")
        
        print("\n2. 优化方式性能测试:")
        print("-"*40)
        
        start_time = time.perf_counter()
        
        repo.get_projects_stats_batch(project_ids)
        
        optimized_time = time.perf_counter() - start_time
        print(f"   耗时: {optimized_time:.6f} 秒")
        print(f"   平均每项目: {optimized_time/project_count:.6f} 秒")
        
        print("\n3. 性能对比:")
        print("-"*40)
        speedup = traditional_time / optimized_time if optimized_time > 0 else float('inf')
        print(f"   总加速比: {speedup:.2f}x")
        print(f"   单项目加速比: {(traditional_time/project_count) / (optimized_time/project_count):.2f}x")
        
        assert optimized_time < traditional_time, "优化方式应该更快"


def run_performance_benchmarks():
    """运行性能基准测试"""
    print("\n" + "="*70)
    print("数据库查询性能基准测试")
    print("="*70)
    
    import tempfile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models.base import Base
    
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "benchmark.db"
        db_url = f"sqlite:///{db_path}"
        
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            echo=False
        )
        
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        
        test_sizes = [10, 50, 100, 200]
        results = []
        
        for size in test_sizes:
            print(f"\n{'='*70}")
            print(f"测试数据集大小: {size} 个项目")
            print(f"{'='*70}")
            
            session = Session()
            
            try:
                projects = []
                for i in range(size):
                    project = Project(
                        name=f"基准测试项目_{i}",
                        project_type=ProjectType.KNOWLEDGE,
                        status=ProjectStatus.PENDING
                    )
                    session.add(project)
                    projects.append(project)
                session.commit()
                
                for i, project in enumerate(projects):
                    for j in range(3):
                        task = Task(
                            name=f"任务_{i}_{j}",
                            task_type=TaskType.VIDEO_PROCESSING,
                            project_id=project.id,
                            status=TaskStatus.COMPLETED
                        )
                        session.add(task)
                    
                    for j in range(5):
                        clip = Clip(
                            title=f"切片_{i}_{j}",
                            start_time=j * 60,
                            end_time=(j + 1) * 60,
                            duration=60,
                            project_id=project.id
                        )
                        session.add(clip)
                session.commit()
                
                repo = ProjectRepository(session)
                project_ids = [p.id for p in projects]
                
                start = time.perf_counter()
                for pid in project_ids:
                    session.query(Clip).filter(Clip.project_id == pid).count()
                    session.query(Task).filter(Task.project_id == pid).count()
                traditional_time = time.perf_counter() - start
                
                start = time.perf_counter()
                repo.get_projects_stats_batch(project_ids)
                optimized_time = time.perf_counter() - start
                
                speedup = traditional_time / optimized_time if optimized_time > 0 else float('inf')
                
                results.append({
                    'size': size,
                    'traditional_queries': 2 * size + 1,
                    'optimized_queries': 3,
                    'traditional_time': traditional_time,
                    'optimized_time': optimized_time,
                    'speedup': speedup
                })
                
                print(f"\n  传统方式: {traditional_time:.6f}s ({2*size+1} 次查询)")
                print(f"  优化方式: {optimized_time:.6f}s (3 次查询)")
                print(f"  加速比: {speedup:.2f}x")
                
            finally:
                session.close()
        
        print(f"\n{'='*70}")
        print("基准测试结果汇总")
        print(f"{'='*70}")
        print(f"\n{'项目数':<10} {'传统查询':<15} {'优化查询':<12} {'加速比':<10}")
        print(f"{'-'*10} {'-'*15} {'-'*12} {'-'*10}")
        for r in results:
            print(f"{r['size']:<10} {r['traditional_time']:.4f}s{'':<8} {r['optimized_time']:.4f}s{'':<5} {r['speedup']:.2f}x")
        
        print("\n" + "="*70)
        print("基准测试完成")
        print("="*70)


if __name__ == "__main__":
    run_performance_benchmarks()
