"""
测试配置和fixture
"""

import sys
import os
from pathlib import Path
import tempfile
import shutil

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from dotenv import load_dotenv
env_path = backend_dir.parent / ".env"
load_dotenv(dotenv_path=env_path)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="function")
def temp_db_path():
    """创建临时数据库路径fixture"""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_autoclip.db"
    yield db_path
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")
def test_engine(temp_db_path):
    """创建测试数据库引擎fixture"""
    db_url = f"sqlite:///{temp_db_path}"
    
    engine = create_engine(
        db_url,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,
            "isolation_level": None
        },
        poolclass=StaticPool,
        echo=False
    )
    
    yield engine
    
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_engine):
    """创建测试数据库会话fixture"""
    from models.base import Base
    
    Base.metadata.create_all(bind=test_engine)
    
    Session = sessionmaker(bind=test_engine)
    session = Session()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def temp_data_dir():
    """创建临时数据目录fixture"""
    temp_dir = tempfile.mkdtemp()
    original_env = os.environ.get("DATA_DIR")
    os.environ["DATA_DIR"] = temp_dir
    
    yield Path(temp_dir)
    
    if original_env:
        os.environ["DATA_DIR"] = original_env
    else:
        os.environ.pop("DATA_DIR", None)
    
    shutil.rmtree(temp_dir)
