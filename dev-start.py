#!/usr/bin/env python3
"""
Hair Style AI Generator - 開発環境用起動スクリプト
Flask runではなく、SocketIOサーバーで起動するためのスクリプト
"""

import os
import sys
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

if __name__ == '__main__':
    print("🎨 Hair Style AI Generator - 開発環境起動")
    print("=" * 50)
    
    # Redis接続チェック（オプション）
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()
        print("✅ Redis接続確認完了")
    except Exception:
        print("⚠️  Redis未接続（開発環境ではオプション）")
    
    # メインアプリケーション起動
    from run import app, socketio
    
    print(f"🚀 サーバー起動中... http://127.0.0.1:5000")
    print("=" * 50)
    
    # SocketIOサーバーで起動
    socketio.run(
        app,
        host='127.0.0.1',
        port=5000,
        debug=True,
        use_reloader=False  # SocketIO使用時はReloader無効
    ) 