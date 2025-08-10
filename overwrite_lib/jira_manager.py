"""
JIRA API 管理模組
處理所有 JIRA 相關的 API 操作
"""
import os
import requests
import re
from typing import Optional, Dict, Any
from gerrit_manager import GerritManager
import utils
import sys

# 加入上一層目錄到路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 載入設定
try:
    import config
    utils.setup_config()  # 設定環境變數
except ImportError:
    print("警告：無法載入 config 模組，使用預設設定")
    config = None

logger = utils.setup_logger(__name__)

class JiraManager:
    """JIRA API 管理類別"""
    
    def __init__(self):
        self.logger = logger
        
        # 優先使用 config 模組的設定，其次使用環境變數
        if config:
            self.site = getattr(config, 'JIRA_SITE', 'jira.realtek.com')
            self.user = getattr(config, 'JIRA_USER', 'vince_lin')
            self.password = getattr(config, 'JIRA_PASSWORD', 'Amon100!')
            self.token = getattr(config, 'JIRA_TOKEN', '')
        else:
            # 回退到環境變數
            self.site = os.getenv("JIRA_SITE", "jira.realtek.com").strip()
            self.user = os.getenv("JIRA_USER", "vince_lin").strip()
            self.password = os.getenv("JIRA_PASSWORD", "Amon100!").strip()
            self.token = os.getenv("JIRA_TOKEN", "").strip()
        
        # 設定認證方式：優先使用 Bearer Token
        if self.token:
            self.auth = None  # 不使用基本認證
            self.headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}"
            }
        elif self.user and self.password:
            self.auth = (self.user, self.password)
            self.headers = {"Accept": "application/json"}
        else:
            raise RuntimeError("JIRA 必須設定 TOKEN 或同時設定 USER/PASSWORD")
        
        self.base_url = f"https://{self.site}"
        
        self.logger.info(f"JIRA Manager 初始化完成 - Site: {self.site}")
        self.logger.info(f"認證方式: {'Bearer Token' if self.token else '基本認證'}")
    
    def _make_request(self, url: str, method: str = 'GET', **kwargs) -> requests.Response:
        """統一的請求方法，自動處理認證"""
        # 合併 headers
        headers = kwargs.get('headers', {})
        headers.update(self.headers)
        kwargs['headers'] = headers
        
        # 設定認證
        if not self.token and self.auth:
            kwargs['auth'] = self.auth
        
        # 根據方法執行請求
        method = method.upper()
        if method == 'GET':
            return requests.get(url, **kwargs)
        elif method == 'POST':
            return requests.post(url, **kwargs)
        elif method == 'PUT':
            return requests.put(url, **kwargs)
        elif method == 'HEAD':
            return requests.head(url, **kwargs)
        else:
            raise ValueError(f"不支援的 HTTP 方法: {method}")
    
    def get_issue_description(self, issue_key: str) -> Optional[str]:
        """
        取得 JIRA issue 的 description
        
        Args:
            issue_key: JIRA issue key (ex: MMQCDB-2302)
            
        Returns:
            description 內容，失敗則返回 None
        """
        try:
            url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
            
            response = self._make_request(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                description = data.get('fields', {}).get('description', '')
                self.logger.info(f"成功取得 {issue_key} 的 description")
                return description
            elif response.status_code == 403:
                self.logger.warning(f"權限被拒絕 - HTTP 403: {issue_key}")
                return None
            elif response.status_code == 401:
                self.logger.warning(f"認證失敗 - HTTP 401: {issue_key}")
                return None
            elif response.status_code == 404:
                self.logger.warning(f"Issue 不存在 - HTTP 404: {issue_key}")
                return None
            else:
                self.logger.warning(f"無法取得 {issue_key} 的資訊 - HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"取得 JIRA issue {issue_key} 失敗: {str(e)}")
            return None
    
    def test_connection(self) -> Dict[str, Any]:
        """測試 JIRA 連線和認證"""
        result = {
            'success': False,
            'message': '',
            'details': {},
            'auth_methods_tested': []
        }
        
        try:
            # 1. 測試基本連線
            self.logger.info("測試 JIRA 基本連線...")
            base_url = f"{self.base_url}/rest/api/2/serverInfo"
            
            try:
                response = self._make_request(base_url, timeout=10)
                self.logger.info(f"JIRA serverInfo 回應: HTTP {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        server_info = response.json()
                        result['details']['server_version'] = server_info.get('version', 'Unknown')
                        self.logger.info(f"JIRA 伺服器版本: {server_info.get('version', 'Unknown')}")
                    except ValueError as e:
                        self.logger.warning(f"JSON 解析失敗: {str(e)}")
                        result['details']['server_version'] = 'Unknown (JSON parse error)'
                else:
                    result['message'] = f"無法連接到 JIRA 伺服器 - HTTP {response.status_code}"
                    return result
            except Exception as e:
                result['message'] = f"網路連線失敗: {str(e)}"
                return result
            
            # 2. 測試認證 - 使用 myself API
            self.logger.info("測試認證...")
            auth_url = f"{self.base_url}/rest/api/2/myself"
            
            try:
                response = self._make_request(auth_url, timeout=30)
                auth_method = 'Bearer Token' if self.token else '基本認證'
                result['auth_methods_tested'].append(f"{auth_method} (HTTP {response.status_code})")
                
                if response.status_code == 200:
                    try:
                        user_info = response.json()
                        result['success'] = True
                        result['message'] = f"JIRA 連線測試成功 ({auth_method})"
                        result['details']['user_name'] = user_info.get('name', 'Unknown')
                        result['details']['display_name'] = user_info.get('displayName', 'Unknown')
                        result['details']['email'] = user_info.get('emailAddress', 'Unknown')
                        self.logger.info(f"認證成功 - 用戶: {user_info.get('displayName', 'Unknown')}")
                        return result
                    except ValueError as e:
                        self.logger.warning(f"用戶資訊 JSON 解析失敗: {str(e)}")
                        result['message'] = f"認證成功但 JSON 解析失敗: {str(e)}"
                        return result
                elif response.status_code == 401:
                    result['message'] = "認證失敗 - 請檢查 Token 或帳號密碼"
                elif response.status_code == 403:
                    result['message'] = "權限不足 - 請檢查帳號權限或 Token 權限"
                else:
                    result['message'] = f"認證失敗 - HTTP {response.status_code}"
                    
            except Exception as e:
                result['message'] = f"認證測試過程發生錯誤: {str(e)}"
            
            return result
            
        except Exception as e:
            result['message'] = f"連線測試過程發生錯誤: {str(e)}"
            self.logger.error(result['message'])
            return result
    
    def diagnose_jira_connection(self) -> Dict[str, Any]:
        """詳細診斷 JIRA 連線問題"""
        result = {
            'tests': [],
            'suggestions': []
        }
        
        try:
            # 1. 測試 JIRA 首頁
            self.logger.info("測試 JIRA 首頁...")
            response = self._make_request(self.base_url, timeout=10)
            result['tests'].append({
                'name': 'JIRA 首頁',
                'url': self.base_url,
                'status': response.status_code,
                'content_type': response.headers.get('content-type', 'Unknown'),
                'content_preview': response.text[:200] if response.text else 'Empty'
            })
            
            # 2. 測試 REST API 根路徑
            api_root = f"{self.base_url}/rest/api/2/"
            self.logger.info("測試 REST API 根路徑...")
            response = self._make_request(api_root, timeout=10)
            result['tests'].append({
                'name': 'REST API 根路徑',
                'url': api_root,
                'status': response.status_code,
                'content_type': response.headers.get('content-type', 'Unknown'),
                'content_preview': response.text[:200] if response.text else 'Empty'
            })
            
            # 3. 測試認證端點
            auth_url = f"{self.base_url}/rest/api/2/myself"
            self.logger.info("測試認證端點...")
            response = self._make_request(auth_url, timeout=10)
            result['tests'].append({
                'name': '認證端點 (myself)',
                'url': auth_url,
                'status': response.status_code,
                'content_type': response.headers.get('content-type', 'Unknown'),
                'content_preview': response.text[:200] if response.text else 'Empty'
            })
            
            # 4. 嘗試不同的 serverInfo 路徑
            serverinfo_urls = [
                f"{self.base_url}/rest/api/2/serverInfo",
                f"{self.base_url}/rest/api/latest/serverInfo",
                f"{self.base_url}/rest/api/serverInfo"
            ]
            
            for url in serverinfo_urls:
                self.logger.info(f"測試 serverInfo: {url}")
                response = self._make_request(url, timeout=10)
                result['tests'].append({
                    'name': f'ServerInfo ({url.split("/")[-1]})',
                    'url': url,
                    'status': response.status_code,
                    'content_type': response.headers.get('content-type', 'Unknown'),
                    'content_preview': response.text[:200] if response.text else 'Empty'
                })
            
            # 分析結果並提供建議
            for test in result['tests']:
                if test['status'] == 403:
                    if 'html' in test.get('content_type', '').lower():
                        result['suggestions'].append(f"❌ {test['name']}: 回傳 HTML 而非 JSON，可能是登入頁面")
                    else:
                        result['suggestions'].append(f"❌ {test['name']}: 403 權限錯誤")
                elif test['status'] == 401:
                    result['suggestions'].append(f"❌ {test['name']}: 401 認證失敗")
                elif test['status'] == 200:
                    if 'json' in test.get('content_type', '').lower():
                        result['suggestions'].append(f"✅ {test['name']}: 正常")
                    else:
                        result['suggestions'].append(f"⚠️ {test['name']}: 狀態正常但非 JSON 回應")
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            return result
    
    def extract_repo_init_command(self, description: str) -> Optional[str]:
        """
        從 description 中提取 repo init 指令
        
        Args:
            description: JIRA description 內容
            
        Returns:
            repo init 指令，找不到則返回 None
        """
        if not description:
            return None
        
        try:
            # 尋找包含 repo init 和 -m 的指令
            pattern = r'repo\s+init\s+.*?-m\s+[\w\-\.]+\.xml'
            matches = re.findall(pattern, description, re.IGNORECASE | re.MULTILINE)
            
            if matches:
                # 返回第一個匹配的指令
                command = matches[0].strip()
                self.logger.info(f"找到 repo init 指令: {command}")
                return command
            else:
                self.logger.warning("在 description 中找不到 repo init 指令")
                return None
                
        except Exception as e:
            self.logger.error(f"解析 repo init 指令失敗: {str(e)}")
            return None
    
    def parse_repo_command(self, repo_command: str) -> Dict[str, str]:
        """
        解析 repo init 指令的參數
        
        Args:
            repo_command: repo init 指令
            
        Returns:
            包含 url, branch, manifest 的字典
        """
        result = {
            'url': '',
            'branch': '',
            'manifest': ''
        }
        
        try:
            # 解析 -u 參數 (URL)
            url_match = re.search(r'-u\s+([^\s]+)', repo_command)
            if url_match:
                result['url'] = url_match.group(1)
            
            # 解析 -b 參數 (branch)
            branch_match = re.search(r'-b\s+([^\s]+)', repo_command)
            if branch_match:
                result['branch'] = branch_match.group(1)
            
            # 解析 -m 參數 (manifest)
            manifest_match = re.search(r'-m\s+([^\s]+)', repo_command)
            if manifest_match:
                result['manifest'] = manifest_match.group(1)
            
            self.logger.info(f"解析結果: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"解析 repo 指令失敗: {str(e)}")
            return result
    
    def create_jira_link(self, db_info: str) -> str:
        """
        根據 DB 資訊建立 JIRA 連結
        
        Args:
            db_info: DB 資訊 (ex: DB2302)
            
        Returns:
            JIRA 連結
        """
        if not db_info:
            return ""
        
        # 轉換格式：DB2302 -> DB-2302
        if db_info.startswith('DB') and len(db_info) > 2:
            formatted_key = f"MMQC{db_info[:2]}-{db_info[2:]}"
            jira_link = f"https://{self.site}/browse/{formatted_key}"
            self.logger.info(f"建立 JIRA 連結: {db_info} -> {jira_link}")
            return jira_link
        else:
            self.logger.warning(f"無效的 DB 格式: {db_info}")
            return ""
    
    def get_issue_info_from_db(self, db_info: str) -> Dict[str, str]:
        """
        根據 DB 資訊取得完整的 JIRA 資訊
        
        Args:
            db_info: DB 資訊 (ex: DB2302)
            
        Returns:
            包含 jira_link, source, manifest, source_link 的字典
        """
        result = {
            'jira_link': '',
            'source': '',
            'manifest': '',
            'source_link': ''
        }
        
        try:
            # 建立 JIRA 連結
            jira_link = self.create_jira_link(db_info)
            result['jira_link'] = jira_link
            
            if not jira_link:
                return result
            
            # 從 JIRA 連結提取 issue key
            issue_key = jira_link.split('/')[-1]
            
            # 取得 description
            description = self.get_issue_description(issue_key)
            if not description:
                return result
            
            # 提取 repo init 指令
            repo_command = self.extract_repo_init_command(description)
            if not repo_command:
                return result
            
            result['source'] = repo_command
            
            # 解析指令參數
            parsed = self.parse_repo_command(repo_command)
            result['manifest'] = parsed['manifest']
            
            # 建立 source_link (使用 gerrit_manager)
            if parsed['url'] and parsed['branch'] and parsed['manifest']:
                gerrit = GerritManager()
                result['source_link'] = gerrit.build_manifest_link(
                    parsed['url'], parsed['branch'], parsed['manifest']
                )
            
            return result
            
        except Exception as e:
            self.logger.error(f"取得 {db_info} 的 JIRA 資訊失敗: {str(e)}")
            return result