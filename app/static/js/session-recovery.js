/**
 * セッション復旧機能
 * ページロード時にセッション状態を確認し、必要に応じて自動復旧
 */
document.addEventListener('DOMContentLoaded', function() {
    
    // セッション状態確認
    function checkSessionStatus() {
        return axios.get('/api/stats')
        .then(response => {
            console.log('セッション状態確認成功');
            return true;
        })
        .catch(error => {
            console.log('セッション状態確認失敗:', error.response?.status);
            
            if (error.response?.status === 401 || 
                error.response?.data?.error?.includes('セッション')) {
                return false;
            }
            
            // その他のエラーはセッション問題ではない
            return true;
        });
    }
    
    // セッション強制初期化
    function forceInitSession() {
        console.log('セッション強制初期化実行');
        
        return axios.post('/api/session/init')
        .then(response => {
            console.log('セッション初期化成功:', response.data);
            return true;
        })
        .catch(error => {
            console.error('セッション初期化失敗:', error);
            return false;
        });
    }
    
    // ページロード時のセッション確認・復旧
    async function initializeSession() {
        try {
            const sessionValid = await checkSessionStatus();
            
            if (!sessionValid) {
                console.log('無効なセッションを検出、復旧を開始します');
                
                // UI通知
                if (typeof showAlert === 'function') {
                    showAlert('info', 'セッションを復旧中...');
                }
                
                const initSuccess = await forceInitSession();
                
                if (initSuccess) {
                    console.log('セッション復旧完了');
                    if (typeof showAlert === 'function') {
                        showAlert('success', 'セッションを復旧しました');
                    }
                } else {
                    console.error('セッション復旧失敗、ページを再読み込みします');
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                }
            } else {
                console.log('セッション状態正常');
            }
            
        } catch (error) {
            console.error('セッション初期化処理エラー:', error);
        }
    }
    
    // ページロード時に実行
    setTimeout(initializeSession, 1000);
    
    // グローバル関数として公開
    window.SessionRecovery = {
        checkStatus: checkSessionStatus,
        forceInit: forceInitSession,
        initialize: initializeSession
    };
}); 