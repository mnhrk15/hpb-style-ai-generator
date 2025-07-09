"""
Hair Style AI Generator - FLUX.1 Kontext Service
FLUX.1 Kontext Pro API統合による高品質ヘアスタイル画像生成
"""

import os
import time
import base64
import logging
import requests
from typing import Dict, Optional, Tuple
from flask import current_app

logger = logging.getLogger(__name__)


class FluxService:
    """
    FLUX.1 Kontext Pro API統合サービス
    人物の顔・表情一貫性保持に特化した画像編集
    """
    
    def __init__(self):
        """FLUX.1 Kontextサービスの初期化"""
        self.api_key = os.getenv('BFL_API_KEY')
        self.base_url = "https://api.us1.bfl.ai/v1"
        
        # API制限設定（要件定義書準拠）
        self.max_wait_time = int(os.getenv('FLUX_MAX_WAIT_TIME', '300'))  # 5分
        self.polling_interval = float(os.getenv('FLUX_POLLING_INTERVAL', '1.5'))  # 1.5秒
        self.prompt_max_tokens = int(os.getenv('FLUX_PROMPT_MAX_TOKENS', '512'))
        
        if not self.api_key:
            logger.warning("BFL_API_KEY が設定されていません")
    
    def generate_hair_style(self, image_base64: str, optimized_prompt: str, 
                          seed: Optional[int] = None, 
                          safety_tolerance: int = 2,
                          output_format: str = "jpeg") -> Optional[str]:
        """
        ヘアスタイル画像生成
        
        Args:
            image_base64 (str): 元画像（base64エンコード）
            optimized_prompt (str): 最適化されたプロンプト（512トークン以内）
            seed (int, optional): 再現性のためのシード値
            safety_tolerance (int): 安全性許容度（0=厳格、6=寛容、デフォルト2）
            output_format (str): 出力フォーマット（"jpeg" or "png"）
            
        Returns:
            str: タスクID（非同期処理用）
            
        Raises:
            Exception: API呼び出しエラー時
        """
        if not self.api_key:
            raise Exception("BFL_API_KEY が設定されていません")
        
        # プロンプト長制限チェック
        if len(optimized_prompt.split()) > 450:  # 安全マージン
            optimized_prompt = ' '.join(optimized_prompt.split()[:450])
            logger.warning("プロンプトを512トークン制限内に調整しました")
        
        endpoint = f"{self.base_url}/flux-kontext-pro"
        
        payload = {
            "prompt": optimized_prompt,
            "input_image": image_base64,
            "seed": seed,  # 再現性のため必要に応じて設定
            "safety_tolerance": safety_tolerance,  # 0=厳格、6=寛容（デフォルト2）
            "output_format": output_format,  # "jpeg" または "png"
            "webhook_url": None,  # 非同期通知用（オプション）
            "webhook_secret": None  # Webhook認証用（オプション）
        }
        
        headers = {
            "accept": "application/json",
            "x-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                task_id = result.get("id")
                logger.info(f"FLUX.1 Kontext 生成タスク開始: {task_id}")
                return task_id
            else:
                error_msg = f"API Error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"FLUX.1 Kontext API リクエストエラー: {e}")
            raise Exception(f"APIリクエスト失敗: {e}")
    
    def get_result(self, task_id: str) -> Dict:
        """
        結果取得（ポーリング用）
        
        Args:
            task_id (str): タスクID
            
        Returns:
            dict: API結果
                - status: "Processing", "Queued", "Ready", "Error", "Content Moderated"
                - result: 成功時は画像URLを含む
                
        Raises:
            Exception: API呼び出しエラー時
        """
        if not self.api_key:
            raise Exception("BFL_API_KEY が設定されていません")
        
        url = f"{self.base_url}/get_result"
        headers = {"accept": "application/json", "x-key": self.api_key}
        params = {"id": task_id}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                # 署名付きURLは10分間のみ有効
                return result
            else:
                error_msg = f"API Error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"FLUX.1 Kontext 結果取得エラー: {e}")
            raise Exception(f"結果取得失敗: {e}")
    
    def poll_until_ready(self, task_id: str, 
                        max_wait_time: Optional[int] = None,
                        progress_callback: Optional[callable] = None) -> Tuple[str, Dict]:
        """
        結果が準備できるまでポーリング
        
        Args:
            task_id (str): タスクID
            max_wait_time (int, optional): 最大待機時間（秒、デフォルト300秒）
            progress_callback (callable, optional): 進捗通知コールバック
            
        Returns:
            tuple: (画像URL, 結果詳細)
            
        Raises:
            Exception: タイムアウト・エラー・制限時
        """
        if max_wait_time is None:
            max_wait_time = self.max_wait_time
        
        start_time = time.time()
        attempt = 0
        
        while time.time() - start_time < max_wait_time:
            try:
                result = self.get_result(task_id)
                status = result.get("status")
                attempt += 1
                
                # 進捗コールバック実行
                if progress_callback:
                    progress_callback({
                        'status': status,
                        'elapsed_time': time.time() - start_time,
                        'attempt': attempt
                    })
                
                logger.debug(f"ポーリング {attempt}回目: {status}")
                
                if status == "Ready":
                    # 署名付きURLは10分以内に取得する必要がある
                    image_url = result["result"]["sample"]
                    logger.info(f"FLUX.1 Kontext 生成完了: {task_id}")
                    return image_url, result
                
                elif status in ["Error", "Content Moderated", "Request Moderated"]:
                    error_detail = result.get("result", {}).get("message", "詳細不明")
                    error_msg = f"生成失敗: {status} - {error_detail}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                elif status in ["Processing", "Queued", "Pending"]:
                    # 継続してポーリング
                    time.sleep(self.polling_interval)
                else:
                    logger.warning(f"未知のステータス: {status}")
                    time.sleep(self.polling_interval)
                    
            except Exception as e:
                if "生成失敗" in str(e):
                    # 生成エラーは再試行しない
                    raise
                
                logger.warning(f"ポーリング中のエラー（再試行します）: {e}")
                time.sleep(self.polling_interval)
        
        # タイムアウト
        elapsed = time.time() - start_time
        raise Exception(f"タイムアウト: 画像生成に{elapsed:.1f}秒かかりました（制限: {max_wait_time}秒）")
    
    def download_and_save_image(self, image_url: str, local_path: str) -> bool:
        """
        署名付きURLから画像をダウンロードして保存
        
        Args:
            image_url (str): 署名付きURL（10分有効）
            local_path (str): 保存先パス
            
        Returns:
            bool: 保存成功可否
        """
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"画像保存完了: {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"画像ダウンロード・保存エラー: {e}")
            return False
    
    def validate_api_connection(self) -> bool:
        """
        FLUX.1 Kontext API接続テスト
        
        Returns:
            bool: 接続成功可否
        """
        if not self.api_key:
            return False
        
        try:
            # ダミーリクエストで接続確認
            headers = {"accept": "application/json", "x-key": self.api_key}
            # get_resultエンドポイントで無効なIDを使って接続確認
            response = requests.get(
                f"{self.base_url}/get_result",
                headers=headers,
                params={"id": "test"},
                timeout=10
            )
            
            # 404やAPIキーエラー以外なら接続成功とみなす
            return response.status_code != 401  # 認証エラーでなければOK
            
        except Exception as e:
            logger.error(f"FLUX.1 Kontext API接続テストエラー: {e}")
            return False
    
    def estimate_generation_time(self, complexity: str = "medium") -> int:
        """
        生成時間予測
        
        Args:
            complexity (str): 複雑度（"simple", "medium", "complex"）
            
        Returns:
            int: 予想生成時間（秒）
        """
        time_estimates = {
            "simple": 30,    # シンプルな変更
            "medium": 60,    # 一般的な変更
            "complex": 120   # 複雑な変更
        }
        
        return time_estimates.get(complexity, 60)
    
    def generate_multiple_hair_styles(self, image_base64: str, optimized_prompt: str, 
                                    count: int = 1, base_seed: Optional[int] = None,
                                    safety_tolerance: int = 2, output_format: str = "jpeg") -> list:
        """
        複数ヘアスタイル画像の並行生成
        
        Args:
            image_base64 (str): 元画像（base64エンコード）
            optimized_prompt (str): 最適化されたプロンプト
            count (int): 生成枚数（1~5枚）
            base_seed (int, optional): ベースシード値（各タスクは+1,+2...される）
            safety_tolerance (int): 安全性許容度
            output_format (str): 出力フォーマット
            
        Returns:
            list: タスクID一覧
            
        Raises:
            Exception: API呼び出しエラー時
        """
        if not 1 <= count <= 5:
            raise ValueError("生成枚数は1~5枚の間で指定してください")
        
        if not self.api_key:
            raise Exception("BFL_API_KEY が設定されていません")
        
        logger.info(f"複数画像生成開始: {count}枚")
        
        task_ids = []
        
        for i in range(count):
            try:
                # 各タスクに異なるseed値を設定（多様性確保）
                seed = None
                if base_seed is not None:
                    seed = base_seed + i
                
                # 個別タスク開始
                task_id = self.generate_hair_style(
                    image_base64=image_base64,
                    optimized_prompt=optimized_prompt,
                    seed=seed,
                    safety_tolerance=safety_tolerance,
                    output_format=output_format
                )
                
                task_ids.append({
                    'task_id': task_id,
                    'index': i + 1,
                    'seed': seed,
                    'status': 'queued'
                })
                
                logger.info(f"タスク {i+1}/{count} 開始: {task_id}")
                
            except Exception as e:
                logger.error(f"タスク {i+1} 開始エラー: {e}")
                # エラーが発生したタスクもリストに含める（エラー追跡のため）
                task_ids.append({
                    'task_id': None,
                    'index': i + 1,
                    'seed': None,
                    'status': 'failed',
                    'error': str(e)
                })
        
        logger.info(f"複数画像生成タスク開始完了: {len([t for t in task_ids if t['task_id']])}枚成功")
        return task_ids

    def poll_multiple_until_ready(self, task_infos: list, 
                                 max_wait_time: Optional[int] = None,
                                 progress_callback: Optional[callable] = None) -> list:
        """
        複数タスクの結果を並行ポーリング
        
        Args:
            task_infos (list): タスク情報リスト
            max_wait_time (int, optional): 最大待機時間
            progress_callback (callable, optional): 進捗通知コールバック
            
        Returns:
            list: 結果リスト [{'index': 1, 'image_url': '...', 'status': 'success'}, ...]
        """
        if max_wait_time is None:
            max_wait_time = self.max_wait_time
        
        start_time = time.time()
        results = []
        
        # 有効なタスクのみ処理
        valid_tasks = [task for task in task_infos if task.get('task_id')]
        
        # 結果初期化
        for task in task_infos:
            results.append({
                'index': task['index'],
                'task_id': task.get('task_id'),
                'status': 'failed' if not task.get('task_id') else 'pending',
                'image_url': None,
                'error': task.get('error'),
                'seed': task.get('seed')
            })
        
        completed_tasks = set()
        attempt = 0
        
        while len(completed_tasks) < len(valid_tasks) and time.time() - start_time < max_wait_time:
            attempt += 1
            
            for i, task in enumerate(valid_tasks):
                task_id = task['task_id']
                
                if task_id in completed_tasks:
                    continue
                
                try:
                    result = self.get_result(task_id)
                    status = result.get("status")
                    
                    # 結果のインデックスを見つける
                    result_idx = next(j for j, r in enumerate(results) if r['task_id'] == task_id)
                    
                    if status == "Ready":
                        image_url = result["result"]["sample"]
                        results[result_idx].update({
                            'status': 'success',
                            'image_url': image_url
                        })
                        completed_tasks.add(task_id)
                        logger.info(f"タスク完了: {task['index']}/{len(task_infos)} - {task_id}")
                    
                    elif status in ["Error", "Content Moderated", "Request Moderated"]:
                        error_detail = result.get("result", {}).get("message", "詳細不明")
                        results[result_idx].update({
                            'status': 'failed',
                            'error': f"{status}: {error_detail}"
                        })
                        completed_tasks.add(task_id)
                        logger.error(f"タスク失敗: {task['index']}/{len(task_infos)} - {error_detail}")
                    
                    # 進捗コールバック実行
                    if progress_callback:
                        progress_callback({
                            'completed': len(completed_tasks),
                            'total': len(valid_tasks),
                            'elapsed_time': time.time() - start_time,
                            'attempt': attempt,
                            'results': results
                        })
                        
                except Exception as e:
                    logger.warning(f"タスク {task_id} ポーリングエラー: {e}")
                    continue
            
            # 未完了タスクがある場合は待機
            if len(completed_tasks) < len(valid_tasks):
                time.sleep(self.polling_interval)
        
        # タイムアウトチェック
        if len(completed_tasks) < len(valid_tasks):
            elapsed = time.time() - start_time
            logger.warning(f"複数画像生成タイムアウト: {len(completed_tasks)}/{len(valid_tasks)}完了 ({elapsed:.1f}秒)")
            
            # 未完了タスクをタイムアウトとしてマーク
            for result in results:
                if result['status'] == 'pending':
                    result.update({
                        'status': 'timeout',
                        'error': f'タイムアウト ({elapsed:.1f}秒)'
                    })
        
        logger.info(f"複数画像生成完了: {len([r for r in results if r['status'] == 'success'])}/{len(results)}枚成功")
        return results

    def download_and_save_multiple_images(self, results: list, user_id: str, 
                                        original_filename: str, prefix: str = "generated") -> list:
        """
        複数画像の一括ダウンロード・保存
        
        Args:
            results (list): poll_multiple_until_readyの結果
            user_id (str): ユーザーID
            original_filename (str): 元ファイル名
            prefix (str): ファイル名プレフィックス
            
        Returns:
            list: 保存結果リスト
        """
        saved_results = []
        
        for result in results:
            if result['status'] != 'success' or not result['image_url']:
                saved_results.append({
                    'index': result['index'],
                    'success': False,
                    'path': None,
                    'error': result.get('error', '画像生成失敗')
                })
                continue
            
            try:
                # ファイル名生成
                name_parts = original_filename.rsplit('.', 1)
                if len(name_parts) == 2:
                    name, ext = name_parts
                    filename = f"{prefix}_{user_id}_{name}_{result['index']}.{ext}"
                else:
                    filename = f"{prefix}_{user_id}_{original_filename}_{result['index']}.jpg"
                
                # 保存パス
                generated_folder = current_app.config.get('GENERATED_FOLDER', 'app/static/generated')
                local_path = os.path.join(generated_folder, filename)
                
                # ダウンロード・保存
                success = self.download_and_save_image(result['image_url'], local_path)
                
                if success:
                    saved_results.append({
                        'index': result['index'],
                        'success': True,
                        'path': local_path,
                        'task_id': result['task_id'],
                        'seed': result.get('seed')
                    })
                else:
                    saved_results.append({
                        'index': result['index'],
                        'success': False,
                        'path': None,
                        'error': '画像保存失敗'
                    })
                    
            except Exception as e:
                logger.error(f"画像 {result['index']} 保存エラー: {e}")
                saved_results.append({
                    'index': result['index'],
                    'success': False,
                    'path': None,
                    'error': str(e)
                })
        
        success_count = len([r for r in saved_results if r['success']])
        logger.info(f"複数画像保存完了: {success_count}/{len(results)}枚成功")
        return saved_results 