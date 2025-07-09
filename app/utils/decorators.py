from functools import wraps
from flask import session, current_app
from app.services.session_service import SessionService
import logging

# ロガー設定
logger = logging.getLogger(__name__)

# SessionServiceのインスタンス化
session_service = SessionService()

def session_required(f):
    """
    リクエスト処理前にユーザーセッションの存在を確認・作成するデコレータ
    - `flask.session`に`user_id`が存在するか確認
    - `user_id`に紐づくセッションデータがRedisに存在するか確認
    - 上記いずれかが存在しない場合、新規セッションを作成する
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        session_data = None
        
        # ユーザーIDが存在する場合、Redisからセッションデータを取得
        if user_id:
            try:
                session_data = session_service.get_session_data(user_id)
            except Exception as e:
                logger.error(f"デコレータ内でのセッションデータ取得エラー: {e}")
                session_data = None
                user_id = None # 取得失敗時はIDもクリアして再作成へ

        # ユーザーIDまたはセッションデータが存在しない場合、新規作成
        if not user_id or not session_data:
            try:
                new_user_id = session_service.create_user_session()
                session['user_id'] = new_user_id
                session.permanent = True  # セッションを永続化
                logger.info(f"デコレータにより新規セッション作成: {new_user_id}")
            except Exception as e:
                logger.critical(f"デコレータ内でのセッション作成に失敗: {e}")
                # セッションが作成できない場合はエラーを返すか、処理を中断するべきかもしれない
                # ここでは処理を続行するが、本番環境では要検討
        
        return f(*args, **kwargs)
    return decorated_function 