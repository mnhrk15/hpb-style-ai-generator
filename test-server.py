#!/usr/bin/env python3
"""
Hair Style AI Generator - サーバー動作テスト
各エンドポイントの簡単な動作確認
"""

import requests
import time
import sys

def test_server(base_url="http://127.0.0.1:5000"):
    """サーバーの基本動作をテスト"""
    print("🧪 Hair Style AI Generator - サーバーテスト")
    print("=" * 50)
    
    tests = [
        ("メインページ", "GET", "/"),
        ("ヘルスチェック", "GET", "/api/health"),
        ("システム情報", "GET", "/api/info"),
        ("ギャラリー", "GET", "/gallery"),
    ]
    
    results = []
    
    for test_name, method, endpoint in tests:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.request(method, url, timeout=5)
            
            if response.status_code == 200:
                status = "✅ 成功"
                color = "\033[92m"
            else:
                status = f"⚠️  警告 ({response.status_code})"
                color = "\033[93m"
            
            print(f"{color}{test_name}: {status}\033[0m")
            results.append((test_name, True if response.status_code == 200 else False))
            
        except Exception as e:
            print(f"\033[91m{test_name}: ❌ 失敗 - {e}\033[0m")
            results.append((test_name, False))
        
        time.sleep(0.5)
    
    print("\n" + "=" * 50)
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    if success_count == total_count:
        print(f"🎉 全テスト成功 ({success_count}/{total_count})")
        return True
    else:
        print(f"⚠️  一部テスト失敗 ({success_count}/{total_count})")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://127.0.0.1:5000"
    
    print(f"テスト対象: {base_url}")
    print("サーバーが起動していることを確認してください")
    print()
    
    success = test_server(base_url)
    sys.exit(0 if success else 1) 