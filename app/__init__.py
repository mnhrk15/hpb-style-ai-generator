"""
Hair Style AI Generator - Flask Application Factory
商用レベルの美容室向けAIヘアスタイル生成アプリケーション
"""

import os
import eventlet
eventlet.monkey_patch(all=False, socket=True) # SocketIOのために必要

from flask import Flask, current_app, send_from_directory
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery import Celery, Task
from dotenv import load_dotenv
import redis # Redisライブラリをインポート
import logging # ロギングのため

# 環境変数読み込み
load_dotenv()

# ロガー設定 (create_app より前に設定することも可能だが、ここでは create_app 内で app.logger を使う)
logger = logging.getLogger(__name__)

# Global extensions
socketio = SocketIO()
csrf = CSRFProtect()
# Limiterの初期化 (key_funcのみ指定し、storage_uriはcreate_app内で設定)
limiter = Limiter(key_func=get_remote_address)
celery = Celery(__name__)


class FlaskTask(Task):
    """Celeryタスクをフラスクコンテキスト内で実行するためのカスタムタスククラス"""
    def __call__(self, *args, **kwargs):
        # create_appが呼ばれてappインスタンスが生成された後でないとcurrent_appは使えない
        # Celeryワーカープロセスでは、Flaskアプリのインスタンスが必要になる
        if current_app:
            with current_app.app_context():
                return self.run(*args, **kwargs)
        else:
            # ワーカー起動時にアプリインスタンスがない場合のフォールバックやエラー処理が必要な場合がある
            # ここでは単純に実行するが、実際のプロジェクトではアプリの再作成や設定のロードが必要になることも
            # from run import app as flask_app # または適切なアプリインスタンス取得方法
            # with flask_app.app_context():
            #     return self.run(*args, **kwargs)
            # 上記は循環importの可能性があるので注意。Celeryのドキュメント参照。
            # 最も一般的なのは、Celeryアプリ作成時にFlaskアプリを渡す方法。
            # このカスタムタスクはCeleryがFlaskアプリのコンテキストを必要とする場合に有効。
            return self.run(*args, **kwargs)


def create_celery_app(app: Flask = None): # appの型ヒントを追加
    """Celeryアプリケーションの作成と設定"""
    # app = app or create_app() # ここでcreate_appを呼ぶと循環参照や二重初期化の可能性
                                # 通常はFlaskアプリ作成後にCeleryアプリを作成する

    # Celery設定 (環境変数またはFlaskアプリのconfigから取得)
    # broker_url と result_backend は .env で CELERY_BROKER_URL, CELERY_RESULT_BACKEND として定義され、
    # Flaskアプリのconfig経由で渡されるか、直接os.getenvで読み込む
    celery_broker_url = app.config.get('CELERY_BROKER_URL', os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'))
    celery_result_backend = app.config.get('CELERY_RESULT_BACKEND', os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'))

    celery.conf.update(
        broker_url=celery_broker_url,
        result_backend=celery_result_backend,
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Tokyo', # アプリケーションのタイムゾーンに合わせる
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30分タイムアウト
        task_soft_time_limit=25 * 60,  # 25分ソフトタイムアウト
        worker_prefetch_multiplier=1, # 1度に1タスクずつ取得 (リソース消費の激しいタスク向け)
        task_acks_late=True, # タスク実行後にACKを返す (ワーカークラッシュ時のタスク再実行のため)
    )
    
    celery.Task = FlaskTask # Flaskコンテキスト内でタスクを実行するように設定
    if app: # Flaskアプリインスタンスがあれば拡張として登録
        app.extensions["celery"] = celery
    return celery


def create_app(config_object_name: str = None): # 設定オブジェクト名を受け取るように変更も可能
    """Flaskアプリケーションファクトリ"""
    app = Flask(__name__) # アプリケーションのルートパスは 'app' パッケージになる

    # 設定の読み込み
    if config_object_name:
        app.config.from_object(f"app.config.{config_object_name}")
    else:
        # 環境変数 FLASK_ENV から設定クラスを決定 (例: DevelopmentConfig, ProductionConfig)
        env_config_name = os.getenv('FLASK_ENV', 'development').capitalize() + 'Config'
        try:
            app.config.from_object(f"app.config.{env_config_name}")
            app.logger.info(f"Loaded config: app.config.{env_config_name}")
        except ImportError:
            app.logger.warning(
                f"Config 'app.config.{env_config_name}' not found. Falling back to DevelopmentConfig."
            )
            from app.config import DevelopmentConfig
            app.config.from_object(DevelopmentConfig)
    
    # .envからの設定でFlaskのconfigを上書き (config.pyより優先度が高い)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', app.config.get('SECRET_KEY', 'dev-secret-key-change-in-production'))
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', app.config.get('MAX_CONTENT_LENGTH', 10485760)))

    # CSRF保護の初期化
    csrf.init_app(app)
    
    # Redis接続確認とレート制限ストレージ設定
    redis_available = False
    redis_url_from_env = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    app.logger.info(f"Flask App: Attempting to use Redis for rate limiting & SocketIO. REDIS_URL from env: {redis_url_from_env}")

    try:
        # from_url は接続文字列からRedisクライアントを作成
        # socket_timeoutとsocket_connect_timeoutを短く設定して、接続できない場合に早く失敗するようにする
        redis_client_test = redis.from_url(redis_url_from_env, socket_timeout=2, socket_connect_timeout=2)
        redis_client_test.ping() # これが成功すればRedisサーバーは応答している
        
        # Flask-Limiterがこの設定キーを自動的に参照する
        app.config['RATELIMIT_STORAGE_URI'] = redis_url_from_env # 新しい正しいキー
        app.logger.info(f"Flask App: Successfully connected to Redis at {redis_url_from_env}. Rate limiting will use Redis.")
        redis_available = True
    except Exception as e: # redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, redis.exceptions.AuthenticationErrorなど
        app.logger.error(f"Flask App: Failed to connect to Redis at {redis_url_from_env} for rate limiting. Error: {e}", exc_info=True)
        app.logger.warning("Flask App: Rate limiting will use in-memory storage (not recommended for production).")
        # RATELIMIT_STORAGE_URL を設定しないか、明示的にメモリを指定することもできるが、
        # 設定しない場合はFlask-Limiterがデフォルトでインメモリを使用し警告を出す。

    # レート制限の初期化 (RATELIMIT_STORAGE_URI設定後)
    limiter.init_app(app)
    
    # SocketIO初期化
    socketio_config = {
        'cors_allowed_origins': "*", # 本番環境では "*" ではなく具体的なオリジンを指定するべき
        'async_mode': 'eventlet'
    }
    
    if redis_available: # Redisが利用可能であればメッセージキューとして使用
        socketio_config['message_queue'] = redis_url_from_env # RATELIMIT_STORAGE_URIと同じRedisインスタンスを使用
        app.logger.info(f"SocketIO will use Redis message queue: {redis_url_from_env}")
    else:
        app.logger.warning("SocketIO will run in single-process mode (Redis not available for message queue).")
    
    socketio.init_app(app, **socketio_config)
    
    # 静的ファイルディレクトリのパス設定と作成
    # UPLOAD_FOLDER と GENERATED_FOLDER は .env または config.py で定義されている想定
    # Flaskのインスタンスパス (app.instance_path) は通常プロジェクトルート直下の 'instance' フォルダ
    # ここではアプリケーションルート (app.root_path) を基準にするのが一般的
    # app.root_path はこの __init__.py がある 'app' ディレクトリを指す
    
    # UPLOAD_FOLDER と GENERATED_FOLDER の設定を .env または config.py から取得
    # デフォルト値は app/config.py の BaseConfig を参照
    default_upload_folder = os.path.join(app.root_path, 'static', 'uploads')
    default_generated_folder = os.path.join(app.root_path, 'static', 'generated')

    upload_folder_path = app.config.get('UPLOAD_FOLDER', default_upload_folder)
    generated_folder_path = app.config.get('GENERATED_FOLDER', default_generated_folder)

    # 設定されたパスが絶対パスでない場合は、アプリケーションルートからの相対パスとして解釈
    if not os.path.isabs(upload_folder_path):
        upload_folder_path = os.path.join(app.root_path, upload_folder_path.replace("app/", "", 1)) # "app/" プレフィックスを削除
    if not os.path.isabs(generated_folder_path):
        generated_folder_path = os.path.join(app.root_path, generated_folder_path.replace("app/", "", 1))

    app.config['UPLOAD_FOLDER_ABSPATH'] = upload_folder_path # 絶対パスをconfigに保存
    app.config['GENERATED_FOLDER_ABSPATH'] = generated_folder_path

    os.makedirs(upload_folder_path, exist_ok=True)
    os.makedirs(generated_folder_path, exist_ok=True)
    app.logger.info(f"Upload folder set to: {upload_folder_path}")
    app.logger.info(f"Generated folder set to: {generated_folder_path}")
    
    # 静的ファイル配信ルート (send_from_directory には絶対パスが必要)
    @app.route('/static/uploads/<path:filename>')
    def uploaded_file(filename):
        """アップロード画像の配信"""
        return send_from_directory(app.config['UPLOAD_FOLDER_ABSPATH'], filename)
    
    @app.route('/static/generated/<path:filename>')
    def generated_file(filename):
        """生成画像の配信"""
        return send_from_directory(app.config['GENERATED_FOLDER_ABSPATH'], filename)
    
    # Blueprintの登録
    from app.routes.main import main_bp
    from app.routes.upload import upload_bp
    from app.routes.generate import generate_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(upload_bp, url_prefix='/upload') # url_prefixに末尾の'/'は不要
    app.register_blueprint(generate_bp, url_prefix='/generate')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Blueprint登録後にCSRF除外を設定
    # APIエンドポイントは通常ステートレスなのでCSRF保護は不要なことが多い
    csrf.exempt(api_bp)
    
    # ファイルアップロードや非同期処理開始エンドポイントも、
    # JavaScriptからのAjax/Fetchリクエストが主で、伝統的なフォームPOSTでない場合、
    # CSRFトークンを別途扱うより除外する方が開発が楽になることがある。
    # ただし、セキュリティリスクを理解した上で行うこと。
    # もしこれらのエンドポイントがブラウザのフォームから直接呼び出される可能性があるなら、CSRF保護は有効にすべき。
    csrf.exempt(upload_bp)
    csrf.exempt(generate_bp)
    
    # SocketIOイベントハンドラーを有効化するために
    # generate.pyの関数をインポート（これによりデコレーターが実行される）
    # appコンテキスト内でインポートすることで、current_appなどが利用可能になる
    with app.app_context():
        from app.routes import generate as generate_route_handlers # SocketIOハンドラー登録のため
        # app.logger.info("SocketIO event handlers from generate.py should be registered now.")

    # エラーハンドラー
    @app.errorhandler(413) # RequestEntityTooLarge
    def too_large(e):
        app.logger.warning(f"File too large: {e.description if hasattr(e, 'description') else str(e)}")
        return {"error": "ファイルサイズが大きすぎます。10MB以下のファイルをアップロードしてください。"}, 413
    
    @app.errorhandler(429) # TooManyRequests (Rate Limit Exceeded)
    def ratelimit_handler(e):
        app.logger.warning(f"Rate limit exceeded: {e.description if hasattr(e, 'description') else str(e)}")
        return {"error": "リクエスト数が制限を超えました。しばらくお待ちください。"}, 429

    @app.errorhandler(Exception) # 未捕捉の一般的な例外
    def handle_generic_exception(e):
        app.logger.error(f"An unhandled exception occurred: {str(e)}", exc_info=True)
        # 本番環境ではユーザーに詳細なエラー情報を見せない
        if app.config.get('DEBUG', False):
            # デバッグモードなら詳細なエラーを返す (開発時)
            return {"error": "サーバー内部エラーが発生しました", "details": str(e)}, 500
        else:
            # 本番モードなら一般的なエラーメッセージ
            return {"error": "サーバー処理中にエラーが発生しました。しばらくしてからもう一度お試しください。"}, 500

    app.logger.info("Flask application created successfully.")
    return app

# CeleryアプリケーションインスタンスをFlaskアプリ作成後に初期化するのが一般的
# run.py や manage.py のようなエントリポイントで以下のようにする
# flask_app = create_app()
# celery_app = create_celery_app(flask_app)
# ただし、このファイルが import celery される時点で celery オブジェクトはグローバルに作成される。
# create_celery_app はその設定を更新する役割。