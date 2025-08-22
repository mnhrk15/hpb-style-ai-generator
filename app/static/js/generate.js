/**
 * Hair Style AI Generator - 生成処理 JavaScript
 * 複数画像生成対応版
 */

// ログレベル管理ユーティリティ
const Logger = {
    isDevelopment: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1',
    
    debug: function(message, data = null) {
        if (this.isDevelopment) {
            if (data) {
                console.log(message, data);
            } else {
                console.log(message);
            }
        }
    },
    
    info: function(message, data = null) {
        if (data) {
            console.info(message, data);
        } else {
            console.info(message);
        }
    },
    
    warn: function(message, data = null) {
        if (data) {
            console.warn(message, data);
        } else {
            console.warn(message);
        }
    },
    
    error: function(message, data = null) {
        if (data) {
            console.error(message, data);
        } else {
            console.error(message);
        }
    }
};

document.addEventListener('DOMContentLoaded', function() {
    // DOM要素の取得
    const elements = initializeElements();
    
    // 状態管理
    const state = {
        uploadedFileInfo: null,
        currentCount: 1,
        currentTaskId: null,
        isGenerating: false,
        currentBrightness: 100,
        targetImages: []
    };

    // イベントリスナーの設定
    setupEventListeners(elements, state);
    
    // 初期化処理
    initialize(elements, state);
});

/**
 * DOM要素の初期化
 */
function initializeElements() {
    const elements = {
        // フォーム関連
        form: document.getElementById('generation-form'),
        generateBtn: document.getElementById('generate-btn'),
        btnText: document.getElementById('btn-text'),
        promptInput: document.getElementById('prompt-input'),
        charCount: document.getElementById('char-count'),
        
        // 結果表示関連
        resultSection: document.getElementById('result-section'),
        statusSection: document.getElementById('generation-status'),
        statusTitle: document.getElementById('status-title'),
        statusMessage: document.getElementById('status-message'),
        singleResult: document.getElementById('single-result'),
        multipleResult: document.getElementById('multiple-result'),
        
        // プログレス関連
        multipleProgress: document.getElementById('multiple-progress'),
        progressBar: document.getElementById('progress-bar'),
        progressText: document.getElementById('progress-text'),
        
        // UI要素
        quickStyles: document.querySelectorAll('.quick-style'),
        effectRadios: document.querySelectorAll('.effect-radio'),
        promptHint: document.getElementById('prompt-hint'),
        countSelectors: document.querySelectorAll('.count-selector'),
        estimatedTimeSpan: document.getElementById('estimated-time'),
        
        // 画像関連
        generatedImagesGrid: document.getElementById('generated-images-grid'),
        successCountSpan: document.getElementById('success-count'),
        totalCountSpan: document.getElementById('total-count'),
        
        // 明るさ調整関連
        imageAdjustmentSection: document.getElementById('image-adjustment-section'),
        brightnessSlider: document.getElementById('brightness-slider'),
        resetBrightnessBtn: document.getElementById('reset-brightness-btn'),
        downloadAdjustedBtn: document.getElementById('download-adjusted-btn'),
        
        // マスキング関連
        brushSizeInput: document.getElementById('brush-size'),
        undoBtn: document.getElementById('undo-mask'),
        resetBtn: document.getElementById('reset-mask'),
        
        // その他のボタン
        newGenerationBtn: document.getElementById('new-generation-btn')
    };

    Logger.debug('DOM要素取得完了:', {
        imageAdjustmentSection: !!elements.imageAdjustmentSection,
        brightnessSlider: !!elements.brightnessSlider,
        resetBrightnessBtn: !!elements.resetBrightnessBtn,
        downloadAdjustedBtn: !!elements.downloadAdjustedBtn
    });

    return elements;
}

/**
 * イベントリスナーの設定
 */
function setupEventListeners(elements, state) {
    // ファイルアップロード関連イベント
    setupFileEvents(elements, state);
    
    // UI操作イベント
    setupUIEvents(elements, state);
    
    // フォーム送信イベント
    setupFormEvents(elements, state);
    
    // Socket.IOイベント
    setupSocketEvents(elements, state);
    
    // 明るさ調整イベント
    setupBrightnessEvents(elements, state);
    
    // その他のボタンイベント
    setupMiscEvents(elements, state);
}

/**
 * ファイル関連イベントの設定
 */
function setupFileEvents(elements, state) {
    document.addEventListener('file:uploaded', (e) => {
        state.uploadedFileInfo = e.detail;
        updateGenerateButton(elements, state);
        
        // マスキングUIに画像を表示
        const img = document.getElementById('source-image-for-masking');
        if (img && state.uploadedFileInfo && state.uploadedFileInfo.url) {
            img.onload = function() {
                Logger.debug('[generate.js] img loaded', {
                    src: img.src,
                    width: img.width,
                    height: img.height
                });
                if (window.maskingTool) {
                    window.maskingTool.init('masking-canvas', 'source-image-for-masking');
                }
            };
            img.src = '';
            img.src = state.uploadedFileInfo.url;
        }
    });

    document.addEventListener('file:cleared', () => {
        state.uploadedFileInfo = null;
        updateGenerateButton(elements, state);
        resetBrightnessAdjustment(elements, state);
    });
}

/**
 * UI操作イベントの設定
 */
function setupUIEvents(elements, state) {
    // プロンプト入力
    if (elements.promptInput && elements.charCount) {
        if (!elements.promptInput._generateListenerAdded) {
            elements.promptInput.addEventListener('input', function() {
                updateCharCount(elements, this.value.length);
                setTimeout(() => updateGenerateButton(elements, state), 15);
            });
            elements.promptInput._generateListenerAdded = true;
        }
    }
    
    // クイックスタイル選択
    elements.quickStyles.forEach(button => {
        button.addEventListener('click', function() {
            if (elements.promptInput) {
                elements.promptInput.value = this.getAttribute('data-prompt');
                elements.promptInput.dispatchEvent(new Event('input'));
            }
        });
    });
    
    // 効果選択
    elements.effectRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            updatePromptRequirement(elements);
            updateGenerateButton(elements, state);
        });
    });
    
    // 生成枚数選択
    elements.countSelectors.forEach(button => {
        button.addEventListener('click', function() {
            const count = parseInt(this.dataset.count);
            selectCount(elements, state, count);
        });
    });
    
    // マスキング関連
    setupMaskingEvents(elements);
}

/**
 * マスキング関連イベントの設定
 */
function setupMaskingEvents(elements) {
    if (elements.brushSizeInput) {
        elements.brushSizeInput.addEventListener('input', function() {
            if (window.maskingTool) window.maskingTool.setBrushSize(parseInt(this.value));
        });
    }
    
    if (elements.undoBtn) {
        elements.undoBtn.addEventListener('click', function() {
            if (window.maskingTool) window.maskingTool.undo();
        });
    }
    
    if (elements.resetBtn) {
        elements.resetBtn.addEventListener('click', function() {
            if (window.maskingTool) window.maskingTool.clear();
        });
    }
}

/**
 * フォーム送信イベントの設定
 */
function setupFormEvents(elements, state) {
    elements.form.addEventListener('submit', async function(e) {
        e.preventDefault();
        await handleFormSubmit(elements, state);
    });
}

/**
 * Socket.IOイベントの設定
 */
function setupSocketEvents(elements, state) {
    if (typeof socket !== 'undefined') {
        socket.on('generation_progress', function(data) {
            handleGenerationProgress(elements, state, data);
        });
        
        socket.on('connect', function() {
            Logger.info('Socket.IO 接続成功');
            setTimeout(() => joinUserRoom(), 100);
        });
        
        socket.on('disconnect', (reason) => {
            Logger.warn(`ソケット接続切断: ${reason}`);
        });
        
        socket.on('joined_room', function(data) {
            Logger.debug('ルーム参加成功:', data);
        });
        
        socket.on('error', function(error) {
            Logger.error('Socket.IO エラー:', error);
        });
        
        // 定期的な接続状態チェック
        setInterval(function() {
            if (state.isGenerating && !socket.connected) {
                Logger.warn('生成中にSocket.IO接続が切断されました');
            }
        }, 5000);
    } else {
        Logger.warn('Socket.IOが利用できません。ポーリングにフォールバックします。');
    }
}

/**
 * 明るさ調整イベントの設定
 */
function setupBrightnessEvents(elements, state) {
    Logger.debug('=== 明るさ調整機能初期化開始 ===');
    
    if (!elements.brightnessSlider) {
        Logger.error('brightnessSlider要素が見つかりません');
        return;
    }

    elements.brightnessSlider.addEventListener('input', function() {
        Logger.debug('明るさスライダー操作:', this.value);
        state.currentBrightness = parseInt(this.value);
        applyBrightnessToImages(state);
        updateDownloadButton(elements, state);
    });

    if (elements.resetBrightnessBtn) {
        elements.resetBrightnessBtn.addEventListener('click', function() {
            Logger.debug('明るさリセットボタンクリック');
            resetBrightness(elements, state);
        });
    }

    if (elements.downloadAdjustedBtn) {
        elements.downloadAdjustedBtn.addEventListener('click', function() {
            Logger.debug('調整済み画像ダウンロードボタンクリック');
            downloadAdjustedImage(state);
        });
    }

    Logger.debug('=== 明るさ調整機能初期化完了 ===');
}

/**
 * その他のボタンイベントの設定
 */
function setupMiscEvents(elements, state) {
    if (elements.newGenerationBtn) {
        elements.newGenerationBtn.addEventListener('click', function() {
            handleNewGeneration(elements, state);
        });
    }
}

/**
 * 初期化処理
 */
function initialize(elements, state) {
    selectCount(elements, state, 1);
    updateGenerateButton(elements, state);
    updatePromptRequirement(elements);
    updateStats();
    
    // SocketIOルーム参加
    setTimeout(() => joinUserRoom(), 100);
    
    // 診断情報出力
    outputDiagnostics();
}

/**
 * 文字数カウント更新
 */
function updateCharCount(elements, length) {
    elements.charCount.textContent = `${length}/300`;
    
    if (length > 250) {
        elements.charCount.classList.add('text-red-400');
    } else {
        elements.charCount.classList.remove('text-red-400');
    }
}

/**
 * 生成枚数選択
 */
function selectCount(elements, state, count) {
    state.currentCount = count;
    
    // UI更新
    elements.countSelectors.forEach(btn => {
        btn.classList.remove('active');
        if (parseInt(btn.dataset.count) === count) {
            btn.classList.add('active');
        }
    });
    
    // 予想時間更新
    if (count === 1) {
        elements.estimatedTimeSpan.textContent = '予想時間: 60-180秒';
    } else {
        elements.estimatedTimeSpan.textContent = `予想時間: ${60 * count}-${180 * count}秒`;
    }
    
    updateGenerateButton(elements, state);
}

/**
 * プロンプト要件更新
 */
function updatePromptRequirement(elements) {
    const selectedEffect = getSelectedEffect();
    
    if (selectedEffect === 'none') {
        elements.promptHint.textContent = '自然な日本語で詳しく説明してください';
    } else {
        elements.promptHint.textContent = '追加効果が選択されているため、プロンプト入力は任意です';
    }
}

/**
 * 選択されたエフェクトを取得
 */
function getSelectedEffect() {
    return document.querySelector('input[name="effect_type"]:checked').value;
}

/**
 * 生成ボタン状態更新
 */
function updateGenerateButton(elements, state) {
    Logger.debug('=== ボタン状態更新 ===', {
        uploadedFileInfo: !!state.uploadedFileInfo,
        prompt: elements.promptInput?.value,
        isGenerating: state.isGenerating,
        currentCount: state.currentCount
    });
    
    if (!state.uploadedFileInfo) {
        elements.generateBtn.disabled = true;
        elements.btnText.textContent = '画像をアップロードしてください';
        return;
    }
    
    const selectedEffect = getSelectedEffect();
    const hasPrompt = elements.promptInput && elements.promptInput.value.trim();
    
    if (selectedEffect === 'none' && !hasPrompt) {
        elements.generateBtn.disabled = true;
        elements.btnText.textContent = 'プロンプトを入力するか、追加効果を選択してください';
        return;
    }
    
    elements.generateBtn.disabled = state.isGenerating;
    if (state.isGenerating) {
        elements.btnText.textContent = '生成中...';
    } else if (state.currentCount === 1) {
        elements.btnText.textContent = 'ヘアスタイルを生成';
    } else {
        elements.btnText.textContent = `${state.currentCount}枚のヘアスタイルを生成`;
    }
    
    Logger.debug('最終ボタン状態:', {
        disabled: elements.generateBtn.disabled,
        text: elements.btnText.textContent
    });
}

/**
 * フォーム送信処理
 */
async function handleFormSubmit(elements, state) {
    if (state.isGenerating) return;
    
    const prompt = elements.promptInput.value.trim();
    const selectedEffect = getSelectedEffect();
    
    if (!state.uploadedFileInfo) {
        showAlert('error', '画像をアップロードしてください');
        return;
    }
    
    if (selectedEffect === 'none' && !prompt) {
        showAlert('error', 'プロンプトを入力するか、追加効果を選択してください');
        return;
    }
    
    // 生成モード取得
    let mode = 'kontext';
    const modeRoot = document.querySelector('[x-data]');
    if (modeRoot && modeRoot.__x) {
        mode = modeRoot.__x.get('mode');
    }
    
    let maskData = null;
    if (mode === 'fill') {
        if (window.maskingTool) {
            maskData = window.maskingTool.getMaskDataURL();
            if (!maskData) {
                showAlert('error', 'マスクが描画されていません。');
                return;
            }
        }
    }
    
    state.isGenerating = true;
    updateGenerateButton(elements, state);
    
    // タスクIDを生成
    state.currentTaskId = self.crypto.randomUUID();
    Logger.info(`新規タスクIDを生成: ${state.currentTaskId}`);
    
    // UI状態切り替え
    elements.resultSection.classList.add('hidden');
    elements.statusSection.classList.remove('hidden');
    
    // プログレスバー設定
    if (state.currentCount > 1) {
        elements.multipleProgress.classList.remove('hidden');
        elements.progressBar.style.width = '0%';
        elements.progressText.textContent = `0/${state.currentCount} 完了`;
    } else {
        elements.multipleProgress.classList.add('hidden');
    }
    
    try {
        const response = await axios.post('/generate/', {
            task_id: state.currentTaskId,
            file_path: state.uploadedFileInfo.path,
            japanese_prompt: prompt,
            original_filename: state.uploadedFileInfo.filename,
            count: state.currentCount,
            seed: Math.floor(Math.random() * 100000),
            mode: mode,
            mask_data: maskData,
            effect_type: selectedEffect
        });
        
        if (response.data.success) {
            elements.statusTitle.textContent = state.currentCount === 1 ? 
                '画像を生成中...' : `${state.currentCount}枚の画像を生成中...`;
            elements.statusMessage.textContent = `しばらくお待ちください（${response.data.data.estimated_time}）`;
            
            showAlert('success', response.data.message);
            
            // SocketIO未接続時のフォールバック
            if (typeof socket === 'undefined') {
                setTimeout(() => pollGenerationStatus(elements, state), 5000);
            }
        } else {
            throw new Error(response.data.error || '生成開始に失敗しました');
        }
    } catch (error) {
        Logger.error('Generation error:', error);
        const message = error.response?.data?.error || error.message || '生成エラーが発生しました';
        showAlert('error', message);
        resetGenerationState(elements, state);
    }
}

/**
 * Socket.IO進捗処理
 */
function handleGenerationProgress(elements, state, data) {
    Logger.info('Socket.IO進捗受信:', data);

    // タスクIDチェック
    if (!state.currentTaskId || data.task_id !== state.currentTaskId) {
        Logger.debug('タスクIDが不一致のためスキップ:', data.task_id, 'vs', state.currentTaskId);
        return;
    }
    
    // ステータス更新
    if (data.message) {
        elements.statusTitle.textContent = data.message;
    }
    
    // 複数画像生成の進捗更新
    if (data.type === 'multiple' && data.count > 1) {
        elements.multipleProgress.classList.remove('hidden');
        
        if (data.completed !== undefined && data.total !== undefined) {
            const percentage = (data.completed / data.total) * 100;
            elements.progressBar.style.width = `${percentage}%`;
            elements.progressText.textContent = `${data.completed}/${data.total} 完了`;
        }
        
        if (data.message) {
            elements.statusMessage.textContent = data.message;
        }
    }
    
    // 完了時の処理
    if (data.status === 'completed') {
        Logger.info('生成完了イベント受信:', data);
        setTimeout(() => {
            handleGenerationComplete(elements, state, data);
        }, 500);
    } else if (data.status === 'failed') {
        Logger.error('生成失敗イベント受信:', data);
        showAlert('error', data.message || '生成に失敗しました');
        resetGenerationState(elements, state);
    }
}

/**
 * 生成完了処理
 */
function handleGenerationComplete(elements, state, data) {
    Logger.debug('=== handleGenerationComplete 開始 ===');
    Logger.debug('Received data:', data);
    
    elements.statusSection.classList.add('hidden');
    elements.resultSection.classList.remove('hidden');
    
    if (data.type === 'multiple' && data.result?.generated_images) {
        Logger.debug('複数画像結果を表示');
        showMultipleResults(elements, state, data.result);
    } else if (data.result) {
        Logger.debug('単数画像結果を表示');
        showSingleResult(elements, state, data.result);
    } else {
        Logger.error('結果データが不正です:', data);
    }
    
    resetGenerationState(elements, state, { keepAdjustmentVisible: true });
    updateStats();
    
    // 結果セクションにスクロール
    elements.resultSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    Logger.debug('=== handleGenerationComplete 完了 ===');
}

/**
 * 単数結果表示
 */
function showSingleResult(elements, state, result) {
    Logger.debug('=== showSingleResult 開始 ===', result);
    
    elements.singleResult.classList.remove('hidden');
    elements.multipleResult.classList.add('hidden');
    elements.imageAdjustmentSection.classList.remove('hidden');
    
    const beforeImage = document.getElementById('before-image');
    const afterImage = document.getElementById('after-image');
    
    if (beforeImage && afterImage) {
        beforeImage.src = result.uploaded_path;
        afterImage.src = result.generated_path;
        
        beforeImage.onload = () => Logger.debug('Before画像読み込み完了:', beforeImage.src);
        afterImage.onload = () => {
            Logger.debug('After画像読み込み完了:', afterImage.src);
            setTargetImages(state);
        };
        beforeImage.onerror = () => Logger.error('Before画像読み込み失敗:', beforeImage.src);
        afterImage.onerror = () => Logger.error('After画像読み込み失敗:', afterImage.src);
    } else {
        Logger.error('画像要素が見つかりません');
    }
    
    setupDownloadButton(result.generated_path, result.original_filename);
    
    Logger.debug('=== showSingleResult 完了 ===');
}

/**
 * 複数結果表示
 */
function showMultipleResults(elements, state, result) {
    elements.singleResult.classList.add('hidden');
    elements.multipleResult.classList.remove('hidden');
    elements.imageAdjustmentSection.classList.remove('hidden');
    
    // 元画像表示
    const originalImage = document.getElementById('original-image-multiple');
    originalImage.src = result.uploaded_path;
    
    // 統計更新
    elements.successCountSpan.textContent = result.total_succeeded;
    elements.totalCountSpan.textContent = result.total_requested;
    
    // 生成画像グリッド表示
    elements.generatedImagesGrid.innerHTML = '';
    
    result.generated_images.forEach((image) => {
        const imageItem = createImageItem(image, result, state);
        elements.generatedImagesGrid.appendChild(imageItem);
    });
    
    // 一括ダウンロードボタン表示
    if (result.generated_images.length > 1) {
        const downloadAllBtn = document.getElementById('download-all-btn');
        downloadAllBtn.classList.remove('hidden');
        downloadAllBtn.onclick = () => downloadAllImages(result);
    }
    
    // メインダウンロードボタン設定
    if (result.generated_images.length > 0) {
        setupDownloadButton(result.generated_images[0].path, result.original_filename);
    }
}

/**
 * 画像アイテム作成
 */
function createImageItem(image, result, state) {
    const imageItem = document.createElement('div');
    imageItem.className = 'generated-image-item';
    imageItem.innerHTML = `
        <img src="${image.path}" alt="生成画像 ${image.index}" loading="lazy">
        <div class="image-overlay">
            <span>画像 ${image.index}</span>
            ${image.seed ? `<br><span>Seed: ${image.seed}</span>` : ''}
        </div>
    `;
    
    const img = imageItem.querySelector('img');
    img.onload = () => setTargetImages(state);
    
    imageItem.addEventListener('click', () => {
        downloadImage(image.path, `${result.original_filename.split('.')[0]}_${image.index}.jpg`);
    });
    
    return imageItem;
}

/**
 * 明るさ調整対象画像設定
 */
function setTargetImages(state) {
    Logger.debug('=== setTargetImages 開始 ===');
    state.targetImages = [];
    
    const afterImage = document.getElementById('after-image');
    const singleResultVisible = !document.getElementById('single-result')?.classList.contains('hidden');
    
    if (afterImage && singleResultVisible) {
        state.targetImages.push(afterImage);
        Logger.debug('after-image を targetImages に追加');
    }
    
    // 複数画像の場合
    const generatedImages = document.querySelectorAll('#generated-images-grid img');
    generatedImages.forEach(img => state.targetImages.push(img));
    
    Logger.debug('最終的な targetImages 数:', state.targetImages.length);
    Logger.debug('=== setTargetImages 完了 ===');
}

/**
 * 明るさ適用
 */
function applyBrightnessToImages(state) {
    const brightnessValue = state.currentBrightness / 100;
    state.targetImages.forEach(img => {
        img.style.filter = `brightness(${brightnessValue})`;
    });
}

/**
 * 明るさリセット
 */
function resetBrightness(elements, state) {
    elements.brightnessSlider.value = 100;
    state.currentBrightness = 100;
    applyBrightnessToImages(state);
    updateDownloadButton(elements, state);
}

/**
 * 明るさ調整リセット
 */
function resetBrightnessAdjustment(elements, state) {
    if (elements.imageAdjustmentSection) elements.imageAdjustmentSection.classList.add('hidden');
    if (elements.brightnessSlider) elements.brightnessSlider.value = 100;
    state.currentBrightness = 100;
    if (elements.downloadAdjustedBtn) elements.downloadAdjustedBtn.classList.add('hidden');
    state.targetImages = [];
}

/**
 * ダウンロードボタン状態更新
 */
function updateDownloadButton(elements, state) {
    if (state.currentBrightness === 100) {
        elements.downloadAdjustedBtn.classList.add('hidden');
    } else {
        elements.downloadAdjustedBtn.classList.remove('hidden');
    }
}

/**
 * 調整済み画像ダウンロード
 */
function downloadAdjustedImage(state) {
    const mainImage = state.targetImages[0];
    if (!mainImage) return;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    canvas.width = mainImage.naturalWidth;
    canvas.height = mainImage.naturalHeight;
    
    ctx.filter = `brightness(${state.currentBrightness / 100})`;
    ctx.drawImage(mainImage, 0, 0);
    
    canvas.toBlob(function(blob) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `adjusted_brightness_${state.currentBrightness}_${Date.now()}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        showAlert('success', '調整済み画像をダウンロードしました');
    }, 'image/png');
}

/**
 * ダウンロードボタン設定
 */
function setupDownloadButton(imagePath, originalFilename) {
    const downloadBtn = document.getElementById('download-btn');
    downloadBtn.onclick = () => {
        downloadImage(imagePath, originalFilename);
    };
}

/**
 * 画像ダウンロード
 */
function downloadImage(imagePath, filename) {
    const link = document.createElement('a');
    link.href = imagePath;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showAlert('success', 'ダウンロードを開始しました');
}

/**
 * 全画像ダウンロード
 */
function downloadAllImages(result) {
    result.generated_images.forEach((image, index) => {
        setTimeout(() => {
            const filename = `${result.original_filename.split('.')[0]}_${image.index}.jpg`;
            downloadImage(image.path, filename);
        }, index * 200);
    });
    showAlert('success', `${result.generated_images.length}枚の画像をダウンロード開始`);
}

/**
 * 生成状態リセット
 */
function resetGenerationState(elements, state, options = {}) {
    const { keepAdjustmentVisible = false } = options;
    state.isGenerating = false;
    state.currentTaskId = null;
    updateGenerateButton(elements, state);
    
    if (!keepAdjustmentVisible) {
        elements.imageAdjustmentSection.classList.add('hidden');
    }
    elements.brightnessSlider.value = 100;
    state.currentBrightness = 100;
    elements.downloadAdjustedBtn.classList.add('hidden');
    state.targetImages = [];
}

/**
 * 新しい生成処理
 */
function handleNewGeneration(elements, state) {
    elements.resultSection.classList.add('hidden');
    
    // フォームリセット
    if (elements.promptInput) {
        elements.promptInput.value = '';
        elements.promptInput.dispatchEvent(new Event('input'));
    }
    
    selectCount(elements, state, 1);
    
    // 追加効果をリセット
    document.querySelector('input[name="effect_type"][value="none"]').checked = true;
    updatePromptRequirement(elements);
    
    // ファイルクリア
    if (window.UploadManager?.clearFile) {
        window.UploadManager.clearFile();
    }
    
    state.uploadedFileInfo = null;
    resetBrightnessAdjustment(elements, state);
    updateGenerateButton(elements, state);
    
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/**
 * 生成ステータスポーリング
 */
function pollGenerationStatus(elements, state) {
    if (!state.currentTaskId || !state.isGenerating) return;
    
    axios.get('/generate/history')
    .then(response => {
        if (response.data.success) {
            const data = response.data.data;
            const generatedImages = data.generated_images || [];
            
            const currentResult = generatedImages.find(img => 
                img.task_id === state.currentTaskId
            );
            
            if (currentResult) {
                handleGenerationComplete(elements, state, {
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
            } else if (state.isGenerating) {
                setTimeout(() => pollGenerationStatus(elements, state), 3000);
            }
        }
    })
    .catch(error => {
        Logger.error('Polling error:', error);
        if (state.isGenerating) {
            setTimeout(() => pollGenerationStatus(elements, state), 5000);
        }
    });
}

/**
 * 統計更新
 */
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
        Logger.error('Stats update error:', error);
    });
}

/**
 * アラート表示
 */
function showAlert(type, message) {
    if (window.showNotification) {
        window.showNotification(type, message);
    } else {
        console.log(`${type.toUpperCase()}: ${message}`);
    }
}

/**
 * Socket.IOルーム参加
 */
function joinUserRoom() {
    if (typeof socket !== 'undefined' && socket.connected) {
        socket.emit('join_user_room', {});
        Logger.debug('ユーザールーム参加要求送信');
    } else if (typeof socket !== 'undefined') {
        socket.on('connect', function() {
            socket.emit('join_user_room', {});
            Logger.debug('接続後にユーザールーム参加要求送信');
        });
    }
}

/**
 * 診断情報出力
 */
function outputDiagnostics() {
    Logger.debug('=== 初期化診断 ===');
    Logger.debug('Socket.IO available:', typeof socket !== 'undefined');
    Logger.debug('Socket.IO connected:', typeof socket !== 'undefined' ? socket.connected : 'N/A');
    Logger.debug('DOM elements check:', {
        singleResult: !!document.getElementById('single-result'),
        multipleResult: !!document.getElementById('multiple-result'),
        beforeImage: !!document.getElementById('before-image'),
        afterImage: !!document.getElementById('after-image'),
        statusSection: !!document.getElementById('generation-status'),
        resultSection: !!document.getElementById('result-section')
    });
    Logger.debug('=================');
}