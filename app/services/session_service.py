"""
Hair Style AI Generator - Session Service
Redis統合マルチユーザーセッション管理
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import redis
from flask import current_app
import os

logger = logging.getLogger(__name__)


class SessionService:
    """
    Redis統合セッション管理サービス
    マルチユーザー対応・並行処理制御
    """
    
    def __init__(self):
        """セッションサービスの初期化"""
        self.redis_client = None
        self.session_timeout = 86400  # 24時間
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Redis接続初期化"""
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(
                redis_url, 
                decode_responses=True,
                socket_timeout=2,  # 2秒タイムアウト
                socket_connect_timeout=2,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # 接続テスト
            self.redis_client.ping()
            logger.info("Redis接続初期化完了")
            
        except Exception as e:
            logger.warning(f"Redis接続失敗（フォールバックモード使用）: {e}")
            self.redis_client = None
    
    def create_user_session(self, user_name: Optional[str] = None) -> str:
        """
        ユーザーセッション作成
        
        Args:
            user_name (str, optional): ユーザー名
            
        Returns:
            str: セッションID
        """
        session_id = str(uuid.uuid4())
        
        session_data = {
            "user_id": session_id,
            "user_name": user_name or f"User_{session_id[:8]}",
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "uploaded_files": [],
            "generated_images": [],
            "active_tasks": [],
            "daily_generation_count": 0,
            "total_generation_count": 0
        }
        
        if self.redis_client:
            try:
                key = f"session:{session_id}"
                self.redis_client.setex(
                    key,
                    self.session_timeout,
                    json.dumps(session_data)
                )
                logger.info(f"ユーザーセッション作成: {session_id}")
            except Exception as e:
                logger.error(f"Redisセッション作成エラー: {e}")
        
        return session_id
    
    def get_session_data(self, session_id: str, update_activity: bool = False) -> Optional[Dict]:
        """
        セッションデータ取得
        
        Args:
            session_id (str): セッションID
            update_activity (bool): 最終アクティビティ更新するか
            
        Returns:
            dict: セッションデータ
        """
        if not self.redis_client:
            # Redisなしの場合は基本データを返す
            return self._get_fallback_session_data(session_id)
        
        try:
            key = f"session:{session_id}"
            data = self.redis_client.get(key)
            
            if data:
                session_data = json.loads(data)
                
                # 日付変更時に日次カウントをリセット
                try:
                    last_activity_str = session_data.get("last_activity")
                    if last_activity_str:
                        last_activity_date = datetime.fromisoformat(last_activity_str).date()
                        today_utc = datetime.utcnow().date()
                        
                        if last_activity_date < today_utc:
                            if session_data.get("daily_generation_count", 0) > 0:
                                logger.info(
                                    f"日付が変わったため日次生成カウントをリセットします: "
                                    f"session_id={session_id}, "
                                    f"old_count={session_data.get('daily_generation_count')}"
                                )
                                session_data["daily_generation_count"] = 0
                except Exception as e:
                    logger.error(f"日次カウントのリセット処理中にエラーが発生しました: {e}", exc_info=True)

                # 明示的に指定された場合のみアクティビティ更新
                if update_activity:
                    session_data["last_activity"] = datetime.utcnow().isoformat()
                    self.redis_client.setex(key, self.session_timeout, json.dumps(session_data))
                
                return session_data
            else:
                logger.warning(f"セッションが見つかりません: {session_id}")
                return None
                
        except Exception as e:
            logger.error(f"セッション取得エラー: {e}")
            return self._get_fallback_session_data(session_id)
    
    def update_session_data(self, session_id: str, data: Dict) -> bool:
        """
        セッションデータ更新
        
        Args:
            session_id (str): セッションID
            data (dict): 更新データ
            
        Returns:
            bool: 更新成功可否
        """
        if not self.redis_client:
            return False
        
        try:
            key = f"session:{session_id}"
            # 無限再帰防止: アクティビティ更新なしで取得
            current_data = self.get_session_data(session_id, update_activity=False)
            
            if current_data:
                # データをマージ
                current_data.update(data)
                current_data["last_activity"] = datetime.utcnow().isoformat()
                
                # Redis更新（タイムアウト設定付き）
                self.redis_client.setex(
                    key,
                    self.session_timeout,
                    json.dumps(current_data)
                )
                return True
            else:
                logger.warning(f"更新対象セッションが見つかりません: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"セッション更新エラー: {e}")
            return False
    
    def add_uploaded_file(self, session_id: str, file_info: Dict) -> bool:
        """
        アップロードファイルをセッションに追加
        
        Args:
            session_id (str): セッションID
            file_info (dict): ファイル情報
            
        Returns:
            bool: 追加成功可否
        """
        session_data = self.get_session_data(session_id, update_activity=False)
        if not session_data:
            return False
        
        # ファイル情報に追加情報を付与
        file_info["uploaded_at"] = datetime.utcnow().isoformat()
        
        session_data["uploaded_files"].append(file_info)
        
        # 最新10件のみ保持
        if len(session_data["uploaded_files"]) > 10:
            session_data["uploaded_files"] = session_data["uploaded_files"][-10:]
        
        return self.update_session_data(session_id, session_data)
    
    def add_generated_image(self, session_id: str, generation_info: Dict) -> bool:
        """
        生成画像をセッションに追加
        
        Args:
            session_id (str): セッションID
            generation_info (dict): 生成画像情報
            
        Returns:
            bool: 追加成功可否
        """
        session_data = self.get_session_data(session_id, update_activity=False)
        if not session_data:
            return False
        
        # 生成情報に追加情報を付与
        generation_info["generated_at"] = datetime.utcnow().isoformat()
        
        session_data["generated_images"].append(generation_info)
        session_data["total_generation_count"] += 1
        
        # 今日の生成数をカウント
        today = datetime.now().date().isoformat()
        if generation_info.get("generated_at", "").startswith(today):
            session_data["daily_generation_count"] += 1
        
        # 最新20件のみ保持
        if len(session_data["generated_images"]) > 20:
            session_data["generated_images"] = session_data["generated_images"][-20:]
        
        return self.update_session_data(session_id, session_data)
    
    def add_active_task(self, session_id: str, task_info: Dict) -> bool:
        """
        アクティブタスクを追加
        
        Args:
            session_id (str): セッションID
            task_info (dict): タスク情報
            
        Returns:
            bool: 追加成功可否
        """
        session_data = self.get_session_data(session_id, update_activity=False)
        if not session_data:
            return False
        
        task_info["started_at"] = datetime.utcnow().isoformat()
        session_data["active_tasks"].append(task_info)
        
        return self.update_session_data(session_id, session_data)
    
    def remove_active_task(self, session_id: str, task_id: str) -> bool:
        """
        アクティブタスクを除去
        
        Args:
            session_id (str): セッションID
            task_id (str): タスクID
            
        Returns:
            bool: 除去成功可否
        """
        session_data = self.get_session_data(session_id, update_activity=False)
        if not session_data:
            return False
        
        # タスクIDに一致するタスクを除去
        session_data["active_tasks"] = [
            task for task in session_data["active_tasks"]
            if task.get("task_id") != task_id
        ]
        
        return self.update_session_data(session_id, session_data)
    
    def check_daily_limit(self, session_id: str) -> Tuple[bool, int, int]:
        """
        日次生成制限チェック
        
        Args:
            session_id (str): セッションID
            
        Returns:
            tuple: (制限内可否, 現在の生成数, 制限数)
        """
        session_data = self.get_session_data(session_id)
        if not session_data:
            logger.warning(f"セッションデータが見つかりません（制限チェック）: {session_id}")
            return False, 0, 0
        
        daily_limit = current_app.config.get('USER_DAILY_LIMIT', 50) if current_app else 50
        daily_count = session_data.get("daily_generation_count", 0)
        
        return daily_count < daily_limit, daily_count, daily_limit
    
    def get_concurrent_tasks_count(self, session_id: str) -> int:
        """
        同時実行タスク数取得
        
        Args:
            session_id (str): セッションID
            
        Returns:
            int: 同時実行タスク数
        """
        session_data = self.get_session_data(session_id, update_activity=False)
        if not session_data:
            return 0
        
        # 古いタスクをクリーンアップ（10分以上前のタスク）
        cutoff_time = datetime.utcnow() - timedelta(minutes=10)
        active_tasks = []
        
        for task in session_data.get("active_tasks", []):
            started_at = datetime.fromisoformat(task.get("started_at", ""))
            if started_at > cutoff_time:
                active_tasks.append(task)
        
        # 更新
        if len(active_tasks) != len(session_data.get("active_tasks", [])):
            session_data["active_tasks"] = active_tasks
            self.update_session_data(session_id, session_data)
        
        return len(active_tasks)
    
    def cleanup_expired_sessions(self) -> int:
        """
        期限切れセッションのクリーンアップ
        
        Returns:
            int: クリーンアップされたセッション数
        """
        if not self.redis_client:
            return 0
        
        try:
            # セッション一覧取得
            session_keys = self.redis_client.keys("session:*")
            cleaned_count = 0
            
            for key in session_keys:
                data = self.redis_client.get(key)
                if data:
                    session_data = json.loads(data)
                    last_activity = datetime.fromisoformat(
                        session_data.get("last_activity", "")
                    )
                    
                    # 24時間以上アクティビティがないセッションを削除
                    if datetime.utcnow() - last_activity > timedelta(hours=24):
                        self.redis_client.delete(key)
                        cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"期限切れセッション {cleaned_count} 件をクリーンアップしました")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"セッションクリーンアップエラー: {e}")
            return 0
    
    def update_last_activity(self, session_id: str) -> bool:
        """
        最終アクティビティ時刻更新
        
        Args:
            session_id (str): セッションID
            
        Returns:
            bool: 更新成功可否
        """
        return self.update_session_data(session_id, {
            "last_activity": datetime.utcnow().isoformat()
        })
    
    def get_session_statistics(self) -> Dict:
        """
        セッション統計情報取得
        
        Returns:
            dict: 統計情報
        """
        if not self.redis_client:
            return {"error": "Redis接続なし"}
        
        try:
            session_keys = self.redis_client.keys("session:*")
            active_sessions = 0
            total_generations = 0
            
            for key in session_keys:
                data = self.redis_client.get(key)
                if data:
                    session_data = json.loads(data)
                    
                    # アクティブセッション判定（過去1時間以内）
                    last_activity = datetime.fromisoformat(
                        session_data.get("last_activity", "")
                    )
                    if datetime.utcnow() - last_activity < timedelta(hours=1):
                        active_sessions += 1
                    
                    total_generations += session_data.get("total_generation_count", 0)
            
            return {
                "total_sessions": len(session_keys),
                "active_sessions": active_sessions,
                "total_generations": total_generations
            }
            
        except Exception as e:
            logger.error(f"統計情報取得エラー: {e}")
            return {"error": str(e)}
    
    def _get_fallback_session_data(self, session_id: str) -> Dict:
        """Redis利用不可時のフォールバックセッションデータ"""
        return {
            "user_id": session_id,
            "user_name": f"User_{session_id[:8]}",
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "uploaded_files": [],
            "generated_images": [],
            "active_tasks": [],
            "daily_generation_count": 0,
            "total_generation_count": 0,
            "fallback_mode": True
        } 