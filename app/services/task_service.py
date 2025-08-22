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
                               japanese_prompt: str, original_filename: str,
                               task_id: Optional[str] = None,
                               mode: str = 'kontext',
                               mask_data: str = None,
                               effect_type: str = 'none') -> str:
        """
        非同期ヘアスタイル生成タスクの開始（特定効果対応版）
        
        Args:
            user_id (str): ユーザーID
            file_path (str): アップロードファイルパス
            japanese_prompt (str): 日本語プロンプト
            original_filename (str): 元ファイル名
            task_id (str, optional): フロントエンドで生成されたタスクID
            mode (str): 生成モード ('kontext' or 'fill')
            mask_data (str): マスクデータ（fill時）
            effect_type (str): 追加効果タイプ ('none', 'bright_bg', 'glossy_hair')
            
        Returns:
            str: タスクID
        """
        if not self.celery_app:
            # Celery利用不可の場合は同期実行
            return self._generate_hairstyle_sync(user_id, file_path, japanese_prompt, original_filename, task_id, effect_type)

        # 非同期タスク開始
        task = self.celery_app.send_task(
            'app.services.task_service.generate_hairstyle_task',
            args=[user_id, file_path, japanese_prompt, original_filename, mode, mask_data, effect_type],
            task_id=task_id
        )

        # セッションにタスク追加
        task_info = {
            "task_id": task.id,
            "type": "hairstyle_generation",
            "japanese_prompt": japanese_prompt,
            "original_filename": original_filename,
            "effect_type": effect_type,
            "status": "queued"
        }
        self.session_service.add_active_task(user_id, task_info)

        logger.info(f"非同期ヘアスタイル生成タスク開始: {task.id} (効果: {effect_type})")
        return task.id
    
    def generate_multiple_hairstyles_async(self, user_id: str, file_path: str, 
                                         japanese_prompt: str, original_filename: str, 
                                         count: int = 1, base_seed: Optional[int] = None,
                                         task_id: Optional[str] = None,
                                         mode: str = 'kontext',
                                         mask_data: str = None,
                                         effect_type: str = 'none') -> str:
        """
        複数画像非同期ヘアスタイル生成タスクの開始（特定効果対応版）
        
        Args:
            user_id (str): ユーザーID
            file_path (str): アップロードファイルパス
            japanese_prompt (str): 日本語プロンプト
            original_filename (str): 元ファイル名
            count (int): 生成枚数（1~5枚）
            base_seed (int, optional): ベースシード値
            task_id (str, optional): フロントエンドで生成されたタスクID
            mode (str): 生成モード ('kontext' or 'fill')
            mask_data (str): マスクデータ（fill時）
            effect_type (str): 追加効果タイプ ('none', 'bright_bg', 'glossy_hair')
            
        Returns:
            str: メインタスクID
        """
        if not 1 <= count <= 5:
            raise ValueError("生成枚数は1~5枚の間で指定してください")

        if not self.celery_app:
            # Celery利用不可の場合は同期実行
            return self._generate_multiple_hairstyles_sync(
                user_id, file_path, japanese_prompt, original_filename, 
                task_id=task_id, count=count, base_seed=base_seed, effect_type=effect_type
            )
        
        # 非同期タスク開始
        task = self.celery_app.send_task(
            'app.services.task_service.generate_multiple_hairstyles_task',
            args=[user_id, file_path, japanese_prompt, original_filename, count, base_seed, mode, mask_data, effect_type],
            task_id=task_id
        )
        
        # セッションにタスク追加
        task_info = {
            "task_id": task.id,
            "type": "multiple_hairstyle_generation",
            "japanese_prompt": japanese_prompt,
            "original_filename": original_filename,
            "count": count,
            "base_seed": base_seed,
            "effect_type": effect_type,
            "status": "queued"
        }
        self.session_service.add_active_task(user_id, task_info)
        
        logger.info(f"複数画像非同期ヘアスタイル生成タスク開始: {task.id} ({count}枚, 効果: {effect_type})")
        return task.id

    def _prepare_generation_assets(self, file_path: str, japanese_prompt: str, effect_type: str = 'none'):
        """
        画像特徴分析・プロンプト最適化・Base64エンコードをまとめて実行（特定効果対応版）
        Args:
            file_path (str): 画像ファイルパス
            japanese_prompt (str): 日本語プロンプト
            effect_type (str): 追加効果タイプ
        Returns:
            tuple: (optimized_prompt, image_base64)
        """
        image_features = self.file_service.analyze_image_features(file_path)
        image_analysis = f"解像度: {image_features.get('width')}x{image_features.get('height')}, 向き: {image_features.get('orientation')}"
        optimized_prompt = self.gemini_service.optimize_hair_style_prompt(japanese_prompt, image_analysis, effect_type=effect_type)
        image_base64 = self.file_service.convert_to_base64(file_path, max_size=2048)
        return optimized_prompt, image_base64

    def _execute_single_generation(self, user_id: str, file_path: str,
                                   japanese_prompt: str, original_filename: str, task_id: str,
                                   mode: str = 'kontext', mask_data: str = None, effect_type: str = 'none'):
        """単一画像生成のコアロジック（特定効果対応版）"""
        emit_progress = lambda data: self._emit_progress(user_id, data)

        emit_progress({
            'task_id': task_id,
            'status': 'processing',
            'stage': 'prompt_optimization',
            'message': 'プロンプトを最適化しています...'
        })
        
        optimized_prompt, image_base64 = self._prepare_generation_assets(file_path, japanese_prompt, effect_type=effect_type)
        
        emit_progress({
            'task_id': task_id,
            'status': 'processing',
            'stage': 'image_generation',
            'message': 'AI画像を生成しています...'
        })
        
        if mode == 'fill' and mask_data:
            flux_task_id, polling_url = self.flux_service.generate_with_fill(image_base64, mask_data, optimized_prompt)
        else:
            flux_task_id = self.flux_service.generate_hair_style(image_base64, optimized_prompt)
            polling_url = None
        
        def progress_callback(progress_info):
            emit_progress({
                'task_id': task_id,
                'status': 'processing',
                'stage': 'waiting_ai',
                'message': f'AI処理中... ({progress_info["elapsed_time"]:.1f}秒)',
                'attempt': progress_info.get('attempt', 0)
            })
        
        image_url, result_detail = self.flux_service.poll_until_ready(
            flux_task_id, progress_callback=progress_callback
        )
        
        emit_progress({
            'task_id': task_id,
            'status': 'processing',
            'stage': 'saving',
            'message': '生成画像を保存しています...'
        })
        
        success, saved_path = self.file_service.save_generated_image(
            image_url, user_id, original_filename, flux_task_id
        )
        
        if success:
            generation_info = {
                "id": str(uuid.uuid4()),
                "task_id": task_id,
                "flux_task_id": flux_task_id,
                "original_filename": original_filename,
                "uploaded_path": file_path,
                "generated_path": saved_path,
                "japanese_prompt": japanese_prompt,
                "optimized_prompt": optimized_prompt,
                "effect_type": effect_type
            }
            self.session_service.add_generated_image(user_id, generation_info)
            
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
            return {'success': True, 'generated_path': saved_path, 'flux_task_id': flux_task_id}
        else:
            raise Exception("生成画像の保存に失敗しました")

    def _execute_multiple_generation(self, user_id: str, file_path: str,
                                     japanese_prompt: str, original_filename: str,
                                     count: int, base_seed: Optional[int], task_id: str,
                                     mode: str = 'kontext', mask_data: str = None):
        """複数画像生成のコアロジック"""
        emit_progress = lambda data: self._emit_progress(user_id, data)

        emit_progress({
            'task_id': task_id, 'status': 'processing', 'stage': 'prompt_optimization',
            'message': 'プロンプトを最適化しています...', 'count': count, 'type': 'multiple'
        })

        optimized_prompt, image_base64 = self._prepare_generation_assets(file_path, japanese_prompt)

        emit_progress({
            'task_id': task_id, 'status': 'processing', 'stage': 'image_generation',
            'message': f'{count}枚の画像を並行生成しています...', 'count': count, 'type': 'multiple'
        })
        
        if mode == 'fill' and mask_data:
            # fillモード時は全て同じマスク・プロンプトで複数回呼び出し
            task_infos = []
            for i in range(count):
                flux_task_id, polling_url = self.flux_service.generate_with_fill(image_base64, mask_data, optimized_prompt)
                task_infos.append({'id': flux_task_id, 'polling_url': polling_url})
        else:
            task_infos = self.flux_service.generate_multiple_hair_styles(
                image_base64=image_base64, optimized_prompt=optimized_prompt, count=count, base_seed=base_seed
            )
        
        def progress_callback(progress_info):
            completed = progress_info.get('completed', 0)
            total = progress_info.get('total', count)
            elapsed = progress_info.get('elapsed_time', 0)
            emit_progress({
                'task_id': task_id, 'status': 'processing', 'stage': 'waiting_ai',
                'message': f'AI処理中... {completed}/{total}枚完了 ({elapsed:.1f}秒)',
                'completed': completed, 'total': total, 'elapsed_time': elapsed, 'count': count, 'type': 'multiple'
            })
            
        if mode == 'fill' and mask_data:
            results = []
            for info in task_infos:
                image_url, result_detail = self.flux_service.poll_until_ready(
                    info['id'], progress_callback=progress_callback
                )
                results.append({'sample': image_url, 'task_id': info['id']})
        else:
            results = self.flux_service.poll_multiple_until_ready(task_infos, progress_callback=progress_callback)
        
        emit_progress({
            'task_id': task_id, 'status': 'processing', 'stage': 'saving',
            'message': '生成画像を保存しています...', 'count': count, 'type': 'multiple'
        })
        
        saved_results = self.flux_service.download_and_save_multiple_images(results, user_id, original_filename)
        
        successful_images = []
        for saved in saved_results:
            if saved['success']:
                generation_info = {
                    "id": str(uuid.uuid4()), "task_id": task_id, "flux_task_id": saved.get('task_id'),
                    "original_filename": original_filename, "uploaded_path": file_path, "generated_path": saved['path'],
                    "japanese_prompt": japanese_prompt, "optimized_prompt": optimized_prompt, "index": saved['index'],
                    "seed": saved.get('seed'), "is_multiple": True, "generation_count": count
                }
                self.session_service.add_generated_image(user_id, generation_info)
                successful_images.append({
                    'index': saved['index'], 'path': saved['path'].replace('app/', '/'), 'seed': saved.get('seed')
                })
                
        success_count = len(successful_images)
        
        emit_progress({
            'task_id': task_id, 'status': 'completed', 'stage': 'finished',
            'message': f'ヘアスタイル生成が完了しました！ ({success_count}/{count}枚成功)',
            'count': count, 'success_count': success_count, 'type': 'multiple',
            'result': {
                'uploaded_path': file_path.replace('app/', '/'), 'original_filename': original_filename,
                'generated_images': successful_images, 'total_requested': count, 'total_succeeded': success_count
            }
        })
        
        return {'success': True, 'count': count, 'success_count': success_count, 'generated_images': successful_images}

    def _generate_hairstyle_sync(self, user_id: str, file_path: str,
                               japanese_prompt: str, original_filename: str, task_id: str, effect_type: str = 'none') -> str:
        """同期ヘアスタイル生成（Celery利用不可時、特定効果対応版）"""
        try:
            # アクティブタスク追加
            task_info = {
                "task_id": task_id, "type": "hairstyle_generation_sync",
                "japanese_prompt": japanese_prompt, "original_filename": original_filename, 
                "effect_type": effect_type, "status": "processing"
            }
            self.session_service.add_active_task(user_id, task_info)
            
            # コアロジック実行
            self._execute_single_generation(user_id, file_path, japanese_prompt, original_filename, task_id, effect_type=effect_type)

        except Exception as e:
            logger.error(f"同期生成エラー: {e}")
            self._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'failed',
                'stage': 'error',
                'message': f'生成エラー: {str(e)}'
            })
        finally:
            # アクティブタスクから削除
            self.session_service.remove_active_task(user_id, task_id)
        
        return task_id
    
    def _generate_multiple_hairstyles_sync(self, user_id: str, file_path: str, 
                                         japanese_prompt: str, original_filename: str, 
                                         task_id: str, count: int = 1, base_seed: Optional[int] = None) -> str:
        """複数画像同期ヘアスタイル生成（Celery利用不可時）"""
        try:
            # アクティブタスク追加
            task_info = {
                "task_id": task_id, "type": "multiple_hairstyle_generation_sync",
                "japanese_prompt": japanese_prompt, "original_filename": original_filename,
                "count": count, "base_seed": base_seed, "status": "processing"
            }
            self.session_service.add_active_task(user_id, task_info)
            
            # コアロジック実行
            self._execute_multiple_generation(user_id, file_path, japanese_prompt, original_filename, count, base_seed, task_id)

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
        finally:
            # アクティブタスクから削除
            self.session_service.remove_active_task(user_id, task_id)
            
        return task_id

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
            progress_data['timestamp'] = time.time()
            logger.info(f"進捗通知: user_id={user_id}, status={progress_data.get('status')}, message='{progress_data.get('message')}'")
            
            if self.external_socketio:
                self.external_socketio.emit(
                    'generation_progress',
                    progress_data,
                    room=f"user_{user_id}"
                )
            else:
                logger.warning("外部SocketIOが利用不可のため、進捗通知をスキップしました。")
                
        except Exception as e:
            logger.error(f"進捗通知中に重大なエラーが発生しました: {e}", exc_info=True)


# Celeryタスク定義
def register_celery_tasks(celery_app: Celery):
    """Celeryタスクの登録"""
    
    @celery_app.task(bind=True, name='app.services.task_service.generate_hairstyle_task')
    def generate_hairstyle_task(self, user_id: str, file_path: str, 
                              japanese_prompt: str, original_filename: str,
                              mode: str = 'kontext',
                              mask_data: str = None):
        """非同期ヘアスタイル生成タスク（Celery用）"""
        task_id = self.request.id
        task_service = TaskService(celery_app) # サービスインスタンス作成
        
        try:
            return task_service._execute_single_generation(user_id, file_path, japanese_prompt, original_filename, task_id, mode, mask_data)
        except Exception as e:
            logger.error(f"Celeryタスクエラー: {e}")
            task_service._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'failed',
                'stage': 'error',
                'message': f'生成エラー: {str(e)}'
            })
            raise
        finally:
            task_service.session_service.remove_active_task(user_id, task_id)

    @celery_app.task(bind=True, name='app.services.task_service.generate_multiple_hairstyles_task')
    def generate_multiple_hairstyles_task(self, user_id: str, file_path: str, 
                                        japanese_prompt: str, original_filename: str, 
                                        count: int = 1, base_seed: Optional[int] = None,
                                        mode: str = 'kontext',
                                        mask_data: str = None):
        """複数画像非同期ヘアスタイル生成タスク（Celery用）"""
        task_id = self.request.id
        task_service = TaskService(celery_app) # サービスインスタンス作成
        
        try:
            return task_service._execute_multiple_generation(user_id, file_path, japanese_prompt, original_filename, count, base_seed, task_id, mode, mask_data)
        except Exception as e:
            logger.error(f"複数画像Celeryタスクエラー: {e}")
            task_service._emit_progress(user_id, {
                'task_id': task_id,
                'status': 'failed',
                'stage': 'error',
                'message': f'生成エラー: {str(e)}',
                'count': count,
                'type': 'multiple'
            })
            raise
        finally:
            task_service.session_service.remove_active_task(user_id, task_id)

    return celery_app 