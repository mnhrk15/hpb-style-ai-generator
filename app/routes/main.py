"""
Hair Style AI Generator - Main Routes
メインページ・ギャラリー・ヘルプ・About
"""

from flask import Blueprint, render_template, current_app, session
from app.services.session_service import SessionService
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)
session_service = SessionService()


@main_bp.route('/')
def index():
    """
    メインページ（ホーム）
    
    Returns:
        HTML: アップロード・生成フォーム
    """
    try:
        # ユーザーセッション確認・自動作成
        user_id = session.get('user_id')
        if not user_id:
            user_id = session_service.create_user_session()
            session['user_id'] = user_id
            session.permanent = True  # セッション永続化
            logger.info(f"新規セッション作成（メインページ）: {user_id}")
        
        # セッションデータ取得・確認
        session_data = session_service.get_session_data(user_id, update_activity=True)
        if not session_data:
            # セッションデータが失われている場合は再作成
            user_id = session_service.create_user_session()
            session['user_id'] = user_id
            session.permanent = True
            session_data = session_service.get_session_data(user_id, update_activity=False)
            logger.info(f"セッションデータ再作成（メインページ）: {user_id}")
        
        # 統計情報作成
        stats = {
            'today_generations': session_data.get('daily_generation_count', 0) if session_data else 0,
            'total_generations': session_data.get('total_generation_count', 0) if session_data else 0,
            'daily_limit_remaining': current_app.config.get('USER_DAILY_LIMIT', 50) - (session_data.get('daily_generation_count', 0) if session_data else 0)
        }
        
        # 負の値を0に制限
        stats['daily_limit_remaining'] = max(0, stats['daily_limit_remaining'])
        
        return render_template('index.html', stats=stats)
        
    except Exception as e:
        logger.error(f"メインページエラー: {e}")
        return render_template('index.html', stats={
            'today_generations': 0,
            'total_generations': 0,
            'daily_limit_remaining': current_app.config.get('USER_DAILY_LIMIT', 50)
        })


@main_bp.route('/gallery')
def gallery():
    """
    ギャラリーページ
    
    Returns:
        HTML: 生成画像一覧
    """
    try:
        # ユーザーセッション確認・自動作成
        user_id = session.get('user_id')
        if not user_id:
            user_id = session_service.create_user_session()
            session['user_id'] = user_id
            session.permanent = True  # セッション永続化
            logger.info(f"新規セッション作成（ギャラリー）: {user_id}")
        
        # セッションデータ取得・確認
        session_data = session_service.get_session_data(user_id, update_activity=True)
        if not session_data:
            # セッションデータが失われている場合は再作成
            user_id = session_service.create_user_session()
            session['user_id'] = user_id
            session.permanent = True
            session_data = session_service.get_session_data(user_id, update_activity=False)
            logger.info(f"セッションデータ再作成（ギャラリー）: {user_id}")
        
        # 生成画像履歴取得
        images = []
        if session_data and 'generated_images' in session_data:
            raw_images = session_data['generated_images']
            
            # 画像データを整理してテンプレート用に変換
            for img in raw_images:
                try:
                    # 日時変換
                    generated_at_str = img.get('generated_at')
                    if generated_at_str:
                        if isinstance(generated_at_str, str):
                            generated_at = datetime.fromisoformat(generated_at_str.replace('Z', '+00:00'))
                        else:
                            generated_at = generated_at_str
                    else:
                        generated_at = datetime.now()
                    
                    processed_image = {
                        'id': img.get('id', ''),
                        'original_filename': img.get('original_filename', 'unknown.jpg'),
                        'uploaded_path': img.get('uploaded_path', ''),
                        'generated_path': img.get('generated_path', ''),
                        'japanese_prompt': img.get('japanese_prompt', ''),
                        'optimized_prompt': img.get('optimized_prompt', ''),
                        'generated_at': generated_at,
                        'file_size': img.get('file_size', 0),
                        'features': img.get('features', {})
                    }
                    
                    images.append(processed_image)
                    
                except Exception as img_error:
                    logger.warning(f"画像データ処理エラー: {img_error}")
                    continue
            
            # 新しい順にソート
            images.sort(key=lambda x: x['generated_at'], reverse=True)
        
        # 統計情報作成
        stats = {
            'today_generations': session_data.get('daily_generation_count', 0) if session_data else 0,
            'total_generations': session_data.get('total_generation_count', 0) if session_data else 0,
            'daily_limit_remaining': current_app.config.get('USER_DAILY_LIMIT', 50) - (session_data.get('daily_generation_count', 0) if session_data else 0)
        }
        
        # 負の値を0に制限
        stats['daily_limit_remaining'] = max(0, stats['daily_limit_remaining'])
        
        logger.info(f"ギャラリー表示: {len(images)}枚の画像")
        
        return render_template('gallery.html', images=images, generated_images=images, stats=stats)
        
    except Exception as e:
        logger.error(f"ギャラリーページエラー: {e}")
        # エラー時のデフォルト統計
        default_stats = {
            'today_generations': 0,
            'total_generations': 0,
            'daily_limit_remaining': current_app.config.get('USER_DAILY_LIMIT', 50)
        }
        return render_template('gallery.html', images=[], generated_images=[], stats=default_stats)


@main_bp.route('/help')
def help_page():
    """
    ヘルプページ
    
    Returns:
        HTML: 使い方ガイド・FAQ
    """
    try:
        limits = {
            'file_size_mb': current_app.config.get('MAX_CONTENT_LENGTH', 10485760) // (1024 * 1024),
            'supported_formats': ['JPG', 'PNG', 'WebP'],
            'daily_limit': current_app.config.get('USER_DAILY_LIMIT', 50)
        }
        
        return render_template('help.html', limits=limits)
        
    except Exception as e:
        logger.error(f"ヘルプページエラー: {e}")
        return render_template('help.html', limits={})


@main_bp.route('/about')
def about():
    """
    技術情報・Aboutページ
    
    Returns:
        HTML: アプリ情報・技術仕様
    """
    try:
        app_info = {
            'name': 'Hair Style AI Generator',
            'version': '1.0.0',
            'description': '美容室のためのAIヘアスタイル再現ツール',
            'technologies': {
                'ai_models': ['FLUX.1 Kontext Pro', 'Gemini 2.5 Flash Preview'],
                'backend': ['Flask 3.0+', 'Python 3.12', 'Celery', 'Redis'],
                'frontend': ['Tailwind CSS 4.1', 'Socket.IO', 'Axios']
            },
            'features': [
                '60-180秒の高速AI画像生成',
                '顔・表情の一貫性保持',
                'リアルタイム進捗表示',
                'マルチユーザー対応',
                'ドラッグ&ドロップファイルアップロード',
                '日本語プロンプト最適化'
            ]
        }
        
        return render_template('about.html', app_info=app_info)
        
    except Exception as e:
        logger.error(f"Aboutページエラー: {e}")
        return render_template('about.html', app_info={}) 