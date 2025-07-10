// masking.js
// 手動マスキング用のCanvas描画ロジック

(function() {
    let canvas, ctx, drawing = false, lastX = 0, lastY = 0;
    let brushSize = 20;
    let history = [];
    let imageLoaded = false;

    function initMaskingCanvas(canvasId, imageId) {
        canvas = document.getElementById(canvasId);
        ctx = canvas.getContext('2d');
        resizeCanvasToImage(imageId);
        clearMask();
        bindEvents();
        imageLoaded = true;
        console.log('[masking.js] initMaskingCanvas called', canvas.width, canvas.height, canvas.style.zIndex, canvas.style.pointerEvents);
    }

    function resizeCanvasToImage(imageId) {
        const img = document.getElementById(imageId);
        if (!img) return;
        const parent = img.parentElement;
        const rect = parent.getBoundingClientRect();
        let width = rect.width;
        let height = rect.height;
        // fallback: 親要素のサイズが0ならimgのnaturalWidth/Heightを使う
        if (width < 10 || height < 10) {
            width = img.naturalWidth;
            height = img.naturalHeight;
        }
        canvas.width = width;
        canvas.height = height;
        canvas.style.width = width + 'px';
        canvas.style.height = height + 'px';
        canvas.style.position = 'absolute';
        canvas.style.left = '0';
        canvas.style.top = '0';
        canvas.style.zIndex = '10';
        canvas.style.pointerEvents = 'auto';
        console.log('[masking.js] resizeCanvasToImage', width, height);
    }

    function bindEvents() {
        // マウス
        canvas.onmousedown = (e) => { drawing = true; [lastX, lastY] = getXY(e); saveHistory(); draw(e); };
        canvas.onmousemove = (e) => { if (drawing) draw(e); };
        canvas.onmouseup = () => { drawing = false; };
        canvas.onmouseleave = () => { drawing = false; };
        // タッチ
        canvas.ontouchstart = (e) => { drawing = true; [lastX, lastY] = getXY(e.touches[0]); saveHistory(); draw(e.touches[0]); };
        canvas.ontouchmove = (e) => { if (drawing) draw(e.touches[0]); e.preventDefault(); };
        canvas.ontouchend = () => { drawing = false; };
    }

    function getXY(e) {
        const rect = canvas.getBoundingClientRect();
        // rect.width/heightで正規化し、canvas.width/heightにマッピング
        const x = (e.clientX - rect.left) * (canvas.width / rect.width);
        const y = (e.clientY - rect.top) * (canvas.height / rect.height);
        return [x, y];
    }

    function draw(e) {
        if (!drawing) return;
        ctx.strokeStyle = 'white';
        ctx.lineWidth = brushSize;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.globalAlpha = 1.0;
        ctx.beginPath();
        ctx.moveTo(lastX, lastY);
        const [x, y] = getXY(e);
        ctx.lineTo(x, y);
        ctx.stroke();
        [lastX, lastY] = [x, y];
    }

    function setBrushSize(size) {
        brushSize = size;
    }

    function saveHistory() {
        if (history.length > 20) history.shift();
        history.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
    }

    function undo() {
        if (history.length > 0) {
            const imgData = history.pop();
            ctx.putImageData(imgData, 0, 0);
        } else {
            clearMask();
        }
    }

    function clearMask() {
        ctx.save();
        ctx.globalAlpha = 1.0;
        ctx.globalCompositeOperation = 'source-over';
        ctx.fillStyle = 'black';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.restore();
        history = [];
    }

    function getMaskDataURL() {
        if (!imageLoaded) return null;
        return canvas.toDataURL('image/png');
    }

    // グローバルAPI
    window.maskingTool = {
        init: initMaskingCanvas,
        setBrushSize: setBrushSize,
        undo: undo,
        clear: clearMask,
        getMaskDataURL: getMaskDataURL
    };
})(); 