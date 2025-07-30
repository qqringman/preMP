"""
系統設定檔
"""

# SFTP 連線設定
SFTP_HOST = 'mmsftpx.realtek.com'
SFTP_PORT = 22
SFTP_USERNAME = 'lgwar_user'
SFTP_PASSWORD = 'Ab!123456'
SFTP_TIMEOUT = 30  # 連線逾時時間（秒）

# 檔案設定
TARGET_FILES = ['F_Version.txt', 'manifest.xml', 'Version.txt']
CASE_INSENSITIVE = True  # 檔案名稱比對不區分大小寫
MAX_SEARCH_DEPTH = 3  # 遞迴搜尋的最大深度
SKIP_EXISTING_FILES = True  # 是否跳過已存在的檔案

# 輸出設定
DEFAULT_OUTPUT_DIR = './downloads'
DEFAULT_COMPARE_DIR = './compare_results'
DEFAULT_ZIP_DIR = './zip_output'

# Excel 設定
FTP_PATH_COLUMN = 'ftp path'  # Excel 中 FTP 路徑的欄位名稱

# 路徑解析規則
MODULE_PATTERN = r'/PrebuildFW/([^/]+)/(RDDB-\d+)'  # 標準格式：用於解析模組和 JIRA ID
# 正則表達式說明：
# - /PrebuildFW/ : 固定的路徑前綴
# - ([^/]+) : 匹配模組名稱（任何非斜線的字符，如 bootcode, emcu, dolby_ta, ufsd_ko 等）
# - (RDDB-\d+) : 匹配 JIRA ID（RDDB- 後接數字）

# 特殊格式也會自動處理：/DailyBuild/Merlin7/DB2302_... → Merlin7/DB2302

# 資料夾後綴規則（根據 FTP 路徑中的關鍵字）
# - premp.google-refplus → -premp
# - mp.google-refplus.wave → -wave  
# - mp.google-refplus.wave.backup → -wave.backup

# 比較設定
# manifest.xml 比較會檢查 revision 差異、動態分支檢查、新增/刪除的專案

# Gerrit URL 設定（用於產生連結，根據您的環境修改）
# 會自動根據 project name 中是否包含 'prebuilt' 或 'prebuild' 來選擇 URL
GERRIT_BASE_URL_PREBUILT = "https://mm2sd-git2.rtkbf.com/gerrit/plugins/gitiles/"
GERRIT_BASE_URL_NORMAL = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/"

# 日誌設定
LOG_LEVEL = 'INFO'  # 可選：DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'