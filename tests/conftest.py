"""
Pytest configuration and fixtures for Hair Style AI Generator tests
"""
import os
import pytest
import tempfile
import shutil
from unittest.mock import Mock, patch
from flask import Flask
from app import create_app
from app.config import TestingConfig


@pytest.fixture(scope='session')
def test_config():
    """テスト用設定"""
    config = TestingConfig()
    
    # テスト用一時ディレクトリ作成
    config.UPLOAD_FOLDER = tempfile.mkdtemp(prefix='test_uploads_')
    config.GENERATED_FOLDER = tempfile.mkdtemp(prefix='test_generated_')
    
    return config


@pytest.fixture
def app(test_config):
    """テスト用Flaskアプリ"""
    app = create_app(test_config)
    
    # テスト用設定
    app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,  # テスト時はCSRF無効
        'CELERY_TASK_ALWAYS_EAGER': True,  # Celeryタスクを同期実行
        'PRESERVE_CONTEXT_ON_EXCEPTION': False
    })
    
    # アプリケーションコンテキスト
    with app.app_context():
        yield app
    
    # テスト後クリーンアップ
    try:
        shutil.rmtree(test_config.UPLOAD_FOLDER)
        shutil.rmtree(test_config.GENERATED_FOLDER)
    except OSError:
        pass


@pytest.fixture
def client(app):
    """テスト用HTTPクライアント"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """テスト用CLIランナー"""
    return app.test_cli_runner()


@pytest.fixture
def auth_session(client):
    """認証済みセッション"""
    with client.session_transaction() as sess:
        sess['user_id'] = 'test_user_123'
        sess['user_name'] = 'テストユーザー'
        sess['created_at'] = '2024-01-01T00:00:00'
    return client


@pytest.fixture
def mock_redis():
    """RedisクライアントのMock"""
    mock = Mock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    mock.delete.return_value = True
    mock.exists.return_value = False
    return mock


@pytest.fixture
def mock_gemini_service():
    """Gemini Serviceのテスト用Mock"""
    with patch('app.services.gemini_service.GeminiService') as mock:
        instance = mock.return_value
        instance.optimize_hair_style_prompt.return_value = "optimized test prompt for short bob hairstyle"
        instance.create_hairstyle_prompt.return_value = "test hairstyle prompt"
        instance.validate_api_connection.return_value = True
        yield instance


@pytest.fixture
def mock_flux_service():
    """Flux Serviceのテスト用Mock"""
    with patch('app.services.flux_service.FluxService') as mock:
        instance = mock.return_value
        instance.generate_hair_style.return_value = "test_task_id_123"
        instance.get_result.return_value = {
            "status": "Ready",
            "result": {
                "sample": "https://test-url.com/generated_image.jpg"
            }
        }
        # 実装では(image_url, result_detail)のタプルを返す
        instance.poll_until_ready.return_value = (
            "https://test-url.com/generated_image.jpg",
            {
                "status": "Ready",
                "result": {
                    "sample": "https://test-url.com/generated_image.jpg"
                }
            }
        )
        instance.validate_api_connection.return_value = True
        instance.download_and_save_image.return_value = True
        yield instance


@pytest.fixture
def sample_image_data():
    """テスト用画像データ"""
    # 1x1ピクセルの透明PNG（最小サイズ）
    import base64
    
    # Base64エンコードされた1x1透明PNG
    png_data = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    
    return {
        'base64': png_data,
        'filename': 'test_image.png',
        'content_type': 'image/png'
    }


@pytest.fixture
def sample_files(sample_image_data):
    """テスト用ファイルアップロード"""
    import io
    import base64
    
    data = base64.b64decode(sample_image_data['base64'])
    
    return {
        'valid_image': (io.BytesIO(data), 'test.png', 'image/png'),
        'invalid_type': (io.BytesIO(b'not an image'), 'test.txt', 'text/plain'),
        'large_file': (io.BytesIO(b'x' * (11 * 1024 * 1024)), 'large.png', 'image/png')  # 11MB
    }


@pytest.fixture
def mock_celery_task():
    """Celeryタスクのテスト用Mock"""
    with patch('app.services.task_service.generate_hair_style_task') as mock:
        task_result = Mock()
        task_result.id = 'test_task_id_123'
        task_result.state = 'PENDING'
        task_result.result = None
        mock.delay.return_value = task_result
        yield mock


class TestDataHelper:
    """テストデータ生成ヘルパー"""
    
    @staticmethod
    def create_test_session_data():
        """テスト用セッションデータ"""
        return {
            'user_id': 'test_user_123',
            'user_name': 'テストユーザー',
            'created_at': '2024-01-01T00:00:00',
            'uploaded_images': [],
            'generated_images': [],
            'active_tasks': [],
            'generation_count_today': 0
        }
    
    @staticmethod
    def create_test_generation_result():
        """テスト用画像生成結果"""
        return {
            'task_id': 'test_task_id_123',
            'status': 'completed',
            'original_image': 'test_original.png',
            'generated_image': 'test_generated.jpg',
            'prompt': 'test prompt',
            'created_at': '2024-01-01T12:00:00'
        }


# テスト用設定
pytest_plugins = [] 