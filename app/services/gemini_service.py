"""
Hair Style AI Generator - Gemini Service
Gemini 2.5 Flashによる美容室専用プロンプト最適化
"""

import os
import logging
from typing import Dict, Optional
from flask import current_app

try:
    from google import genai
    from google.genai import types
    GenerateContentConfig = types.GenerateContentConfig
    ThinkingConfig = types.ThinkingConfig
except ImportError:
    genai = None
    types = None
    GenerateContentConfig = None
    ThinkingConfig = None

logger = logging.getLogger(__name__)


class GeminiService:
    """
    Gemini 2.5 Flashによる美容室専用プロンプト最適化サービス
    thinking_budget=0で速度重視の設定
    """
    
    def __init__(self):
        """Geminiサービスの初期化"""
        self.client = None
        self.api_key = None
        self._initialize_client()
        
        # 美容室専用プロンプトテンプレート（要件定義書準拠）
        self.hairstyle_templates = {
            "cut_change": "Change the hairstyle to {style_name} while maintaining identical facial features, expression, and skin tone. Keep the same lighting, background, and camera angle.",
            
            "color_change": "Change the hair color to {color_name} while keeping the exact same hairstyle, facial features, and expression. Maintain identical lighting and background.",
            
            "style_and_color": "Transform the hairstyle to {style_name} and change hair color to {color_name} while preserving identical facial features, expression, and composition.",
            
            "length_adjustment": "Adjust the hair length to {length_description} while maintaining the same style, facial features, and overall composition."
        }
    
    def _initialize_client(self):
        """Geminiクライアントの初期化"""
        if genai is None:
            logger.error("google-generativeai パッケージがインストールされていません")
            raise ImportError("google-generativeai が必要です")
        
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            logger.error("GEMINI_API_KEY が設定されていません")
            raise ValueError("GEMINI_API_KEY が設定されていません")
        
        try:
            self.client = genai.Client(api_key=self.api_key)
            logger.info("Gemini 2.5 Flash クライアント初期化完了")
        except Exception as e:
            logger.error(f"Geminiクライアント初期化エラー: {e}")
            raise
    
    def optimize_hair_style_prompt(self, japanese_input: str, image_analysis: Optional[str] = None) -> str:
        """
        日本語指示をFLUX.1 Kontext最適プロンプトに変換
        
        Args:
            japanese_input (str): 日本語のヘアスタイル変更指示
            image_analysis (str, optional): 画像の特徴分析結果
            
        Returns:
            str: 最適化された英語プロンプト（512トークン以内）
            
        Example:
            入力: "ショートボブで茶色の髪に変更してください"
            出力: "Transform the woman with long black hair to have a short bob cut,
                  change hair color to warm brown, maintain identical facial features,
                  expression, and composition, keep the same lighting and background"
        """
        if not self.client:
            logger.error("Geminiクライアントが初期化されていません。APIキーが設定されているか確認してください。")
            return self._generate_fallback_prompt(japanese_input)
        
        try:
            # システムプロンプト（顔の一貫性を最優先する美容室専用最適化）
            system_prompt = """
あなたは、AI画像生成モデル「FLUX.1 Kontext」向けのプロンプトを生成する、世界トップクラスのプロンプトエンジニアです。
特に、人物写真（特に顔）の一貫性を維持したまま、髪型や服装などを変更するプロンプトの生成に特化しています。

あなたの最重要タスクは、日本語の指示内容に基づき、元の画像の人物と「完全に同一の人物」に見える画像を生成できる、高品質な英語プロンプトを作成することです。

## 厳守すべきルール

### 1. **顔の一貫性維持が最優先事項**
- **最重要指示**: `maintain the exact same facial features, identity, and expression` のような、顔の完全な一貫性を強制するフレーズを**必ず**プロンプトに含めてください。
- **変更禁止項目**: 元画像の人物の**人種、顔の輪郭、目、鼻、口の形と配置、肌の色合い、年齢感**は**一切変更してはなりません**。
- **具体例**: `A photo of the same woman...` のように、同一人物であることを明確に指示してください。

### 2. **ヘアスタイルとその他の変更点**
- 日本語の指示に沿って、髪型、髪色、髪の長さなどの変更点を具体的に記述してください。
- `Change the hairstyle to a short bob cut` や `Change the hair color to a warm brown` のように、具体的で明確な指示を出してください。

### 3. **品質と構成の維持**
- `photorealistic, high detail, sharp focus` のような、写真品質を高く保つためのキーワードを追加してください。
- 背景、照明、カメラアングル、構図も、指示がない限りは元画像と同一に保つように `keep the same lighting and background` のように指示してください。
- **顔と体の向き**: 元画像の向き（正面、横顔、後ろ姿など）を完全に維持してください。`maintain the same head and body orientation` や `preserve the original viewing angle (e.g., side view, back view)` のようなフレーズを使用してください。

### 4. **プロンプトのフォーマット**
- 出力は英語のプロンプトのみ。説明や前置きは不要です。
- 簡潔かつ効果的な文章で構成してください。

## 画像コンテキストの分析
- ユーザーから提供される「画像の特徴」には、画像の向きに関する重要なヒント（`exif_orientation_desc`や`subject_orientation_hint`）が含まれています。
- この情報を最優先で考慮し、プロンプトが画像の物理的な向きや構図と一致するようにしてください。
- 例えば、`subject_orientation_hint`が`side or rotated`の場合、生成されるプロンプトは横顔や特定の角度からの視点を維持することを絶対に強制する必要があります。

## 思考プロセス
1. **画像コンテキストの確認**: まず提供された「画像の特徴」を分析し、特に`exif_orientation_desc`と`subject_orientation_hint`から、画像の向き（正面、横顔、後ろ姿、回転など）を正確に把握する。
2. 日本語の指示から、ヘアスタイルに関する変更点を正確に抽出する。
3. 「顔の一貫性維持」と「画像の向きの維持」を最優先事項として、それを実現するための強力な英語表現をプロンプトの中心に据える。
4. ヘアスタイルの変更点を具体的に記述する。
5. 全体の品質を維持するための指示を追加する。
6. 最終的なプロンプトを生成する。
            """.strip()
            
            # ユーザープロンプト構築
            image_context = f"\n画像の特徴: {image_analysis}" if image_analysis else ""
            
            full_prompt = f"""
{system_prompt}

日本語指示: {japanese_input}{image_context}

最適化された英語プロンプト:
            """.strip()
            
            # Gemini 2.5 Flash での生成（速度重視設定）
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt,
                config=GenerateContentConfig(
                    thinking_config=ThinkingConfig(
                        thinking_budget=0  # 速度重視のため思考機能無効化
                    ),
                    temperature=0.3,  # 一貫性重視
                    top_p=0.8,
                    max_output_tokens=512  # FLUX.1制限準拠
                )
            )
            
            optimized_prompt = response.text.strip()
            
            # 512トークン制限確認（概算）
            if len(optimized_prompt.split()) > 450:  # 安全マージン
                optimized_prompt = ' '.join(optimized_prompt.split()[:450])
                logger.warning("プロンプトを512トークン制限内に調整しました")
            
            logger.info(f"プロンプト最適化成功: {len(optimized_prompt.split())} words")
            return optimized_prompt
            
        except Exception as e:
            logger.error(f"Geminiプロンプト最適化エラー: {e}")
            return self._generate_fallback_prompt(japanese_input)
    
    def _generate_fallback_prompt(self, japanese_input: str) -> str:
        """
        Gemini利用不可時のフォールバックプロンプト生成
        
        Args:
            japanese_input (str): 日本語入力
            
        Returns:
            str: 基本的な英語プロンプト
        """
        # 基本的なキーワードマッピング
        keyword_mapping = {
            'ショート': 'short hair',
            'ボブ': 'bob cut',
            'ロング': 'long hair',
            'ミディアム': 'medium length hair',
            '茶色': 'brown hair',
            '金髪': 'blonde hair',
            '黒髪': 'black hair',
            'カール': 'curly hair',
            'ストレート': 'straight hair',
            'パーマ': 'permed hair'
        }
        
        # キーワード検出と基本プロンプト生成
        detected_styles = []
        for jp_word, eng_word in keyword_mapping.items():
            if jp_word in japanese_input:
                detected_styles.append(eng_word)
        
        if detected_styles:
            style_description = ', '.join(detected_styles)
            fallback_prompt = f"Change the hairstyle to {style_description} while maintaining identical facial features, expression, and skin tone. Keep the same lighting, background, and camera angle."
        else:
            fallback_prompt = "Transform the hairstyle while maintaining identical facial features, expression, and composition. Keep the same lighting and background."
        
        logger.info("フォールバックプロンプトを生成しました")
        return fallback_prompt
    
    def create_hairstyle_prompt(self, change_type: str, **kwargs) -> Optional[str]:
        """
        定型的なヘアスタイル変更プロンプトの生成
        
        Args:
            change_type (str): 変更タイプ（cut_change, color_change, etc.）
            **kwargs: テンプレート変数
            
        Returns:
            str: 生成されたプロンプト
        """
        template = self.hairstyle_templates.get(change_type)
        if not template:
            logger.warning(f"未知の変更タイプ: {change_type}")
            return None
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"テンプレート変数不足: {e}")
            return None
    
    def validate_api_connection(self) -> bool:
        """
        Gemini API接続テスト
        
        Returns:
            bool: 接続成功可否
        """
        if not self.client:
            return False
        
        try:
            # 簡単なテストクエリ
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents="Test connection",
                config=GenerateContentConfig(
                    thinking_config=ThinkingConfig(thinking_budget=0),
                    max_output_tokens=10
                )
            )
            return bool(response.text)
        except Exception as e:
            logger.error(f"Gemini API接続テストエラー: {e}")
            return False 