"""
Hair Style AI Generator - API Routes
REST API・システム情報・統計・管理機能
"""

from flask import Blueprint, jsonify, request, session, current_app
from app import limiter
from app.services.session_service import SessionService
from app.services.gemini_service import GeminiService
from app.services.flux_service import FluxService
import logging
import os

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)
session_service = SessionService()
gemini_service = GeminiService()
flux_service = FluxService()


@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    ヘルスチェックエンドポイント
    
    Returns:
        JSON: システム状態
    """
    try:
        # 基本情報
        status = {
            'status': 'healthy',
            'timestamp': lambda: __import__('datetime').datetime.utcnow().isoformat(),
            'services': {}
        }
        
        # Redis接続確認
        try:
            session_service.redis_client.ping() if session_service.redis_client else None
            status['services']['redis'] = 'connected'
        except:
            status['services']['redis'] = 'disconnected'
        
        # Gemini API確認
        try:
            has_gemini_key = bool(os.getenv('GEMINI_API_KEY'))
            status['services']['gemini'] = 'configured' if has_gemini_key else 'not_configured'
        except:
            status['services']['gemini'] = 'error'
        
        # FLUX.1 API確認
        try:
            has_flux_key = bool(os.getenv('BFL_API_KEY'))
            status['services']['flux'] = 'configured' if has_flux_key else 'not_configured'
        except:
            status['services']['flux'] = 'error'
        
        status['timestamp'] = status['timestamp']()
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"ヘルスチェックエラー: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@api_bp.route('/info', methods=['GET'])
@limiter.limit("50 per hour")
def system_info():
    """
    システム情報取得
    
    Returns:
        JSON: システム設定情報
    """
    try:
        info = {
            'app_name': 'Hair Style AI Generator',
            'version': '1.0.0',
            'features': {
                'max_file_size_mb': current_app.config.get('MAX_CONTENT_LENGTH', 10485760) // (1024 * 1024),
                'supported_formats': ['JPG', 'PNG', 'WebP'],
                'daily_limit': current_app.config.get('USER_DAILY_LIMIT', 50),
                'max_concurrent_tasks': current_app.config.get('MAX_CONCURRENT_TASKS', 3),
                'max_resolution': '4096x4096',
                'min_resolution': '256x256'
            },
            'apis': {
                'gemini_model': 'gemini-2.5-flash-preview-05-20',
                'flux_model': 'flux-kontext-pro',
                'real_time_progress': True,
                'webhook_support': False
            }
        }
        
        return jsonify(info)
        
    except Exception as e:
        logger.error(f"システム情報エラー: {e}")
        return jsonify({
            'error': 'システム情報取得に失敗しました'
        }), 500


@api_bp.route('/stats', methods=['GET'])
@limiter.limit("20 per hour")
def system_stats():
    """
    システム統計情報取得
    
    Returns:
        JSON: 統計情報
    """
    try:
        # セッション統計
        session_stats = session_service.get_session_statistics()
        
        # 現在のユーザー情報
        user_id = session.get('user_id')
        user_stats = {}
        
        if user_id:
            session_data = session_service.get_session_data(user_id)
            if session_data:
                user_stats = {
                    'daily_generations': session_data.get('daily_generation_count', 0),
                    'total_generations': session_data.get('total_generation_count', 0),
                    'uploaded_files': len(session_data.get('uploaded_files', [])),
                    'active_tasks': len(session_data.get('active_tasks', []))
                }
        
        stats = {
            'system': session_stats,
            'user': user_stats,
            'limits': {
                'daily_limit': current_app.config.get('USER_DAILY_LIMIT', 50),
                'remaining_today': current_app.config.get('USER_DAILY_LIMIT', 50) - user_stats.get('daily_generations', 0)
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"統計情報エラー: {e}")
        return jsonify({
            'error': '統計情報取得に失敗しました'
        }), 500


@api_bp.route('/session', methods=['GET'])
@limiter.limit("100 per hour")
def get_session_info():
    """
    現在のセッション情報取得
    
    Returns:
        JSON: セッション情報
    """
    try:
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({
                'authenticated': False,
                'message': 'セッションが見つかりません'
            })
        
        session_data = session_service.get_session_data(user_id)
        
        if session_data:
            return jsonify({
                'authenticated': True,
                'user_id': user_id,
                'user_name': session_data.get('user_name'),
                'created_at': session_data.get('created_at'),
                'last_activity': session_data.get('last_activity'),
                'stats': {
                    'daily_generations': session_data.get('daily_generation_count', 0),
                    'total_generations': session_data.get('total_generation_count', 0),
                    'uploaded_files': len(session_data.get('uploaded_files', [])),
                    'active_tasks': len(session_data.get('active_tasks', []))
                }
            })
        else:
            return jsonify({
                'authenticated': False,
                'message': 'セッションデータが見つかりません'
            })
            
    except Exception as e:
        logger.error(f"セッション情報エラー: {e}")
        return jsonify({
            'error': 'セッション情報取得に失敗しました'
        }), 500


@api_bp.route('/session', methods=['POST'])
@limiter.limit("10 per hour")
def create_new_session():
    """
    新しいセッション作成
    
    Expected JSON:
        {
            "user_name": "美容師01" (optional)
        }
    
    Returns:
        JSON: 新セッション情報
    """
    try:
        data = request.get_json() or {}
        user_name = data.get('user_name')
        
        # 新セッション作成
        new_user_id = session_service.create_user_session(user_name)
        
        # Flask sessionに設定
        session['user_id'] = new_user_id
        
        return jsonify({
            'success': True,
            'message': 'セッションを作成しました',
            'user_id': new_user_id,
            'user_name': user_name or f"User_{new_user_id[:8]}"
        })
        
    except Exception as e:
        logger.error(f"セッション作成エラー: {e}")
        return jsonify({
            'success': False,
            'error': 'セッション作成に失敗しました'
        }), 500


@api_bp.route('/session', methods=['DELETE'])
@limiter.limit("10 per hour")
def clear_session():
    """
    セッションクリア
    
    Returns:
        JSON: クリア結果
    """
    try:
        session.clear()
        
        return jsonify({
            'success': True,
            'message': 'セッションをクリアしました'
        })
        
    except Exception as e:
        logger.error(f"セッションクリアエラー: {e}")
        return jsonify({
            'success': False,
            'error': 'セッションクリアに失敗しました'
        }), 500


@api_bp.route('/test/gemini', methods=['POST'])
@limiter.limit("5 per hour")
def test_gemini_api():
    """
    Gemini API接続テスト
    
    Expected JSON:
        {
            "test_prompt": "ショートヘアに変更してください"
        }
    
    Returns:
        JSON: テスト結果
    """
    try:
        if not os.getenv('GEMINI_API_KEY'):
            return jsonify({
                'success': False,
                'error': 'GEMINI_API_KEY が設定されていません'
            }), 400
        
        data = request.get_json() or {}
        test_prompt = data.get('test_prompt', 'ショートヘアに変更してください')
        
        # プロンプト最適化テスト
        optimized = gemini_service.optimize_hair_style_prompt(
            test_prompt, 
            "テスト画像: 女性、ロングヘア、正面向き"
        )
        
        return jsonify({
            'success': True,
            'message': 'Gemini API接続成功',
            'input': test_prompt,
            'output': optimized
        })
        
    except Exception as e:
        logger.error(f"Gemini APIテストエラー: {e}")
        return jsonify({
            'success': False,
            'error': f'Gemini APIテスト失敗: {str(e)}'
        }), 500


@api_bp.route('/test/flux', methods=['POST'])
@limiter.limit("2 per hour")
def test_flux_api():
    """
    FLUX.1 API接続テスト（実際の生成は行わない）
    
    Returns:
        JSON: テスト結果
    """
    try:
        if not os.getenv('BFL_API_KEY'):
            return jsonify({
                'success': False,
                'error': 'BFL_API_KEY が設定されていません'
            }), 400
        
        # API接続確認のみ（実際の生成は行わない）
        is_valid = flux_service.validate_api_connection()
        
        if is_valid:
            return jsonify({
                'success': True,
                'message': 'FLUX.1 API接続成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'FLUX.1 API接続失敗'
            }), 500
            
    except Exception as e:
        logger.error(f"FLUX APIテストエラー: {e}")
        return jsonify({
            'success': False,
            'error': f'FLUX APIテスト失敗: {str(e)}'
        }), 500


@api_bp.route('/gallery/<string:image_id>', methods=['DELETE'])
@limiter.limit("20 per hour")
def delete_gallery_image(image_id):
    """
    ギャラリー画像削除
    
    Args:
        image_id: 削除する画像のID
    
    Returns:
        JSON: 削除結果
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': '認証が必要です'
            }), 401
        
        # セッションデータ取得
        session_data = session_service.get_session_data(user_id)
        if not session_data:
            return jsonify({
                'success': False,
                'error': 'セッションが見つかりません'
            }), 404
        
        # 生成済み画像から対象を検索
        generated_images = session_data.get('generated_images', [])
        target_image = None
        target_index = -1
        
        for idx, img in enumerate(generated_images):
            if img.get('id') == image_id:
                target_image = img
                target_index = idx
                break
        
        if not target_image:
            return jsonify({
                'success': False,
                'error': '指定された画像が見つかりません'
            }), 404
        
        # 画像ファイルを削除
        try:
            # アップロード画像の削除
            if target_image.get('uploaded_path'):
                uploaded_file_path = os.path.join(
                    current_app.root_path, 
                    target_image['uploaded_path'].lstrip('/')
                )
                if os.path.exists(uploaded_file_path):
                    os.remove(uploaded_file_path)
                    logger.info(f"アップロード画像削除: {uploaded_file_path}")
            
            # 生成画像の削除
            if target_image.get('generated_path'):
                generated_file_path = os.path.join(
                    current_app.root_path,
                    target_image['generated_path'].lstrip('/')
                )
                if os.path.exists(generated_file_path):
                    os.remove(generated_file_path)
                    logger.info(f"生成画像削除: {generated_file_path}")
                    
        except Exception as file_error:
            logger.warning(f"ファイル削除エラー: {file_error}")
            # ファイル削除失敗でも処理続行
        
        # セッションデータから削除
        generated_images.pop(target_index)
        session_data['generated_images'] = generated_images
        
        # 統計更新
        session_data['total_generation_count'] = len(generated_images)
        
        # セッションデータを保存
        session_service.update_session_data(user_id, session_data)
        
        return jsonify({
            'success': True,
            'message': '画像を削除しました',
            'deleted_image_id': image_id,
            'remaining_count': len(generated_images)
        })
        
    except Exception as e:
        logger.error(f"画像削除エラー: {e}")
        return jsonify({
            'success': False,
            'error': '画像削除に失敗しました'
        }), 500


@api_bp.route('/gallery/search', methods=['GET'])
@limiter.limit("30 per hour")
def search_gallery():
    """
    ギャラリー検索
    
    Query Parameters:
        q: 検索クエリ
        sort: ソート方法 (newest, oldest, filename)
        limit: 取得件数制限
    
    Returns:
        JSON: 検索結果
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': '認証が必要です'
            }), 401
        
        # クエリパラメータ取得
        search_query = request.args.get('q', '').lower().strip()
        sort_method = request.args.get('sort', 'newest')
        limit = int(request.args.get('limit', 50))
        
        # セッションデータ取得
        session_data = session_service.get_session_data(user_id)
        if not session_data:
            return jsonify({
                'success': False,
                'error': 'セッションが見つかりません'
            }), 404
        
        # 生成済み画像取得
        generated_images = session_data.get('generated_images', [])
        
        # 検索フィルタリング
        if search_query:
            filtered_images = []
            for img in generated_images:
                filename = img.get('original_filename', '').lower()
                prompt = img.get('japanese_prompt', '').lower()
                
                if search_query in filename or search_query in prompt:
                    filtered_images.append(img)
        else:
            filtered_images = generated_images.copy()
        
        # ソート
        if sort_method == 'newest':
            filtered_images.sort(key=lambda x: x.get('generated_at', ''), reverse=True)
        elif sort_method == 'oldest':
            filtered_images.sort(key=lambda x: x.get('generated_at', ''))
        elif sort_method == 'filename':
            filtered_images.sort(key=lambda x: x.get('original_filename', ''))
        
        # 制限適用
        limited_results = filtered_images[:limit]
        
        return jsonify({
            'success': True,
            'query': search_query,
            'sort': sort_method,
            'total_found': len(filtered_images),
            'returned_count': len(limited_results),
            'images': limited_results
        })
        
    except Exception as e:
        logger.error(f"ギャラリー検索エラー: {e}")
        return jsonify({
            'success': False,
            'error': '検索に失敗しました'
        }), 500 