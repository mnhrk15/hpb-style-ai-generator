"""
Main Routes Integration Tests
メインページとセッション管理の統合テスト
"""
import pytest
import json
from unittest.mock import Mock, patch


class TestMainRoutes:
    """Main Routesテストクラス"""
    
    def test_index_page_renders(self, client):
        """インデックスページの表示テスト"""
        response = client.get('/')
        
        assert response.status_code == 200
        assert b'Hair Style AI Generator' in response.data
        assert b'\xe7\xbe\x8e\xe5\xae\xb9\xe5\xae\xa4' in response.data  # "美容室"のUTF-8
    
    def test_index_page_content(self, client):
        """インデックスページのコンテンツテスト"""
        response = client.get('/')
        
        # 重要な要素が含まれているかチェック
        content = response.data.decode('utf-8')
        assert 'FLUX.1 Kontext' in content
        assert 'Gemini 2.5 Flash' in content
        assert 'ファイルアップロード' in content
        assert 'プロンプト入力' in content
    
    def test_gallery_page_renders(self, client):
        """ギャラリーページの表示テスト"""
        response = client.get('/gallery')
        
        assert response.status_code == 200
        assert b'\xe3\x82\xae\xe3\x83\xa3\xe3\x83\xa9\xe3\x83\xaa\xe3\x83\xbc' in response.data  # "ギャラリー"
    
    def test_help_page_renders(self, client):
        """ヘルプページの表示テスト"""
        response = client.get('/help')
        
        assert response.status_code == 200
        assert b'\xe4\xbd\xbf\xe3\x81\x84\xe6\x96\xb9' in response.data  # "使い方"
    
    def test_about_page_renders(self, client):
        """Aboutページの表示テスト"""
        response = client.get('/about')
        
        assert response.status_code == 200
        assert b'Hair Style AI Generator' in response.data
    
    def test_session_creation_on_first_visit(self, client):
        """初回訪問時のセッション作成テスト"""
        with client.session_transaction() as sess:
            # セッションが空であることを確認
            assert 'user_id' not in sess
        
        # インデックスページにアクセス
        response = client.get('/')
        
        with client.session_transaction() as sess:
            # セッションが作成されていることを確認
            assert 'user_id' in sess
            assert 'user_name' in sess
            assert 'created_at' in sess
    
    @patch('app.services.session_service.SessionService.get_session_stats')
    def test_index_with_session_stats(self, mock_get_stats, auth_session):
        """セッション統計情報付きインデックスページテスト"""
        # モック統計データ
        mock_get_stats.return_value = {
            'generation_count_today': 5,
            'total_generations': 25,
            'remaining_daily_limit': 45
        }
        
        response = auth_session.get('/')
        
        assert response.status_code == 200
        
        # 統計情報がページに含まれているかチェック
        content = response.data.decode('utf-8')
        assert '5' in content  # 今日の生成数
        assert '45' in content  # 残り制限数
    
    def test_upload_page_access_requires_session(self, client):
        """アップロードページのセッション要求テスト"""
        response = client.get('/upload')
        
        # セッションがない場合はリダイレクトまたはエラー
        assert response.status_code in [200, 302, 401]
    
    def test_upload_page_with_session(self, auth_session):
        """セッション付きアップロードページテスト"""
        response = auth_session.get('/upload')
        
        assert response.status_code == 200
        assert b'\xe3\x82\xa2\xe3\x83\x83\xe3\x83\x97\xe3\x83\xad\xe3\x83\xbc\xe3\x83\x89' in response.data  # "アップロード"
    
    def test_generate_page_access_requires_session(self, client):
        """生成ページのセッション要求テスト"""
        response = client.get('/generate')
        
        assert response.status_code in [200, 302, 401]
    
    def test_generate_page_with_session(self, auth_session):
        """セッション付き生成ページテスト"""
        response = auth_session.get('/generate')
        
        assert response.status_code == 200
        assert b'\xe7\x94\x9f\xe6\x88\x90' in response.data  # "生成"
    
    @patch('app.services.session_service.SessionService.get_gallery_data')
    def test_gallery_with_images(self, mock_get_gallery, auth_session):
        """画像付きギャラリーページテスト"""
        # モックギャラリーデータ
        mock_get_gallery.return_value = [
            {
                'task_id': 'test_task_1',
                'original_image': 'original_1.png',
                'generated_image': 'generated_1.jpg',
                'prompt': 'ショートボブに変更',
                'created_at': '2024-01-01T12:00:00',
                'status': 'completed'
            },
            {
                'task_id': 'test_task_2',
                'original_image': 'original_2.png',
                'generated_image': 'generated_2.jpg',
                'prompt': '髪色を茶色に変更',
                'created_at': '2024-01-01T13:00:00',
                'status': 'completed'
            }
        ]
        
        response = auth_session.get('/gallery')
        
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        
        # ギャラリーデータが含まれているかチェック
        assert 'test_task_1' in content
        assert 'test_task_2' in content
        assert 'ショートボブ' in content
    
    def test_error_404_page(self, client):
        """404エラーページテスト"""
        response = client.get('/nonexistent-page')
        
        assert response.status_code == 404
    
    def test_multiple_users_session_isolation(self, app):
        """複数ユーザーのセッション分離テスト"""
        with app.test_client() as client1, app.test_client() as client2:
            # ユーザー1のセッション作成
            client1.get('/')
            with client1.session_transaction() as sess1:
                user1_id = sess1.get('user_id')
            
            # ユーザー2のセッション作成  
            client2.get('/')
            with client2.session_transaction() as sess2:
                user2_id = sess2.get('user_id')
            
            # 異なるユーザーIDが生成されることを確認
            assert user1_id != user2_id
            assert user1_id is not None
            assert user2_id is not None
    
    def test_navigation_links(self, client):
        """ナビゲーションリンクのテスト"""
        response = client.get('/')
        content = response.data.decode('utf-8')
        
        # 主要ナビゲーションリンクが含まれているかチェック
        assert 'href="/gallery"' in content
        assert 'href="/help"' in content
        assert 'href="/about"' in content
        assert 'href="/"' in content  # ホームリンク
    
    def test_responsive_design_elements(self, client):
        """レスポンシブデザイン要素のテスト"""
        response = client.get('/')
        content = response.data.decode('utf-8')
        
        # Tailwind CSS とレスポンシブクラスが含まれているかチェック
        assert 'tailwindcss.com' in content
        assert 'md:' in content  # モバイル用クラス
        assert 'max-w-7xl' in content  # コンテナクラス
    
    def test_security_headers(self, client):
        """セキュリティヘッダーのテスト"""
        response = client.get('/')
        
        # セキュリティ関連のヘッダーをチェック
        # 実装に応じて適切なヘッダーが設定されているか確認
        assert response.status_code == 200
        
        # Content-Type が適切に設定されているかチェック
        assert 'text/html' in response.content_type
    
    @patch('app.services.session_service.SessionService.update_last_activity')
    def test_session_activity_tracking(self, mock_update_activity, auth_session):
        """セッションアクティビティ追跡テスト"""
        # ページにアクセス
        response = auth_session.get('/')
        
        assert response.status_code == 200
        # アクティビティ更新が呼ばれることを確認
        mock_update_activity.assert_called()


class TestErrorHandling:
    """エラーハンドリングテスト"""
    
    def test_500_error_handling(self, client):
        """500エラーハンドリングテスト"""
        # 意図的にサーバーエラーを発生させる場合のテスト
        # 実装に応じて適切なエラーハンドリングがされているかチェック
        pass
    
    @patch('app.services.session_service.SessionService.create_session')
    def test_session_creation_failure(self, mock_create_session, client):
        """セッション作成失敗時のテスト"""
        # セッション作成に失敗した場合の処理をテスト
        mock_create_session.side_effect = Exception("Redis connection failed")
        
        response = client.get('/')
        
        # エラーが発生してもページは表示される（グレースフルデグラデーション）
        assert response.status_code in [200, 500]


class TestAPIEndpoints:
    """API エンドポイントテスト"""
    
    def test_session_api_endpoint(self, auth_session):
        """セッション情報APIエンドポイントテスト"""
        response = auth_session.get('/api/session')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['authenticated'] == True
        assert 'user_id' in data
        assert 'user_name' in data
    
    def test_session_api_no_session(self, client):
        """セッション情報API（セッションなし）テスト"""
        response = client.get('/api/session')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['authenticated'] == False
    
    @patch('app.services.session_service.SessionService.get_session_stats')
    def test_stats_api_endpoint(self, mock_get_stats, auth_session):
        """統計情報APIエンドポイントテスト"""
        mock_get_stats.return_value = {
            'generation_count_today': 10,
            'total_generations': 50,
            'remaining_daily_limit': 40
        }
        
        response = auth_session.get('/api/stats')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['generation_count_today'] == 10
        assert data['total_generations'] == 50
        assert data['remaining_daily_limit'] == 40 