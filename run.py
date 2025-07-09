#!/usr/bin/env python3
"""
Hair Style AI Generator - Main Application Runner
商用レベル美容室向けAIヘアスタイル生成アプリケーション
"""

import os
import sys
import logging
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# プロジェクトルートをPythonパスに追加
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app import create_app, socketio, create_celery_app
from app.config import get_config


def setup_logging():
    """ログ設定の初期化"""
    config = get_config()
    log_level = getattr(config, 'LOG_LEVEL', 'INFO')
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('hair_style_generator.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def validate_environment():
    """必要な環境変数の検証"""
    required_vars = ['GEMINI_API_KEY', 'BFL_API_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ 以下の環境変数が設定されていません: {', '.join(missing_vars)}")
        print("env.example を参考に環境変数を設定してください。")
        sys.exit(1)
    
    print("✅ 環境変数の検証完了")


def check_redis_connection():
    """Redis接続確認"""
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()
        print("✅ Redis接続確認完了")
        return True
    except Exception as e:
        print(f"❌ Redis接続エラー: {e}")
        print("Redisサーバーが起動していることを確認してください。")
        return False


def create_directories():
    """必要なディレクトリの作成"""
    directories = [
        'app/static/uploads',
        'app/static/generated',
        'logs'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    print("✅ ディレクトリ作成完了")


def validate_secret_key(app):
    """本番環境でのデフォルトSECRET_KEY使用を防止"""
    if os.getenv('FLASK_ENV') == 'production' and \
       app.config.get('SECRET_KEY') == 'dev-secret-key-change-in-production':
        print("❌ 本番環境でデフォルトのSECRET_KEYが使用されています。")
        print("環境変数 'SECRET_KEY' を設定してください。")
        sys.exit(1)
    
    print("✅ SECRET_KEY検証完了")


# アプリケーションとCeleryインスタンスの作成
app = create_app()
celery_app = create_celery_app(app)


if __name__ == '__main__':
    # セットアップ処理
    setup_logging()
    validate_environment()
    create_directories()
    validate_secret_key(app)
    
    # Redis接続確認（開発環境のみ）
    if app.config.get('DEBUG', False):
        if not check_redis_connection():
            print("⚠️  Redis未接続ですが、開発モードで続行します。")
            print("完全な機能を使用するにはRedisを起動してください。")
    
    # 起動情報表示
    print("\n" + "="*60)
    print("🎨 Hair Style AI Generator Starting...")
    print("="*60)
    print(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
    print(f"Debug Mode: {app.config.get('DEBUG', False)}")
    print(f"Upload Folder: {app.config.get('UPLOAD_FOLDER')}")
    print(f"Generated Folder: {app.config.get('GENERATED_FOLDER')}")
    print("="*60)
    
    # アプリケーション起動
    try:
        socketio.run(
            app,
            host=os.getenv('FLASK_HOST', '127.0.0.1'),
            port=int(os.getenv('FLASK_PORT', '5001')),
            debug=app.config.get('DEBUG', False),
            use_reloader=False  # SocketIOと併用時はReloaderを無効化
        )
    except KeyboardInterrupt:
        print("\n🛑 アプリケーションを停止しました。")
    except Exception as e:
        print(f"\n❌ アプリケーション起動エラー: {e}")
        sys.exit(1) 