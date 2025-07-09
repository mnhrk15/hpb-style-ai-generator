"""
Hair Style AI Generator - File Service
画像ファイルの処理・バリデーション・保存・変換
"""

import os
import uuid
import hashlib
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
from PIL import Image, ImageOps
from flask import current_app
import base64
from io import BytesIO

logger = logging.getLogger(__name__)


class FileService:
    """
    画像ファイル処理サービス
    アップロード・保存・変換・バリデーション機能
    """
    
    def __init__(self):
        """ファイルサービスの初期化"""
        self.allowed_extensions = {'png', 'jpg', 'jpeg', 'webp'}
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.max_dimensions = (4096, 4096)  # 最大解像度
        self.min_dimensions = (256, 256)   # 最小解像度
    
    def validate_uploaded_file(self, file) -> Tuple[bool, Optional[str]]:
        """
        アップロードファイルのバリデーション
        
        Args:
            file: Flaskアップロードファイルオブジェクト
            
        Returns:
            tuple: (検証成功可否, エラーメッセージ)
        """
        try:
            logger.info(f"=== ファイルバリデーション開始 ===")
            logger.info(f"File object: {file}")
            logger.info(f"File filename: {getattr(file, 'filename', 'None')}")
            
            # ファイル存在確認
            if not file or not file.filename:
                logger.warning("ファイル存在確認失敗")
                return False, "ファイルが選択されていません"
            
            # ファイル名拡張子確認
            if not self._allowed_file(file.filename):
                supported = ', '.join(self.allowed_extensions)
                return False, f"対応していない形式です。対応形式: {supported}"
            
            # ファイルサイズ確認（概算）
            file.seek(0, 2)  # ファイル末尾に移動
            file_size = file.tell()
            file.seek(0)     # ファイル先頭に戻る
            
            if file_size > self.max_file_size:
                size_mb = self.max_file_size / (1024 * 1024)
                return False, f"ファイルサイズが大きすぎます（上限: {size_mb:.1f}MB）"
            
            if file_size == 0:
                return False, "ファイルが空です"
            
            # 画像として読み込み可能か確認
            try:
                with Image.open(file.stream) as img:
                    # 画像解像度確認
                    width, height = img.size
                    
                    if width < self.min_dimensions[0] or height < self.min_dimensions[1]:
                        return False, f"解像度が小さすぎます（最小: {self.min_dimensions[0]}x{self.min_dimensions[1]}）"
                    
                    if width > self.max_dimensions[0] or height > self.max_dimensions[1]:
                        return False, f"解像度が大きすぎます（最大: {self.max_dimensions[0]}x{self.max_dimensions[1]}）"
                    
                    # カラーモード確認（RGBに変換可能か）
                    if img.mode not in ['RGB', 'RGBA', 'L']:
                        return False, "対応していない画像形式です"
                
                # ファイルポインタを先頭に戻す
                file.seek(0)
                return True, None
                
            except Exception as e:
                file.seek(0)
                return False, f"無効な画像ファイルです: {str(e)}"
                
        except Exception as e:
            logger.error(f"ファイルバリデーションエラー: {e}")
            return False, "ファイル検証中にエラーが発生しました"
    
    def save_uploaded_file(self, file, user_id: str, 
                          optimize: bool = True) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        アップロードファイルの保存
        
        Args:
            file: Flaskアップロードファイルオブジェクト
            user_id (str): ユーザーID
            optimize (bool): 画像最適化実行可否
            
        Returns:
            tuple: (保存成功可否, 保存パス, ファイル情報)
        """
        try:
            # バリデーション
            is_valid, error_msg = self.validate_uploaded_file(file)
            if not is_valid:
                return False, None, {"error": error_msg}
            
            # ファイル名生成
            original_filename = file.filename
            safe_filename = self._generate_safe_filename(original_filename, user_id)
            
            # 保存パス構築
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
            file_path = os.path.join(upload_folder, safe_filename)
            
            # ディレクトリ作成
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 画像処理・保存
            with Image.open(file.stream) as img:
                # EXIF情報による自動回転
                img = ImageOps.exif_transpose(img)
                
                # RGBモードに変換
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 最適化処理
                if optimize:
                    img = self._optimize_image(img)
                
                # 保存（JPEG形式で品質90%）
                img.save(file_path, 'JPEG', quality=90, optimize=True)
            
            # ファイル情報取得
            file_info = self._get_file_info(file_path, original_filename)
            
            logger.info(f"ファイル保存完了: {file_path}")
            return True, file_path, file_info
            
        except Exception as e:
            logger.error(f"ファイル保存エラー: {e}")
            return False, None, {"error": f"ファイル保存に失敗しました: {str(e)}"}
    
    def save_image_from_url(self, image_url: str, user_id: str, 
                               original_filename: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        URLから画像をダウンロードしてアップロードフォルダに保存する
        
        Args:
            image_url (str): 画像URL
            user_id (str): ユーザーID
            original_filename (str): 元のファイル名
        
        Returns:
            tuple: (保存成功可否, 保存パス, ファイル情報)
        """
        try:
            import requests
            
            # 画像ダウンロード
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # BytesIOを使用して画像データをメモリ上で扱う
            image_data = BytesIO(response.content)
            
            # ファイル名生成
            safe_filename = self._generate_safe_filename(original_filename, user_id)
            
            # 保存パス構築
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
            file_path = os.path.join(upload_folder, safe_filename)
            
            # ディレクトリ作成
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 画像処理・保存 (save_uploaded_fileと同様の処理)
            with Image.open(image_data) as img:
                # EXIF情報による自動回転
                img = ImageOps.exif_transpose(img)
                
                # RGBモードに変換
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 最適化処理
                img = self._optimize_image(img)
                
                # 保存
                img.save(file_path, 'JPEG', quality=90, optimize=True)
            
            # ファイル情報取得
            file_info = self._get_file_info(file_path, original_filename)
            
            logger.info(f"URLからの画像保存完了: {file_path}")
            return True, file_path, file_info
            
        except Exception as e:
            logger.error(f"URLからの画像保存エラー: {e}")
            return False, None, {"error": f"URLからの画像保存に失敗しました: {str(e)}"}

    def convert_to_base64(self, file_path: str, max_size: Optional[int] = None) -> str:
        """
        画像ファイルをBase64エンコード
        
        Args:
            file_path (str): 画像ファイルパス
            max_size (int, optional): 最大サイズ（ピクセル）
            
        Returns:
            str: Base64エンコード済み画像データ
        """
        try:
            with Image.open(file_path) as img:
                # サイズ調整
                if max_size and max(img.size) > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # RGBモードに変換
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # BytesIOに保存
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                buffer.seek(0)
                
                # Base64エンコード
                encoded_string = base64.b64encode(buffer.getvalue()).decode('utf-8')
                return encoded_string
                
        except Exception as e:
            logger.error(f"Base64変換エラー: {e}")
            raise Exception(f"画像のBase64変換に失敗しました: {str(e)}")
    
    def save_generated_image(self, image_url: str, user_id: str, 
                           original_filename: str, task_id: str) -> Tuple[bool, Optional[str]]:
        """
        生成画像の保存
        
        Args:
            image_url (str): 生成画像URL
            user_id (str): ユーザーID
            original_filename (str): 元ファイル名
            task_id (str): タスクID
            
        Returns:
            tuple: (保存成功可否, 保存パス)
        """
        try:
            import requests
            
            # 画像ダウンロード
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # ファイル名生成
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_name = self._sanitize_filename(original_filename)
            generated_filename = f"{user_id}_{timestamp}_{safe_name}_{task_id[:8]}.jpg"
            
            # 保存パス構築
            generated_folder = current_app.config.get('GENERATED_FOLDER', 'app/static/generated')
            file_path = os.path.join(generated_folder, generated_filename)
            
            # ディレクトリ作成
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # ファイル保存
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"生成画像保存完了: {file_path}")
            return True, file_path
            
        except Exception as e:
            logger.error(f"生成画像保存エラー: {e}")
            return False, None
    
    def analyze_image_features(self, file_path: str) -> Dict:
        """
        画像特徴分析（簡易版）
        
        Args:
            file_path (str): 画像ファイルパス
            
        Returns:
            dict: 画像特徴情報
        """
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                aspect_ratio = width / height
                
                # 基本的な特徴抽出
                features = {
                    'width': width,
                    'height': height,
                    'aspect_ratio': round(aspect_ratio, 2),
                    'orientation': 'landscape' if width > height else 'portrait' if height > width else 'square',
                    'resolution': width * height,
                    'file_size': os.path.getsize(file_path),
                    'format': img.format,
                    'mode': img.mode
                }
                
                # 解像度カテゴリ
                if features['resolution'] < 500000:  # 0.5MP
                    features['quality'] = 'low'
                elif features['resolution'] < 2000000:  # 2MP
                    features['quality'] = 'medium'
                else:
                    features['quality'] = 'high'
                
                return features
                
        except Exception as e:
            logger.error(f"画像分析エラー: {e}")
            return {'error': str(e)}
    
    def _allowed_file(self, filename: str) -> bool:
        """ファイル拡張子確認"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def _generate_safe_filename(self, original_filename: str, user_id: str) -> str:
        """安全なファイル名生成"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = self._sanitize_filename(original_filename)
        unique_id = str(uuid.uuid4())[:8]
        
        return f"{user_id}_{timestamp}_{safe_name}_{unique_id}.jpg"
    
    def _sanitize_filename(self, filename: str) -> str:
        """ファイル名のサニタイズ"""
        # 拡張子を除去
        name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
        # 安全な文字のみを保持
        safe_chars = []
        for char in name:
            if char.isalnum() or char in '-_':
                safe_chars.append(char)
            else:
                safe_chars.append('_')
        
        safe_name = ''.join(safe_chars)
        
        # 長すぎる場合は短縮
        if len(safe_name) > 50:
            safe_name = safe_name[:50]
        
        return safe_name or 'image'
    
    def _optimize_image(self, img: Image.Image) -> Image.Image:
        """画像最適化処理"""
        # 大きすぎる場合はリサイズ
        max_size = 2048
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        return img
    
    def _get_file_info(self, file_path: str, original_filename: str) -> Dict:
        """ファイル情報取得"""
        try:
            stat = os.stat(file_path)
            
            with Image.open(file_path) as img:
                return {
                    'original_filename': original_filename,
                    'saved_path': file_path,
                    'file_size': stat.st_size,
                    'width': img.size[0],
                    'height': img.size[1],
                    'format': img.format,
                    'mode': img.mode,
                    'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat()
                }
        except Exception as e:
            logger.error(f"ファイル情報取得エラー: {e}")
            return {'error': str(e)} 