/**
 * Hair Style AI Generator - 生成処理 JavaScript
 * 複数画像生成対応版
 */

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('generation-form');
    const resultSection = document.getElementById('result-section');
    const statusSection = document.getElementById('generation-status');
    const generateBtn = document.getElementById('generate-btn');
    const btnText = document.getElementById('btn-text');
    const statusTitle = document.getElementById('status-title');
    const statusMessage = document.getElementById('status-message');
    const promptInput = document.getElementById('prompt-input');
    const charCount = document.getElementById('char-count');
    const quickStyles = document.querySelectorAll('.quick-style');
    
    // 複数画像生成用の新しい要素
    const countSelectors = document.querySelectorAll('.count-selector');
    const estimatedTimeSpan = document.getElementById('estimated-time');
    const singleResult = document.getElementById('single-result');
    const multipleResult = document.getElementById('multiple-result');
    const multipleProgress = document.getElementById('multiple-progress');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const generatedImagesGrid = document.getElementById('generated-images-grid');
    const successCountSpan = document.getElementById('success-count');
    const totalCountSpan = document.getElementById('total-count');
    
    let uploadedFileInfo = null; // ローカルスコープでファイル情報を管理
    let currentCount = 1; // 現在選択されている生成枚数
    let currentTaskId = null;
    let isGenerating = false;
    
    // --- イベント購読 ---
    document.addEventListener('file:uploaded', (e) => {
        uploadedFileInfo = e.detail;
        updateGenerateButton();
    });

    document.addEventListener('file:cleared', () => {
        uploadedFileInfo = null;
        updateGenerateButton();
    });


    // プロンプト入力の文字数カウントと状態更新
    if (promptInput && charCount) {
        // 重複イベントリスナーを防ぐためのフラグチェック
        if (!promptInput._generateListenerAdded) {
            promptInput.addEventListener('input', function() {
                const length = this.value.length;
                charCount.textContent = `${length}/300`;
                
                if (length > 250) {
                    charCount.classList.add('text-red-400');
                } else {
                    charCount.classList.remove('text-red-400');
                }
                
                // upload.jsとの競合を避けるため短時間遅延
                setTimeout(updateGenerateButton, 15);
            });
            promptInput._generateListenerAdded = true;
        }
    }
    
    // クイックスタイル選択
    quickStyles.forEach(button => {
        button.addEventListener('click', function() {
            const prompt = this.getAttribute('data-prompt');
            if (promptInput) {
                promptInput.value = prompt;
                promptInput.dispatchEvent(new Event('input'));
            }
        });
    });
    
    // 生成枚数選択の処理
    countSelectors.forEach(button => {
        button.addEventListener('click', function() {
            const count = parseInt(this.dataset.count);
            selectCount(count);
        });
    });
    
    function selectCount(count) {
        currentCount = count;
        
        // UI更新
        countSelectors.forEach(btn => {
            btn.classList.remove('active');
            if (parseInt(btn.dataset.count) === count) {
                btn.classList.add('active');
            }
        });
        
        // 予想時間更新
        if (count === 1) {
            estimatedTimeSpan.textContent = '予想時間: 60-180秒';
        } else {
            estimatedTimeSpan.textContent = `予想時間: ${60 * count}-${180 * count}秒`;
        }
        
        // ボタンテキスト更新
        updateGenerateButton();
    }
    
    function updateGenerateButton() {
        
        // デバッグログ（開発環境のみ）
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.log('=== ボタン状態更新 ===');
            console.log('uploadedFileInfo:', uploadedFileInfo);
            console.log('prompt:', promptInput?.value);
            console.log('isGenerating:', isGenerating);
            console.log('currentCount:', currentCount);
        }
        
        if (!uploadedFileInfo) {
            generateBtn.disabled = true;
            btnText.textContent = '画像をアップロードしてください';
            return;
        }
        
        if (!promptInput || !promptInput.value.trim()) {
            generateBtn.disabled = true;
            btnText.textContent = 'プロンプトを入力してください';
            return;
        }
        
        generateBtn.disabled = isGenerating;
        if (isGenerating) {
            btnText.textContent = '生成中...';
        } else if (currentCount === 1) {
            btnText.textContent = 'ヘアスタイルを生成';
        } else {
            btnText.textContent = `${currentCount}枚のヘアスタイルを生成`;
        }
        
        // デバッグログ（開発環境のみ）
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.log('最終ボタン状態:', {
                disabled: generateBtn.disabled,
                text: btnText.textContent
            });
        }
    }
    
    // フォーム送信処理
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        if (isGenerating) return;
        
        const prompt = promptInput.value.trim();
        
        if (!uploadedFileInfo || !prompt) {
            showAlert('error', '画像とプロンプトの両方が必要です');
            return;
        }
        
        isGenerating = true;
        updateGenerateButton();
        
        // タスクIDをフロントエンドで先に生成
        currentTaskId = self.crypto.randomUUID();
        console.log(`新規タスクIDを生成: ${currentTaskId}`);
        
        // UI状態切り替え
        resultSection.classList.add('hidden');
        statusSection.classList.remove('hidden');
        
        // 複数生成時はプログレスバー表示
        if (currentCount > 1) {
            multipleProgress.classList.remove('hidden');
            progressBar.style.width = '0%';
            progressText.textContent = `0/${currentCount} 完了`;
        } else {
            multipleProgress.classList.add('hidden');
        }
        
        try {
            // 生成リクエスト送信
            const response = await axios.post('/generate/', {
                task_id: currentTaskId, // 生成したタスクIDを送信
                file_path: uploadedFileInfo.path,
                japanese_prompt: prompt,
                original_filename: uploadedFileInfo.filename,
                count: currentCount,
                seed: Math.floor(Math.random() * 100000) // ランダムシード
            });
            
            if (response.data.success) {
                // currentTaskId はリクエスト前に設定済み
                statusTitle.textContent = currentCount === 1 ? '画像を生成中...' : `${currentCount}枚の画像を生成中...`;
                statusMessage.textContent = `しばらくお待ちください（${response.data.data.estimated_time}）`;
                
                showAlert('success', response.data.message);
                
                // SocketIO未接続時のフォールバック
                if (typeof socket === 'undefined') {
                    setTimeout(pollGenerationStatus, 5000);
                }
            } else {
                throw new Error(response.data.error || '生成開始に失敗しました');
            }
            
        } catch (error) {
            console.error('Generation error:', error);
            const message = error.response?.data?.error || error.message || '生成エラーが発生しました';
            showAlert('error', message);
            
            resetGenerationState();
        }
    });
    
    // Socket.IO 進捗イベント処理（強化版）
    if (typeof socket !== 'undefined') {
        socket.on('generation_progress', function(data) {
            console.log('Socket.IO進捗受信:', data);

            // タスクIDが現在のタスクと一致しない場合は無視
            if (!currentTaskId || data.task_id !== currentTaskId) {
                console.log('タスクIDが不一致のためスキップ:', data.task_id, 'vs', currentTaskId);
                return;
            }
            
            // ステータス更新
            if (data.message) {
                statusTitle.textContent = data.message;
            }
            
            // 複数画像生成の進捗更新
            if (data.type === 'multiple' && data.count > 1) {
                multipleProgress.classList.remove('hidden');
                
                if (data.completed !== undefined && data.total !== undefined) {
                    const percentage = (data.completed / data.total) * 100;
                    progressBar.style.width = `${percentage}%`;
                    progressText.textContent = `${data.completed}/${data.total} 完了`;
                }
                
                if (data.message) {
                    statusMessage.textContent = data.message;
                }
            }
            
            // 完了時の処理
            if (data.status === 'completed') {
                console.log('生成完了イベント受信:', data);
                setTimeout(() => {
                    handleGenerationComplete(data);
                }, 500);
            } else if (data.status === 'failed') {
                console.error('生成失敗イベント受信:', data);
                showAlert('error', data.message || '生成に失敗しました');
                resetGenerationState();
            }
        });
        
        // その他の有用なSocketIOイベント
        socket.on('connect', function() {
            console.log('Socket.IO 接続成功');
            // 接続時に自動でルーム参加
            setTimeout(joinUserRoom, 100);
        });
        
        socket.on('disconnect', function() {
            console.log('Socket.IO 接続断了');
        });
        
        socket.on('joined_room', function(data) {
            console.log('ルーム参加成功:', data);
        });
        
        socket.on('error', function(error) {
            console.error('Socket.IO エラー:', error);
        });
        
        // 定期的な接続状態チェック
        setInterval(function() {
            if (isGenerating && !socket.connected) {
                console.warn('生成中にSocket.IO接続が切断されました');
            }
        }, 5000);
        
    } else {
        console.warn('Socket.IOが利用できません。ポーリングにフォールバックします。');
    }
    
    function handleGenerationComplete(data) {
        console.log('=== handleGenerationComplete 開始 ===');
        console.log('Received data:', data);
        console.log('Data type:', data.type);
        console.log('Data result:', data.result);
        
        statusSection.classList.add('hidden');
        resultSection.classList.remove('hidden');
        
        console.log('UI切り替え完了: statusSection hidden, resultSection visible');
        
        if (data.type === 'multiple' && data.result?.generated_images) {
            console.log('複数画像結果を表示');
            showMultipleResults(data.result);
        } else if (data.result) {
            console.log('単数画像結果を表示');
            console.log('Result paths:', {
                generated: data.result.generated_path,
                uploaded: data.result.uploaded_path,
                filename: data.result.original_filename
            });
            showSingleResult(data.result);
        } else {
            console.error('結果データが不正です:', data);
        }
        
        resetGenerationState();
        updateStats();
        
        // 結果セクションにスクロール
        resultSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        console.log('=== handleGenerationComplete 完了 ===');
    }
    
    function showSingleResult(result) {
        console.log('=== showSingleResult 開始 ===');
        console.log('Result data:', result);
        
        singleResult.classList.remove('hidden');
        multipleResult.classList.add('hidden');
        
        console.log('単数結果UI表示切り替え完了');
        
        const beforeImage = document.getElementById('before-image');
        const afterImage = document.getElementById('after-image');
        
        console.log('画像要素取得:', {
            beforeImage: beforeImage ? 'found' : 'not found',
            afterImage: afterImage ? 'found' : 'not found'
        });
        
        if (beforeImage && afterImage) {
            console.log('画像パス設定:', {
                before: result.uploaded_path,
                after: result.generated_path
            });
            
            beforeImage.src = result.uploaded_path;
            afterImage.src = result.generated_path;
            
            // 画像読み込み完了の確認
            beforeImage.onload = function() {
                console.log('Before画像読み込み完了:', this.src);
            };
            afterImage.onload = function() {
                console.log('After画像読み込み完了:', this.src);
            };
            beforeImage.onerror = function() {
                console.error('Before画像読み込み失敗:', this.src);
            };
            afterImage.onerror = function() {
                console.error('After画像読み込み失敗:', this.src);
            };
        } else {
            console.error('画像要素が見つかりません');
        }
        
        setupDownloadButton(result.generated_path, result.original_filename);
        
        console.log('=== showSingleResult 完了 ===');
    }
    
    function showMultipleResults(result) {
        singleResult.classList.add('hidden');
        multipleResult.classList.remove('hidden');
        
        // 元画像表示
        const originalImage = document.getElementById('original-image-multiple');
        originalImage.src = result.uploaded_path;
        
        // 統計更新
        successCountSpan.textContent = result.total_succeeded;
        totalCountSpan.textContent = result.total_requested;
        
        // 生成画像グリッド表示
        generatedImagesGrid.innerHTML = '';
        
        result.generated_images.forEach((image, index) => {
            const imageItem = document.createElement('div');
            imageItem.className = 'generated-image-item';
            imageItem.innerHTML = `
                <img src="${image.path}" alt="生成画像 ${image.index}" loading="lazy">
                <div class="image-overlay">
                    <span>画像 ${image.index}</span>
                    ${image.seed ? `<br><span>Seed: ${image.seed}</span>` : ''}
                </div>
            `;
            
            // クリックでダウンロード
            imageItem.addEventListener('click', () => {
                downloadImage(image.path, `${result.original_filename.split('.')[0]}_${image.index}.jpg`);
            });
            
            generatedImagesGrid.appendChild(imageItem);
        });
        
        // 一括ダウンロードボタン表示
        if (result.generated_images.length > 1) {
            const downloadAllBtn = document.getElementById('download-all-btn');
            downloadAllBtn.classList.remove('hidden');
            downloadAllBtn.onclick = () => downloadAllImages(result);
        }
        
        // メインダウンロードボタンは最初の画像に設定
        if (result.generated_images.length > 0) {
            setupDownloadButton(result.generated_images[0].path, result.original_filename);
        }
    }
    
    function setupDownloadButton(imagePath, originalFilename) {
        const downloadBtn = document.getElementById('download-btn');
        downloadBtn.onclick = () => {
            downloadImage(imagePath, originalFilename);
        };
    }
    
    function downloadImage(imagePath, filename) {
        const link = document.createElement('a');
        link.href = imagePath;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showAlert('success', 'ダウンロードを開始しました');
    }
    
    function downloadAllImages(result) {
        result.generated_images.forEach((image, index) => {
            setTimeout(() => {
                const filename = `${result.original_filename.split('.')[0]}_${image.index}.jpg`;
                downloadImage(image.path, filename);
            }, index * 200); // 200ms間隔でダウンロード
        });
        showAlert('success', `${result.generated_images.length}枚の画像をダウンロード開始`);
    }
    
    function resetGenerationState() {
        isGenerating = false;
        currentTaskId = null;
        updateGenerateButton();
    }
    
    // 生成ステータスポーリング（SocketIO未接続時）
    function pollGenerationStatus() {
        if (!currentTaskId || !isGenerating) return;
        
        axios.get('/generate/history')
        .then(response => {
            if (response.data.success) {
                const data = response.data.data;
                const generatedImages = data.generated_images || [];
                
                // 現在のタスクIDの結果を確認
                const currentResult = generatedImages.find(img => 
                    img.task_id === currentTaskId
                );
                
                if (currentResult) {
                    // 生成完了
                    handleGenerationComplete({
                        status: 'completed',
                        type: currentResult.is_multiple ? 'multiple' : 'single',
                        result: currentResult.is_multiple ? {
                            uploaded_path: currentResult.uploaded_path,
                            generated_images: [currentResult],
                            total_requested: 1,
                            total_succeeded: 1,
                            original_filename: currentResult.original_filename
                        } : {
                            generated_path: currentResult.generated_path,
                            uploaded_path: currentResult.uploaded_path,
                            original_filename: currentResult.original_filename
                        }
                    });
                } else if (isGenerating) {
                    // まだ生成中、再度ポーリング
                    setTimeout(pollGenerationStatus, 3000);
                }
            }
        })
        .catch(error => {
            console.error('Polling error:', error);
            if (isGenerating) {
                setTimeout(pollGenerationStatus, 5000);
            }
        });
    }
    
    // 新しい生成ボタン
    const newGenerationBtn = document.getElementById('new-generation-btn');
    if (newGenerationBtn) {
        newGenerationBtn.addEventListener('click', function() {
            resultSection.classList.add('hidden');
            
            // フォームリセット
            if (promptInput) {
                promptInput.value = '';
                promptInput.dispatchEvent(new Event('input'));
            }
            
            // 生成枚数を1にリセット
            selectCount(1);
            
            // ファイルをクリア
            if (window.UploadManager?.clearFile) {
                window.UploadManager.clearFile();
            }
            
            // uploadedFileInfoも確実にクリア
            uploadedFileInfo = null;
            
            updateGenerateButton();
            
            // ページトップにスクロール
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
    
    // 統計更新
    function updateStats() {
        axios.get('/api/stats')
        .then(response => {
            const stats = response.data;
            const todayElement = document.getElementById('today-count');
            const totalElement = document.getElementById('total-count');
            const remainingElement = document.getElementById('remaining-count');
            
            if (todayElement) todayElement.textContent = stats.user?.daily_generations || 0;
            if (totalElement) totalElement.textContent = stats.user?.total_generations || 0;
            if (remainingElement) remainingElement.textContent = stats.limits?.remaining_today || 0;
        })
        .catch(error => {
            console.error('Stats update error:', error);
        });
    }
    
    // showAlert関数（共通）
    function showAlert(type, message) {
        // 既存のアラート機能を使用
        if (window.showNotification) {
            window.showNotification(type, message);
        } else {
            console.log(`${type.toUpperCase()}: ${message}`);
        }
    }
    
    // 外部からのアクセス用インターフェースは不要になったので削除
    
    // Socket.IOルーム参加（確実に実行）
    function joinUserRoom() {
        if (typeof socket !== 'undefined' && socket.connected) {
            socket.emit('join_user_room', {});
            console.log('ユーザールーム参加要求送信');
        } else if (typeof socket !== 'undefined') {
            // 接続待機後に再試行
            socket.on('connect', function() {
                socket.emit('join_user_room', {});
                console.log('接続後にユーザールーム参加要求送信');
            });
        }
    }
    
    // 初期化
    selectCount(1);
    updateGenerateButton();
    
    // ページロード時に統計更新
    updateStats();
    
    // SocketIOルーム参加
    setTimeout(joinUserRoom, 100);
    
    // 診断情報出力
    console.log('=== 初期化診断 ===');
    console.log('Socket.IO available:', typeof socket !== 'undefined');
    console.log('Socket.IO connected:', typeof socket !== 'undefined' ? socket.connected : 'N/A');
    console.log('DOM elements check:', {
        singleResult: document.getElementById('single-result') ? 'found' : 'not found',
        multipleResult: document.getElementById('multiple-result') ? 'found' : 'not found',
        beforeImage: document.getElementById('before-image') ? 'found' : 'not found',
        afterImage: document.getElementById('after-image') ? 'found' : 'not found',
        statusSection: document.getElementById('generation-status') ? 'found' : 'not found',
        resultSection: document.getElementById('result-section') ? 'found' : 'not found'
    });
    console.log('=================');
}); 