"""
Gemini Service Unit Tests
プロンプト最適化とレスポンス品質のテスト
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.gemini_service import GeminiService


class TestGeminiService:
    """Gemini Serviceテストクラス"""
    
    def test_init_with_api_key(self):
        """API キー設定のテスト"""
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'}):
            service = GeminiService()
            assert service.api_key == 'test-api-key'
    
    def test_init_without_api_key(self):
        """API キー未設定時の警告テスト"""
        with patch.dict('os.environ', {}, clear=True):
            # 実装では例外ではなく警告ログが出力される
            service = GeminiService()
            assert service.api_key is None
    
    @patch('app.services.gemini_service.genai.Client')
    def test_optimize_hair_style_prompt_success(self, mock_client):
        """プロンプト最適化の成功テスト"""
        # Mock設定
        mock_response = Mock()
        mock_response.text = "Transform the hairstyle to short bob while maintaining identical facial features"
        
        mock_instance = Mock()
        mock_instance.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_instance
        
        # テスト実行
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}):
            service = GeminiService()
            result = service.optimize_hair_style_prompt(
                "ショートボブに変更",
                "woman with long black hair"
            )
        
        # アサーション
        assert "short bob" in result.lower()
        assert "maintain" in result.lower()
        mock_instance.models.generate_content.assert_called_once()
    
    def test_optimize_hair_style_prompt_fallback(self):
        """API利用不可時のフォールバック機能テスト"""
        with patch.dict('os.environ', {}, clear=True):
            service = GeminiService()
            
            # フォールバック機能のテスト
            result = service.optimize_hair_style_prompt("ショートボブに変更")
            
            assert isinstance(result, str)
            assert len(result) > 0
            assert "maintaining identical" in result or "maintain identical" in result
    
    @patch('app.services.gemini_service.genai.Client')
    def test_optimize_hair_style_prompt_with_long_input(self, mock_client):
        """長いプロンプトの最適化テスト"""
        mock_response = Mock()
        mock_response.text = "Optimized prompt within 512 tokens"
        
        mock_instance = Mock()
        mock_instance.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_instance
        
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}):
            service = GeminiService()
            long_prompt = "とても長い" * 100  # 非常に長いプロンプト
            
            result = service.optimize_hair_style_prompt(long_prompt, "test image analysis")
            
            # 結果が適切に返されることを確認
            assert isinstance(result, str)
            assert len(result) > 0
    
    @patch('app.services.gemini_service.genai.Client')
    def test_optimize_hair_style_prompt_api_error(self, mock_client):
        """API エラー時のフォールバック処理テスト"""
        mock_instance = Mock()
        mock_instance.models.generate_content.side_effect = Exception("API Error")
        mock_client.return_value = mock_instance
        
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}):
            service = GeminiService()
            
            # APIエラー時はフォールバックが実行される
            result = service.optimize_hair_style_prompt("test prompt")
            assert isinstance(result, str)
            assert len(result) > 0
    
    def test_create_hairstyle_prompt_success(self):
        """定型プロンプト生成成功テスト"""
        service = GeminiService()
        
        result = service.create_hairstyle_prompt(
            "cut_change", 
            style_name="short bob"
        )
        
        assert "short bob" in result
        assert "maintaining identical" in result or "maintain identical" in result
    
    def test_create_hairstyle_prompt_invalid_type(self):
        """無効な変更タイプのテスト"""
        service = GeminiService()
        
        result = service.create_hairstyle_prompt("invalid_type")
        
        assert result is None
    
    def test_create_hairstyle_prompt_missing_variables(self):
        """テンプレート変数不足のテスト"""
        service = GeminiService()
        
        # style_name変数が必要だが提供されていない
        result = service.create_hairstyle_prompt("cut_change")
        
        assert result is None
    
    def test_generate_fallback_prompt_keyword_detection(self):
        """フォールバック機能のキーワード検出テスト"""
        service = GeminiService()
        
        test_cases = [
            ("ショートボブに変更", "short hair", "bob cut"),
            ("髪の色を茶色に変更", "brown hair"),
            ("ロングヘアにして", "long hair"),
            ("カールをつけて", "curly hair")
        ]
        
        for japanese_input, *expected_keywords in test_cases:
            result = service._generate_fallback_prompt(japanese_input)
            
            for keyword in expected_keywords:
                assert keyword in result.lower()
    
    @patch('app.services.gemini_service.genai.Client')
    def test_validate_api_connection_success(self, mock_client):
        """API接続テスト成功"""
        mock_response = Mock()
        mock_response.text = "Connection successful"
        
        mock_instance = Mock()
        mock_instance.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_instance
        
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}):
            service = GeminiService()
            result = service.validate_api_connection()
            
            assert result == True
    
    def test_validate_api_connection_no_client(self):
        """API接続テスト（クライアント未初期化）"""
        with patch.dict('os.environ', {}, clear=True):
            service = GeminiService()
            result = service.validate_api_connection()
            
            assert result == False
    
    @patch('app.services.gemini_service.genai.Client')
    def test_validate_api_connection_failure(self, mock_client):
        """API接続テスト失敗"""
        mock_instance = Mock()
        mock_instance.models.generate_content.side_effect = Exception("API Error")
        mock_client.return_value = mock_instance
        
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}):
            service = GeminiService()
            result = service.validate_api_connection()
            
            assert result == False


class TestGeminiServiceIntegration:
    """統合テスト（実際のAPIキー使用）"""
    
    @pytest.mark.skip(reason="実際のAPIキーが必要")
    def test_real_api_call(self):
        """実際のAPI呼び出しテスト（手動実行用）"""
        import os
        if not os.getenv('GEMINI_API_KEY'):
            pytest.skip("GEMINI_API_KEY not found")
        
        service = GeminiService()
        result = service.optimize_hair_style_prompt(
            "ショートボブに変更",
            "woman with long hair"
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
        print(f"API Result: {result}") 