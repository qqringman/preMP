// 主要 JavaScript 檔案

// 全域變數
let socket = null;

// 初始化 Socket.IO
function initSocket() {
    if (typeof io === 'undefined') {
        console.warn('Socket.IO not loaded');
        return;
    }
    
    socket = io();
    
    socket.on('connect', () => {
        console.log('Connected to server');
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
    });
    
    socket.on('progress_update', (data) => {
        handleProgressUpdate(data);
    });
}

// 處理進度更新
function handleProgressUpdate(data) {
    const event = new CustomEvent('task-progress', { detail: data });
    document.dispatchEvent(event);
}

// 顯示通知
function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    if (!notification) {
        console.warn('Notification element not found');
        return;
    }
    
    const icon = notification.querySelector('.notification-icon');
    const messageEl = notification.querySelector('.notification-message');
    
    // 設定圖示
    const icons = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        info: 'fas fa-info-circle',
        warning: 'fas fa-exclamation-triangle'
    };
    
    if (icon) {
        icon.className = `notification-icon ${icons[type] || icons.info}`;
    }
    
    if (messageEl) {
        messageEl.textContent = message;
    }
    
    // 設定樣式
    notification.className = `notification ${type}`;
    notification.classList.remove('hidden');
    notification.classList.add('show');
    
    // 3秒後自動隱藏
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.classList.add('hidden');
        }, 300);
    }, 3000);
}

// 顯示載入遮罩
function showLoading(text = '處理中...') {
    const overlay = document.getElementById('loading-overlay');
    if (!overlay) return;
    
    const loadingText = overlay.querySelector('.loading-text');
    if (loadingText) {
        loadingText.textContent = text;
    }
    overlay.classList.remove('hidden');
}

// 隱藏載入遮罩
function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.classList.add('hidden');
    }
}

// API 請求封裝
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        const contentType = response.headers.get('content-type');
        let data;
        
        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
        } else {
            data = await response.text();
        }
        
        if (!response.ok) {
            // 如果有錯誤訊息，使用它；否則使用狀態碼
            const errorMessage = (data && data.error) ? data.error : `HTTP error! status: ${response.status}`;
            throw new Error(errorMessage);
        }
        
        return data;
    } catch (error) {
        console.error('API request failed:', error);
        showNotification('請求失敗：' + error.message, 'error');
        throw error;
    }
}

// 改進的上傳檔案函數
async function uploadFile(file) {
    // 檢查檔案類型（可選）
    const allowedExtensions = ['.xlsx', '.xls', '.csv'];
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    
    if (!allowedExtensions.includes(fileExtension)) {
        showNotification(`不支援的檔案格式: ${fileExtension}`, 'error');
        throw new Error(`不支援的檔案格式: ${fileExtension}`);
    }
    
    // 檢查檔案大小
    const maxSize = 16 * 1024 * 1024; // 16MB
    if (file.size > maxSize) {
        showNotification('檔案大小超過 16MB 限制', 'error');
        throw new Error('檔案大小超過限制');
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    // 顯示上傳進度
    showLoading(`正在上傳檔案: ${file.name}...`);
    
    // 記錄檔案資訊（調試用）
    console.log('Uploading file:', {
        name: file.name,
        size: file.size,
        type: file.type || 'unknown',
        extension: fileExtension
    });
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        // 先嘗試解析回應
        let responseData;
        const contentType = response.headers.get('content-type');
        
        if (contentType && contentType.includes('application/json')) {
            responseData = await response.json();
        } else {
            // 如果不是 JSON，嘗試讀取文字
            const text = await response.text();
            console.error('Non-JSON response:', text);
            responseData = { error: text };
        }
        
        if (!response.ok) {
            // 從後端獲取詳細錯誤訊息
            const errorMessage = responseData.error || 
                               responseData.message || 
                               `上傳失敗 (${response.status})`;
            
            console.error('Upload failed:', {
                status: response.status,
                statusText: response.statusText,
                error: errorMessage,
                response: responseData
            });
            
            hideLoading();
            showNotification(errorMessage, 'error');
            throw new Error(errorMessage);
        }
        
        // 驗證返回的資料結構
        if (!responseData.filepath && !responseData.file_path) {
            console.error('Invalid response structure:', responseData);
            hideLoading();
            showNotification('伺服器回應格式錯誤', 'error');
            throw new Error('伺服器回應格式錯誤');
        }
        
        hideLoading();
        showNotification(`檔案 ${file.name} 上傳成功`, 'success');
        
        // 統一返回格式（相容不同的後端回應）
        return {
            filepath: responseData.filepath || responseData.file_path,
            filename: responseData.filename || file.name,
            size: responseData.size || file.size
        };
        
    } catch (error) {
        hideLoading();
        
        // 網路錯誤或其他錯誤
        if (error.name === 'TypeError' && error.message === 'Failed to fetch') {
            showNotification('網路連線失敗，請檢查伺服器是否正常運行', 'error');
            throw new Error('網路連線失敗');
        }
        
        // 如果已經處理過的錯誤，直接拋出
        if (error.message) {
            throw error;
        }
        
        // 未知錯誤
        console.error('Upload error:', error);
        showNotification('檔案上傳失敗', 'error');
        throw new Error('檔案上傳失敗');
    }
}

// 格式化檔案大小
function formatFileSize(bytes) {
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

// 格式化時間
function formatTime(date) {
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return '剛剛';
    if (minutes < 60) return `${minutes} 分鐘前`;
    
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} 小時前`;
    
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days} 天前`;
    
    return date.toLocaleDateString('zh-TW');
}

// 下載檔案
function urlDownloadFile(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'download';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// 複製到剪貼簿
function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showNotification('已複製到剪貼簿', 'success');
        }).catch(() => {
            fallbackCopyToClipboard(text);
        });
    } else {
        fallbackCopyToClipboard(text);
    }
}

// 備用複製方法
function fallbackCopyToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        showNotification('已複製到剪貼簿', 'success');
    } catch (err) {
        showNotification('複製失敗', 'error');
    }
    
    document.body.removeChild(textArea);
}

// 防抖函數
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 節流函數
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// 驗證 Email
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// 驗證 URL
function validateUrl(url) {
    try {
        new URL(url);
        return true;
    } catch (e) {
        return false;
    }
}

// 生成唯一 ID
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// 平滑滾動
function smoothScroll(element) {
    element.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
    });
}

// 格式化數字（加千分位）
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// 頁面載入完成後初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化 Socket.IO
    initSocket();
    
    // 設定全域錯誤處理
    window.addEventListener('error', (event) => {
        console.error('Global error:', event.error);
        showNotification('發生錯誤，請重新整理頁面', 'error');
    });
    
    // 設定未處理的 Promise 錯誤
    window.addEventListener('unhandledrejection', (event) => {
        console.error('Unhandled promise rejection:', event.reason);
        showNotification('發生錯誤，請重新整理頁面', 'error');
    });
    
    // 監聽網路狀態
    window.addEventListener('online', () => {
        showNotification('網路已連線', 'success');
    });
    
    window.addEventListener('offline', () => {
        showNotification('網路已斷線', 'warning');
    });
});

// 匯出工具函數
window.utils = {
    showNotification,
    showLoading,
    hideLoading,
    apiRequest,
    uploadFile,
    formatFileSize,
    formatTime,
    urlDownloadFile,
    copyToClipboard,
    debounce,
    throttle,
    validateEmail,
    validateUrl,
    generateId,
    smoothScroll,
    formatNumber
};