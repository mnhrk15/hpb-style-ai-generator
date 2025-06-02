"""
Hair Style AI Generator - Flask Application Factory
商用レベルの美容室向けAIヘアスタイル生成アプリケーション
"""

import os
import eventlet
eventlet.monkey_patch(all=False, socket=True)

from flask import Flask, current_app, send_from_directory
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
    
    # レート制限設定
    limiter.init_app(app)
    
    # Redis接続確認とフォールバック
    redis_available = False
    try:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        redis_client = redis.from_url(redis_url)
        redis_client.ping()
        app.config['RATELIMIT_STORAGE_URL'] = redis_url
        redis_available = True
    except (redis.ConnectionError, redis.TimeoutError) as e:
        app.logger.warning(f"Redis接続失敗: {e}, メモリベースレート制限を使用")
        # Redis接続失敗時はメモリベースにフォールバック
    
    # SocketIO初期化（Redis利用可能時のみmessage_queueを設定）
    socketio_config = {
        'cors_allowed_origins': "*",
        'async_mode': 'eventlet'
    }
    
    if redis_available:
        socketio_config['message_queue'] = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    else:
        app.logger.warning("Redis未接続: SocketIOはシングルプロセスモードで動作")
    
    socketio.init_app(app, **socketio_config)
    
    # 静的ファイルディレクトリの作成
    upload_folder = os.path.join(app.instance_path, '..', app.config.get('UPLOAD_FOLDER', 'app/static/uploads'))
    generated_folder = os.path.join(app.instance_path, '..', app.config.get('GENERATED_FOLDER', 'app/static/generated'))
    
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(generated_folder, exist_ok=True)
    
    # 静的ファイル配信ルート
    @app.route('/static/uploads/<path:filename>')
    def uploaded_file(filename):
        """アップロード画像の配信"""
        upload_path = os.path.join(app.instance_path, '..', app.config.get('UPLOAD_FOLDER', 'app/static/uploads'))
        return send_from_directory(upload_path, filename)
    
    @app.route('/static/generated/<path:filename>')
    def generated_file(filename):
        """生成画像の配信"""
        generated_path = os.path.join(app.instance_path, '..', app.config.get('GENERATED_FOLDER', 'app/static/generated'))
        return send_from_directory(generated_path, filename)
    
    # Blueprintの登録
    from app.routes.main import main_bp
    from app.routes.upload import upload_bp
    from app.routes.generate import generate_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(upload_bp, url_prefix='/upload')
    app.register_blueprint(generate_bp, url_prefix='/generate')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Blueprint登録後にCSRF除外を設定
    # APIエンドポイント除外
    csrf.exempt(api_bp)
    
    # アップロードエンドポイント除外
    csrf.exempt(upload_bp)
    
    # 生成エンドポイント除外
    csrf.exempt(generate_bp)
    
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