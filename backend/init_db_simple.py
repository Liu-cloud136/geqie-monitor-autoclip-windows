#!/usr/bin/env python3
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

os.chdir(backend_dir)

from core.database import init_database, test_connection, create_tables
from models.base import Base
from models.project import Project, ProjectStatus, ProjectType
from models.clip import Clip
from models.task import Task, TaskStatus, TaskType
from sqlalchemy.orm import Session
from core.database import SessionLocal

def create_initial_data():
    db = SessionLocal()
    try:
        existing_projects = db.query(Project).count()
        if existing_projects > 0:
            print("Database already has data, skipping initial data creation")
            return
        
        test_project = Project(
            name="Test Project",
            description="This is a test project for verifying system functionality",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING,
            processing_config={
                "chunk_size": 5000,
                "min_score_threshold": 0.8,
                "max_clips_per_collection": 5
            }
        )
        db.add(test_project)
        db.commit()
        db.refresh(test_project)
        
        test_task = Task(
            name="Test Task",
            description="Test processing task",
            task_type=TaskType.VIDEO_PROCESSING,
            project_id=test_project.id,
            status=TaskStatus.PENDING,
            progress=0,
            current_step="Waiting to start",
            total_steps=6
        )
        db.add(test_task)
        
        test_clip = Clip(
            title="Test Clip",
            description="This is a test clip content",
            start_time=0,
            end_time=30,
            duration=30,
            score=0.8,
            project_id=test_project.id
        )
        db.add(test_clip)
        
        db.commit()
        print("Initial test data created successfully")
        
    except Exception as e:
        print(f"Failed to create initial data: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    print("Starting database initialization...")
    
    if test_connection():
        print("Database connection successful")
    else:
        print("Database connection failed")
        sys.exit(1)
    
    try:
        create_tables()
        print("Database tables created successfully")
    except Exception as e:
        print(f"Failed to create database tables: {e}")
        sys.exit(1)
    
    create_initial_data()
    
    print("Database initialization complete!")

if __name__ == "__main__":
    main()
