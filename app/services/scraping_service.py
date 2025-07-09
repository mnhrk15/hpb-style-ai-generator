"""
Hair Style AI Generator - Scraping Service
外部サイトからの画像スクレイピング
"""

import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)


class ScrapingService:
    """
    Webサイトから画像をスクレイピングするサービス
    """
    
    def __init__(self):
        """スクレイピングサービスの初期化"""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_image_from_url(self, page_url: str, selector: str) -> str:
        """
        指定されたURLのページから画像URLを取得する
        
        Args:
            page_url (str): 対象のページURL
            selector (str): 画像要素のCSSセレクタ
            
        Returns:
            str: 高画質化された画像URL
            
        Raises:
            Exception: 取得に失敗した場合
        """
        try:
            logger.info(f"スクレイピング開始: {page_url}")
            
            # ページ取得
            response = requests.get(page_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # HTMLパース
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 画像要素検索
            img_element = soup.select_one(selector)
            if not img_element:
                raise Exception(f"指定されたセレクタ '{selector}' に一致する画像が見つかりません。")
            
            # 画像URL取得
            image_src = img_element.get('src')
            if not image_src:
                raise Exception("画像要素にsrc属性が見つかりません。")
            
            # URLを絶対パスに変換
            absolute_image_url = urljoin(page_url, image_src)
            
            # URLからクエリパラメータを削除して高画質化
            high_quality_url = absolute_image_url.split('?')[0]
            
            logger.info(f"画像URL取得成功: {high_quality_url}")
            return high_quality_url

        except requests.exceptions.RequestException as e:
            logger.error(f"ページ取得エラー: {e}")
            raise Exception(f"ページの取得に失敗しました。URLを確認してください。")
        except Exception as e:
            logger.error(f"スクレイピングエラー: {e}")
            raise 