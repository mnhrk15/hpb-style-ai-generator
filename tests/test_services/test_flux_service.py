"""
FLUX.1 Kontext Service Unit Tests
画像生成とポーリング処理のテスト
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.flux_service import FluxService
import time
import requests


class TestFluxService:
    """FLUX.1 Kontext Serviceテストクラス"""
    
    def test_init_with_api_key(self):
        """API キー設定のテスト"""
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-bfl-key'}):
            service = FluxService()
            assert service.api_key == 'test-bfl-key'
            assert service.base_url == "https://api.us1.bfl.ai/v1"
    
    def test_init_without_api_key(self):
        """API キー未設定時の警告テスト"""
        with patch.dict('os.environ', {}, clear=True):
            # 実装では例外ではなく警告ログが出力される
            service = FluxService()
            assert service.api_key is None
    
    @patch('requests.post')
    def test_generate_hair_style_success(self, mock_post):
        """画像生成API成功テスト"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "test_task_id_123"}
        mock_post.return_value = mock_response
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            task_id = service.generate_hair_style(
                "base64_image_data",
                "Transform hairstyle to short bob"
            )
        
        assert task_id == "test_task_id_123"
        
        # API呼び出しの検証
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # 位置引数とキーワード引数の確認
        args, kwargs = call_args
        
        # エンドポイント確認
        assert args[0] == "https://api.us1.bfl.ai/v1/flux-kontext-pro"
        
        # ヘッダー確認
        headers = kwargs['headers']
        assert headers['x-key'] == 'test-key'
        assert headers['Content-Type'] == 'application/json'
        
        # ペイロード確認
        payload = kwargs['json']
        assert payload['prompt'] == "Transform hairstyle to short bob"
        assert payload['input_image'] == "base64_image_data"
        assert payload['output_format'] == "jpeg"
    
    @patch('requests.post')
    def test_generate_hair_style_with_optional_params(self, mock_post):
        """オプションパラメータ付き画像生成テスト"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "test_task_id_456"}
        mock_post.return_value = mock_response
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            task_id = service.generate_hair_style(
                "base64_image_data",
                "Test prompt",
                seed=12345,
                safety_tolerance=4,
                output_format="png"
            )
        
        # パラメータが正しく渡されることを確認
        payload = mock_post.call_args[1]['json']
        assert payload['seed'] == 12345
        assert payload['safety_tolerance'] == 4
        assert payload['output_format'] == "png"
    
    def test_generate_hair_style_no_api_key(self):
        """APIキー未設定時の例外処理テスト"""
        with patch.dict('os.environ', {}, clear=True):
            service = FluxService()
            
            with pytest.raises(Exception, match="BFL_API_KEY が設定されていません"):
                service.generate_hair_style("base64_data", "test prompt")
    
    @patch('requests.post')
    def test_generate_hair_style_api_error(self, mock_post):
        """API エラー時の例外処理テスト"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request: Invalid prompt"
        mock_post.return_value = mock_response
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            
            with pytest.raises(Exception, match="API Error: 400"):
                service.generate_hair_style("base64_data", "invalid prompt")
    
    @patch('requests.get')
    def test_get_result_ready(self, mock_get):
        """結果取得（Ready状態）テスト"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "Ready",
            "result": {
                "sample": "https://test-url.com/generated_image.jpg"
            }
        }
        mock_get.return_value = mock_response
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            result = service.get_result("test_task_id")
        
        assert result["status"] == "Ready"
        assert result["result"]["sample"] == "https://test-url.com/generated_image.jpg"
        
        # API呼び出しの検証
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        
        # 位置引数とキーワード引数の確認
        args, kwargs = call_args
        
        # エンドポイント確認
        assert args[0] == "https://api.us1.bfl.ai/v1/get_result"
        
        # パラメータ確認
        assert kwargs['params'] == {"id": "test_task_id"}
    
    @patch('requests.get')
    def test_get_result_processing(self, mock_get):
        """結果取得（Processing状態）テスト"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "Processing"}
        mock_get.return_value = mock_response
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            result = service.get_result("test_task_id")
        
        assert result["status"] == "Processing"
    
    def test_get_result_no_api_key(self):
        """APIキー未設定時の例外処理テスト"""
        with patch.dict('os.environ', {}, clear=True):
            service = FluxService()
            
            with pytest.raises(Exception, match="BFL_API_KEY が設定されていません"):
                service.get_result("test_task_id")
    
    @patch('requests.get')
    def test_get_result_api_error(self, mock_get):
        """結果取得API エラー時の例外処理テスト"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Task not found"
        mock_get.return_value = mock_response
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            
            with pytest.raises(Exception, match="API Error: 404"):
                service.get_result("invalid_task_id")
    
    @patch('time.sleep')
    @patch.object(FluxService, 'get_result')
    def test_poll_until_ready_success(self, mock_get_result, mock_sleep):
        """ポーリング成功テスト"""
        # 3回のポーリングで完了
        mock_get_result.side_effect = [
            {"status": "Queued"},
            {"status": "Processing"},
            {
                "status": "Ready",
                "result": {"sample": "https://test-url.com/result.jpg"}
            }
        ]
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            # 実装では(image_url, result_detail)のタプルを返す
            result_url, result_detail = service.poll_until_ready("test_task_id")
        
        assert result_url == "https://test-url.com/result.jpg"
        assert result_detail["status"] == "Ready"
        assert mock_get_result.call_count == 3
        assert mock_sleep.call_count == 2  # 2回sleep（1.5秒間隔）
    
    @patch('time.sleep')
    @patch.object(FluxService, 'get_result')
    def test_poll_until_ready_timeout(self, mock_get_result, mock_sleep):
        """ポーリングタイムアウトテスト"""
        # 常にProcessing状態を返す
        mock_get_result.return_value = {"status": "Processing"}
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            
            with pytest.raises(Exception, match="タイムアウト"):
                service.poll_until_ready("test_task_id", max_wait_time=5)
    
    @patch('time.sleep')
    @patch.object(FluxService, 'get_result')
    def test_poll_until_ready_error_status(self, mock_get_result, mock_sleep):
        """ポーリング時のエラーステータステスト"""
        error_statuses = ["Error", "Content Moderated", "Request Moderated"]
        
        for status in error_statuses:
            mock_get_result.return_value = {"status": status, "result": {"message": "test error"}}
            
            with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
                service = FluxService()
                
                with pytest.raises(Exception, match=f"生成失敗: {status}"):
                    service.poll_until_ready("test_task_id")
    
    def test_poll_until_ready_progress_callback(self):
        """ポーリング進捗コールバックテスト"""
        progress_calls = []
        
        def mock_callback(progress_info):
            progress_calls.append(progress_info)
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            
            with patch.object(service, 'get_result') as mock_get_result:
                mock_get_result.side_effect = [
                    {"status": "Processing"},
                    {"status": "Ready", "result": {"sample": "https://test.com/result.jpg"}}
                ]
                
                with patch('time.sleep'):
                    result_url, _ = service.poll_until_ready("test_task_id", progress_callback=mock_callback)
                
                assert result_url == "https://test.com/result.jpg"
                assert len(progress_calls) >= 2  # Processing と Ready
                assert all('status' in call for call in progress_calls)
    
    def test_download_and_save_image_success(self):
        """画像ダウンロード・保存成功テスト"""
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            
            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.content = b'fake_image_data'
                mock_get.return_value = mock_response
                mock_get.return_value.raise_for_status = Mock()
                
                with patch('builtins.open', mock_open()) as mock_file:
                    result = service.download_and_save_image(
                        "https://test.com/image.jpg",
                        "/test/path/image.jpg"
                    )
                    
                    assert result == True
                    mock_file().write.assert_called_once_with(b'fake_image_data')
    
    def test_download_and_save_image_failure(self):
        """画像ダウンロード・保存失敗テスト"""
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            
            with patch('requests.get') as mock_get:
                mock_get.side_effect = Exception("Network error")
                
                result = service.download_and_save_image(
                    "https://test.com/image.jpg",
                    "/test/path/image.jpg"
                )
                
                assert result == False
    
    @patch('requests.get')
    def test_validate_api_connection_success(self, mock_get):
        """API接続テスト成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            result = service.validate_api_connection()
            
            assert result == True
    
    def test_validate_api_connection_no_key(self):
        """API接続テスト（キー未設定）"""
        with patch.dict('os.environ', {}, clear=True):
            service = FluxService()
            result = service.validate_api_connection()
            
            assert result == False
    
    @patch('requests.get')
    def test_validate_api_connection_auth_error(self, mock_get):
        """API接続テスト認証エラー"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'invalid-key'}):
            service = FluxService()
            result = service.validate_api_connection()
            
            assert result == False
    
    def test_estimate_generation_time(self):
        """生成時間予測テスト"""
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            
            assert service.estimate_generation_time("simple") == 30
            assert service.estimate_generation_time("medium") == 60
            assert service.estimate_generation_time("complex") == 120
            assert service.estimate_generation_time("unknown") == 60  # デフォルト
    
    @patch('requests.post')
    @patch('requests.get')
    def test_full_generation_workflow(self, mock_get, mock_post):
        """完全な生成ワークフローテスト"""
        # 生成リクエスト
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"id": "workflow_test_id"}
        mock_post.return_value = mock_post_response
        
        # ポーリング結果
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "status": "Ready",
            "result": {"sample": "https://final-result.com/image.jpg"}
        }
        mock_get.return_value = mock_get_response
        
        with patch.dict('os.environ', {'BFL_API_KEY': 'test-key'}):
            service = FluxService()
            
            # 1. 生成開始
            task_id = service.generate_hair_style(
                "test_base64_image",
                "Transform to short bob style"
            )
            
            # 2. 結果取得
            result = service.get_result(task_id)
            
            assert task_id == "workflow_test_id"
            assert result["status"] == "Ready"
            assert "final-result.com" in result["result"]["sample"]


class TestFluxServiceIntegration:
    """統合テスト（実際のAPIキー使用）"""
    
    @pytest.mark.skip(reason="実際のAPIキーが必要")
    def test_real_api_generation(self):
        """実際のAPI呼び出しテスト（手動実行用）"""
        import os
        if not os.getenv('BFL_API_KEY'):
            pytest.skip("BFL_API_KEY not found")
        
        service = FluxService()
        
        # 実際のbase64画像データが必要
        # task_id = service.generate_hair_style(
        #     "actual_base64_image_data",
        #     "Transform hairstyle to short bob"
        # )
        # 
        # assert isinstance(task_id, str)
        # assert len(task_id) > 0
        
        print("Real API test would require actual image data")


def mock_open(read_data=b''):
    """モック用のopen関数"""
    from unittest.mock import mock_open as base_mock_open
    return base_mock_open(read_data=read_data) 