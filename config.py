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
# SFTP 連線設定
# =====================================
SFTP_HOST = 'mmsftpx.realtek.com'
SFTP_PORT = 22
SFTP_USERNAME = 'lgwar_user'
SFTP_PASSWORD = 'Ab!123456'
SFTP_TIMEOUT = 30  # 連線逾時時間（秒）

# =====================================
# 檔案設定
# =====================================
TARGET_FILES = ['F_Version.txt', 'manifest.xml', 'Version.txt']
CASE_INSENSITIVE = True  # 檔案名稱比對不區分大小寫
MAX_SEARCH_DEPTH = 3  # 遞迴搜尋的最大深度
SKIP_EXISTING_FILES = True  # 是否跳過已存在的檔案

# =====================================
# 輸出設定
# =====================================
DEFAULT_OUTPUT_DIR = './downloads'
DEFAULT_COMPARE_DIR = './compare_results'
DEFAULT_ZIP_DIR = './zip_output'

# =====================================
# Excel 設定
# =====================================
FTP_PATH_COLUMN = 'ftp path'  # Excel 中 FTP 路徑的欄位名稱
FTP_PATH_COLUMN_ALTERNATIVE = 'SftpURL'  # Excel 中 FTP 路徑的備用欄位名稱
FTP_PATH_COLUMNS = ['ftp path', 'SftpURL', 'SftpPath', 'compare_SftpPath']  # 可能的 FTP 路徑欄位名稱列表

# =====================================
# 路徑替換規則
# =====================================
PATH_REPLACEMENTS = {
    '/mnt/cq488': '/DailyBuild'  # 將 /mnt/cq488 替換成 /DailyBuild
}

# =====================================
# 伺服器瀏覽預設路徑
# =====================================
DEFAULT_SERVER_PATH = '/home/vince_lin/ai/preMP'  # 預設的伺服器瀏覽路徑

# =====================================
# 常用路徑建議（用於自動補全）
# =====================================
COMMON_PATHS = [
    '/home/vince_lin/ai/preMP',
    '/home/vince_lin/ai/R306_ShareFolder',
    '/home/vince_lin/ai/R306_ShareFolder/nightrun_log',
    '/home/vince_lin/ai/R306_ShareFolder/nightrun_log/Demo_stress_Test_log',
    '/home/vince_lin/ai/DailyBuild',
    '/home/vince_lin/ai/DailyBuild/Merlin7',
    '/home/vince_lin/ai/PrebuildFW'
]

# =====================================
# 路徑解析規則
# =====================================
MODULE_PATTERN = r'/PrebuildFW/([^/]+)/(RDDB-\d+)'  # RDDB 格式
DB_PATTERN = r'/DailyBuild/([^/]+)/(DB\d+)_'  # DB 格式

# =====================================
# 檔案格式設定
# =====================================
RDDB_TARGET_FILES = ['F_Version.txt', 'manifest.xml', 'Version.txt']
DB_TARGET_FILES = ['manifest_{version}.xml', 'Version_{version}.txt']  # {version} 會被替換

# 資料夾後綴規則（根據 FTP 路徑中的關鍵字）
# - premp.google-refplus → -premp
# - mp.google-refplus.wave → -wave  
# - mp.google-refplus.wave.backup → -wave.backup

# 比較設定
# manifest.xml 比較會檢查 revision 差異、動態分支檢查、新增/刪除的專案

# =====================================
# Gerrit URL 設定（用於產生連結，根據您的環境修改）
# =====================================
GERRIT_SORUCE_URL = "https://mm2sd.rtkbf.com"
GERRIT_PREBUILT_URL = "https://mm2sd-git2.rtkbf.com"
GERRIT_BASE_URL_PREBUILT = "https://mm2sd-git2.rtkbf.com/gerrit/plugins/gitiles/"
GERRIT_BASE_URL_NORMAL = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/"

# =====================================
# 日誌設定
# =====================================
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

# 🔥 新增：當前 Android 版本（用於動態替換硬編碼的 android-14）
CURRENT_ANDROID_VERSION = '14'

# 🆕 新增：當前 Android 前一版本升級號（用於 upgrade 分支）
CURRENT_ANDROID_PREV_VERSION = '11'

# =====================================
# ===== 動態 Android 版本輔助函數 =====
# =====================================

def get_current_android_version() -> str:
    """取得當前使用的 Android 版本"""
    return CURRENT_ANDROID_VERSION

def get_current_android_prev_version() -> str:
    """取得當前 Android 前一版本升級號"""
    return CURRENT_ANDROID_PREV_VERSION

def get_premp_branch_with_version_upgrade(version: str, chip_rtd: str = None) -> str:
    """取得帶版本升級的 premp 分支"""
    upgrade_ver = get_current_android_prev_version()
    if chip_rtd:
        return f'realtek/{version}/premp.google-refplus.upgrade-{upgrade_ver}.{chip_rtd}'
    else:
        return f'realtek/{version}/premp.google-refplus.upgrade-{upgrade_ver}'
    
def get_android_path(template: str) -> str:
    """
    將模板中的 {android_version} 替換為當前版本
    
    Args:
        template: 包含 {android_version} 的模板字符串
        
    Returns:
        替換後的字符串
        
    Example:
        get_android_path('realtek/android-{android_version}/premp.google-refplus')
        -> 'realtek/android-14/premp.google-refplus'
    """
    return template.format(android_version=CURRENT_ANDROID_VERSION)

def get_default_premp_branch() -> str:
    """取得預設的 premp 分支"""
    return f'realtek/android-{CURRENT_ANDROID_VERSION}/premp.google-refplus'

def get_default_android_master_branch() -> str:
    """取得預設的 Android master 分支"""
    return f'realtek/android-{CURRENT_ANDROID_VERSION}/master'

# 🆕 新增輔助函數
def get_premp_branch_with_chip(chip_rtd: str) -> str:
    """取得帶晶片型號的 premp 分支"""
    return f'realtek/android-{CURRENT_ANDROID_VERSION}/premp.google-refplus.{chip_rtd}'

def get_premp_branch_with_upgrade(upgrade_version: str, chip_rtd: str = None) -> str:
    """取得帶 upgrade 版本的 premp 分支"""
    if chip_rtd:
        return f'realtek/android-{CURRENT_ANDROID_VERSION}/premp.google-refplus.upgrade-{upgrade_version}.{chip_rtd}'
    else:
        return f'realtek/android-{CURRENT_ANDROID_VERSION}/premp.google-refplus.upgrade-{upgrade_version}'

def get_linux_android_path(linux_version: str, template: str) -> str:
    """
    取得 Linux + Android 的動態路徑
    
    Args:
        linux_version: Linux 版本 (如 '5.15')
        template: 路徑模板
        
    Returns:
        完整路徑
        
    Example:
        get_linux_android_path('5.15', 'realtek/linux-{linux_ver}/android-{android_version}/premp.google-refplus')
        -> 'realtek/linux-5.15/android-14/premp.google-refplus'
    """
    return template.format(linux_ver=linux_version, android_version=CURRENT_ANDROID_VERSION)

# =====================================
# ===== Gerrit URL 動態生成函數 =====
# =====================================

def get_gerrit_manifest_base_path() -> str:
    """取得 Gerrit manifest 的基礎路徑"""
    return f'realtek/android-{CURRENT_ANDROID_VERSION}/master'

def get_gerrit_manifest_url(filename: str) -> str:
    """
    生成 Gerrit manifest 檔案的完整 URL
    
    Args:
        filename: manifest 檔案名 (如 'atv-google-refplus.xml')
        
    Returns:
        完整的 Gerrit URL
    """
    base_path = get_gerrit_manifest_base_path()
    return f'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/{base_path}/{filename}'

def get_repo_manifest_url() -> str:
    """取得 repo manifest 的 SSH URL"""
    return "ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest"

def get_repo_branch() -> str:
    """取得 repo 分支名稱"""
    return get_gerrit_manifest_base_path()

# 預定義常用的 manifest 檔案 URL
def get_master_manifest_url() -> str:
    """取得 Master manifest URL"""
    return get_gerrit_manifest_url('atv-google-refplus.xml')

def get_premp_manifest_url() -> str:
    """取得 PreMP manifest URL"""
    return get_gerrit_manifest_url('atv-google-refplus-premp.xml')

def get_mp_manifest_url() -> str:
    """取得 MP manifest URL"""
    return get_gerrit_manifest_url('atv-google-refplus-wave.xml')

def get_mp_backup_manifest_url() -> str:
    """取得 MP Backup manifest URL"""
    return get_gerrit_manifest_url('atv-google-refplus-wave-backup.xml')

# =====================================
# ===== 專案轉換跳過設定 =====
# =====================================

# Feature Two (建立分支映射表) 跳過專案設定
FEATURE_TWO_SKIP_PROJECTS = {
    # 🔥 原始功能的處理類型
    'master_vs_premp': [
        '.*tvconfigs_prebuilt'
    ],
    
    'premp_vs_mp': [
        '.*tvconfigs_prebuilt'
    ],
    
    'mp_vs_mpbackup': [
        '.*tvconfigs_prebuilt'
    ],
    
    # 🔥 tvconfig 功能的處理類型
    'master_to_premp': [
        '.*tvconfigs_prebuilt'
    ],
    
    'master_to_mp': [
        '.*tvconfigs_prebuilt'
    ],
    
    'master_to_mpbackup': [
        '.*tvconfigs_prebuilt'
    ]
}

# 跳過建立分支的模式列表 (不去建立 branch)
SKIP_BRANCH_CREATION_PATTERNS = [
    'google/u-tv-keystone-rtk-refplus'  # 包含此字串就跳過
]

# Feature Three (Manifest 轉換工具) 跳過專案設定
FEATURE_THREE_SKIP_PROJECTS = {
    'master_to_premp': [
        '.*tvconfigs_prebuilt'
    ],
    
    'premp_to_mp': [
        '.*tvconfigs_prebuilt'
    ],
    
    'mp_to_mpbackup': [
        '.*tvconfigs_prebuilt'
    ]
}

# Tvconfig 轉換跳過專案設定
# 🔥 注意：tvconfig 只使用 master_to_* 類型，所以從 FEATURE_TWO_SKIP_PROJECTS 中提取對應部分
TVCONFIG_SKIP_PROJECTS = {
    'master_to_premp': FEATURE_TWO_SKIP_PROJECTS['master_to_premp'],
    'master_to_mp': FEATURE_TWO_SKIP_PROJECTS['master_to_mp'],
    'master_to_mpbackup': FEATURE_TWO_SKIP_PROJECTS['master_to_mpbackup']
}

# =====================================
# ===== 自定義專案轉換規則設定 =====
# =====================================

FEATURE_TWO_CUSTOM_CONVERSIONS = {
    'master_vs_premp': {
    },
    
    'premp_vs_mp': {
    },
    
    'mp_vs_mpbackup': {
    },
    
    # tvconfig 功能的處理類型
    'master_to_premp': {
    },
    
    'master_to_mp': {
    },
    
    'master_to_mpbackup': {
        # 🆕 支援陣列格式：同一個 name pattern 可以有多個不同的 path 條件
        # '.*tvconfigs_prebuilt': [
        #     {
        #         'path_pattern': '.*refplus2.*',
        #         'target': 'realtek/android-14/mp.google-refplus.wave.backup.upgrade-11'
        #     },            
        #     {
        #         'path_pattern': '.*refplus3.*',
        #         'target': 'realtek/android-14/mp.google-refplus.wave.backup.upgrade-11'
        #     },
        #     {
        #         'path_pattern': '.*refplus5.*',
        #         'target': 'realtek/android-14/mp.google-refplus.wave.backup'
        #     }
        # ],

        # 🆕 仍然支援簡單格式
        # '.*tvconfigs_prebuilt': 'realtek/android-14/mp.google-refplus.wave.backup',
        
        # 🆕 也支援單一物件格式
        # '.*another_pattern': {
        #    'target': 'some_target',
        #    'path_pattern': '.*some_path.*'
        # }
    }
}

FEATURE_THREE_CUSTOM_CONVERSIONS = {
    'master_to_premp': {
    },
    
    'premp_to_mp': {
    },
    
    'mp_to_mpbackup': {
        # 🆕 支援陣列格式：同一個 name pattern 可以有多個不同的 path 條件
        # '.*tvconfigs_prebuilt': [
        #     {
        #         'path_pattern': '.*refplus2.*',
        #         'target': 'realtek/android-14/mp.google-refplus.wave.backup.upgrade-11'
        #     },            
        #     {
        #         'path_pattern': '.*refplus3.*',
        #         'target': 'realtek/android-14/mp.google-refplus.wave.backup.upgrade-11'
        #     },
        #     {
        #         'path_pattern': '.*refplus5.*',
        #         'target': 'realtek/android-14/mp.google-refplus.wave.backup'
        #     }
        # ],
        
        # 🆕 仍然支援簡單格式
        # '.*tvconfigs_prebuilt': 'realtek/android-14/mp.google-refplus.wave.backup',
        
        # 🆕 也支援單一物件格式
        # '.*another_pattern': {
        #    'target': 'some_target',
        #    'path_pattern': '.*some_path.*'
        # }
    }
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
    'matrix': 'rtd2811'
}