"""
Hair Style AI Generator - Configuration Classes
環境別設定クラス（開発・テスト・本番）
"""

import os
from datetime import timedelta


class BaseConfig:
    """基本設定クラス"""
    
    # Flask基本設定
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # ファイルアップロード設定
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', '10485760'))  # 10MB
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'app/static/uploads')
    GENERATED_FOLDER = os.getenv('GENERATED_FOLDER', 'app/static/generated')
    
    # 対応ファイル形式
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    
    # スクレイピング設定
    HOTPEPPER_BEAUTY_IMAGE_SELECTOR = os.getenv(
        'HOTPEPPER_BEAUTY_IMAGE_SELECTOR',
        '#jsiHoverAlphaLayerScope > div.cFix.mT20.pH10 > div.fl > div.pr > img'
    )
    
    # API設定
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    BFL_API_KEY = os.getenv('BFL_API_KEY')
    
    # FLUX.1 Kontext API制限
    FLUX_MAX_WAIT_TIME = int(os.getenv('FLUX_MAX_WAIT_TIME', '300'))
    FLUX_POLLING_INTERVAL = float(os.getenv('FLUX_POLLING_INTERVAL', '1.5'))
    FLUX_PROMPT_MAX_TOKENS = int(os.getenv('FLUX_PROMPT_MAX_TOKENS', '512'))
    FLUX_API_BASE_URL = os.getenv('FLUX_API_BASE_URL', "https://api.us1.bfl.ai/v1")
    FLUX_REQUEST_TIMEOUT_POST = int(os.getenv('FLUX_REQUEST_TIMEOUT_POST', '30'))
    FLUX_REQUEST_TIMEOUT_GET = int(os.getenv('FLUX_REQUEST_TIMEOUT_GET', '10'))
    FLUX_MAX_PARALLEL_GENERATIONS = int(os.getenv('FLUX_MAX_PARALLEL_GENERATIONS', '5'))

    # Gemini API設定
    GEMINI_MODEL_NAME = os.getenv('GEMINI_MODEL_NAME', 'gemini-2.5-flash')
    
    # Redis設定
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    REDIS_SOCKET_TIMEOUT = int(os.getenv('REDIS_SOCKET_TIMEOUT', '2'))
    REDIS_CONNECT_TIMEOUT = int(os.getenv('REDIS_CONNECT_TIMEOUT', '2'))
    REDIS_HEALTH_CHECK_INTERVAL = int(os.getenv('REDIS_HEALTH_CHECK_INTERVAL', '30'))
    
    # Celery設定
    CELERY_CONFIG = {
        'broker_url': os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        'result_backend': os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': 'Asia/Tokyo',
        'enable_utc': True,
    }
    
    # セッション設定
    SESSION_KEY_PREFIX = os.getenv('SESSION_KEY_PREFIX', 'session:')
    SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '86400'))  # 24時間
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=SESSION_TIMEOUT)
    SESSION_MAX_UPLOADED_FILES = int(os.getenv('SESSION_MAX_UPLOADED_FILES', '10'))
    SESSION_MAX_GENERATED_IMAGES = int(os.getenv('SESSION_MAX_GENERATED_IMAGES', '20'))
    SESSION_ACTIVE_TASK_CLEANUP_MINS = int(os.getenv('SESSION_ACTIVE_TASK_CLEANUP_MINS', '10'))
    
    # レート制限設定
    RATELIMIT_STORAGE_URI = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    RATE_LIMIT_PER_DAY = int(os.getenv('RATE_LIMIT_PER_DAY', '200'))
    RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', '50'))
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', '10'))
    
    # 商用運用設定
    MAX_CONCURRENT_GENERATIONS = int(os.getenv('MAX_CONCURRENT_GENERATIONS', '5'))
    USER_DAILY_LIMIT = int(os.getenv('USER_DAILY_LIMIT', '50'))
    
    # アプリケーション情報
    APP_VERSION = os.getenv('APP_VERSION', '1.0.0')
    IMAGE_MAX_RESOLUTION = os.getenv('IMAGE_MAX_RESOLUTION', '4096x4096')
    IMAGE_MIN_RESOLUTION = os.getenv('IMAGE_MIN_RESOLUTION', '256x256')
    WEBHOOK_SUPPORT_ENABLED = os.getenv('WEBHOOK_SUPPORT_ENABLED', 'False').lower() in ('true', '1', 't')

    # SocketIO設定
    SOCKETIO_ASYNC_MODE = 'eventlet'
    SOCKETIO_MESSAGE_QUEUE = REDIS_URL


class DevelopmentConfig(BaseConfig):
    """開発環境設定"""
    
    DEBUG = True
    TESTING = False
    
    # 開発用：より寛容な制限
    RATE_LIMIT_PER_MINUTE = 20
    USER_DAILY_LIMIT = 100
    
    # デバッグ用ログ設定
    LOG_LEVEL = 'DEBUG'


class TestingConfig(BaseConfig):
    """テスト環境設定"""
    
    DEBUG = False
    TESTING = True
    
    # テスト用データベース
    REDIS_URL = 'redis://localhost:6379/1'  # テスト用DB
    
    # テスト用制限緩和
    RATE_LIMIT_PER_DAY = 1000
    RATE_LIMIT_PER_HOUR = 200
    RATE_LIMIT_PER_MINUTE = 50
    
    # WTF CSRF無効化（テスト用）
    WTF_CSRF_ENABLED = False
    
    # テスト用API設定
    FLUX_MAX_WAIT_TIME = 60  # テスト用短縮
    
    # ログレベル
    LOG_LEVEL = 'INFO'


class ProductionConfig(BaseConfig):
    """本番環境設定"""
    
    DEBUG = False
    TESTING = False
    
    # 本番用：厳格な制限
    RATE_LIMIT_PER_DAY = 200
    RATE_LIMIT_PER_HOUR = 50
    RATE_LIMIT_PER_MINUTE = 10
    
    # セキュリティ強化
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # HTTPS強制
    PREFERRED_URL_SCHEME = 'https'
    
    # ログレベル
    LOG_LEVEL = 'WARNING'
    
    def __init__(self):
        super().__init__()
        # 本番用Celery設定追加
        self.CELERY_CONFIG = BaseConfig.CELERY_CONFIG.copy()
        self.CELERY_CONFIG.update({
            'worker_prefetch_multiplier': 1,
            'task_acks_late': True,
            'task_reject_on_worker_lost': True,
            'task_time_limit': 30 * 60,  # 30分
            'task_soft_time_limit': 25 * 60,  # 25分
        })


# 環境による設定選択
config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """現在の環境設定を取得"""
    env = os.getenv('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig) 