/**
 * シンプルな画像生成機能
 */
document.addEventListener('DOMContentLoaded', function() {
    const generationForm = document.getElementById('generation-form');
    const promptInput = document.getElementById('prompt-input');
    const charCount = document.getElementById('char-count');
    const generateBtn = document.getElementById('generate-btn');
    const quickStyles = document.querySelectorAll('.quick-style');
    const generationStatus = document.getElementById('generation-status');
    const resultSection = document.getElementById('result-section');
    const statusTitle = document.getElementById('status-title');
    const statusMessage = document.getElementById('status-message');
    const beforeImage = document.getElementById('before-image');
    const afterImage = document.getElementById('after-image');
    const downloadBtn = document.getElementById('download-btn');
    const newGenerationBtn = document.getElementById('new-generation-btn');
    
    let isGenerating = false;
    let currentTaskId = null;
    
    // プロンプト入力の文字数カウント
    if (promptInput && charCount) {
        promptInput.addEventListener('input', function() {
            const length = this.value.length;
            charCount.textContent = `${length}/300`;
            
            if (length > 250) {
                charCount.classList.add('text-red-400');
            } else {
                charCount.classList.remove('text-red-400');
            }
        });
    }
    
    // クイックスタイル選択
    quickStyles.forEach(button => {
        button.addEventListener('click', function() {
            const prompt = this.dataset.prompt;
            if (promptInput) {
                promptInput.value = prompt;
                promptInput.dispatchEvent(new Event('input'));
            }
        });
    });
    
    // フォーム送信
    if (generationForm) {
        generationForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (isGenerating || generateBtn.disabled) {
                return;
            }
            
            startGeneration();
        });
    }
    
    // 生成開始
    function startGeneration() {
        const filePath = window.UploadManager?.getCurrentFilePath();
        const prompt = promptInput?.value.trim();
        
        if (!filePath || !prompt) {
            showAlert('error', 'ファイルとプロンプトの両方が必要です');
            return;
        }
        
        isGenerating = true;
        showGenerationStatus();
        
        const requestData = {
            file_path: filePath,
            japanese_prompt: prompt,
            original_filename: window.UploadManager?.getCurrentFile()?.name || 'image.jpg'
        };
        
        axios.post('/generate/', requestData)
        .then(response => {
            currentTaskId = response.data.data.task_id;
            showAlert('success', 'ヘアスタイル生成を開始しました');
        })
        .catch(error => {
            console.error('Generation error:', error);
            showAlert('error', error.response?.data?.error || '生成開始に失敗しました');
            resetGeneration();
        });
    }
    
    // 生成ステータス表示
    function showGenerationStatus() {
        // 他のセクションを隠す
        resultSection?.classList.add('hidden');
        
        // ステータスセクションを表示
        generationStatus?.classList.remove('hidden');
        
        // ページをスクロール
        generationStatus?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    
    // 生成リセット
    function resetGeneration() {
        isGenerating = false;
        currentTaskId = null;
        generationStatus?.classList.add('hidden');
        
        // ボタン状態を更新
        window.UploadManager?.clearFile?.();
    }
    
    // 結果表示
    function showResult(result) {
        isGenerating = false;
        
        // ステータスを隠して結果を表示
        generationStatus?.classList.add('hidden');
        
        if (beforeImage && afterImage) {
            beforeImage.src = window.UploadManager?.getCurrentFilePath() || '';
            afterImage.src = result.generated_path || '';
        }
        
        resultSection?.classList.remove('hidden');
        resultSection?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // 統計更新
        updateStats();
    }
    
    // ダウンロードボタン
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function() {
            const imageUrl = afterImage?.src;
            if (imageUrl) {
                const link = document.createElement('a');
                link.href = imageUrl;
                link.download = 'hairstyle_generated.jpg';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                showAlert('success', '画像をダウンロードしました');
            }
        });
    }
    
    // 新しい生成ボタン
    if (newGenerationBtn) {
        newGenerationBtn.addEventListener('click', function() {
            // 結果セクションを隠す
            resultSection?.classList.add('hidden');
            
            // フォームをリセット
            if (promptInput) {
                promptInput.value = '';
                promptInput.dispatchEvent(new Event('input'));
            }
            
            // ファイルをクリア
            window.UploadManager?.clearFile?.();
            
            // ページトップにスクロール
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
    
    // Socket.IO進捗更新
    if (typeof socket !== 'undefined') {
        socket.on('generation_progress', function(data) {
            if (data.task_id === currentTaskId) {
                updateProgress(data);
            }
        });
    }
    
    // 進捗更新
    function updateProgress(data) {
        if (!statusTitle || !statusMessage) return;
        
        if (data.status === 'completed') {
            showResult(data.result);
        } else if (data.status === 'failed') {
            showAlert('error', data.message || '生成に失敗しました');
            resetGeneration();
        } else {
            // ステータスメッセージ更新
            const progressMessages = {
                'prompt_optimization': 'プロンプトを最適化中...',
                'image_generation': 'AI画像を生成中...',
                'waiting_ai': 'AI処理中...',
                'saving': '画像を保存中...'
            };
            
            const message = progressMessages[data.stage] || data.message || '処理中...';
            statusMessage.textContent = message;
        }
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
}); 