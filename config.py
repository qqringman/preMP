"""
系統設定檔
"""

# SFTP 連線設定
SFTP_HOST = 'your.sftp.server.com'
SFTP_PORT = 22
SFTP_USERNAME = 'your_username'
SFTP_PASSWORD = 'your_password'
SFTP_TIMEOUT = 30  # 連線逾時時間（秒）

# 檔案設定
TARGET_FILES = ['F_Version.txt', 'manifest.xml', 'Version.txt']
CASE_INSENSITIVE = True  # 檔案名稱比對不區分大小寫

# 輸出設定
DEFAULT_OUTPUT_DIR = './downloads'
DEFAULT_COMPARE_DIR = './compare_results'
DEFAULT_ZIP_DIR = './zip_output'

# Excel 設定
FTP_PATH_COLUMN = 'ftp path'  # Excel 中 FTP 路徑的欄位名稱
MODULE_PATTERN = r'/(bootcode|emcu|[^/]+)/(RDDB-\d+)'  # 用於解析模組和 JIRA ID 的正則表達式

# 比較設定
MANIFEST_PRIMARY_KEYS = ['name', 'revision', 'upstream', 'dest-branch']  # manifest.xml 比較的主鍵

# 日誌設定
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'