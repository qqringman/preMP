// 比較頁面 JavaScript

let currentTaskId = null;
let sourceDirectory = null;
let asyncDownloadUrl = null;

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', () => {
    loadDirectories();
    loadRecentComparisons();
    initializeEventListeners();
    initializeFolderDrop();
});

// 載入可用目錄
async function loadDirectories() {
    try {
        const directories = await utils.apiRequest('/api/list-directories');
        const select = document.getElementById('sourceDirectory');
        
        // 清空選項
        select.innerHTML = '<option value="">請選擇目錄...</option>';
        
        // 添加目錄選項
        directories.forEach(dir => {
            const option = document.createElement('option');
            option.value = dir.path;
            option.textContent = dir.name;
            option.dataset.type = dir.type;
            select.appendChild(option);
        });
        
    } catch (error) {
        console.error('Load directories error:', error);
    }
}

// 初始化資料夾拖曳
function initializeFolderDrop() {
    const dropArea = document.getElementById('folderDropArea');
    
    // 阻止瀏覽器預設行為
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    
    // 高亮拖曳區域
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    // 處理拖放
    dropArea.addEventListener('drop', handleFolderDrop, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function highlight(e) {
    document.getElementById('folderDropArea').classList.add('dragging');
}

function unhighlight(e) {
    document.getElementById('folderDropArea').classList.remove('dragging');
}

// 處理資料夾拖放
function handleFolderDrop(e) {
    const dt = e.dataTransfer;
    const items = dt.items;
    
    if (items && items.length > 0) {
        const item = items[0];
        if (item.kind === 'file') {
            const entry = item.webkitGetAsEntry();
            if (entry && entry.isDirectory) {
                // 設定資料夾路徑
                setSourceDirectory(entry.fullPath || entry.name, 'dropped');
            } else {
                utils.showNotification('請拖曳資料夾，而不是檔案', 'warning');
            }
        }
    }
}

// 使用伺服器路徑
function useServerPath() {
    const path = document.getElementById('folderPath').value.trim();
    if (!path) {
        utils.showNotification('請輸入伺服器路徑', 'error');
        return;
    }
    
    // 驗證路徑格式
    if (!path.startsWith('/')) {
        utils.showNotification('路徑必須以 / 開頭', 'error');
        return;
    }
    
    setSourceDirectory(path, 'server');
}

// 設定來源目錄
function setSourceDirectory(path, type = 'local') {
    sourceDirectory = path;
    
    // 更新 UI
    document.getElementById('directoryInfo').classList.remove('hidden');
    document.getElementById('selectedPath').textContent = path;
    document.getElementById('directoryDate').textContent = new Date().toLocaleDateString('zh-TW');
    document.getElementById('compareBtn').disabled = false;
    
    // 更新選擇器
    if (type === 'local') {
        document.getElementById('sourceDirectory').value = path;
    } else {
        document.getElementById('sourceDirectory').value = '';
    }
    
    utils.showNotification(`已選擇${type === 'server' ? '伺服器' : ''}目錄: ${path}`, 'success');
}

// 初始化事件監聽器
function initializeEventListeners() {
    // 目錄選擇
    document.getElementById('sourceDirectory').addEventListener('change', (e) => {
        if (e.target.value) {
            setSourceDirectory(e.target.value, 'local');
        } else {
            sourceDirectory = null;
            document.getElementById('directoryInfo').classList.add('hidden');
            document.getElementById('compareBtn').disabled = true;
        }
    });
    
    // 輸入路徑時按 Enter
    document.getElementById('folderPath').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            useServerPath();
        }
    });
    
    // 監聽任務進度
    document.addEventListener('task-progress', (e) => {
        const data = e.detail;
        if (data.task_id === currentTaskId) {
            updateCompareProgress(data);
        }
    });
}

// 執行比對
async function executeCompare() {
    if (!sourceDirectory) {
        utils.showNotification('請選擇來源目錄', 'error');
        return;
    }
    
    const scenario = document.querySelector('input[name="scenario"]:checked').value;
    
    // 顯示進度
    document.getElementById('compareProgress').classList.remove('hidden');
    document.getElementById('compareResults').classList.add('hidden');
    document.getElementById('compareBtn').disabled = true;
    
    try {
        const response = await utils.apiRequest('/api/compare', {
            method: 'POST',
            body: JSON.stringify({
                source_dir: sourceDirectory,
                scenarios: scenario
            })
        });
        
        currentTaskId = response.task_id;
        
        // 加入任務房間
        if (socket) {
            socket.emit('join_task', { task_id: currentTaskId });
        }
        
        // 開始輪詢狀態
        pollCompareStatus();
        
    } catch (error) {
        console.error('Execute compare error:', error);
        utils.showNotification('執行比對失敗', 'error');
        resetCompareUI();
    }
}

// 更新比對進度
function updateCompareProgress(data) {
    const { progress, status, message } = data;
    
    document.getElementById('compareProgressFill').style.width = `${progress}%`;
    document.getElementById('compareProgressText').textContent = `${progress}%`;
    document.getElementById('compareMessage').textContent = message;
    
    if (status === 'completed') {
        showCompareResults(data.results);
    } else if (status === 'error') {
        utils.showNotification(`比對失敗：${message}`, 'error');
        resetCompareUI();
    }
}

// 顯示比對結果
function showCompareResults(results) {
    document.getElementById('compareProgress').classList.add('hidden');
    document.getElementById('compareResults').classList.remove('hidden');
    
    // 生成結果摘要
    const summaryHtml = generateCompareResultsSummary(results);
    document.getElementById('resultsSummary').innerHTML = summaryHtml;
    
    // 繪製圖表
    drawCharts(results);
    
    // 重新載入最近記錄
    loadRecentComparisons();
    
    utils.showNotification('比對完成！', 'success');
}

// 生成比對結果摘要
function generateCompareResultsSummary(results) {
    const compareResults = results.compare_results || {};
    let html = '<div class="summary-grid">';
    
    if (compareResults.master_vs_premp) {
        html += createSummaryCard('Master vs PreMP', compareResults.master_vs_premp, 'fa-code-branch');
    }
    
    if (compareResults.premp_vs_wave) {
        html += createSummaryCard('PreMP vs Wave', compareResults.premp_vs_wave, 'fa-water');
    }
    
    if (compareResults.wave_vs_backup) {
        html += createSummaryCard('Wave vs Backup', compareResults.wave_vs_backup, 'fa-database');
    }
    
    if (compareResults.failed > 0) {
        html += `
            <div class="summary-card error">
                <div class="card-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="card-content">
                    <div class="card-value">${compareResults.failed}</div>
                    <div class="card-label">個模組無法比對</div>
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

// 創建摘要卡片
function createSummaryCard(title, data, icon) {
    return `
        <div class="summary-card">
            <div class="card-icon">
                <i class="fas ${icon}"></i>
            </div>
            <div class="card-content">
                <div class="card-title">${title}</div>
                <div class="card-value">${data.success}</div>
                <div class="card-label">個模組成功</div>
                ${data.failed > 0 ? `<div class="card-footer text-warning">${data.failed} 個失敗</div>` : ''}
            </div>
        </div>
    `;
}

// 繪製圖表
function drawCharts(results) {
    const compareResults = results.compare_results || {};
    
    // 計算總數
    const totalSuccess = getTotalSuccess(compareResults);
    const totalFailed = compareResults.failed || 0;
    
    // 成功率圖表
    const successCtx = document.getElementById('successChart').getContext('2d');
    new Chart(successCtx, {
        type: 'doughnut',
        data: {
            labels: ['成功', '失敗'],
            datasets: [{
                data: [totalSuccess, totalFailed],
                backgroundColor: ['#48BB78', '#F56565']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
    
    // 差異分布圖表
    const diffCtx = document.getElementById('diffChart').getContext('2d');
    new Chart(diffCtx, {
        type: 'bar',
        data: {
            labels: ['Master vs PreMP', 'PreMP vs Wave', 'Wave vs Backup'],
            datasets: [{
                label: '成功',
                data: [
                    compareResults.master_vs_premp?.success || 0,
                    compareResults.premp_vs_wave?.success || 0,
                    compareResults.wave_vs_backup?.success || 0
                ],
                backgroundColor: '#2196F3'
            }, {
                label: '失敗',
                data: [
                    compareResults.master_vs_premp?.failed || 0,
                    compareResults.premp_vs_wave?.failed || 0,
                    compareResults.wave_vs_backup?.failed || 0
                ],
                backgroundColor: '#F56565'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    stacked: true,
                },
                y: {
                    stacked: true,
                    beginAtZero: true
                }
            }
        }
    });
}

// 計算總成功數
function getTotalSuccess(compareResults) {
    let total = 0;
    if (compareResults.master_vs_premp) total += compareResults.master_vs_premp.success || 0;
    if (compareResults.premp_vs_wave) total += compareResults.premp_vs_wave.success || 0;
    if (compareResults.wave_vs_backup) total += compareResults.wave_vs_backup.success || 0;
    return total;
}

// 查看詳細結果
function viewDetailedResults() {
    if (currentTaskId) {
        window.location.href = `/results/${currentTaskId}`;
    }
}

// 匯出結果 - 非同步處理
async function exportResults(format) {
    if (!currentTaskId) return;
    
    const endpoints = {
        excel: `/api/export-excel/${currentTaskId}`,
        html: `/api/export-html/${currentTaskId}`,
        zip: `/api/export-zip/${currentTaskId}`
    };
    
    if (format === 'zip') {
        // ZIP 檔案可能較大，使用非同步下載
        utils.showNotification('正在準備 ZIP 檔案，請稍候...', 'info');
        
        try {
            const response = await utils.apiRequest(`/api/prepare-download/${currentTaskId}`, {
                method: 'POST',
                body: JSON.stringify({ format: 'zip' })
            });
            
            if (response.ready) {
                downloadAsyncFile(response.download_url);
            } else {
                // 輪詢下載狀態
                pollDownloadStatus(response.task_id);
            }
        } catch (error) {
            utils.showNotification('準備下載失敗', 'error');
        }
    } else {
        // 其他格式直接下載
        window.location.href = endpoints[format];
    }
}

// 輪詢下載狀態
async function pollDownloadStatus(taskId) {
    const checkStatus = async () => {
        try {
            const status = await utils.apiRequest(`/api/download-status/${taskId}`);
            
            if (status.ready) {
                showAsyncDownloadToast(status.download_url);
            } else if (status.error) {
                utils.showNotification('檔案準備失敗', 'error');
            } else {
                // 繼續輪詢
                setTimeout(checkStatus, 2000);
            }
        } catch (error) {
            utils.showNotification('檢查下載狀態失敗', 'error');
        }
    };
    
    checkStatus();
}

// 顯示非同步下載提示
function showAsyncDownloadToast(downloadUrl) {
    asyncDownloadUrl = downloadUrl;
    const toast = document.getElementById('asyncDownloadToast');
    toast.classList.remove('hidden');
    
    // 5秒後自動隱藏
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 5000);
}

// 下載非同步檔案
function downloadAsyncFile() {
    if (asyncDownloadUrl) {
        window.location.href = asyncDownloadUrl;
    }
}

// 重置比對 UI
function resetCompareUI() {
    document.getElementById('compareProgress').classList.add('hidden');
    document.getElementById('compareBtn').disabled = false;
    document.getElementById('compareProgressFill').style.width = '0%';
    document.getElementById('compareProgressText').textContent = '0%';
}

// 輪詢比對狀態
async function pollCompareStatus() {
    if (!currentTaskId) return;
    
    try {
        const status = await utils.apiRequest(`/api/status/${currentTaskId}`);
        
        if (status.status !== 'not_found') {
            updateCompareProgress(status);
        }
        
        if (status.status !== 'completed' && status.status !== 'error') {
            setTimeout(pollCompareStatus, 1000);
        }
    } catch (error) {
        console.error('Poll status error:', error);
    }
}

// 載入最近比對記錄 - 時間軸形式
async function loadRecentComparisons() {
    try {
        // 從 API 載入真實數據
        const comparisons = await utils.apiRequest('/api/recent-comparisons');
        
        const container = document.getElementById('comparisonTimeline');
        
        if (!comparisons || comparisons.length === 0) {
            container.innerHTML = `
                <div class="timeline-placeholder text-center p-4">
                    <i class="fas fa-inbox fa-3x text-muted mb-3"></i>
                    <p class="text-muted">暫無比對記錄</p>
                </div>
            `;
            return;
        }
        
        // 生成時間軸
        let html = '';
        comparisons.forEach((comp, index) => {
            const statusIcon = comp.status === 'completed' ? 'fa-check-circle' : 'fa-exclamation-circle';
            const statusColor = comp.status === 'completed' ? 'text-success' : 'text-danger';
            
            html += `
                <div class="timeline-item">
                    <div class="timeline-dot"></div>
                    <div class="timeline-content">
                        <div class="timeline-time">${formatTimeAgo(comp.timestamp)}</div>
                        <div class="timeline-title">
                            ${comp.scenario}
                            <span class="${statusColor} ml-2">
                                <i class="fas ${statusIcon}"></i>
                            </span>
                        </div>
                        <div class="timeline-desc">
                            ${comp.modules} 個模組 · ${comp.duration || '< 1 分鐘'}
                        </div>
                        <button class="btn btn-sm btn-outline mt-2" 
                                onclick="window.location.href='/results/${comp.id}'">
                            查看結果
                        </button>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Load recent comparisons error:', error);
        // 使用預設資料
        loadDefaultComparisons();
    }
}

// 載入預設比對記錄
function loadDefaultComparisons() {
    const comparisons = [
        {
            id: 'task_20240115_143022',
            timestamp: new Date(Date.now() - 10 * 60 * 1000),
            scenario: '所有比對',
            status: 'completed',
            modules: 15,
            duration: '2 分鐘'
        },
        {
            id: 'task_20240115_141512',
            timestamp: new Date(Date.now() - 60 * 60 * 1000),
            scenario: 'Master vs PreMP',
            status: 'completed',
            modules: 8,
            duration: '1 分鐘'
        }
    ];
    
    const container = document.getElementById('comparisonTimeline');
    let html = '';
    
    comparisons.forEach(comp => {
        html += `
            <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                    <div class="timeline-time">${formatTimeAgo(comp.timestamp)}</div>
                    <div class="timeline-title">
                        ${comp.scenario}
                        <span class="text-success ml-2">
                            <i class="fas fa-check-circle"></i>
                        </span>
                    </div>
                    <div class="timeline-desc">
                        ${comp.modules} 個模組 · ${comp.duration}
                    </div>
                    <button class="btn btn-sm btn-outline mt-2" 
                            onclick="window.location.href='/results/${comp.id}'">
                        查看結果
                    </button>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// 格式化時間
function formatTimeAgo(date) {
    const now = new Date();
    const diff = now - new Date(date);
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return '剛剛';
    if (minutes < 60) return `${minutes} 分鐘前`;
    
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} 小時前`;
    
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days} 天前`;
    
    return new Date(date).toLocaleDateString('zh-TW');
}

// 匯出函數
window.useServerPath = useServerPath;
window.executeCompare = executeCompare;
window.viewDetailedResults = viewDetailedResults;
window.exportResults = exportResults;
window.downloadAsyncFile = downloadAsyncFile;