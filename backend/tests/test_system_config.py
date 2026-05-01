"""
系统配置 API 测试
测试系统配置管理器和API路由
"""

import sys
import os
from pathlib import Path
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from dotenv import load_dotenv
env_path = backend_dir.parent / ".env"
load_dotenv(dotenv_path=env_path)


@pytest.fixture(scope="module")
def temp_config_dir():
    """创建临时配置目录fixture"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestSystemConfigManager:
    """系统配置管理器测试"""

    def test_default_config_initialization(self, temp_config_dir):
        """测试默认配置初始化"""
        from core.system_config import SystemConfigManager, SystemConfig

        config_file = temp_config_dir / "test_system_config.json"
        manager = SystemConfigManager(config_file)

        assert manager.config is not None
        assert isinstance(manager.config, SystemConfig)

        assert manager.config.processing.chunk_size == 5000
        assert manager.config.processing.min_score_threshold == 70.0
        assert manager.config.processing.max_clips_per_collection == 5
        assert manager.config.processing.max_retries == 3
        assert manager.config.processing.api_timeout == 600

        assert manager.config.video.use_stream_copy is True
        assert manager.config.video.use_hardware_accel is True
        assert manager.config.video.encoder_preset == "p6"
        assert manager.config.video.crf == 23

        assert manager.config.topic.min_topic_duration_minutes == 2
        assert manager.config.topic.max_topic_duration_minutes == 12
        assert manager.config.topic.target_topic_duration_minutes == 5
        assert manager.config.topic.min_topics_per_chunk == 3
        assert manager.config.topic.max_topics_per_chunk == 8

        assert manager.config.logging.log_level == "INFO"
        assert manager.config.advanced.proxy_url == ""

    def test_save_and_load_config(self, temp_config_dir):
        """测试配置保存和加载"""
        from core.system_config import SystemConfigManager

        config_file = temp_config_dir / "test_save_config.json"
        manager = SystemConfigManager(config_file)

        manager.config.processing.chunk_size = 10000
        manager.config.video.crf = 20
        manager.config.topic.min_topic_duration_minutes = 3
        manager.config.advanced.proxy_url = "http://localhost:7890"

        manager.save_configs()

        assert config_file.exists()

        with open(config_file, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)

        assert saved_data["processing"]["chunk_size"] == 10000
        assert saved_data["video"]["crf"] == 20
        assert saved_data["topic"]["min_topic_duration_minutes"] == 3
        assert saved_data["advanced"]["proxy_url"] == "http://localhost:7890"

        manager2 = SystemConfigManager(config_file)
        assert manager2.config.processing.chunk_size == 10000
        assert manager2.config.video.crf == 20
        assert manager2.config.topic.min_topic_duration_minutes == 3
        assert manager2.config.advanced.proxy_url == "http://localhost:7890"

    def test_get_all_configs(self, temp_config_dir):
        """测试获取所有配置"""
        from core.system_config import SystemConfigManager

        config_file = temp_config_dir / "test_get_all_configs.json"
        manager = SystemConfigManager(config_file)

        all_configs = manager.get_all_configs()

        assert "processing" in all_configs
        assert "video" in all_configs
        assert "topic" in all_configs
        assert "logging" in all_configs
        assert "advanced" in all_configs

        assert all_configs["processing"]["chunk_size"] == 5000
        assert all_configs["video"]["use_stream_copy"] is True

    def test_update_config(self, temp_config_dir):
        """测试更新配置"""
        from core.system_config import SystemConfigManager

        config_file = temp_config_dir / "test_update_config.json"
        manager = SystemConfigManager(config_file)

        manager.update_config("processing", {
            "chunk_size": 8000,
            "min_score_threshold": 80.0
        })

        assert manager.config.processing.chunk_size == 8000
        assert manager.config.processing.min_score_threshold == 80.0

        manager.update_config("video", {
            "use_stream_copy": False,
            "crf": 18
        })

        assert manager.config.video.use_stream_copy is False
        assert manager.config.video.crf == 18

        with open(config_file, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)

        assert saved_data["processing"]["chunk_size"] == 8000
        assert saved_data["video"]["use_stream_copy"] is False

    def test_reset_all_configs(self, temp_config_dir):
        """测试重置所有配置"""
        from core.system_config import SystemConfigManager

        config_file = temp_config_dir / "test_reset_all.json"
        manager = SystemConfigManager(config_file)

        manager.update_config("processing", {"chunk_size": 20000})
        manager.update_config("video", {"crf": 10})
        manager.update_config("topic", {"min_topic_duration_minutes": 10})

        assert manager.config.processing.chunk_size == 20000
        assert manager.config.video.crf == 10

        manager.reset_all_configs()

        assert manager.config.processing.chunk_size == 5000
        assert manager.config.video.crf == 23
        assert manager.config.topic.min_topic_duration_minutes == 2

    def test_reset_category_config(self, temp_config_dir):
        """测试重置指定分类配置"""
        from core.system_config import SystemConfigManager

        config_file = temp_config_dir / "test_reset_category.json"
        manager = SystemConfigManager(config_file)

        manager.update_config("processing", {"chunk_size": 20000})
        manager.update_config("video", {"crf": 10})

        manager.reset_category_config("processing")

        assert manager.config.processing.chunk_size == 5000
        assert manager.config.video.crf == 10

    def test_get_category_configs(self, temp_config_dir):
        """测试获取分类配置"""
        from core.system_config import SystemConfigManager

        config_file = temp_config_dir / "test_category_configs.json"
        manager = SystemConfigManager(config_file)

        processing_config = manager.get_processing_config()
        video_config = manager.get_video_config()
        topic_config = manager.get_topic_config()
        logging_config = manager.get_logging_config()
        advanced_config = manager.get_advanced_config()

        assert processing_config.chunk_size == 5000
        assert video_config.use_stream_copy is True
        assert topic_config.min_topic_duration_minutes == 2
        assert logging_config.log_level == "INFO"
        assert advanced_config.proxy_url == ""


class TestSystemConfigAPI:
    """系统配置 API 测试"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_config_file = Path(self.temp_dir) / "system_config.json"

    def teardown_method(self):
        """每个测试方法后的清理"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def create_test_client(self):
        """创建测试客户端"""
        from fastapi import FastAPI
        from api.v1 import router as api_router

        app = FastAPI()
        app.include_router(api_router, prefix="/api/v1")

        return TestClient(app)

    def test_get_all_system_configs(self):
        """测试获取所有系统配置"""
        from core.system_config import SystemConfigManager

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(self.temp_config_file)

            with patch('api.v1.system_config.get_system_config_manager', return_value=manager):
                client = self.create_test_client()

                response = client.get("/api/v1/system-config/")

                assert response.status_code == 200
                data = response.json()

                assert "processing" in data
                assert "video" in data
                assert "topic" in data
                assert "logging" in data
                assert "advanced" in data

                assert data["processing"]["chunk_size"] == 5000

    def test_get_processing_config(self):
        """测试获取处理配置"""
        from core.system_config import SystemConfigManager

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(self.temp_config_file)
            manager.config.processing.chunk_size = 15000

            with patch('api.v1.system_config.get_system_config_manager', return_value=manager):
                client = self.create_test_client()

                response = client.get("/api/v1/system-config/processing")

                assert response.status_code == 200
                data = response.json()

                assert data["chunk_size"] == 15000
                assert "min_score_threshold" in data
                assert "max_clips_per_collection" in data
                assert "max_retries" in data
                assert "api_timeout" in data

    def test_update_processing_config(self):
        """测试更新处理配置"""
        from core.system_config import SystemConfigManager

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(self.temp_config_file)

            with patch('api.v1.system_config.get_system_config_manager', return_value=manager):
                client = self.create_test_client()

                response = client.put("/api/v1/system-config/processing", json={
                    "chunk_size": 8000,
                    "min_score_threshold": 85.0
                })

                assert response.status_code == 200
                data = response.json()

                assert data["message"] == "处理配置已更新"
                assert data["config"]["chunk_size"] == 8000
                assert data["config"]["min_score_threshold"] == 85.0

                assert manager.config.processing.chunk_size == 8000

    def test_get_video_config(self):
        """测试获取视频配置"""
        from core.system_config import SystemConfigManager

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(self.temp_config_file)

            with patch('api.v1.system_config.get_system_config_manager', return_value=manager):
                client = self.create_test_client()

                response = client.get("/api/v1/system-config/video")

                assert response.status_code == 200
                data = response.json()

                assert "use_stream_copy" in data
                assert "use_hardware_accel" in data
                assert "encoder_preset" in data
                assert "crf" in data

    def test_update_video_config(self):
        """测试更新视频配置"""
        from core.system_config import SystemConfigManager

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(self.temp_config_file)

            with patch('api.v1.system_config.get_system_config_manager', return_value=manager):
                client = self.create_test_client()

                response = client.put("/api/v1/system-config/video", json={
                    "use_stream_copy": False,
                    "crf": 18
                })

                assert response.status_code == 200
                data = response.json()

                assert data["message"] == "视频配置已更新"
                assert data["config"]["use_stream_copy"] is False
                assert data["config"]["crf"] == 18

    def test_get_topic_config(self):
        """测试获取话题配置"""
        from core.system_config import SystemConfigManager

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(self.temp_config_file)

            with patch('api.v1.system_config.get_system_config_manager', return_value=manager):
                client = self.create_test_client()

                response = client.get("/api/v1/system-config/topic")

                assert response.status_code == 200
                data = response.json()

                assert "min_topic_duration_minutes" in data
                assert "max_topic_duration_minutes" in data
                assert "target_topic_duration_minutes" in data
                assert "min_topics_per_chunk" in data
                assert "max_topics_per_chunk" in data

    def test_get_logging_config(self):
        """测试获取日志配置"""
        from core.system_config import SystemConfigManager

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(self.temp_config_file)

            with patch('api.v1.system_config.get_system_config_manager', return_value=manager):
                client = self.create_test_client()

                response = client.get("/api/v1/system-config/logging")

                assert response.status_code == 200
                data = response.json()

                assert "log_level" in data
                assert "log_format" in data

    def test_get_advanced_config(self):
        """测试获取高级配置"""
        from core.system_config import SystemConfigManager

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(self.temp_config_file)

            with patch('api.v1.system_config.get_system_config_manager', return_value=manager):
                client = self.create_test_client()

                response = client.get("/api/v1/system-config/advanced")

                assert response.status_code == 200
                data = response.json()

                assert "proxy_url" in data
                assert "encryption_key" in data
                assert "bilibili_cookie" in data

    def test_update_advanced_config(self):
        """测试更新高级配置"""
        from core.system_config import SystemConfigManager

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(self.temp_config_file)

            with patch('api.v1.system_config.get_system_config_manager', return_value=manager):
                client = self.create_test_client()

                response = client.put("/api/v1/system-config/advanced", json={
                    "proxy_url": "http://127.0.0.1:7890"
                })

                assert response.status_code == 200
                data = response.json()

                assert data["message"] == "高级配置已更新"
                assert data["config"]["proxy_url"] == "http://127.0.0.1:7890"

    def test_reset_category_config(self):
        """测试重置分类配置"""
        from core.system_config import SystemConfigManager

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(self.temp_config_file)
            manager.config.processing.chunk_size = 20000

            with patch('api.v1.system_config.get_system_config_manager', return_value=manager):
                client = self.create_test_client()

                response = client.post("/api/v1/system-config/reset/processing")

                assert response.status_code == 200
                data = response.json()

                assert "processing" in data["message"]
                assert data["config"]["chunk_size"] == 5000

    def test_reset_category_config_invalid(self):
        """测试重置无效分类配置"""
        from core.system_config import SystemConfigManager

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(self.temp_config_file)

            with patch('api.v1.system_config.get_system_config_manager', return_value=manager):
                client = self.create_test_client()

                response = client.post("/api/v1/system-config/reset/invalid_category")

                assert response.status_code == 400

    def test_get_config_info(self):
        """测试获取配置说明信息"""
        client = self.create_test_client()

        response = client.get("/api/v1/system-config/config-info")

        assert response.status_code == 200
        data = response.json()

        assert "categories" in data
        assert "processing" in data["categories"]
        assert "video" in data["categories"]
        assert "topic" in data["categories"]
        assert "logging" in data["categories"]
        assert "advanced" in data["categories"]


class TestHelperFunctions:
    """辅助函数测试"""

    def test_get_processing_config_dict(self, temp_config_dir):
        """测试获取处理配置字典"""
        from core.system_config import SystemConfigManager, get_processing_config_dict

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(temp_config_dir / "test_helpers.json")
            manager.config.processing.chunk_size = 12345
            manager.config.processing.min_score_threshold = 75.0

            with patch('core.system_config._system_config_manager', manager):
                config = get_processing_config_dict()

                assert config["chunk_size"] == 12345
                assert config["min_score_threshold"] == 75.0
                assert "max_clips_per_collection" in config
                assert "max_retries" in config

    def test_get_video_config_dict(self, temp_config_dir):
        """测试获取视频配置字典"""
        from core.system_config import SystemConfigManager, get_video_config_dict

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(temp_config_dir / "test_video_dict.json")
            manager.config.video.use_stream_copy = False
            manager.config.video.crf = 20

            with patch('core.system_config._system_config_manager', manager):
                config = get_video_config_dict()

                assert config["use_stream_copy"] is False
                assert config["crf"] == 20

    def test_get_topic_config_dict(self, temp_config_dir):
        """测试获取话题配置字典"""
        from core.system_config import SystemConfigManager, get_topic_config_dict

        with patch('core.system_config._system_config_manager', None):
            manager = SystemConfigManager(temp_config_dir / "test_topic_dict.json")
            manager.config.topic.min_topic_duration_minutes = 5
            manager.config.topic.max_topic_duration_minutes = 15

            with patch('core.system_config._system_config_manager', manager):
                config = get_topic_config_dict()

                assert config["min_topic_duration_minutes"] == 5
                assert config["max_topic_duration_minutes"] == 15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
