"""
Hair Style AI Generator - Gemini Service
Gemini 2.5 Flashによる美容室専用プロンプト最適化
"""

import os
import logging
from typing import Optional
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
    
    def optimize_hair_style_prompt(self, japanese_input: str, image_analysis: Optional[str] = None, effect_type: str = 'none') -> str:
        """
        日本語指示をFLUX.1 Kontext最適プロンプトに変換（特定効果対応版）
        
        Args:
            japanese_input (str): 日本語のヘアスタイル変更指示
            image_analysis (str, optional): 画像の特徴分析結果
            effect_type (str): 追加効果タイプ ('none', 'bright_bg', 'glossy_hair')
            
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
            return self._generate_fallback_prompt(japanese_input, effect_type)

        try:
            # システムプロンプト（簡潔・一貫性重視）
            system_prompt = """
You write concise English prompts for FLUX.1 Kontext from Japanese instructions.

Rules:
- Always preserve identity: include "maintain the exact same facial features, identity, and expression".
- Preserve the same head and body orientation and camera angle (use image context if provided).
- Keep the same lighting and background unless an effect is explicitly requested.
- Output: one short English sentence (about 35–45 words). No explanations, no lists, no extra text.
            """.strip()
            
            # ユーザープロンプト構築
            image_context = f"\n画像の特徴: {image_analysis}" if image_analysis else ""
            
            # ユーザー入力が空の場合の処理
            if not japanese_input or japanese_input.strip() == "":
                if effect_type != 'none':
                    # 効果のみ指定時はGeminiをスキップし、最小プロンプトを返す
                    base_prompt = (
                        "Maintain the exact same facial features, identity, and expression. "
                        "Keep the same head and body orientation and camera angle. "
                    )
                    optimized_prompt = self._apply_effect_to_prompt(base_prompt, effect_type)
                    optimized_prompt = self._ensure_orientation_lock(optimized_prompt)
                    logger.info("効果のみ指定のため、Geminiをスキップして最小プロンプトを返却しました")
                    return optimized_prompt
                else:
                    # 効果なし＆入力なしの場合はエラー
                    logger.warning("プロンプト入力と効果選択の両方が空です")
                    return "Maintain the exact same image with identical facial features, expression, and composition."
            
            full_prompt = f"""
{system_prompt}

日本語指示: {japanese_input}{image_context}

最適化された英語プロンプト:
            """.strip()
            
            # Gemini 2.5 Flash での生成（簡潔出力・速度重視設定）
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt,
                config=GenerateContentConfig(
                    thinking_config=ThinkingConfig(
                        thinking_budget=0  # 速度重視のため思考機能無効化
                    ),
                    temperature=0.3,  # 一貫性重視
                    top_p=0.8,
                    max_output_tokens=120  # 簡潔出力
                )
            )
            
            optimized_prompt = response.text.strip()
            # 余分な改行・空白の正規化
            optimized_prompt = ' '.join(optimized_prompt.split())
            
            if effect_type != 'none':
                optimized_prompt = self._apply_effect_to_prompt(optimized_prompt, effect_type)
            
            # 顔の向き固定フレーズを後付け（既出チェックあり）
            optimized_prompt = self._ensure_orientation_lock(optimized_prompt)
            
            logger.info(f"プロンプト最適化成功 (効果: {effect_type}): {len(optimized_prompt.split())} words")
            return optimized_prompt
            
        except Exception as e:
            logger.error(f"Geminiプロンプト最適化エラー: {e}")
            return self._generate_fallback_prompt(japanese_input, effect_type)
    
    def _generate_fallback_prompt(self, japanese_input: str, effect_type: str = 'none') -> str:
        """
        Gemini利用不可時のフォールバックプロンプト生成（特定効果対応版）
        
        Args:
            japanese_input (str): 日本語入力
            effect_type (str): 追加効果タイプ
            
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
        
        # 特定効果を適用
        if effect_type != 'none':
            fallback_prompt = self._apply_effect_to_prompt(fallback_prompt, effect_type)
        
        # フォールバックにも顔の向き固定を適用
        fallback_prompt = self._ensure_orientation_lock(fallback_prompt)
        
        logger.info(f"フォールバックプロンプトを生成しました (効果: {effect_type})")
        return fallback_prompt

    def _ensure_orientation_lock(self, base_prompt: str) -> str:
        """
        顔の向きが変わらないように固定フレーズを常に後付けする
        """
        orientation_lock = (
            " Keep the face orientation exactly the same as the original image. "
        )
        return base_prompt + orientation_lock

    
    
    def _apply_effect_to_prompt(self, base_prompt: str, effect_type: str) -> str:
        """
        基本プロンプトに特定効果の指示を適用
        
        Args:
            base_prompt (str): 基本プロンプト
            effect_type (str): 効果タイプ
            
        Returns:
            str: 効果適用済みプロンプト
        """
        effect_prompts = {
            'bright_bg': " Replace only the background with a softly textured white concrete wall. The wall should be evenly lit by bright, diffuse natural daylight with no visible shadows.",
            'glossy_hair': " Add gel-like natural shine to the hair only; do not change the hairstyle or hair length or color. Keep the face, background, lighting, and overall composition unchanged."
        }
        
        effect_addition = effect_prompts.get(effect_type, "")
        if effect_addition:
            return base_prompt + effect_addition
        return base_prompt
    
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