"""
模型单元测试
测试数据模型的定义和行为
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

import pytest
from sqlalchemy import func


class TestProjectModel:
    """Project 模型测试"""
    
    def test_project_creation(self, test_session):
        """测试项目创建"""
        from models.project import Project, ProjectStatus, ProjectType
        
        project = Project(
            name="测试项目",
            description="这是一个测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING,
            video_path="/data/test.mp4"
        )
        
        test_session.add(project)
        test_session.commit()
        
        assert project.id is not None
        assert project.name == "测试项目"
        assert project.description == "这是一个测试项目"
        assert project.project_type == ProjectType.KNOWLEDGE
        assert project.status == ProjectStatus.PENDING
        assert project.video_path == "/data/test.mp4"
        assert project.created_at is not None
        assert project.updated_at is not None
    
    def test_project_status_transitions(self, test_session):
        """测试项目状态转换"""
        from models.project import Project, ProjectStatus, ProjectType
        
        project = Project(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        test_session.add(project)
        test_session.commit()
        
        project.status = ProjectStatus.PROCESSING
        test_session.commit()
        assert project.status == ProjectStatus.PROCESSING
        
        project.status = ProjectStatus.COMPLETED
        project.completed_at = datetime.utcnow()
        test_session.commit()
        assert project.status == ProjectStatus.COMPLETED
        assert project.completed_at is not None
        
        project.status = ProjectStatus.FAILED
        test_session.commit()
        assert project.status == ProjectStatus.FAILED
    
    def test_project_with_metadata(self, test_session):
        """测试项目元数据"""
        from models.project import Project, ProjectStatus, ProjectType
        
        project = Project(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING,
            project_metadata={
                "source_url": "http://example.com/video.mp4",
                "original_filename": "video.mp4",
                "duration": 3600
            },
            processing_config={
                "resolution": "1080p",
                "fps": 30,
                "subtitle_mode": "ai_generated"
            }
        )
        test_session.add(project)
        test_session.commit()
        
        assert project.project_metadata["source_url"] == "http://example.com/video.mp4"
        assert project.project_metadata["duration"] == 3600
        assert project.processing_config["resolution"] == "1080p"
        assert project.processing_config["subtitle_mode"] == "ai_generated"
    
    def test_project_query_by_status(self, test_session):
        """测试按状态查询项目"""
        from models.project import Project, ProjectStatus, ProjectType
        
        for i in range(5):
            project = Project(
                name=f"项目 {i}",
                project_type=ProjectType.KNOWLEDGE,
                status=ProjectStatus.COMPLETED if i < 3 else ProjectStatus.PROCESSING
            )
            test_session.add(project)
        test_session.commit()
        
        completed_count = test_session.query(Project).filter(
            Project.status == ProjectStatus.COMPLETED
        ).count()
        assert completed_count == 3
        
        processing_count = test_session.query(Project).filter(
            Project.status == ProjectStatus.PROCESSING
        ).count()
        assert processing_count == 2


class TestTaskModel:
    """Task 模型测试"""
    
    def test_task_creation(self, test_session):
        """测试任务创建"""
        from models.project import Project, ProjectStatus, ProjectType
        from models.task import Task, TaskStatus, TaskType
        
        project = Project(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        test_session.add(project)
        test_session.commit()
        
        task = Task(
            name="视频处理任务",
            description="处理视频生成剪辑",
            task_type=TaskType.VIDEO_PROCESSING,
            project_id=project.id,
            status=TaskStatus.PENDING,
            current_step="step_1",
            total_steps=5,
            progress=0.0
        )
        test_session.add(task)
        test_session.commit()
        
        assert task.id is not None
        assert task.name == "视频处理任务"
        assert task.task_type == TaskType.VIDEO_PROCESSING
        assert task.project_id == project.id
        assert task.status == TaskStatus.PENDING
        assert task.current_step == "step_1"
        assert task.total_steps == 5
        assert task.progress == 0.0
    
    def test_task_progress_update(self, test_session):
        """测试任务进度更新"""
        from models.project import Project, ProjectStatus, ProjectType
        from models.task import Task, TaskStatus, TaskType
        
        project = Project(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        test_session.add(project)
        test_session.commit()
        
        task = Task(
            name="测试任务",
            task_type=TaskType.VIDEO_PROCESSING,
            project_id=project.id,
            status=TaskStatus.PENDING,
            total_steps=10
        )
        test_session.add(task)
        test_session.commit()
        
        task.status = TaskStatus.RUNNING
        task.current_step = "step_3"
        task.progress = 30.0
        test_session.commit()
        
        assert task.status == TaskStatus.RUNNING
        assert task.current_step == "step_3"
        assert task.progress == 30.0
    
    def test_task_status_transitions(self, test_session):
        """测试任务状态转换"""
        from models.project import Project, ProjectStatus, ProjectType
        from models.task import Task, TaskStatus, TaskType
        
        project = Project(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        test_session.add(project)
        test_session.commit()
        
        task = Task(
            name="测试任务",
            task_type=TaskType.VIDEO_PROCESSING,
            project_id=project.id
        )
        test_session.add(task)
        test_session.commit()
        
        assert task.status == TaskStatus.PENDING
        
        task.status = TaskStatus.RUNNING
        test_session.commit()
        assert task.status == TaskStatus.RUNNING
        
        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        task.result_data = {"clips_generated": 10, "duration": 300}
        test_session.commit()
        assert task.status == TaskStatus.COMPLETED
        assert task.progress == 100.0
        assert task.result_data["clips_generated"] == 10
        
        task.status = TaskStatus.FAILED
        task.error_message = "处理失败：内存不足"
        test_session.commit()
        assert task.status == TaskStatus.FAILED
        assert "内存不足" in task.error_message
    
    def test_task_query_by_project(self, test_session):
        """测试按项目查询任务"""
        from models.project import Project, ProjectStatus, ProjectType
        from models.task import Task, TaskStatus, TaskType
        
        project1 = Project(name="项目1", project_type=ProjectType.KNOWLEDGE, status=ProjectStatus.PENDING)
        project2 = Project(name="项目2", project_type=ProjectType.KNOWLEDGE, status=ProjectStatus.PENDING)
        test_session.add_all([project1, project2])
        test_session.commit()
        
        for i in range(3):
            task = Task(
                name=f"任务 {i}",
                task_type=TaskType.VIDEO_PROCESSING,
                project_id=project1.id
            )
            test_session.add(task)
        
        for i in range(5):
            task = Task(
                name=f"任务 {i}",
                task_type=TaskType.VIDEO_PROCESSING,
                project_id=project2.id
            )
            test_session.add(task)
        
        test_session.commit()
        
        project1_tasks = test_session.query(Task).filter(
            Task.project_id == project1.id
        ).all()
        assert len(project1_tasks) == 3
        
        project2_tasks = test_session.query(Task).filter(
            Task.project_id == project2.id
        ).all()
        assert len(project2_tasks) == 5


class TestClipModel:
    """Clip 模型测试"""
    
    def test_clip_creation(self, test_session):
        """测试剪辑创建"""
        from models.project import Project, ProjectStatus, ProjectType
        from models.clip import Clip, ClipStatus
        
        project = Project(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        test_session.add(project)
        test_session.commit()
        
        clip = Clip(
            title="精彩片段1",
            description="这是一个精彩的片段",
            start_time=0.0,
            end_time=60.0,
            duration=60.0,
            score=0.85,
            project_id=project.id,
            status=ClipStatus.PENDING
        )
        test_session.add(clip)
        test_session.commit()
        
        assert clip.id is not None
        assert clip.title == "精彩片段1"
        assert clip.start_time == 0.0
        assert clip.end_time == 60.0
        assert clip.duration == 60.0
        assert clip.score == 0.85
        assert clip.project_id == project.id
        assert clip.status == ClipStatus.PENDING
    
    def test_clip_tags(self, test_session):
        """测试剪辑标签"""
        from models.project import Project, ProjectStatus, ProjectType
        from models.clip import Clip, ClipStatus
        
        project = Project(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        test_session.add(project)
        test_session.commit()
        
        clip = Clip(
            title="精彩片段",
            start_time=0.0,
            end_time=60.0,
            duration=60.0,
            project_id=project.id,
            tags=["搞笑", "精彩", "热门"],
            metadata={
                "view_count": 1000,
                "share_count": 50
            }
        )
        test_session.add(clip)
        test_session.commit()
        
        assert len(clip.tags) == 3
        assert "搞笑" in clip.tags
        assert "精彩" in clip.tags
        assert "热门" in clip.tags
        assert clip.metadata["view_count"] == 1000
        assert clip.metadata["share_count"] == 50
    
    def test_clip_status_transitions(self, test_session):
        """测试剪辑状态转换"""
        from models.project import Project, ProjectStatus, ProjectType
        from models.clip import Clip, ClipStatus
        
        project = Project(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        test_session.add(project)
        test_session.commit()
        
        clip = Clip(
            title="测试片段",
            start_time=0.0,
            end_time=60.0,
            duration=60.0,
            project_id=project.id
        )
        test_session.add(clip)
        test_session.commit()
        
        assert clip.status == ClipStatus.PENDING
        
        clip.status = ClipStatus.PROCESSING
        test_session.commit()
        assert clip.status == ClipStatus.PROCESSING
        
        clip.status = ClipStatus.COMPLETED
        test_session.commit()
        assert clip.status == ClipStatus.COMPLETED
        
        clip.status = ClipStatus.FAILED
        test_session.commit()
        assert clip.status == ClipStatus.FAILED
    
    def test_clip_query_by_project(self, test_session):
        """测试按项目查询剪辑"""
        from models.project import Project, ProjectStatus, ProjectType
        from models.clip import Clip, ClipStatus
        
        project1 = Project(name="项目1", project_type=ProjectType.KNOWLEDGE, status=ProjectStatus.PENDING)
        project2 = Project(name="项目2", project_type=ProjectType.KNOWLEDGE, status=ProjectStatus.PENDING)
        test_session.add_all([project1, project2])
        test_session.commit()
        
        for i in range(10):
            clip = Clip(
                title=f"片段 {i}",
                start_time=i * 60.0,
                end_time=(i + 1) * 60.0,
                duration=60.0,
                score=0.5 + i * 0.05,
                project_id=project1.id if i < 7 else project2.id
            )
            test_session.add(clip)
        
        test_session.commit()
        
        project1_clips = test_session.query(Clip).filter(
            Clip.project_id == project1.id
        ).all()
        assert len(project1_clips) == 7
        
        project2_clips = test_session.query(Clip).filter(
            Clip.project_id == project2.id
        ).all()
        assert len(project2_clips) == 3
    
    def test_clip_score_ranking(self, test_session):
        """测试剪辑分数排序"""
        from models.project import Project, ProjectStatus, ProjectType
        from models.clip import Clip, ClipStatus
        
        project = Project(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        test_session.add(project)
        test_session.commit()
        
        scores = [0.95, 0.75, 0.85, 0.50, 0.90]
        for i, score in enumerate(scores):
            clip = Clip(
                title=f"片段 {i}",
                start_time=0.0,
                end_time=60.0,
                duration=60.0,
                score=score,
                project_id=project.id
            )
            test_session.add(clip)
        
        test_session.commit()
        
        top_clips = test_session.query(Clip).filter(
            Clip.project_id == project.id
        ).order_by(Clip.score.desc()).limit(3).all()
        
        assert len(top_clips) == 3
        assert top_clips[0].score == 0.95
        assert top_clips[1].score == 0.90
        assert top_clips[2].score == 0.85
