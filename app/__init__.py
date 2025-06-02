"""
Hair Style AI Generator - Flask Application Factory
商用レベルの美容室向けAIヘアスタイル生成アプリケーション
"""

import os
import eventlet
eventlet.monkey_patch(all=False, socket=True)

from flask import Flask, current_app
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery import Celery, Task
from dotenv import load_dotenv
import redis

# 環境変数読み込み
load_dotenv()

# Global extensions
socketio = SocketIO()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
celery = Celery(__name__)


class FlaskTask(Task):
    """Celeryタスクをフラスクコンテキスト内で実行するためのカスタムタスククラス"""
    def __call__(self, *args, **kwargs):
        with current_app.app_context():
            return self.run(*args, **kwargs)


def create_celery_app(app=None):
    """Celeryアプリケーションの作成と設定"""
    app = app or create_app()
    
    celery.conf.update(
        broker_url=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Tokyo',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30分タイムアウト
        task_soft_time_limit=25 * 60,  # 25分ソフトタイムアウト
        worker_prefetch_multiplier=1,
        task_acks_late=True,
    )
    
    celery.Task = FlaskTask
    app.extensions["celery"] = celery
    return celery


def create_app(config_object=None):
    """Flaskアプリケーションファクトリ"""
    app = Flask(__name__)
    
    # 設定の読み込み
    if config_object:
        app.config.from_object(config_object)
    else:
        from app.config import DevelopmentConfig
        app.config.from_object(DevelopmentConfig)
    
    # セキュリティ設定
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', '10485760'))  # 10MB
    
    # CSRF保護
    csrf.init_app(app)
    
    # API エンドポイントはCSRF無効化
    csrf.exempt('api.upload_file')
    csrf.exempt('api.generate_image')
    csrf.exempt('api.get_result')
    csrf.exempt('api.get_session_info')
    csrf.exempt('api.get_stats')
    csrf.exempt('api.delete_image')
    csrf.exempt('api.search_gallery')
    
    # レート制限設定
    limiter.init_app(app)
    
    # Redis接続確認とフォールバック
    try:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        redis_client = redis.from_url(redis_url)
        redis_client.ping()
        app.config['RATELIMIT_STORAGE_URL'] = redis_url
    except (redis.ConnectionError, redis.TimeoutError) as e:
        app.logger.warning(f"Redis接続失敗: {e}, メモリベースレート制限を使用")
        # Redis接続失敗時はメモリベースにフォールバック
    
    # SocketIO初期化
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode='eventlet',
        message_queue=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    )
    
    # 静的ファイルディレクトリの作成
    upload_folder = os.path.join(app.instance_path, '..', app.config.get('UPLOAD_FOLDER', 'app/static/uploads'))
    generated_folder = os.path.join(app.instance_path, '..', app.config.get('GENERATED_FOLDER', 'app/static/generated'))
    
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(generated_folder, exist_ok=True)
    
    # Blueprintの登録
    from app.routes.main import main_bp
    from app.routes.upload import upload_bp
    from app.routes.generate import generate_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(upload_bp, url_prefix='/upload')
    app.register_blueprint(generate_bp, url_prefix='/generate')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # SocketIOイベントハンドラーを有効化するために
    # generate.pyの関数をインポート（これによりデコレーターが実行される）
    with app.app_context():
        from app.routes import generate  # SocketIOハンドラー登録のため
    
    # エラーハンドラー
    @app.errorhandler(413)
    def too_large(e):
        return {"error": "ファイルサイズが大きすぎます。10MB以下のファイルをアップロードしてください。"}, 413
    
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return {"error": "リクエスト数が制限を超えました。しばらくお待ちください。"}, 429
    
    return app 