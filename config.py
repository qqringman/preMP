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
FTP_PATH_COLUMN_ALTERNATIVE = 'SftpURL'  # Excel 中 FTP 路徑的備用欄位名稱
FTP_PATH_COLUMNS = ['ftp path', 'SftpURL']  # 可能的 FTP 路徑欄位名稱列表

# 路徑替換規則
PATH_REPLACEMENTS = {
    '/mnt/cq488': '/DailyBuild'  # 將 /mnt/cq488 替換成 /DailyBuild
}

# 伺服器瀏覽預設路徑
DEFAULT_SERVER_PATH = '/home/vince_lin/ai/preMP'  # 預設的伺服器瀏覽路徑

# 常用路徑建議（用於自動補全）
COMMON_PATHS = [
    '/home/vince_lin/ai/preMP',
    '/home/vince_lin/ai/R306_ShareFolder',
    '/home/vince_lin/ai/R306_ShareFolder/nightrun_log',
    '/home/vince_lin/ai/R306_ShareFolder/nightrun_log/Demo_stress_Test_log',
    '/home/vince_lin/ai/DailyBuild',
    '/home/vince_lin/ai/DailyBuild/Merlin7',
    '/home/vince_lin/ai/PrebuildFW'
]

# 路徑解析規則
MODULE_PATTERN = r'/PrebuildFW/([^/]+)/(RDDB-\d+)'  # RDDB 格式
DB_PATTERN = r'/DailyBuild/([^/]+)/(DB\d+)_'  # DB 格式

# 檔案格式設定
RDDB_TARGET_FILES = ['F_Version.txt', 'manifest.xml', 'Version.txt']
DB_TARGET_FILES = ['manifest_{version}.xml', 'Version_{version}.txt']  # {version} 會被替換

# 資料夾後綴規則（根據 FTP 路徑中的關鍵字）
# - premp.google-refplus → -premp
# - mp.google-refplus.wave → -wave  
# - mp.google-refplus.wave.backup → -wave.backup

# 比較設定
# manifest.xml 比較會檢查 revision 差異、動態分支檢查、新增/刪除的專案

# Gerrit URL 設定（用於產生連結，根據您的環境修改）
GERRIT_BASE_URL_PREBUILT = "https://mm2sd-git2.rtkbf.com/gerrit/plugins/gitiles/"
GERRIT_BASE_URL_NORMAL = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/"

# 日誌設定
LOG_LEVEL = 'INFO'  # 可選：DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# ======================================
# ===== gen_mapping_excel 相關設定 =====
# ======================================

# 輸入檔案設定
ALL_CHIP_MAPPING_TABLE = 'all_chip_mapping_table.xlsx'  # 預設的 mapping table 檔案名稱

# 輸出檔案設定
DEFAULT_DAILYBUILD_OUTPUT = 'DailyBuild_mapping.xlsx'  # 功能1預設輸出檔名
DEFAULT_PREBUILD_OUTPUT = 'PrebuildFW_mapping.xlsx'    # 功能2預設輸出檔名

# DB Type 對應關係
DB_TYPE_PAIRS = [
    ('master', 'premp'),
    ('premp', 'mp'),
    ('mp', 'mpbackup')
]

# 預設參數
DEFAULT_DB_FILTER = 'all'  # 預設抓取所有 DB
DEFAULT_FILTER = 'all'     # 預設處理所有資料

# SFTP 版本排序設定
VERSION_SORT_REVERSE = True  # True = 最新版本優先
