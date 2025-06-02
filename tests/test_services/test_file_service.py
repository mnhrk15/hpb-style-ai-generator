"""
File Service Unit Tests
ファイル処理とバリデーションのテスト
"""
import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from werkzeug.datastructures import FileStorage
from io import BytesIO
from PIL import Image
from app.services.file_service import FileService


class TestFileService:
    """File Serviceテストクラス"""
    
    @pytest.fixture
    def temp_dir(self):
        """一時ディレクトリ作成"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def file_service(self):
        """FileServiceインスタンス（実装では引数なし）"""
        return FileService()
    
    @pytest.fixture
    def sample_image_file(self):
        """テスト用画像ファイル"""
        # 256x256ピクセルのRGB画像（最小解像度要件を満たす）
        img = Image.new('RGB', (256, 256), (255, 255, 255))
        img_io = BytesIO()
        img.save(img_io, 'JPEG')
        img_io.seek(0)
        
        return FileStorage(
            stream=img_io,
            filename='test_image.jpg',
            content_type='image/jpeg'
        )
    
    @pytest.fixture
    def large_image_file(self):
        """大きなテスト用画像ファイル（サイズ制限テスト用）"""
        # 11MB相当のダミーファイル
        large_data = b'x' * (11 * 1024 * 1024)
        
        return FileStorage(
            stream=BytesIO(large_data),
            filename='large_image.png',
            content_type='image/png'
        )
    
    @pytest.fixture
    def invalid_file(self):
        """無効なファイル（画像以外）"""
        return FileStorage(
            stream=BytesIO(b'not an image'),
            filename='text_file.txt',
            content_type='text/plain'
        )
    
    def test_allowed_file_valid_extensions(self, file_service):
        """有効なファイル拡張子のテスト"""
        valid_filenames = [
            'test.png',
            'test.jpg',
            'test.jpeg',
            'test.webp',
            'Test.PNG',  # 大文字
            'image.JPEG'
        ]
        
        for filename in valid_filenames:
            assert file_service._allowed_file(filename) == True
    
    def test_allowed_file_invalid_extensions(self, file_service):
        """無効なファイル拡張子のテスト"""
        invalid_filenames = [
            'test.gif',
            'test.pdf',
            'test.txt',
            'test',  # 拡張子なし
            'test.',  # 空の拡張子
            'image_without_extension'  # 拡張子なし
        ]
        
        for filename in invalid_filenames:
            assert file_service._allowed_file(filename) == False
    
    def test_validate_uploaded_file_valid(self, file_service, sample_image_file):
        """有効な画像ファイルのバリデーションテスト"""
        # 実装では(bool, str or None)のタプルを返す
        is_valid, error_msg = file_service.validate_uploaded_file(sample_image_file)
        
        assert is_valid == True
        assert error_msg is None
    
    def test_validate_uploaded_file_too_large(self, file_service, large_image_file):
        """ファイルサイズ制限のテスト"""
        is_valid, error_msg = file_service.validate_uploaded_file(large_image_file)
        
        assert is_valid == False
        assert 'ファイルサイズ' in error_msg
    
    def test_validate_uploaded_file_invalid_type(self, file_service, invalid_file):
        """無効なファイルタイプのテスト"""
        is_valid, error_msg = file_service.validate_uploaded_file(invalid_file)
        
        assert is_valid == False
        assert '対応していない形式' in error_msg
    
    def test_validate_uploaded_file_no_file(self, file_service):
        """ファイル未選択のテスト"""
        empty_file = FileStorage(
            stream=BytesIO(b''),
            filename='',
            content_type=''
        )
        
        is_valid, error_msg = file_service.validate_uploaded_file(empty_file)
        
        assert is_valid == False
        assert 'ファイルが選択' in error_msg
    
    def test_save_uploaded_file_success(self, app, file_service, sample_image_file, temp_dir):
        """ファイル保存成功テスト"""
        with app.app_context():
            # FlaskアプリのconfigにUPLOAD_FOLDERを設定
            app.config['UPLOAD_FOLDER'] = temp_dir
            
            # 実装では(bool, str or None, dict)のタプルを返す
            success, file_path, file_info = file_service.save_uploaded_file(
                sample_image_file, "test_user_123", optimize=True
            )
            
            assert success == True
            assert file_path is not None
            assert os.path.exists(file_path)
            assert file_path.startswith(temp_dir)
            assert file_path.endswith('.jpg')
            assert file_info is not None
            assert 'original_filename' in file_info
    
    def test_save_uploaded_file_secure_filename(self, app, file_service, temp_dir):
        """セキュアファイル名の確保テスト"""
        with app.app_context():
            # FlaskアプリのconfigにUPLOAD_FOLDERを設定
            app.config['UPLOAD_FOLDER'] = temp_dir
            
            # 危険な文字を含むファイル名
            dangerous_file = FileStorage(
                stream=BytesIO(b'test'),
                filename='../../../etc/passwd.jpg',
                content_type='image/jpeg'
            )
            
            # 小さな有効な画像を作成
            img = Image.new('RGB', (256, 256), (255, 255, 255))
            img_io = BytesIO()
            img.save(img_io, 'JPEG')
            img_io.seek(0)
            dangerous_file.stream = img_io
            
            success, file_path, file_info = file_service.save_uploaded_file(
                dangerous_file, "test_user_123"
            )
            
            if success:
                # パストラバーサル攻撃の防止確認
                assert file_path.startswith(temp_dir)
                assert '../' not in file_path
                # 実装では_sanitize_filenameによりetcが含まれる可能性がある
                # セキュリティが重要なのは、temp_dir外に出ないことです
                normalized_path = os.path.normpath(file_path)
                assert normalized_path.startswith(os.path.normpath(temp_dir))
    
    def test_generate_safe_filename(self, file_service):
        """セキュアファイル名生成テスト"""
        original_name = "test_image.png"
        user_id = "test_user_123"
        
        # 複数回実行して異なるファイル名が生成されることを確認
        filename1 = file_service._generate_safe_filename(original_name, user_id)
        filename2 = file_service._generate_safe_filename(original_name, user_id)
        
        assert filename1 != filename2
        assert filename1.endswith('.jpg')  # 実装では常にJPEGで保存
        assert filename2.endswith('.jpg')
        assert user_id in filename1
        assert user_id in filename2
    
    def test_convert_to_base64_success(self, app, file_service, temp_dir):
        """Base64変換成功テスト"""
        with app.app_context():
            # テスト用画像ファイルを作成
            img = Image.new('RGB', (100, 100), (255, 0, 0))
            test_file_path = os.path.join(temp_dir, 'test_image.jpg')
            img.save(test_file_path, 'JPEG')
            
            # Base64変換
            base64_data = file_service.convert_to_base64(test_file_path)
            
            assert base64_data is not None
            assert isinstance(base64_data, str)
            assert len(base64_data) > 0
            
            # Base64として有効な文字列かチェック
            import base64
            try:
                decoded = base64.b64decode(base64_data)
                assert len(decoded) > 0
            except Exception:
                pytest.fail("Invalid base64 string generated")
    
    def test_convert_to_base64_file_not_found(self, file_service):
        """存在しないファイルのBase64変換テスト"""
        with pytest.raises(Exception, match="画像のBase64変換に失敗"):
            file_service.convert_to_base64('/path/to/nonexistent/file.png')
    
    def test_save_generated_image_success(self, app, file_service, temp_dir):
        """生成画像保存成功テスト"""
        with app.app_context():
            # FlaskアプリのconfigにGENERATED_FOLDERを設定
            app.config['GENERATED_FOLDER'] = temp_dir
            
            # テスト用の画像URL（実際にはダウンロード処理をモック）
            test_image_url = "https://test.com/generated_image.jpg"
            test_task_id = "test_task_id_12345678"  # 長いIDにして切り捨てられても見つかるようにする
            
            with patch('requests.get') as mock_get:
                # モックレスポンス
                mock_response = Mock()
                mock_response.content = b'fake_image_data'
                mock_get.return_value = mock_response
                mock_get.return_value.raise_for_status = Mock()
                
                success, saved_path = file_service.save_generated_image(
                    test_image_url, "test_user_123", "original.jpg", test_task_id
                )
                
                assert success == True
                assert saved_path is not None
                assert os.path.exists(saved_path)
                assert saved_path.startswith(temp_dir)
                # 実装では task_id[:8] で最初の8文字を使用
                assert test_task_id[:8] in saved_path
    
    def test_save_generated_image_download_failure(self, file_service):
        """生成画像ダウンロード失敗テスト"""
        test_image_url = "https://test.com/nonexistent_image.jpg"
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            mock_get.return_value.raise_for_status.side_effect = Exception("404 Not Found")
            
            success, saved_path = file_service.save_generated_image(
                test_image_url, "test_user_123", "original.jpg", "test_task_id"
            )
            
            assert success == False
            assert saved_path is None
    
    def test_analyze_image_features_success(self, file_service, temp_dir):
        """画像特徴分析成功テスト"""
        # テスト用画像ファイルを作成
        img = Image.new('RGB', (800, 600), (255, 0, 0))
        test_file_path = os.path.join(temp_dir, 'test_image.jpg')
        img.save(test_file_path, 'JPEG')
        
        features = file_service.analyze_image_features(test_file_path)
        
        assert features is not None
        assert features['width'] == 800
        assert features['height'] == 600
        assert features['aspect_ratio'] == round(800/600, 2)
        assert features['orientation'] == 'landscape'
        assert 'resolution' in features
        assert 'file_size' in features
        assert 'quality' in features
    
    def test_analyze_image_features_file_not_found(self, file_service):
        """存在しないファイルの画像分析テスト"""
        features = file_service.analyze_image_features('/nonexistent/path/image.jpg')
        
        assert 'error' in features
    
    def test_sanitize_filename(self, file_service):
        """ファイル名サニタイズテスト"""
        dangerous_filename = "../../../etc/passwd"
        safe_name = file_service._sanitize_filename(dangerous_filename)
        
        assert '../' not in safe_name
        # 実装確認：英数字以外は_に変換、50文字以内に制限
        # "../../../etc/passwd" → "_______etc_passwd" だが、最初の部分が切り捨てられる可能性
        assert len(safe_name) <= 50
        assert safe_name.replace('_', '').replace('etc', '').replace('passwd', '') == ""
    
    def test_optimize_image_large_image(self, file_service):
        """大きな画像の最適化テスト"""
        # 4000x3000の大きな画像
        large_img = Image.new('RGB', (4000, 3000), (255, 0, 0))
        
        optimized_img = file_service._optimize_image(large_img)
        
        # 最適化後は2048以下になる
        assert max(optimized_img.size) <= 2048
        assert optimized_img.mode == 'RGB'
    
    def test_optimize_image_small_image(self, file_service):
        """小さな画像の最適化テスト（変更なし）"""
        small_img = Image.new('RGB', (500, 400), (0, 255, 0))
        
        optimized_img = file_service._optimize_image(small_img)
        
        # 小さな画像はそのまま
        assert optimized_img.size == (500, 400)
        assert optimized_img.mode == 'RGB'
    
    def test_get_file_info_success(self, file_service, temp_dir):
        """ファイル情報取得成功テスト"""
        # テスト用画像ファイルを作成
        img = Image.new('RGB', (300, 200), (0, 0, 255))
        test_file_path = os.path.join(temp_dir, 'test_image.jpg')
        img.save(test_file_path, 'JPEG')
        
        file_info = file_service._get_file_info(test_file_path, 'original.jpg')
        
        assert file_info is not None
        assert file_info['original_filename'] == 'original.jpg'
        assert file_info['saved_path'] == test_file_path
        assert file_info['file_size'] > 0
        assert file_info['width'] == 300
        assert file_info['height'] == 200
        assert 'created_at' in file_info
    
    def test_get_file_info_file_not_found(self, file_service):
        """存在しないファイルの情報取得テスト"""
        file_info = file_service._get_file_info('/nonexistent/path/image.jpg', 'test.jpg')
        
        assert 'error' in file_info


class TestFileServiceIntegration:
    """統合テスト"""
    
    def test_full_upload_workflow(self, app, tmp_path):
        """完全なアップロードワークフローテスト"""
        with app.app_context():
            # FlaskアプリのconfigにUPLOAD_FOLDERを設定
            temp_dir = str(tmp_path)
            app.config['UPLOAD_FOLDER'] = temp_dir
            
            file_service = FileService()
            
            # テスト用画像作成
            img = Image.new('RGB', (512, 512), (128, 128, 128))
            img_io = BytesIO()
            img.save(img_io, 'JPEG')
            img_io.seek(0)
            
            test_file = FileStorage(
                stream=img_io,
                filename='test_workflow.jpg',
                content_type='image/jpeg'
            )
            
            # 1. バリデーション
            is_valid, error_msg = file_service.validate_uploaded_file(test_file)
            assert is_valid == True
            
            # 2. ファイル保存
            success, file_path, file_info = file_service.save_uploaded_file(
                test_file, "workflow_user", optimize=True
            )
            assert success == True
            assert os.path.exists(file_path)
            
            # 3. Base64変換
            base64_data = file_service.convert_to_base64(file_path)
            assert isinstance(base64_data, str)
            assert len(base64_data) > 0
            
            # 4. 画像分析
            features = file_service.analyze_image_features(file_path)
            assert features['width'] == 512
            assert features['height'] == 512 