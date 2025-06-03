"""
Hair Style AI Generator - Task Service
Celery非同期タスク処理とSocketIO統合
"""

import logging
import time
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
    
    def generate_multiple_hairstyles_async(self, user_id: str, file_path: str, 
                                         japanese_prompt: str, original_filename: str, 
                                         count: int = 1, base_seed: Optional[int] = None) -> str:
        """
        複数画像非同期ヘアスタイル生成タスクの開始
        
        Args:
            user_id (str): ユーザーID
            file_path (str): アップロードファイルパス
            japanese_prompt (str): 日本語プロンプト
            original_filename (str): 元ファイル名
            count (int): 生成枚数（1~5枚）
            base_seed (int, optional): ベースシード値
            
        Returns:
            str: メインタスクID
        """
        if not 1 <= count <= 5:
            raise ValueError("生成枚数は1~5枚の間で指定してください")

        if not self.celery_app:
            # Celery利用不可の場合は同期実行
            return self._generate_multiple_hairstyles_sync(user_id, file_path, japanese_prompt, original_filename, count, base_seed)
        
        # 非同期タスク開始
        task = self.celery_app.send_task(
            'app.services.task_service.generate_multiple_hairstyles_task',
            args=[user_id, file_path, japanese_prompt, original_filename, count, base_seed]
        )
        
        # セッションにタスク追加
        task_info = {
            "task_id": task.id,
            "type": "multiple_hairstyle_generation",
            "japanese_prompt": japanese_prompt,
            "original_filename": original_filename,
            "count": count,
            "base_seed": base_seed,
            "status": "queued"
        }
        self.session_service.add_active_task(user_id, task_info)
        
        logger.info(f"複数画像非同期ヘアスタイル生成タスク開始: {task.id} ({count}枚)")
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
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "flux_task_id": flux_task_id,
                    "original_filename": original_filename,
                    "uploaded_path": file_path,  # アップロード画像のパス
                    "generated_path": saved_path,  # 生成画像のパス
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
                        'uploaded_path': file_path.replace('app/', '/'),
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
    
    def _generate_multiple_hairstyles_sync(self, user_id: str, file_path: str, 
                                         japanese_prompt: str, original_filename: str, 
                                         count: int = 1, base_seed: Optional[int] = None) -> str:
        """
        複数画像同期ヘアスタイル生成（Celery利用不可時）
        
        Args:
            user_id (str): ユーザーID
            file_path (str): アップロードファイルパス
            japanese_prompt (str): 日本語プロンプト
            original_filename (str): 元ファイル名
            count (int): 生成枚数
            base_seed (int, optional): ベースシード値
            
        Returns:
            str: 疑似タスクID
        """
        task_id = str(uuid.uuid4())
        
        try:
            self._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'processing',
                'stage': 'prompt_optimization',
                'message': 'プロンプトを最適化しています...',
                'count': count,
                'type': 'multiple'
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
                'message': f'{count}枚の画像を並行生成しています...',
                'count': count,
                'type': 'multiple'
            })
            
            # Base64変換
            image_base64 = self.file_service.convert_to_base64(file_path, max_size=2048)
            
            # 複数FLUX.1生成開始
            task_infos = self.flux_service.generate_multiple_hair_styles(
                image_base64=image_base64,
                optimized_prompt=optimized_prompt,
                count=count,
                base_seed=base_seed
            )
            
            # 複数タスクポーリング（進捗通知付き）
            def progress_callback(progress_info):
                completed = progress_info.get('completed', 0)
                total = progress_info.get('total', count)
                elapsed = progress_info.get('elapsed_time', 0)
                
                self._emit_progress(user_id, {
                    'task_id': task_id,
                    'status': 'processing',
                    'stage': 'waiting_ai',
                    'message': f'AI処理中... {completed}/{total}枚完了 ({elapsed:.1f}秒)',
                    'completed': completed,
                    'total': total,
                    'elapsed_time': elapsed,
                    'count': count,
                    'type': 'multiple'
                })
            
            results = self.flux_service.poll_multiple_until_ready(
                task_infos, progress_callback=progress_callback
            )
            
            self._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'processing',
                'stage': 'saving',
                'message': '生成画像を保存しています...',
                'count': count,
                'type': 'multiple'
            })
            
            # 複数画像保存
            saved_results = self.flux_service.download_and_save_multiple_images(
                results, user_id, original_filename
            )
            
            # 成功した画像をセッションに追加
            successful_images = []
            for i, saved in enumerate(saved_results):
                if saved['success']:
                    generation_info = {
                        "id": str(uuid.uuid4()),
                        "task_id": task_id,
                        "flux_task_id": saved.get('task_id'),
                        "original_filename": original_filename,
                        "uploaded_path": file_path,
                        "generated_path": saved['path'],
                        "japanese_prompt": japanese_prompt,
                        "optimized_prompt": optimized_prompt,
                        "index": saved['index'],
                        "seed": saved.get('seed'),
                        "is_multiple": True,
                        "generation_count": count
                    }
                    self.session_service.add_generated_image(user_id, generation_info)
                    successful_images.append({
                        'index': saved['index'],
                        'path': saved['path'].replace('app/', '/'),
                        'seed': saved.get('seed')
                    })
            
            success_count = len(successful_images)
            
            # 完了通知
            self._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'completed',
                'stage': 'finished',
                'message': f'ヘアスタイル生成が完了しました！ ({success_count}/{count}枚成功)',
                'count': count,
                'success_count': success_count,
                'type': 'multiple',
                'result': {
                    'uploaded_path': file_path.replace('app/', '/'),
                    'original_filename': original_filename,
                    'generated_images': successful_images,
                    'total_requested': count,
                    'total_succeeded': success_count
                }
            })
            
            return task_id
                
        except Exception as e:
            logger.error(f"複数画像同期生成エラー: {e}")
            self._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'failed',
                'stage': 'error',
                'message': f'生成エラー: {str(e)}',
                'count': count,
                'type': 'multiple'
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
            # 必ずタイムスタンプを追加
            progress_data['timestamp'] = time.time()
            
            # 強化されたログ出力
            logger.info(f"=== 進捗通知開始 ===")
            logger.info(f"User ID: {user_id}")
            logger.info(f"Status: {progress_data.get('status', 'unknown')}")
            logger.info(f"Message: {progress_data.get('message', '')}")
            logger.info(f"Task ID: {progress_data.get('task_id', 'none')}")
            
            # 複数の方法で通知を試行
            notification_attempts = []
            
            # 1. 外部SocketIO使用（Celeryワーカー用）
            if self.external_socketio:
                try:
                    self.external_socketio.emit(
                        'generation_progress',
                        progress_data,
                        room=f"user_{user_id}"
                    )
                    notification_attempts.append("外部SocketIO: 成功")
                    logger.info(f"外部SocketIO通知送信成功: {user_id}")
                except Exception as e:
                    notification_attempts.append(f"外部SocketIO: 失敗 - {e}")
                    logger.warning(f"外部SocketIO通知失敗: {e}")
            else:
                notification_attempts.append("外部SocketIO: 利用不可")
                logger.info("外部SocketIO利用不可")
            
            # 2. 直接SocketIO使用
            try:
                from app import socketio
                socketio.emit(
                    'generation_progress',
                    progress_data,
                    room=f"user_{user_id}"
                )
                notification_attempts.append("直接SocketIO: 成功")
                logger.info(f"直接SocketIO通知送信成功: {user_id}")
            except Exception as e:
                notification_attempts.append(f"直接SocketIO: 失敗 - {e}")
                logger.warning(f"直接SocketIO通知失敗: {e}")
            
            # 3. ブロードキャスト（ルーム指定なし）も試行
            try:
                from app import socketio
                socketio.emit('generation_progress', progress_data)
                notification_attempts.append("ブロードキャスト: 成功")
                logger.info(f"ブロードキャスト通知送信成功: {user_id}")
            except Exception as e:
                notification_attempts.append(f"ブロードキャスト: 失敗 - {e}")
                logger.error(f"ブロードキャスト通知も失敗: {e}")
            
            # 結果サマリー
            logger.info(f"=== 通知結果サマリー ===")
            for attempt in notification_attempts:
                logger.info(f"  - {attempt}")
            logger.info(f"========================")
            
        except Exception as e:
            logger.error(f"進捗通知重大エラー: {e}")
            import traceback
            logger.error(traceback.format_exc())


# Celeryタスク定義
def register_celery_tasks(celery_app: Celery):
    """Celeryタスクの登録"""
    
    @celery_app.task(bind=True, name='app.services.task_service.generate_hairstyle_task')
    def generate_hairstyle_task(self, user_id: str, file_path: str, 
                              japanese_prompt: str, original_filename: str):
        """
        非同期ヘアスタイル生成タスク（Celery用）
        
        Args:
            user_id (str): ユーザーID
            file_path (str): アップロードファイルパス
            japanese_prompt (str): 日本語プロンプト
            original_filename (str): 元ファイル名
        """
        task_id = self.request.id
        
        # サービス初期化
        gemini_service = GeminiService()
        flux_service = FluxService()
        file_service = FileService()
        session_service = SessionService()
        
        # 外部SocketIO（Celeryワーカー用）
        external_socketio = None
        try:
            external_socketio = create_socketio_external()
        except Exception as e:
            logger.warning(f"外部SocketIO初期化失敗: {e}")
        
        def emit_progress(progress_data):
            """進捗通知ヘルパー"""
            try:
                if external_socketio:
                    external_socketio.emit(
                        'generation_progress',
                        progress_data,
                        room=f"user_{user_id}"
                    )
                logger.debug(f"進捗通知: {progress_data.get('message', '')}")
            except Exception as e:
                logger.warning(f"進捗通知エラー: {e}")
        
        try:
            emit_progress({
                'task_id': task_id,
                'status': 'processing',
                'stage': 'prompt_optimization',
                'message': 'プロンプトを最適化しています...'
            })
            
            # プロンプト最適化
            image_features = file_service.analyze_image_features(file_path)
            image_analysis = f"解像度: {image_features.get('width')}x{image_features.get('height')}, 向き: {image_features.get('orientation')}"
            
            optimized_prompt = gemini_service.optimize_hair_style_prompt(
                japanese_prompt, image_analysis
            )
            
            emit_progress({
                'task_id': task_id,
                'status': 'processing',
                'stage': 'image_generation',
                'message': 'AI画像を生成しています...'
            })
            
            # Base64変換
            image_base64 = file_service.convert_to_base64(file_path, max_size=2048)
            
            # FLUX.1生成
            flux_task_id = flux_service.generate_hair_style(image_base64, optimized_prompt)
            
            # ポーリング（進捗通知付き）
            def progress_callback(progress_info):
                emit_progress({
                    'task_id': task_id,
                    'status': 'processing',
                    'stage': 'waiting_ai',
                    'message': f'AI処理中... ({progress_info["elapsed_time"]:.1f}秒)',
                    'attempt': progress_info.get('attempt', 0)
                })
            
            image_url, result_detail = flux_service.poll_until_ready(
                flux_task_id, progress_callback=progress_callback
            )
            
            emit_progress({
                'task_id': task_id,
                'status': 'processing',
                'stage': 'saving',
                'message': '生成画像を保存しています...'
            })
            
            # 画像保存
            success, saved_path = file_service.save_generated_image(
                image_url, user_id, original_filename, flux_task_id
            )
            
            if success:
                # セッションに追加
                generation_info = {
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "flux_task_id": flux_task_id,
                    "original_filename": original_filename,
                    "uploaded_path": file_path,
                    "generated_path": saved_path,
                    "japanese_prompt": japanese_prompt,
                    "optimized_prompt": optimized_prompt
                }
                session_service.add_generated_image(user_id, generation_info)
                
                emit_progress({
                    'task_id': task_id,
                    'status': 'completed',
                    'stage': 'finished',
                    'message': 'ヘアスタイル生成が完了しました！',
                    'result': {
                        'generated_path': saved_path.replace('app/', '/'),
                        'uploaded_path': file_path.replace('app/', '/'),
                        'original_filename': original_filename
                    }
                })
                
                return {
                    'success': True,
                    'generated_path': saved_path,
                    'flux_task_id': flux_task_id
                }
            else:
                raise Exception("生成画像の保存に失敗しました")
                
        except Exception as e:
            logger.error(f"Celeryタスクエラー: {e}")
            emit_progress({
                'task_id': task_id,
                'status': 'failed',
                'stage': 'error',
                'message': f'生成エラー: {str(e)}'
            })
            raise
        finally:
            # アクティブタスクから削除
            session_service.remove_active_task(user_id, task_id)

    @celery_app.task(bind=True, name='app.services.task_service.generate_multiple_hairstyles_task')
    def generate_multiple_hairstyles_task(self, user_id: str, file_path: str, 
                                        japanese_prompt: str, original_filename: str, 
                                        count: int = 1, base_seed: Optional[int] = None):
        """
        複数画像非同期ヘアスタイル生成タスク（Celery用）
        
        Args:
            user_id (str): ユーザーID
            file_path (str): アップロードファイルパス
            japanese_prompt (str): 日本語プロンプト
            original_filename (str): 元ファイル名
            count (int): 生成枚数
            base_seed (int, optional): ベースシード値
        """
        task_id = self.request.id
        
        # サービス初期化
        gemini_service = GeminiService()
        flux_service = FluxService()
        file_service = FileService()
        session_service = SessionService()
        
        # 外部SocketIO（Celeryワーカー用）
        external_socketio = None
        try:
            external_socketio = create_socketio_external()
        except Exception as e:
            logger.warning(f"外部SocketIO初期化失敗: {e}")
        
        def emit_progress(progress_data):
            """進捗通知ヘルパー"""
            try:
                if external_socketio:
                    external_socketio.emit(
                        'generation_progress',
                        progress_data,
                        room=f"user_{user_id}"
                    )
                logger.debug(f"進捗通知: {progress_data.get('message', '')}")
            except Exception as e:
                logger.warning(f"進捗通知エラー: {e}")
        
        try:
            emit_progress({
                'task_id': task_id,
                'status': 'processing',
                'stage': 'prompt_optimization',
                'message': 'プロンプトを最適化しています...',
                'count': count,
                'type': 'multiple'
            })
            
            # プロンプト最適化
            image_features = file_service.analyze_image_features(file_path)
            image_analysis = f"解像度: {image_features.get('width')}x{image_features.get('height')}, 向き: {image_features.get('orientation')}"
            
            optimized_prompt = gemini_service.optimize_hair_style_prompt(
                japanese_prompt, image_analysis
            )
            
            emit_progress({
                'task_id': task_id,
                'status': 'processing',
                'stage': 'image_generation',
                'message': f'{count}枚の画像を並行生成しています...',
                'count': count,
                'type': 'multiple'
            })
            
            # Base64変換
            image_base64 = file_service.convert_to_base64(file_path, max_size=2048)
            
            # 複数FLUX.1生成開始
            task_infos = flux_service.generate_multiple_hair_styles(
                image_base64=image_base64,
                optimized_prompt=optimized_prompt,
                count=count,
                base_seed=base_seed
            )
            
            # 複数タスクポーリング（進捗通知付き）
            def progress_callback(progress_info):
                completed = progress_info.get('completed', 0)
                total = progress_info.get('total', count)
                elapsed = progress_info.get('elapsed_time', 0)
                
                emit_progress({
                    'task_id': task_id,
                    'status': 'processing',
                    'stage': 'waiting_ai',
                    'message': f'AI処理中... {completed}/{total}枚完了 ({elapsed:.1f}秒)',
                    'completed': completed,
                    'total': total,
                    'elapsed_time': elapsed,
                    'count': count,
                    'type': 'multiple'
                })
            
            results = flux_service.poll_multiple_until_ready(
                task_infos, progress_callback=progress_callback
            )
            
            emit_progress({
                'task_id': task_id,
                'status': 'processing',
                'stage': 'saving',
                'message': '生成画像を保存しています...',
                'count': count,
                'type': 'multiple'
            })
            
            # 複数画像保存
            saved_results = flux_service.download_and_save_multiple_images(
                results, user_id, original_filename
            )
            
            # 成功した画像をセッションに追加
            successful_images = []
            for i, saved in enumerate(saved_results):
                if saved['success']:
                    generation_info = {
                        "id": str(uuid.uuid4()),
                        "task_id": task_id,
                        "flux_task_id": saved.get('task_id'),
                        "original_filename": original_filename,
                        "uploaded_path": file_path,
                        "generated_path": saved['path'],
                        "japanese_prompt": japanese_prompt,
                        "optimized_prompt": optimized_prompt,
                        "index": saved['index'],
                        "seed": saved.get('seed'),
                        "is_multiple": True,
                        "generation_count": count
                    }
                    session_service.add_generated_image(user_id, generation_info)
                    successful_images.append({
                        'index': saved['index'],
                        'path': saved['path'].replace('app/', '/'),
                        'seed': saved.get('seed')
                    })
            
            success_count = len(successful_images)
            
            # 完了通知
            emit_progress({
                'task_id': task_id,
                'status': 'completed',
                'stage': 'finished',
                'message': f'ヘアスタイル生成が完了しました！ ({success_count}/{count}枚成功)',
                'count': count,
                'success_count': success_count,
                'type': 'multiple',
                'result': {
                    'uploaded_path': file_path.replace('app/', '/'),
                    'original_filename': original_filename,
                    'generated_images': successful_images,
                    'total_requested': count,
                    'total_succeeded': success_count
                }
            })
            
            return {
                'success': True,
                'count': count,
                'success_count': success_count,
                'generated_images': successful_images
            }
                
        except Exception as e:
            logger.error(f"複数画像Celeryタスクエラー: {e}")
            emit_progress({
                'task_id': task_id,
                'status': 'failed',
                'stage': 'error',
                'message': f'生成エラー: {str(e)}',
                'count': count,
                'type': 'multiple'
            })
            raise
        finally:
            # アクティブタスクから削除
            session_service.remove_active_task(user_id, task_id)

    return celery_app 