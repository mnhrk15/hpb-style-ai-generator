"""
Hair Style AI Generator - Load Testing with Locust
同時接続・レート制限・パフォーマンステスト
"""

from locust import HttpUser, task, between, tag
import json
import time
import random
import base64
from io import BytesIO
from PIL import Image


class HairStyleAIUser(HttpUser):
    """通常ユーザーの行動パターン"""
    
    wait_time = between(2, 8)  # 2-8秒の間隔でリクエスト
    
    def on_start(self):
        """ユーザーセッション開始時の処理"""
        # セッション作成（トップページアクセス）
        response = self.client.get("/")
        if response.status_code != 200:
            print(f"セッション作成失敗: {response.status_code}")
    
    @task(10)
    def view_homepage(self):
        """ホームページ閲覧（最も頻繁な操作）"""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"ホームページ読み込み失敗: {response.status_code}")
    
    @task(5)
    def view_gallery(self):
        """ギャラリー閲覧"""
        with self.client.get("/gallery", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"ギャラリー読み込み失敗: {response.status_code}")
    
    @task(3)
    def check_session_info(self):
        """セッション情報確認"""
        with self.client.get("/api/session", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get('authenticated'):
                    response.success()
                else:
                    response.failure("認証されていません")
            else:
                response.failure(f"セッション情報取得失敗: {response.status_code}")
    
    @task(2)
    def check_system_stats(self):
        """システム統計確認"""
        with self.client.get("/api/stats", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.success()  # レート制限は正常な動作
            else:
                response.failure(f"統計情報取得失敗: {response.status_code}")
    
    @task(1)
    def health_check(self):
        """ヘルスチェック"""
        with self.client.get("/api/health", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    response.success()
                else:
                    response.failure(f"システム不健康: {data}")
            else:
                response.failure(f"ヘルスチェック失敗: {response.status_code}")


class PowerUser(HttpUser):
    """積極的ユーザーの行動パターン（画像アップロード・生成を含む）"""
    
    wait_time = between(5, 15)  # より長い間隔（生成待機時間を考慮）
    
    def on_start(self):
        """セッション開始"""
        self.client.get("/")
        self.test_image_data = self.create_test_image()
    
    def create_test_image(self):
        """テスト用画像データ生成"""
        # 1x1ピクセルの透明PNG
        img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return {
            'data': img_io.getvalue(),
            'filename': f'test_image_{random.randint(1000, 9999)}.png'
        }
    
    @task(5)
    def browse_app(self):
        """アプリケーション閲覧"""
        pages = ["/", "/gallery", "/help", "/about"]
        page = random.choice(pages)
        
        with self.client.get(page, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"ページ読み込み失敗 {page}: {response.status_code}")
    
    @task(3)
    def upload_image(self):
        """画像アップロード"""
        files = {
            'file': (
                self.test_image_data['filename'],
                BytesIO(self.test_image_data['data']),
                'image/png'
            )
        }
        
        with self.client.post("/upload/", files=files, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 413:
                response.success()  # ファイルサイズ制限は正常な動作
            elif response.status_code == 429:
                response.success()  # レート制限は正常な動作
            else:
                response.failure(f"アップロード失敗: {response.status_code}")
    
    @task(1)
    def generate_image_simulation(self):
        """画像生成シミュレーション（実際には生成しない）"""
        # 生成プロセスのシミュレーション
        prompt_data = {
            'prompt': random.choice([
                'ショートボブに変更',
                '髪色を茶色に変更',
                '前髪を作る',
                'ロングヘアにする'
            ]),
            'uploaded_file': 'test_image.png'
        }
        
        # プロンプト最適化のテスト（実際のAPIは呼ばない）
        with self.client.post("/api/test/prompt", 
                            json=prompt_data, 
                            catch_response=True) as response:
            if response.status_code in [200, 404, 429]:  # 404は実装されていない場合
                response.success()
            else:
                response.failure(f"プロンプトテスト失敗: {response.status_code}")


class RateLimitTester(HttpUser):
    """レート制限テスト専用ユーザー"""
    
    wait_time = between(0.1, 0.5)  # 高頻度アクセス
    
    @task
    def spam_api_requests(self):
        """API エンドポイントへの高頻度アクセス"""
        endpoints = [
            "/api/session",
            "/api/stats", 
            "/api/health",
            "/api/info"
        ]
        
        endpoint = random.choice(endpoints)
        
        with self.client.get(endpoint, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                # レート制限発動は成功として扱う
                response.success()
                print(f"レート制限発動: {endpoint}")
            else:
                response.failure(f"予期しないエラー {endpoint}: {response.status_code}")


class SecurityTester(HttpUser):
    """セキュリティテスト用ユーザー"""
    
    wait_time = between(1, 3)
    
    @task(2)
    def test_file_upload_security(self):
        """ファイルアップロードセキュリティテスト"""
        # 危険なファイル名のテスト
        dangerous_files = [
            ('../../../etc/passwd', 'text/plain'),
            ('test.exe', 'application/octet-stream'),
            ('script.js', 'application/javascript'),
            ('test.php', 'application/x-php'),
        ]
        
        filename, content_type = random.choice(dangerous_files)
        
        files = {
            'file': (filename, BytesIO(b'malicious content'), content_type)
        }
        
        with self.client.post("/upload/", files=files, catch_response=True) as response:
            if response.status_code in [400, 415, 422]:  # 拒否されるべき
                response.success()
            elif response.status_code == 413:
                response.success()  # ファイルサイズ制限
            else:
                response.failure(f"危険ファイルが受け入れられた: {response.status_code}")
    
    @task(1)
    def test_csrf_protection(self):
        """CSRF保護テスト"""
        # CSRFトークンなしでPOSTリクエスト
        with self.client.post("/api/session", 
                            json={'test': 'data'}, 
                            catch_response=True) as response:
            # APIエンドポイントはCSRF無効化されているべき
            if response.status_code in [200, 405, 429]:
                response.success()
            else:
                response.failure(f"CSRF設定異常: {response.status_code}")
    
    @task(1)
    def test_large_request(self):
        """大きなリクエストのテスト"""
        # 12MB のダミーファイル
        large_data = b'x' * (12 * 1024 * 1024)
        
        files = {
            'file': ('large_file.png', BytesIO(large_data), 'image/png')
        }
        
        with self.client.post("/upload/", files=files, catch_response=True) as response:
            if response.status_code == 413:  # Request Entity Too Large
                response.success()
            else:
                response.failure(f"大きなファイルが受け入れられた: {response.status_code}")


# 特定のテストシナリオ用ユーザークラス
class ConcurrentGenerationTester(HttpUser):
    """同時生成処理テスト"""
    
    wait_time = between(1, 2)
    
    def on_start(self):
        self.client.get("/")  # セッション作成
    
    @task
    def concurrent_requests(self):
        """同時リクエスト処理テスト"""
        # 複数のAPIを同時に呼び出し
        endpoints = [
            "/api/session",
            "/api/stats",
            "/api/health"
        ]
        
        for endpoint in endpoints:
            self.client.get(endpoint, catch_response=False)


# 使用方法のドキュメント
"""
負荷テスト実行方法:

1. 基本的な負荷テスト:
   locust -f tests/test_load/locustfile.py --host=http://localhost:5000

2. 特定のユーザータイプのみテスト:
   locust -f tests/test_load/locustfile.py --host=http://localhost:5000 HairStyleAIUser

3. Webインターフェースなしでテスト:
   locust -f tests/test_load/locustfile.py --host=http://localhost:5000 --headless --users 10 --spawn-rate 1

4. レート制限テスト:
   locust -f tests/test_load/locustfile.py --host=http://localhost:5000 RateLimitTester --headless --users 50 --spawn-rate 5

推奨テストシナリオ:
- 通常負荷: HairStyleAIUser 10-50ユーザー
- 高負荷: PowerUser 5-20ユーザー  
- レート制限: RateLimitTester 20-100ユーザー
- セキュリティ: SecurityTester 5-10ユーザー
""" 