"""
Hair Style AI Generator - Upload Routes
ファイルアップロード・バリデーション・セッション管理
"""

from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.utils import secure_filename
from app import limiter
from app.services.file_service import FileService
from app.services.session_service import SessionService
import logging

logger = logging.getLogger(__name__)

upload_bp = Blueprint('upload', __name__)
file_service = FileService()
session_service = SessionService()


@upload_bp.route('/', methods=['POST'])
@limiter.limit("20 per hour")  # アップロード制限
def upload_file():
    """
    ファイルアップロード処理
    
    Returns:
        JSON: アップロード結果
    """
    try:
        # セッション確認・初期化
        user_id = session.get('user_id')
        if not user_id:
            import uuid
            user_id = str(uuid.uuid4())
            session['user_id'] = user_id
            session_service.create_user_session(f"User_{user_id[:8]}")
        
        # ファイル存在確認
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'ファイルが選択されていません'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'ファイルが選択されていません'
            }), 400
        
        # ファイル保存処理
        success, file_path, file_info = file_service.save_uploaded_file(
            file, user_id, optimize=True
        )
        
        if success:
            # セッションに追加
            session_service.add_uploaded_file(user_id, file_info)
            
            # 画像特徴分析
            features = file_service.analyze_image_features(file_path)
            
            logger.info(f"ファイルアップロード成功: {user_id} - {file.filename}")
            
            return jsonify({
                'success': True,
                'message': 'ファイルのアップロードが完了しました',
                'data': {
                    'file_path': file_path.replace('app/', '/'),
                    'original_filename': file.filename,
                    'file_info': file_info,
                    'features': features
                }
            })
        else:
            error_msg = file_info.get('error', 'アップロードに失敗しました')
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
            
    except Exception as e:
        logger.error(f"アップロード処理エラー: {e}")
        return jsonify({
            'success': False,
            'error': 'サーバーエラーが発生しました'
        }), 500


@upload_bp.route('/validate', methods=['POST'])
@limiter.limit("50 per hour")
def validate_file():
    """
    アップロード前のファイルバリデーション
    
    Returns:
        JSON: バリデーション結果
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                'valid': False,
                'error': 'ファイルが選択されていません'
            })
        
        file = request.files['file']
        
        # バリデーション実行
        is_valid, error_msg = file_service.validate_uploaded_file(file)
        
        return jsonify({
            'valid': is_valid,
            'error': error_msg,
            'message': 'ファイルは有効です' if is_valid else error_msg
        })
        
    except Exception as e:
        logger.error(f"バリデーションエラー: {e}")
        return jsonify({
            'valid': False,
            'error': 'バリデーション中にエラーが発生しました'
        })


@upload_bp.route('/history', methods=['GET'])
@limiter.limit("100 per hour")
def upload_history():
    """
    ユーザーのアップロード履歴取得
    
    Returns:
        JSON: アップロード履歴
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
            uploaded_files = session_data.get('uploaded_files', [])
            return jsonify({
                'success': True,
                'data': {
                    'uploaded_files': uploaded_files,
                    'count': len(uploaded_files)
                }
            })
        else:
            return jsonify({
                'success': True,
                'data': {
                    'uploaded_files': [],
                    'count': 0
                }
            })
            
    except Exception as e:
        logger.error(f"履歴取得エラー: {e}")
        return jsonify({
            'success': False,
            'error': '履歴取得に失敗しました'
        }), 500 