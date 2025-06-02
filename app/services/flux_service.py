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
                
                elif status in ["Processing", "Queued"]:
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
    
    @staticmethod
    def encode_image_to_base64(image_path: str) -> str:
        """
        画像ファイルをbase64エンコード
        
        Args:
            image_path (str): 画像ファイルパス
            
        Returns:
            str: base64エンコード済み画像データ
        """
        try:
            with open(image_path, 'rb') as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except Exception as e:
            logger.error(f"画像base64エンコードエラー: {e}")
            raise Exception(f"画像エンコード失敗: {e}") 