// 前端工具函數
const utils = {
    // API 請求封裝
    async apiRequest(url, options = {}) {
        try {
            // 只有在有 body 且不是 FormData 時才設定 Content-Type
            let headers = { ...options.headers };
            
            if (options.body && !(options.body instanceof FormData)) {
                headers['Content-Type'] = 'application/json';
            }
            
            const response = await fetch(url, {
                ...options,
                headers: headers
            });
            
            if (!response.ok) {
                const contentType = response.headers.get('content-type');
                let errorMessage = `${response.status} ${response.statusText}`;
                
                try {
                    // 在 apiRequest 函數中修改 JSON 解析部分
                    if (contentType && contentType.includes('application/json')) {
                        try {
                            return await response.json();
                        } catch (jsonError) {
                            // 如果 JSON 解析失敗，嘗試處理特殊情況
                            const text = await response.text();
                            
                            // 嘗試替換 NaN 值
                            const sanitizedText = text.replace(/:\s*NaN/g, ':null');
                            
                            try {
                                return JSON.parse(sanitizedText);
                            } catch (e) {
                                console.error('JSON 解析失敗:', text);
                                throw new Error('伺服器返回無效的 JSON 格式');
                            }
                        }
                    } else {
                        const text = await response.text();
                        if (text) {
                            errorMessage = `${response.status} ${response.statusText}: ${text}`;
                        }
                    }
                } catch (e) {
                    // 保持原始錯誤訊息
                }
                
                throw new Error(errorMessage);
            }
            
            // 檢查回應類型
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                // 如果不是 JSON，返回原始 response
                return response;
            }
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    },
    
    // 檔案上傳
    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        // 不要設定 Content-Type，讓瀏覽器自動設定
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
            // 移除 headers，讓瀏覽器自動處理
        });
        
        if (!response.ok) {
            let errorMessage = '檔案上傳失敗';
            try {
                const error = await response.json();
                errorMessage = error.error || errorMessage;
            } catch (e) {
                errorMessage = `${response.status} ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }
        
        return await response.json();
    },
    
    // 顯示通知
    showNotification(message, type = 'info') {
        // 建立通知元素
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${this.getNotificationIcon(type)}"></i>
            <span>${message}</span>
        `;
        
        // 添加到頁面
        document.body.appendChild(notification);
        
        // 顯示動畫
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
        
        // 自動移除
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 3000);
    },
    
    // 獲取通知圖標
    getNotificationIcon(type) {
        const icons = {
            'success': 'check-circle',
            'error': 'exclamation-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    },
    
    // 格式化檔案大小
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    // 格式化日期
    formatDate(date) {
        if (!date) return '';
        
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hour = String(d.getHours()).padStart(2, '0');
        const minute = String(d.getMinutes()).padStart(2, '0');
        
        return `${year}-${month}-${day} ${hour}:${minute}`;
    }
};

// 全域通知樣式
const notificationStyles = `
    <style>
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: white;
        padding: 16px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        display: flex;
        align-items: center;
        gap: 12px;
        transform: translateX(400px);
        transition: transform 0.3s ease;
        z-index: 10000;
        max-width: 400px;
    }
    
    .notification.show {
        transform: translateX(0);
    }
    
    .notification i {
        font-size: 1.25rem;
    }
    
    .notification-success {
        border-left: 4px solid #22C55E;
    }
    
    .notification-success i {
        color: #22C55E;
    }
    
    .notification-error {
        border-left: 4px solid #EF4444;
    }
    
    .notification-error i {
        color: #EF4444;
    }
    
    .notification-warning {
        border-left: 4px solid #F59E0B;
    }
    
    .notification-warning i {
        color: #F59E0B;
    }
    
    .notification-info {
        border-left: 4px solid #3B82F6;
    }
    
    .notification-info i {
        color: #3B82F6;
    }
    </style>
`;

// 注入通知樣式
document.head.insertAdjacentHTML('beforeend', notificationStyles);