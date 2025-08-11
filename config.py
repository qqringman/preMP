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
GERRIT_SORUCE_URL = "https://mm2sd.rtkbf.com"
GERRIT_PREBUILT_URL = "https://mm2sd-git2.rtkbf.com"
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

# =====================================
# ===== 登入系統設定 =====
# =====================================

# 登入功能開關
ENABLE_LOGIN = True  # 是否啟用登入功能

# 登入模式設定
LOGIN_MODE = 'admin_only'  # 'global' = 全站登入, 'admin_only' = 僅後台登入

# 管理員帳號設定
ADMIN_USERS = {
    'admin': 'admin',
    'vince_lin': 'vince_lin'
}

# Session 設定
SECRET_KEY = 'your-secret-key-change-this-in-production'
SESSION_TIMEOUT = 3600  # Session 過期時間（秒）

# =====================================
# ===== Admin 後台管理設定 =====
# =====================================

# Chip Mapping 設定
DEFAULT_MAPPING_TABLE_PATH = '/home/vince_lin/ai/preMP/vp_lib/all_chip_mapping_table.xlsx'
USE_DEFAULT_MAPPING_TABLE = True  # 預設是否使用 server 上的檔案

# 預設輸出資料夾
DEFAULT_CHIP_OUTPUT_DIR = './output/chip_mapping'
DEFAULT_PREBUILD_OUTPUT_DIR = './output/prebuild_mapping'

# DB 版本設定
MAX_DB_VERSIONS = 5  # 最大顯示版本數，設為 'max' 則顯示全部

# =====================================
# ===== 動態篩選設定 =====
# =====================================

# Filter 類型預設選項
FILTER_TYPE_OPTIONS = [
    ('all', 'All'),
    ('master_vs_premp', 'Master vs PreMP'),
    ('premp_vs_mp', 'PreMP vs MP'),
    ('mp_vs_mpbackup', 'MP vs MP Backup')
]

# Chip Filter 預設選項（會從 mapping table 動態載入）
DEFAULT_CHIP_OPTIONS = [
    ('all', 'All Chips')
]

# DB 選擇預設選項（會從 mapping table 動態載入）
DEFAULT_DB_OPTIONS = [
    ('all', 'All')
]

# =====================================
# ===== JIRA/Gerrit 整合工具設定 =====
# =====================================

# JIRA 連線設定
JIRA_SITE = 'jira.realtek.com'
JIRA_USER = 'vince_lin'
JIRA_PASSWORD = ''
JIRA_TOKEN = ''

# Gerrit 連線設定
GERRIT_BASE = 'https://mm2sd.rtkbf.com/'
GERRIT_API_PREFIX = '/a'
GERRIT_USER = 'vince_lin'
GERRIT_PW = ''

# JIRA/Gerrit 工具設定
JIRA_BASE_URL = f'https://{JIRA_SITE}'
GERRIT_API_URL = f'{GERRIT_BASE.rstrip("/")}{GERRIT_API_PREFIX.rstrip("/")}'

# 預設 Gerrit manifest 連結模板
GERRIT_MANIFEST_BASE_URL = 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master'

# JIRA issue 連結模板
JIRA_ISSUE_URL_TEMPLATE = f'{JIRA_BASE_URL}/browse/{{issue_key}}'

# 環境變數設定函數
def setup_environment_variables():
    """設定系統環境變數"""
    import os
    
    # JIRA 環境變數
    os.environ['JIRA_SITE'] = JIRA_SITE
    os.environ['JIRA_USER'] = JIRA_USER
    os.environ['JIRA_PASSWORD'] = JIRA_PASSWORD
    os.environ['JIRA_TOKEN'] = JIRA_TOKEN
    
    # Gerrit 環境變數
    os.environ['GERRIT_BASE'] = GERRIT_BASE
    os.environ['GERRIT_API_PREFIX'] = GERRIT_API_PREFIX
    os.environ['GERRIT_USER'] = GERRIT_USER
    os.environ['GERRIT_PW'] = GERRIT_PW

# =====================================
# ===== Git Commit Message 設定 =====
# =====================================

# Commit Message 模板
COMMIT_MESSAGE_TEMPLATE = """[{rddb_number}][Manifest][Feat]: manifest update: {overwrite_type}
 
 * Problem: for google request
 * Root Cause: change branches every three months
 * Solution: manifest update: {overwrite_type}
 * Dependency: N
 * Testing Performed:
 - ac/dc on/off: ok
 * RD-CodeSync: Y
 * PL-CodeSync: N
 - Mac7p: N
 - Mac8q: N
 - Mac9q: N
 - Merlin5: N
 - Merlin7: N
 - Merlin8: N
 - Merlin8p: N
 - Merlin9: N
 - Dante: N
 - Dora: N
 - MatriX: N
 - Midas: N
 - AN11: N
 - AN12: N
 - AN14: N
 - AN16: N
 - R2U: N
 - Kernel_Only: N
 * Supplementary:
  
  * Issue:
  - {rddb_number}"""

# 預設 RDDB 號碼（可以在執行時覆蓋）
DEFAULT_RDDB_NUMBER = "RDDB-923"

# Commit Message 簡化版（用於快速提交）
COMMIT_MESSAGE_SIMPLE = """Auto-generated manifest update: {overwrite_type}

Generated by manifest conversion tool
Source: {source_file}
Target: {target_file}"""

# 選擇使用哪個模板
USE_DETAILED_COMMIT_MESSAGE = True  # True = 使用詳細模板, False = 使用簡單模板
# =====================================
# ===== Android 版本設定 =====
# =====================================

# 預設 Android 版本
DEFAULT_ANDROID_VERSION = '14'

# 支援的 Android 版本列表
SUPPORTED_ANDROID_VERSIONS = ['11', '12', '13', '14', '15']

# 版本對應的 upgrade 版本
ANDROID_UPGRADE_MAPPING = {
    '14': '11',  # Android 14 升級自 Android 11
    '15': '12'   # Android 15 升級自 Android 12
}

# =====================================
# ===== 晶片映射設定 =====
# =====================================

# 晶片到 RTD 型號的映射
CHIP_TO_RTD_MAPPING = {
    'mac7p': 'rtd2851a',
    'mac8q': 'rtd2851f',
    'mac9p': 'rtd2895p',
    'merlin7': 'rtd6748',
    'merlin8': 'rtd2885p',
    'merlin8p': 'rtd2885q',
    'merlin9': 'rtd2875q',
}

# RTD 型號到晶片的反向映射（自動生成）
RTD_TO_CHIP_MAPPING = {v: k for k, v in CHIP_TO_RTD_MAPPING.items()}

# =====================================
# ===== Kernel 版本設定 =====
# =====================================

# 支援的 Linux Kernel 版本
SUPPORTED_KERNEL_VERSIONS = ['4.14', '4.19', '5.4', '5.10', '5.15', '6.1']

# =====================================
# ===== Manifest 轉換映射規則 =====
# =====================================

# Master to PreMP 轉換規則（精確匹配）
MASTER_TO_PREMP_EXACT_MAPPING = {
    # 晶片特定的 master 分支轉換
    'realtek/mac7p/master': 'realtek/android-14/premp.google-refplus.rtd2851a',
    'realtek/mac8q/master': 'realtek/android-14/premp.google-refplus.rtd2851f',
    'realtek/mac9p/master': 'realtek/android-14/premp.google-refplus.rtd2895p',
    'realtek/merlin7/master': 'realtek/android-14/premp.google-refplus.rtd6748',
    'realtek/merlin8/master': 'realtek/android-14/premp.google-refplus.rtd2885p',
    'realtek/merlin8p/master': 'realtek/android-14/premp.google-refplus.rtd2885q',
    'realtek/merlin9/master': 'realtek/android-14/premp.google-refplus.rtd2875q',
    
    # 通用 master 分支
    'realtek/master': 'realtek/android-14/premp.google-refplus',
    'realtek/gaia': 'realtek/android-14/premp.google-refplus',
    'realtek/gki/master': 'realtek/android-14/premp.google-refplus',
    
    # Android 14 相關轉換
    'realtek/android-14/master': 'realtek/android-14/premp.google-refplus.upgrade-11',
    'realtek/android-14/mp.google-refplus': 'realtek/android-14/premp.google-refplus',
    
    # Kernel 版本轉換
    'realtek/linux-5.15/android-14/master': 'realtek/linux-5.15/android-14/premp.google-refplus',
    'realtek/linux-4.14/android-14/mp.google-refplus': 'realtek/linux-4.14/android-14/premp.google-refplus',
    
    # 特殊的保持不變的項目
    'master-kernel-build-2022': 'master-kernel-build-2022',
}

# Master to PreMP 模式匹配規則（用於動態匹配）
MASTER_TO_PREMP_PATTERN_RULES = [
    # Upgrade 版本轉換規則
    {
        'pattern': r'realtek/android-(\d+)/mp\.google-refplus\.upgrade-(\d+)\.?(rtd\w+)?',
        'replacement': r'realtek/android-\1/premp.google-refplus.upgrade-\2.\3',
        'description': 'Android upgrade 版本轉換（帶晶片型號）'
    },
    {
        'pattern': r'realtek/android-(\d+)/mp\.google-refplus\.upgrade-(\d+)$',
        'replacement': r'realtek/android-\1/premp.google-refplus.upgrade-\2',
        'description': 'Android upgrade 版本轉換（無晶片型號）'
    },
    
    # Kernel 版本轉換規則
    {
        'pattern': r'realtek/linux-([\d.]+)/android-(\d+)/mp\.google-refplus\.(rtd\w+)',
        'replacement': r'realtek/linux-\1/android-\2/premp.google-refplus.\3',
        'description': 'Linux kernel 版本轉換（帶晶片型號）'
    },
    
    # refs/tags 保持不變
    {
        'pattern': r'^refs/tags/.*',
        'replacement': None,  # None 表示保持原值
        'description': 'Git tags 保持不變'
    },
]

# PreMP to MP 轉換規則
PREMP_TO_MP_KEYWORD = 'premp.google-refplus'
MP_TO_MPBACKUP_KEYWORD = 'mp.google-refplus.wave'

# PreMP to MP 轉換目標
PREMP_TO_MP_TARGET = 'mp.google-refplus.wave'

# MP to MP Backup 轉換目標
MP_TO_MPBACKUP_TARGET = 'mp.google-refplus.wave.backup'

# =====================================
# ===== 轉換選項設定 =====
# =====================================

# 是否啟用智能匹配（當精確匹配失敗時）
ENABLE_SMART_MATCHING = True

# 是否記錄未匹配的 revision
LOG_UNMATCHED_REVISIONS = True

# 預設轉換行為（當沒有匹配規則時）
DEFAULT_CONVERSION_BEHAVIOR = 'use_default'  # 'use_default', 'keep_original', 'raise_error'

# 預設的 premp 分支（當無法匹配時使用）
DEFAULT_PREMP_BRANCH = 'realtek/android-{android_version}/premp.google-refplus'

# =====================================
# ===== 輔助函數 =====
# =====================================

def get_android_version_from_path(path: str) -> str:
    """從路徑中提取 Android 版本號"""
    import re
    match = re.search(r'android-(\d+)', path)
    if match:
        return match.group(1)
    return DEFAULT_ANDROID_VERSION

def get_chip_from_path(path: str) -> str:
    """從路徑中提取晶片名稱"""
    import re
    # 嘗試匹配晶片名稱
    for chip in CHIP_TO_RTD_MAPPING.keys():
        if f'/{chip}/' in path:
            return chip
    
    # 嘗試匹配 RTD 型號
    match = re.search(r'rtd(\w+)', path)
    if match:
        rtd_model = f'rtd{match.group(1)}'
        if rtd_model in RTD_TO_CHIP_MAPPING:
            return RTD_TO_CHIP_MAPPING[rtd_model]
    
    return None

def get_kernel_version_from_path(path: str) -> str:
    """從路徑中提取 Kernel 版本號"""
    import re
    match = re.search(r'linux-([\d.]+)', path)
    if match:
        return match.group(1)
    return None