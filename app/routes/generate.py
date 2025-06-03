"""
Hair Style AI Generator - Generate Routes
画像生成・非同期処理・SocketIO統合
"""

from flask import Blueprint, request, jsonify, session, current_app
from app import limiter, socketio
from app.services.task_service import TaskService
from app.services.session_service import SessionService
from app.services.file_service import FileService
from flask_socketio import emit, join_room
import os
import logging
import time

logger = logging.getLogger(__name__)

generate_bp = Blueprint('generate', __name__)
task_service = TaskService()
session_service = SessionService()
file_service = FileService()


@generate_bp.route('/', methods=['POST'])
@limiter.limit("10 per hour")  # 生成制限
def generate_hairstyle():
    """
    ヘアスタイル画像生成開始（複数画像対応）
    
    Expected JSON:
        {
            "file_path": "static/uploads/...",
            "japanese_prompt": "ショートボブで茶色の髪に変更してください",
            "original_filename": "photo.jpg",
            "count": 3,  # 生成枚数（1-5枚、オプション、デフォルト1）
            "seed": 12345  # ベースシード値（オプション）
        }
    
    Returns:
        JSON: 生成タスク開始結果
    """
    try:
        # セッション確認・自動作成
        user_id = session.get('user_id')
        if not user_id:
            # セッションが存在しない場合は新規作成
            user_id = session_service.create_user_session()
            session['user_id'] = user_id
            session.permanent = True  # セッション永続化
            logger.info(f"新規セッション作成（生成時）: {user_id}")
            
        # セッションデータの存在確認（アクティビティ更新付き）
        session_data = session_service.get_session_data(user_id, update_activity=True)
        if not session_data:
            # セッションデータが失われている場合は再作成
            user_id = session_service.create_user_session()
            session['user_id'] = user_id
            session.permanent = True
            logger.info(f"セッションデータ再作成: {user_id}")
            # 再作成後のデータ確認
            session_data = session_service.get_session_data(user_id, update_activity=False)
        
        # リクエストデータ取得
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'リクエストデータが無効です'
            }), 400
        
        file_path = data.get('file_path')
        japanese_prompt = data.get('japanese_prompt')
        original_filename = data.get('original_filename')
        count = data.get('count', 1)  # デフォルト1枚
        base_seed = data.get('seed')  # オプション
        
        # 必須パラメータ確認
        if not all([file_path, japanese_prompt, original_filename]):
            return jsonify({
                'success': False,
                'error': '必須パラメータが不足しています'
            }), 400
        
        # 生成枚数バリデーション
        if not isinstance(count, int) or not 1 <= count <= 5:
            return jsonify({
                'success': False,
                'error': '生成枚数は1〜5枚の間で指定してください'
            }), 400
        
        # ファイルパス正規化
        if file_path.startswith('/'):
            file_path = f"app{file_path}"
        elif not file_path.startswith('app/'):
            file_path = f"app/{file_path}"
        
        # ファイル存在確認
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': 'アップロードファイルが見つかりません'
            }), 404
        
        # 日次制限チェック（複数画像の場合は枚数分消費）
        within_limit, current_count, daily_limit = session_service.check_daily_limit(user_id)
        if current_count + count > daily_limit:
            return jsonify({
                'success': False,
                'error': f'日次生成制限を超過します（現在: {current_count}/{daily_limit}、要求: {count}枚）'
            }), 429
        
        # 同時実行タスク数チェック
        concurrent_tasks = session_service.get_concurrent_tasks_count(user_id)
        max_concurrent = current_app.config.get('MAX_CONCURRENT_TASKS', 3)
        
        if concurrent_tasks >= max_concurrent:
            return jsonify({
                'success': False,
                'error': f'同時実行制限に達しています（{concurrent_tasks}/{max_concurrent}）'
            }), 429
        
                # タスク開始（単数・複数対応）
        if count == 1:
            # 従来の単数生成
            task_id = task_service.generate_hairstyle_async(
                user_id=user_id,
                file_path=file_path,
                japanese_prompt=japanese_prompt,
                original_filename=original_filename
            )
        else:
            # 新しい複数生成
            task_id = task_service.generate_multiple_hairstyles_async(
                user_id=user_id,
                file_path=file_path,
                japanese_prompt=japanese_prompt,
                original_filename=original_filename,
                count=count,
                base_seed=base_seed
            )
        
        logger.info(f"ヘアスタイル生成開始: {user_id} - {task_id} ({count}枚)")
        
        return jsonify({
            'success': True,
            'message': f'ヘアスタイル生成を開始しました（{count}枚）',
            'data': {
                'task_id': task_id,
                'user_id': user_id,
                'japanese_prompt': japanese_prompt,
                'count': count,
                'estimated_time': f'{60 * count}-{180 * count}秒' if count > 1 else '60-180秒'
            }
        })
        
    except ValueError as e:
        logger.warning(f"バリデーションエラー: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"生成開始エラー: {e}")
        return jsonify({
            'success': False,
            'error': 'サーバーエラーが発生しました'
        }), 500


@generate_bp.route('/status/<task_id>', methods=['GET'])
@limiter.limit("100 per hour")
def get_generation_status(task_id):
    """
    生成タスクの状態取得
    
    Args:
        task_id (str): タスクID
        
    Returns:
        JSON: タスク状態情報
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'セッションが見つかりません'
            }), 401
        
        # タスク状態取得
        status_info = task_service.get_task_status(task_id)
        
        return jsonify({
            'success': True,
            'data': status_info
        })
        
    except Exception as e:
        logger.error(f"状態取得エラー: {e}")
        return jsonify({
            'success': False,
            'error': '状態取得に失敗しました'
        }), 500


@generate_bp.route('/cancel/<task_id>', methods=['POST'])
@limiter.limit("20 per hour")
def cancel_generation(task_id):
    """
    生成タスクのキャンセル
    
    Args:
        task_id (str): タスクID
        
    Returns:
        JSON: キャンセル結果
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'セッションが見つかりません'
            }), 401
        
        # タスクキャンセル
        success = task_service.cancel_task(task_id, user_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'タスクをキャンセルしました'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'キャンセルに失敗しました'
            }), 400
            
    except Exception as e:
        logger.error(f"キャンセルエラー: {e}")
        return jsonify({
            'success': False,
            'error': 'キャンセル処理に失敗しました'
        }), 500


@generate_bp.route('/history', methods=['GET'])
@limiter.limit("100 per hour")
def generation_history():
    """
    ユーザーの生成履歴取得
    
    Returns:
        JSON: 生成履歴
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'セッションが見つかりません'
            }), 401
        
        # セッションデータ取得
        session_data = session_service.get_session_data(user_id)
        if session_data:
            generated_images = session_data.get('generated_images', [])
            active_tasks = session_data.get('active_tasks', [])
            
            return jsonify({
                'success': True,
                'data': {
                    'generated_images': generated_images,
                    'active_tasks': active_tasks,
                    'daily_count': session_data.get('daily_generation_count', 0),
                    'total_count': session_data.get('total_generation_count', 0)
                }
            })
        else:
            return jsonify({
                'success': True,
                'data': {
                    'generated_images': [],
                    'active_tasks': [],
                    'daily_count': 0,
                    'total_count': 0
                }
            })
            
    except Exception as e:
        logger.error(f"履歴取得エラー: {e}")
        return jsonify({
            'success': False,
            'error': '履歴取得に失敗しました'
        }), 500


# SocketIOイベントハンドラー
@socketio.on('join_user_room')
def handle_join_user_room(data):
    """
    ユーザールームへの参加（リアルタイム進捗通知用）
    """
    try:
        user_id = session.get('user_id')
        logger.info(f"=== SocketIOルーム参加要求 ===")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Session Data: {dict(session)}")
        logger.info(f"Request Data: {data}")
        
        if user_id:
            room = f"user_{user_id}"
            join_room(room)
            emit('joined_room', {
                'message': f'ルーム {room} に参加しました',
                'user_id': user_id,
                'timestamp': time.time()
            })
            logger.info(f"ユーザー {user_id} がルーム {room} に参加成功")
            logger.info(f"================================")
        else:
            logger.warning("ユーザーIDが見つからないためルーム参加失敗")
            emit('error', {'message': 'セッションが見つかりません'})
    except Exception as e:
        logger.error(f"ルーム参加エラー: {e}")
        import traceback
        logger.error(traceback.format_exc())
        emit('error', {'message': 'ルーム参加に失敗しました'})


@socketio.on('connect')
def handle_connect():
    """WebSocket接続時の処理"""
    logger.debug("SocketIO接続確立")
    emit('connected', {'message': 'サーバーに接続しました'})


@socketio.on('disconnect')
def handle_disconnect():
    """WebSocket切断時の処理"""
    logger.debug("SocketIO接続切断") 