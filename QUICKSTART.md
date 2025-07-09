# 🚀 Hair Style AI Generator - クイックスタートガイド

## 📝 現在のエラー修正状況

### ✅ 修正完了
- **テンプレートエラー**: ギャラリーページの`stats`変数未定義エラー → ✅ 修正済み
- **SocketIO設定**: Redis未接続時の適切な設定 → ✅ 修正済み
- **CSRF問題**: アップロードエンドポイントのCSRF除外 → ✅ 修正済み
- **アップロードエラー**: Content-Type・セッション・バリデーション → ✅ 修正済み

### 🛠 推奨起動方法

#### 1. 正しい起動コマンド
```bash
# ❌ 使用しないでください
flask run

# ✅ 推奨: SocketIOサーバー使用
python dev-start.py

# ✅ または通常の起動
python run.py
```

#### 2. Redis（オプション）
```bash
# 別ターミナルでRedis起動（推奨、必須ではない）
redis-server

# Redis無しでも基本機能は動作します
```

## 🧪 動作確認手順

### 1. サーバー起動確認
```bash
python dev-start.py
```

以下のメッセージが表示されれば成功：
```
🎨 Hair Style AI Generator - 開発環境起動
==================================================
⚠️  Redis未接続（開発環境ではオプション）
🚀 サーバー起動中... http://127.0.0.1:5001
==================================================
```

### 2. 基本テスト実行
```bash
# 別ターミナルで
python test-server.py
```

### 3. ブラウザ確認
- メインページ: http://127.0.0.1:5001
- ギャラリー: http://127.0.0.1:5001/gallery
- ヘルスチェック: http://127.0.0.1:5001/api/health

## 🔧 トラブルシューティング

### SocketIOエラーが出る場合
```bash
# 必ず以下を使用
python dev-start.py

# flask run は使用しない
```

### Redis接続エラー
```bash
# Redis起動（オプション）
redis-server

# またはRedis無しで続行（基本機能は動作）
```

### アップロードエラー
- CSRF除外設定済み
- ファイルサイズ制限: 10MB
- 対応形式: JPG, PNG, WebP

## 📊 確認事項

### ✅ チェックリスト
- [x] `python dev-start.py` でエラー無く起動
- [x] http://127.0.0.1:5001 にアクセス可能
- [x] ギャラリーページが表示される
- [x] SocketIOエラーが出ない
- [x] ファイルアップロード可能（CSRFエラー無し）

### 🐛 既知の制限
- Redis無し: セッション永続化されない（ブラウザリロード時にリセット）
- Celery無し: 非同期タスク処理は同期処理にフォールバック
- AI API無し: プロンプト最適化・画像生成機能は動作しない

## 🎯 次のステップ：環境設定

アプリケーションを完全に機能させるには、環境変数の設定が**必須**です。

### 1. 環境変数ファイル作成
プロジェクトルートにある `env.example` をコピーして `.env` ファイルを作成します。

```bash
cp env.example .env
```

### 2. APIキーとSECRET_KEYの設定
作成した `.env` ファイルを開き、以下の**必須項目**を設定してください。

```dotenv
# .env ファイル

# 1. Gemini APIキー（プロンプト最適化に必須）
# このキーがないとアプリケーションは起動しません。
GEMINI_API_KEY="your_gemini_api_key_here"

# 2. FLUX.1 Kontext APIキー（画像生成に必須）
BFL_API_KEY="your_bfl_api_key_here"

# 3. SECRET_KEY（本番環境では必ず変更してください）
# ランダムでセキュアな文字列に変更しないと、本番モードで起動できません。
SECRET_KEY="your_super_secret_and_random_string_here"

# 4. Redis接続情報（オプション、推奨）
# Redisサーバーにパスワードが設定されている場合は必ず設定してください。
REDIS_URL="redis://:your_redis_password@localhost:6379/0"
```

### 3. RedisとCeleryの起動（オプション）
より高度な機能（セッションの永続化、非同期タスク処理）を使用する場合は、RedisとCeleryワーカーを起動してください。

```bash
# Redisサーバー起動
redis-server

# Celeryワーカー起動 (別ターミナルで)
celery -A run.celery_app worker --loglevel=info
```

## 📞 サポート

問題が続く場合は以下を確認：
1. Python 3.12+ が使用されているか
2. 仮想環境が有効化されているか
3. 依存関係が正しくインストールされているか 