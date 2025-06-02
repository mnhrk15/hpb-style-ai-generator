# Hair Style AI Generator - Production Dockerfile
# Python 3.12 Alpine ベース（軽量化）
FROM python:3.12-alpine

# メタデータ
LABEL maintainer="Hair Style AI Generator Team"
LABEL version="1.0.0"
LABEL description="美容室向けAIヘアスタイル生成アプリケーション"

# 作業ディレクトリ設定
WORKDIR /app

# システム依存関係のインストール
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    lcms2-dev \
    openjpeg-dev \
    tiff-dev \
    tk-dev \
    tcl-dev \
    harfbuzz-dev \
    fribidi-dev \
    libimagequant-dev \
    libxcb-dev \
    libpng-dev \
    && rm -rf /var/cache/apk/*

# Python依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY . .

# 静的ファイルディレクトリの作成
RUN mkdir -p app/static/uploads app/static/generated

# 非rootユーザーの作成
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# アプリケーションディレクトリの権限設定
RUN chown -R appuser:appgroup /app
RUN chmod -R 755 /app

# 非rootユーザーに切り替え
USER appuser

# ポート公開
EXPOSE 5000

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/health')" || exit 1

# 本番用起動コマンド
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "--timeout", "300", "--keep-alive", "10", "run:app"] 