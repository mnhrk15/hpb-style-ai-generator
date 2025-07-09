#!/usr/bin/env python3
"""
Hair Style AI Generator - アップロードテスト
ファイルアップロード機能の直接テスト
"""

import requests
import io
from PIL import Image
import base64
import os

# 設定
base_url = os.getenv('BASE_URL', 'http://127.0.0.1:5001')
upload_url = f"{base_url}/upload"
generate_url = f"{base_url}/generate"
validate_url = f"{base_url}/upload/validate"
scrape_url = f"{base_url}/api/scrape-image"

def create_test_image():
    """テスト用の小さな画像を作成"""
    # 300x300の青い正方形を作成
    img = Image.new('RGB', (300, 300), color='blue')
    
    # メモリ上でJPEGとして保存
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='JPEG', quality=90)
    img_buffer.seek(0)
    
    return img_buffer

def test_upload(base_url="http://127.0.0.1:5000"):
    """アップロード機能をテスト"""
    print("🧪 アップロード機能テスト")
    print("=" * 40)
    
    try:
        # テスト画像作成
        test_image = create_test_image()
        
        # ファイルアップロード準備
        files = {
            'file': ('test_image.jpg', test_image, 'image/jpeg')
        }
        
        # セッション保持のためrequests.Session使用
        session = requests.Session()
        
        # まずメインページにアクセスしてセッション開始
        main_response = session.get(f"{base_url}/")
        print(f"メインページアクセス: {main_response.status_code}")
        
        # アップロードテスト
        upload_url = f"{base_url}/upload/"
        print(f"アップロード先: {upload_url}")
        
        response = session.post(upload_url, files=files, timeout=10)
        
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンスヘッダー: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ アップロード成功")
            print(f"レスポンス: {data}")
            return True
        else:
            print(f"❌ アップロード失敗")
            print(f"エラー内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        return False

if __name__ == "__main__":
    print("サーバーが起動していることを確認してください")
    print("推奨: python dev-start.py")
    print()
    
    success = test_upload()
    
    if success:
        print("\n🎉 アップロードテスト成功")
    else:
        print("\n💥 アップロードテスト失敗")
        print("詳細なログを確認してください") 