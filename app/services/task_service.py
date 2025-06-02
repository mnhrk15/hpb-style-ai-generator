"""
Hair Style AI Generator - Task Service
Celery非同期タスク処理とSocketIO統合
"""

import logging
from typing import Dict, Optional, Any
from celery import Celery
from flask import current_app
from flask_socketio import emit
from datetime import datetime
import uuid

from app.services.gemini_service import GeminiService
from app.services.flux_service import FluxService
from app.services.file_service import FileService
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)


def create_socketio_external():
    """Celeryワーカーからの通信用SocketIO"""
    from flask_socketio import SocketIO
    import os
    return SocketIO(message_queue=os.getenv('REDIS_URL', 'redis://localhost:6379/0'))


class TaskService:
    """
    Celery非同期タスク処理サービス
    SocketIOリアルタイム進捗通知統合
    """
    
    def __init__(self, celery_app: Optional[Celery] = None):
        """タスクサービスの初期化"""
        self.celery_app = celery_app
        self.gemini_service = GeminiService()
        self.flux_service = FluxService()
        self.file_service = FileService()
        self.session_service = SessionService()
        
        # 外部SocketIO（Celeryワーカー用）
        self.external_socketio = None
        try:
            self.external_socketio = create_socketio_external()
        except Exception as e:
            logger.warning(f"外部SocketIO初期化失敗: {e}")
    
    def generate_hairstyle_async(self, user_id: str, file_path: str, 
                               japanese_prompt: str, original_filename: str) -> str:
        """
        非同期ヘアスタイル生成タスクの開始
        
        Args:
            user_id (str): ユーザーID
            file_path (str): アップロードファイルパス
            japanese_prompt (str): 日本語プロンプト
            original_filename (str): 元ファイル名
            
        Returns:
            str: タスクID
        """
        if not self.celery_app:
            # Celery利用不可の場合は同期実行
            return self._generate_hairstyle_sync(user_id, file_path, japanese_prompt, original_filename)
        
        # 非同期タスク開始
        task = self.celery_app.send_task(
            'app.services.task_service.generate_hairstyle_task',
            args=[user_id, file_path, japanese_prompt, original_filename]
        )
        
        # セッションにタスク追加
        task_info = {
            "task_id": task.id,
            "type": "hairstyle_generation",
            "japanese_prompt": japanese_prompt,
            "original_filename": original_filename,
            "status": "queued"
        }
        self.session_service.add_active_task(user_id, task_info)
        
        logger.info(f"非同期ヘアスタイル生成タスク開始: {task.id}")
        return task.id
    
    def _generate_hairstyle_sync(self, user_id: str, file_path: str, 
                               japanese_prompt: str, original_filename: str) -> str:
        """
        同期ヘアスタイル生成（Celery利用不可時）
        
        Args:
            user_id (str): ユーザーID
            file_path (str): アップロードファイルパス
            japanese_prompt (str): 日本語プロンプト
            original_filename (str): 元ファイル名
            
        Returns:
            str: 疑似タスクID
        """
        task_id = str(uuid.uuid4())
        
        try:
            self._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'processing',
                'stage': 'prompt_optimization',
                'message': 'プロンプトを最適化しています...'
            })
            
            # プロンプト最適化
            image_features = self.file_service.analyze_image_features(file_path)
            image_analysis = f"解像度: {image_features.get('width')}x{image_features.get('height')}, 向き: {image_features.get('orientation')}"
            
            optimized_prompt = self.gemini_service.optimize_hair_style_prompt(
                japanese_prompt, image_analysis
            )
            
            self._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'processing',
                'stage': 'image_generation',
                'message': 'AI画像を生成しています...'
            })
            
            # Base64変換
            image_base64 = self.file_service.convert_to_base64(file_path, max_size=2048)
            
            # FLUX.1生成
            flux_task_id = self.flux_service.generate_hair_style(image_base64, optimized_prompt)
            
            # ポーリング（進捗通知付き）
            def progress_callback(progress_info):
                self._emit_progress(user_id, {
                    'task_id': task_id,
                    'status': 'processing',
                    'stage': 'waiting_ai',
                    'message': f'AI処理中... ({progress_info["elapsed_time"]:.1f}秒)',
                    'attempt': progress_info.get('attempt', 0)
                })
            
            image_url, result_detail = self.flux_service.poll_until_ready(
                flux_task_id, progress_callback=progress_callback
            )
            
            self._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'processing',
                'stage': 'saving',
                'message': '生成画像を保存しています...'
            })
            
            # 画像保存
            success, saved_path = self.file_service.save_generated_image(
                image_url, user_id, original_filename, flux_task_id
            )
            
            if success:
                # セッションに追加
                generation_info = {
                    "task_id": task_id,
                    "flux_task_id": flux_task_id,
                    "original_filename": original_filename,
                    "generated_path": saved_path,
                    "japanese_prompt": japanese_prompt,
                    "optimized_prompt": optimized_prompt
                }
                self.session_service.add_generated_image(user_id, generation_info)
                
                self._emit_progress(user_id, {
                    'task_id': task_id,
                    'status': 'completed',
                    'stage': 'finished',
                    'message': 'ヘアスタイル生成が完了しました！',
                    'result': {
                        'generated_path': saved_path.replace('app/', '/'),
                        'original_filename': original_filename
                    }
                })
                
                return task_id
            else:
                raise Exception("生成画像の保存に失敗しました")
                
        except Exception as e:
            logger.error(f"同期生成エラー: {e}")
            self._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'failed',
                'stage': 'error',
                'message': f'生成エラー: {str(e)}'
            })
            return task_id
        finally:
            # アクティブタスクから削除
            self.session_service.remove_active_task(user_id, task_id)
    
    def get_task_status(self, task_id: str) -> Dict:
        """
        タスクステータス取得
        
        Args:
            task_id (str): タスクID
            
        Returns:
            dict: タスクステータス情報
        """
        if not self.celery_app:
            return {
                "task_id": task_id,
                "status": "unknown",
                "message": "Celery利用不可"
            }
        
        try:
            result = self.celery_app.AsyncResult(task_id)
            
            return {
                "task_id": task_id,
                "status": result.status,
                "result": result.result if result.ready() else None,
                "traceback": result.traceback if result.failed() else None
            }
            
        except Exception as e:
            logger.error(f"タスクステータス取得エラー: {e}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": str(e)
            }
    
    def cancel_task(self, task_id: str, user_id: str) -> bool:
        """
        タスクキャンセル
        
        Args:
            task_id (str): タスクID
            user_id (str): ユーザーID
            
        Returns:
            bool: キャンセル成功可否
        """
        if not self.celery_app:
            return False
        
        try:
            self.celery_app.control.revoke(task_id, terminate=True)
            
            # セッションから削除
            self.session_service.remove_active_task(user_id, task_id)
            
            # キャンセル通知
            self._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'cancelled',
                'message': 'タスクがキャンセルされました'
            })
            
            logger.info(f"タスクキャンセル: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"タスクキャンセルエラー: {e}")
            return False
    
    def cleanup_old_tasks(self, hours: int = 24) -> int:
        """
        古いタスクのクリーンアップ
        
        Args:
            hours (int): 保持時間（時間）
            
        Returns:
            int: クリーンアップされたタスク数
        """
        # セッションサービスのクリーンアップを委譲
        return self.session_service.cleanup_expired_sessions()
    
    def get_user_active_tasks(self, user_id: str) -> list:
        """
        ユーザーのアクティブタスク一覧取得
        
        Args:
            user_id (str): ユーザーID
            
        Returns:
            list: アクティブタスク一覧
        """
        session_data = self.session_service.get_session_data(user_id)
        if not session_data:
            return []
        
        return session_data.get("active_tasks", [])
    
    def _emit_progress(self, user_id: str, progress_data: Dict):
        """
        進捗をSocketIOで通知
        
        Args:
            user_id (str): ユーザーID
            progress_data (dict): 進捗データ
        """
        try:
            # 外部SocketIO使用（Celeryワーカー用）
            if self.external_socketio:
                self.external_socketio.emit(
                    'generation_progress',
                    progress_data,
                    room=f"user_{user_id}"
                )
            
            logger.debug(f"進捗通知送信: {user_id} - {progress_data.get('message', '')}")
            
        except Exception as e:
            logger.warning(f"進捗通知エラー: {e}")


# Celeryタスク定義
def register_celery_tasks(celery_app: Celery):
    """Celeryタスクの登録"""
    
    @celery_app.task(bind=True, name='app.services.task_service.generate_hairstyle_task')
    def generate_hairstyle_task(self, user_id: str, file_path: str, 
                              japanese_prompt: str, original_filename: str):
        """
        Celeryヘアスタイル生成タスク
        
        Args:
            user_id (str): ユーザーID
            file_path (str): アップロードファイルパス
            japanese_prompt (str): 日本語プロンプト
            original_filename (str): 元ファイル名
        """
        task_service = TaskService(celery_app)
        task_id = self.request.id
        
        try:
            # 進捗通知
            task_service._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'processing',
                'stage': 'prompt_optimization',
                'message': 'プロンプトを最適化しています...'
            })
            
            # プロンプト最適化
            image_features = task_service.file_service.analyze_image_features(file_path)
            image_analysis = f"解像度: {image_features.get('width')}x{image_features.get('height')}, 向き: {image_features.get('orientation')}"
            
            optimized_prompt = task_service.gemini_service.optimize_hair_style_prompt(
                japanese_prompt, image_analysis
            )
            
            task_service._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'processing',
                'stage': 'image_generation',
                'message': 'AI画像を生成しています...'
            })
            
            # Base64変換
            image_base64 = task_service.file_service.convert_to_base64(file_path, max_size=2048)
            
            # FLUX.1生成
            flux_task_id = task_service.flux_service.generate_hair_style(image_base64, optimized_prompt)
            
            # ポーリング（進捗通知付き）
            def progress_callback(progress_info):
                task_service._emit_progress(user_id, {
                    'task_id': task_id,
                    'status': 'processing',
                    'stage': 'waiting_ai',
                    'message': f'AI処理中... ({progress_info["elapsed_time"]:.1f}秒)',
                    'attempt': progress_info.get('attempt', 0)
                })
            
            image_url, result_detail = task_service.flux_service.poll_until_ready(
                flux_task_id, progress_callback=progress_callback
            )
            
            task_service._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'processing',
                'stage': 'saving',
                'message': '生成画像を保存しています...'
            })
            
            # 画像保存
            success, saved_path = task_service.file_service.save_generated_image(
                image_url, user_id, original_filename, flux_task_id
            )
            
            if success:
                # セッションに追加
                generation_info = {
                    "task_id": task_id,
                    "flux_task_id": flux_task_id,
                    "original_filename": original_filename,
                    "generated_path": saved_path,
                    "japanese_prompt": japanese_prompt,
                    "optimized_prompt": optimized_prompt
                }
                task_service.session_service.add_generated_image(user_id, generation_info)
                
                # 完了通知
                task_service._emit_progress(user_id, {
                    'task_id': task_id,
                    'status': 'completed',
                    'stage': 'finished',
                    'message': 'ヘアスタイル生成が完了しました！',
                    'result': {
                        'generated_path': saved_path.replace('app/', '/'),
                        'original_filename': original_filename
                    }
                })
                
                return {
                    'success': True,
                    'generated_path': saved_path,
                    'optimized_prompt': optimized_prompt
                }
            else:
                raise Exception("生成画像の保存に失敗しました")
                
        except Exception as e:
            logger.error(f"Celeryタスクエラー: {e}")
            
            # エラー通知
            task_service._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'failed',
                'stage': 'error',
                'message': f'生成エラー: {str(e)}'
            })
            
            raise
        finally:
            # アクティブタスクから削除
            task_service.session_service.remove_active_task(user_id, task_id)
    
    return celery_app 