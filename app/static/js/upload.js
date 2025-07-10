/**
 * ファイルアップロードとURLからの画像取得機能
 */
document.addEventListener('DOMContentLoaded', function() {
    // --- DOM要素の取得 ---
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileSelectButton = document.querySelector('#drop-zone button');

    const imagePreviewContainer = document.getElementById('image-preview-container');
    const previewImage = document.getElementById('preview-image');
    const fileNameElement = document.getElementById('file-name');
    const removeImageButton = document.getElementById('remove-image');

    const fetchImageButton = document.getElementById('fetch-image-btn');
    const imageUrlInput = document.getElementById('image-url-input');

    const generateButton = document.getElementById('generate-btn');
    const promptInput = document.getElementById('prompt-input');

    // --- 状態管理変数 ---
    let uploadedFilePath = null;
    let originalFilename = null;

    // --- イベントリスナーの設定 ---

    // ファイルアップロード関連
    if (dropZone) {
        dropZone.addEventListener('click', (e) => {
             if (e.target.tagName !== 'BUTTON') fileInput.click();
        });
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('hover:bg-gray-100');
        });
        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropZone.classList.remove('hover:bg-gray-100');
        });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('hover:bg-gray-100');
            if (e.dataTransfer.files.length > 0) {
                handleFileUpload(e.dataTransfer.files[0]);
            }
        });
        fileSelectButton.addEventListener('click', (e) => {
            e.stopPropagation(); // dropZoneのクリックイベントを発火させない
            fileInput.click();
        });
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                handleFileUpload(fileInput.files[0]);
            }
        });
    }

    // URLからの画像取得
    if (fetchImageButton) {
        fetchImageButton.addEventListener('click', handleUrlFetch);
    }

    // 共通のイベントリスナー
    removeImageButton.addEventListener('click', clearImagePreview);
    promptInput.addEventListener('input', updateGenerateButtonState);


    // --- 主要な関数 ---

    /**
     * ファイルアップロード処理
     * @param {File} file 選択またはドロップされたファイル
     */
    async function handleFileUpload(file) {
        // バリデーションは省略（既存のものを想定）
        const objectUrl = URL.createObjectURL(file);
        showImagePreview(objectUrl, file.name);

        const formData = new FormData();
        formData.append('file', file);
        
        setLoading(dropZone, true);

        try {
            const response = await axios.post('/upload/', formData);
            if (response.data.success) {
                const data = response.data.data;
                const fileInfo = { path: data.file_path, filename: data.original_filename, url: objectUrl };
                
                // イベントを発行して他のモジュールに通知
                const event = new CustomEvent('file:uploaded', { detail: fileInfo });
                document.dispatchEvent(event);

                showToast('アップロード成功', 'success');
            } else {
                throw new Error(response.data.error);
            }
        } catch (error) {
            showToast(error.message || 'アップロードに失敗しました', 'error');
            clearImagePreview();
        } finally {
            setLoading(dropZone, false);
            // updateGenerateButtonState(); // generate.jsが自律的に更新するので不要
        }
    }

    /**
     * URLからの画像取得処理
     */
    async function handleUrlFetch() {
        const url = imageUrlInput.value.trim();
        if (!url || !url.startsWith('http')) {
            showToast('有効なURLを入力してください', 'error');
            return;
        }

        setLoading(fetchImageButton, true, '取得中...');

        try {
            const response = await axios.post('/api/scrape-image', { url });
            if (response.data.success) {
                const data = response.data.data;
                // サーバー保存パスをそのままimg.srcに使えるようにする
                const fileInfo = { path: data.file_path, filename: data.original_filename, url: data.file_path };

                // イベントを発行して他のモジュールに通知
                const event = new CustomEvent('file:uploaded', { detail: fileInfo });
                document.dispatchEvent(event);
                
                showImagePreview(data.file_path, data.original_filename);
                showToast('画像の取得に成功しました', 'success');
            } else {
                throw new Error(response.data.error);
            }
        } catch (error) {
            showToast(error.message || '画像の取得に失敗しました', 'error');
            clearImagePreview();
        } finally {
            setLoading(fetchImageButton, false, '画像を取得');
            // updateGenerateButtonState(); // generate.jsが自律的に更新するので不要
        }
    }


    // --- ヘルパー関数 ---

    /**
     * 画像プレビューを表示する
     * @param {string} src 画像ソース（URL or ObjectURL）
     * @param {string} name ファイル名
     */
    function showImagePreview(src, name) {
        previewImage.src = src;
        fileNameElement.textContent = name;
        imagePreviewContainer.classList.remove('hidden');
        if(dropZone) dropZone.classList.add('hidden'); // ドロップゾーンを隠す
    }

    /**
     * 画像プレビューをクリアする
     */
    function clearImagePreview() {
        // イベントを発行して他のモジュールに通知
        document.dispatchEvent(new CustomEvent('file:cleared'));

        fileInput.value = '';
        imageUrlInput.value = '';
        imagePreviewContainer.classList.add('hidden');
        previewImage.src = '';
        fileNameElement.textContent = '';
        if(dropZone) dropZone.classList.remove('hidden'); // ドロップゾーンを再表示
        // updateGenerateButtonState(); // generate.jsが自律的に更新するので不要
    }

    /**
     * 生成ボタンの状態を更新する
     */
    function updateGenerateButtonState() {
        // このモジュールは生成ボタンの状態を直接知る必要がなくなる
        // この関数はローカルでのみ使用するか、削除する
    }

    /**
     * トースト通知を表示する
     * @param {string} message 表示メッセージ
     * @param {'info'|'success'|'error'} type トーストの種類
     */
    function showToast(message, type = 'info') {
        const colors = {
            info: '#17a2b8',
            success: '#28a745',
            error: '#dc3545',
        };
        Toastify({
            text: message,
            duration: 3000,
            close: true,
            gravity: "top",
            position: "right",
            backgroundColor: colors[type] || colors.info,
        }).showToast();
    }
    
    /**
     * ローディング状態を設定する
     * @param {HTMLElement} element 対象要素
     * @param {boolean} isLoading ローディング中か
     * @param {string} [text] ボタンのテキスト
     */
    function setLoading(element, isLoading, text) {
        if (!element) return;
        
        element.disabled = isLoading;

        if (element.tagName === 'BUTTON') {
             const originalText = text || element.textContent;
             element.innerHTML = isLoading
                ? `<svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> <span>${text}</span>`
                : originalText.replace('取得中...', '画像を取得');
        } else if (element.id === 'drop-zone') {
            // ドロップゾーンのローディング表示（必要であれば実装）
        }
    }
    
    // 外部からのアクセス用インターフェース
    window.UploadManager = {
        clearFile: clearImagePreview
    };
});