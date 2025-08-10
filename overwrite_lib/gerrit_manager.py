"""
Gerrit API 管理模組 - 修復版（使用正確的下載方法）
主要修復：優先使用 API 風格 URL 進行檔案下載
"""
import os
import requests
import re
import base64
import urllib.parse
from typing import Optional, Dict, Any, List
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

class GerritManager:
    """Gerrit API 管理類別 - 修復版（使用正確的下載方法）"""
    
    def __init__(self):
        self.logger = logger
        
        # 優先使用 config 模組的設定，其次使用環境變數
        if config:
            self.base_url = getattr(config, 'GERRIT_BASE', 'https://mm2sd.rtkbf.com/').rstrip('/')
            self.api_prefix = getattr(config, 'GERRIT_API_PREFIX', '/a').rstrip('/')
            self.user = getattr(config, 'GERRIT_USER', '')
            self.password = getattr(config, 'GERRIT_PW', '')
        else:
            # 回退到環境變數
            self.base_url = os.environ.get('GERRIT_BASE', 'https://mm2sd.rtkbf.com/').rstrip('/')
            self.api_prefix = os.environ.get('GERRIT_API_PREFIX', '/a').rstrip('/')
            self.user = os.environ.get('GERRIT_USER', '')
            self.password = os.environ.get('GERRIT_PW', '')
        
        # 設定認證
        self.auth = (self.user, self.password) if self.user and self.password else None
        self.api_url = f"{self.base_url}{self.api_prefix}"
        
        # 建立會話並設定瀏覽器模擬標頭
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        if self.auth:
            self.session.auth = self.auth
        
        self.logger.info(f"Gerrit Manager 初始化完成 - Base URL: {self.base_url}")
    
    def _make_request(self, url: str, method: str = 'GET', **kwargs) -> requests.Response:
        """統一的請求方法，使用 session 處理認證"""
        # 使用 session 而不是直接的 requests
        method = method.upper()
        if method == 'GET':
            return self.session.get(url, **kwargs)
        elif method == 'POST':
            return self.session.post(url, **kwargs)
        elif method == 'PUT':
            return self.session.put(url, **kwargs)
        elif method == 'HEAD':
            return self.session.head(url, **kwargs)
        else:
            raise ValueError(f"不支援的 HTTP 方法: {method}")
    
    def build_manifest_link(self, repo_url: str, branch: str, manifest_file: str) -> str:
        """
        根據 repo 參數建立 manifest 檔案的 Gerrit 連結
        
        Args:
            repo_url: repo URL (ex: ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest)
            branch: 分支名稱 (ex: realtek/android-14/master)
            manifest_file: manifest 檔案名稱 (ex: atv-google-refplus.xml)
            
        Returns:
            Gerrit 檔案連結
        """
        try:
            # 從 repo URL 提取專案路徑
            # ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest -> realtek/android/manifest
            project_path = repo_url.split('/')[-3:]  # 取最後三個部分
            project_name = '/'.join(project_path)
            
            # 建立 Gerrit 檔案連結
            link = f"{self.base_url}/gerrit/plugins/gitiles/{project_name}/+/refs/heads/{branch}/{manifest_file}"
            
            self.logger.info(f"建立 manifest 連結: {link}")
            return link
            
        except Exception as e:
            self.logger.error(f"建立 manifest 連結失敗: {str(e)}")
            return ""
    
    def download_file_from_link(self, file_link: str, output_path: str) -> bool:
        """
        從 Gerrit 連結下載檔案 - 修復版（使用 API 風格 URL）
        優先使用成功的 API 方法
        """
        try:
            self.logger.info(f"開始下載檔案: {file_link}")
            
            # 策略 1: 使用 API 風格 URL（最可靠的方法）
            if self._try_download_with_api_url(file_link, output_path):
                return True
            
            # 策略 2: 直接使用原始 URL（有認證）
            if self._try_download_with_auth_direct(file_link, output_path):
                return True
            
            # 策略 3: 直接使用原始 URL（無認證）
            if self._try_download_direct(file_link, output_path):
                return True
            
            # 策略 4: 嘗試其他 URL 格式
            if self._try_download_with_corrected_paths(file_link, output_path):
                return True
            
            self.logger.error(f"所有下載策略都失敗: {file_link}")
            return False
            
        except Exception as e:
            self.logger.error(f"下載檔案失敗: {str(e)}")
            return False

    def _try_download_with_api_url(self, file_link: str, output_path: str) -> bool:
        """策略 1: 使用 API 風格 URL（成功方法）"""
        try:
            self.logger.info(f"策略 1: 使用 API 風格 URL")
            
            # 轉換為 API URL
            api_url = self._convert_to_api_url(file_link)
            if not api_url:
                self.logger.warning("無法轉換為 API URL")
                return False
            
            self.logger.info(f"API URL: {api_url}")
            
            response = self._make_request(api_url, timeout=30)
            
            if response.status_code == 200:
                self.logger.info("策略 1 成功！")
                return self._save_response_to_file(response, output_path, api_url, is_base64=True)
            else:
                self.logger.warning(f"策略 1 失敗 - HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.warning(f"策略 1 異常: {str(e)}")
            return False

    def _convert_to_api_url(self, original_url: str) -> Optional[str]:
        """
        將 gitiles URL 轉換為 API URL
        
        原始: https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml
        轉換: https://mm2sd.rtkbf.com/gerrit/a/projects/realtek%2Fandroid%2Fmanifest/branches/realtek%2Fandroid-14%2Fmaster/files/atv-google-refplus.xml/content
        """
        try:
            if '/gerrit/plugins/gitiles/' not in original_url:
                self.logger.warning("URL 不是 gitiles 格式")
                return None
            
            # 解析 URL 組件
            parts = original_url.split('/gerrit/plugins/gitiles/')
            if len(parts) != 2:
                self.logger.warning("URL 格式不正確")
                return None
            
            base_url = parts[0]
            path_part = parts[1]
            
            # 解析路徑組件
            # realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml
            path_components = path_part.split('/')
            
            if len(path_components) < 7:
                self.logger.warning(f"路徑組件不足: {path_components}")
                return None
            
            # 找到 '+' 的位置
            plus_index = -1
            for i, component in enumerate(path_components):
                if component == '+':
                    plus_index = i
                    break
            
            if plus_index == -1:
                self.logger.warning("找不到 '+' 分隔符")
                return None
            
            # 提取組件
            project_path = '/'.join(path_components[:plus_index])  # realtek/android/manifest
            ref_parts = path_components[plus_index + 1:]  # refs/heads/realtek/android-14/master/atv-google-refplus.xml
            
            if len(ref_parts) < 5:
                self.logger.warning(f"ref 組件不足: {ref_parts}")
                return None
            
            # 提取分支和檔案
            if ref_parts[0] == 'refs' and ref_parts[1] == 'heads':
                # refs/heads/realtek/android-14/master/atv-google-refplus.xml
                branch_parts = ref_parts[2:-1]  # realtek/android-14/master
                file_name = ref_parts[-1]  # atv-google-refplus.xml
                
                branch_path = '/'.join(branch_parts)
            else:
                self.logger.warning(f"不是標準的 refs/heads 格式: {ref_parts}")
                return None
            
            # URL 編碼
            project_encoded = urllib.parse.quote(project_path, safe='')
            branch_encoded = urllib.parse.quote(branch_path, safe='')
            file_encoded = urllib.parse.quote(file_name, safe='')
            
            # 構建 API URL
            api_url = f"{base_url}/gerrit/a/projects/{project_encoded}/branches/{branch_encoded}/files/{file_encoded}/content"
            
            self.logger.info(f"URL 轉換成功:")
            self.logger.info(f"  專案: {project_path}")
            self.logger.info(f"  分支: {branch_path}")
            self.logger.info(f"  檔案: {file_name}")
            self.logger.info(f"  API URL: {api_url}")
            
            return api_url
            
        except Exception as e:
            self.logger.error(f"URL 轉換失敗: {str(e)}")
            return None

    def _try_download_direct(self, file_link: str, output_path: str) -> bool:
        """策略 2: 直接下載（無認證）"""
        try:
            self.logger.info(f"策略 2: 直接下載（無認證）")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = requests.get(file_link, headers=headers, timeout=30)
            
            if response.status_code == 200:
                self.logger.info("策略 2 成功！")
                return self._save_response_to_file(response, output_path, file_link)
            else:
                self.logger.warning(f"策略 2 失敗 - HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.warning(f"策略 2 異常: {str(e)}")
            return False

    def _try_download_with_auth_direct(self, file_link: str, output_path: str) -> bool:
        """策略 3: 直接下載（有認證）"""
        try:
            self.logger.info(f"策略 3: 直接下載（有認證）")
            
            response = self._make_request(file_link, timeout=30)
            
            if response.status_code == 200:
                self.logger.info("策略 3 成功！")
                return self._save_response_to_file(response, output_path, file_link)
            else:
                self.logger.warning(f"策略 3 失敗 - HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.warning(f"策略 3 異常: {str(e)}")
            return False

    def _try_download_with_corrected_paths(self, file_link: str, output_path: str) -> bool:
        """策略 4: 使用其他 URL 格式"""
        try:
            self.logger.info(f"策略 4: 使用其他 URL 格式")
            
            # 嘗試 ?format=TEXT
            text_url = f"{file_link}?format=TEXT" if '?' not in file_link else f"{file_link}&format=TEXT"
            
            self.logger.info(f"  嘗試 ?format=TEXT: {text_url}")
            response = self._make_request(text_url, timeout=30)
            
            if response.status_code == 200:
                self.logger.info("  策略 4 成功（?format=TEXT）！")
                return self._save_response_to_file(response, output_path, text_url, is_base64=True)
            else:
                self.logger.warning(f"  ?format=TEXT 失敗 - HTTP {response.status_code}")
            
            return False
            
        except Exception as e:
            self.logger.warning(f"策略 4 異常: {str(e)}")
            return False
    
    def _save_response_to_file(self, response: requests.Response, output_path: str, 
                          source_url: str, is_base64: bool = None) -> bool:
        """儲存回應內容到檔案 - 保持原始格式，不進行 XML 格式化"""
        try:
            # 確保輸出目錄存在
            utils.ensure_dir(os.path.dirname(output_path))
            
            # 改進的 base64 檢測邏輯
            if is_base64 is None:
                # 檢查多種可能的 base64 情況
                is_base64 = (
                    '?format=TEXT' in source_url or  # 原有邏輯
                    ('/files/' in source_url and '/content' in source_url) or  # API 格式
                    ('projects/' in source_url and 'branches/' in source_url and '/content' in source_url)  # API 路徑
                )
            
            content = response.text
            
            # 如果懷疑是 base64，先檢查內容特徵
            if is_base64 or self._looks_like_base64(content):
                try:
                    # 嘗試 base64 解碼
                    decoded_content = base64.b64decode(content)
                    content = decoded_content.decode('utf-8')
                    self.logger.info(f"成功解碼 base64 內容，解碼後 {len(content)} 字符")
                except Exception as decode_error:
                    self.logger.warning(f"Base64 解碼失敗，使用原始內容: {str(decode_error)}")
                    # content 保持原樣
            
            # ⭐ 移除 XML 格式化 - 保持 Gerrit 原始格式
            # 不再對 XML 檔案進行額外的格式化處理
            self.logger.info(f"保持檔案原始格式，不進行額外處理")
            
            # 儲存檔案
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 統計行數和基本資訊
            line_count = len(content.split('\n'))
            char_count = len(content)
            
            # 如果是 XML，提供更多統計
            if utils.is_xml_file(output_path):
                project_count = content.count('<project ')
                self.logger.info(f"成功儲存 XML 檔案: {output_path} (保持原始格式)")
                self.logger.info(f"  行數: {line_count}")
                self.logger.info(f"  字符數: {char_count}")
                self.logger.info(f"  專案數: {project_count}")
            else:
                self.logger.info(f"成功儲存檔案: {output_path} ({line_count} 行, {char_count} 字符)")
            
            return True
                    
        except Exception as e:
            self.logger.error(f"儲存檔案失敗: {str(e)}")
            return False

    def _looks_like_base64(self, content: str) -> bool:
        """檢查內容是否看起來像 base64 編碼"""
        try:
            # 如果內容很長但只有很少換行，可能是 base64
            if len(content) > 1000 and content.count('\n') < 3:
                self.logger.debug(f"內容疑似 base64: {len(content)} 字符, {content.count('\n')} 換行")
                return True
            
            # 檢查是否只包含 base64 字符
            import re
            base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
            lines = content.strip().split('\n')
            
            if len(lines) <= 2:  # base64 通常是 1-2 行
                for line in lines:
                    if line and not base64_pattern.match(line.strip()):
                        return False
                self.logger.debug(f"內容符合 base64 格式: {len(lines)} 行")
                return True
            
            return False
        except:
            return False
            
    def check_file_exists(self, file_link: str) -> bool:
        """
        檢查 Gerrit 上的檔案是否存在 - 使用 API 方法
        """
        try:
            self.logger.info(f"檢查檔案是否存在: {file_link}")
            
            # 策略 1: 使用 API URL 檢查
            api_url = self._convert_to_api_url(file_link)
            if api_url:
                try:
                    response = self._make_request(api_url, method='HEAD', timeout=10)
                    if response.status_code == 200:
                        self.logger.info(f"檔案存在 (API): {file_link}")
                        return True
                except Exception as e:
                    self.logger.debug(f"API 檢查失敗: {str(e)}")
            
            # 策略 2: 直接檢查（無認證）
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                }
                
                response = requests.head(file_link, headers=headers, timeout=10)
                if response.status_code == 200:
                    self.logger.info(f"檔案存在 (無認證): {file_link}")
                    return True
            except Exception as e:
                self.logger.debug(f"無認證檢查失敗: {str(e)}")
            
            # 策略 3: 使用認證檢查
            try:
                response = self._make_request(file_link, method='HEAD', timeout=10)
                if response.status_code == 200:
                    self.logger.info(f"檔案存在 (有認證): {file_link}")
                    return True
            except Exception as e:
                self.logger.debug(f"認證檢查失敗: {str(e)}")
            
            self.logger.warning(f"檔案不存在或無法存取: {file_link}")
            return False
                
        except Exception as e:
            self.logger.error(f"檢查檔案存在性失敗: {str(e)}")
            return False
    
    # 保留其他方法不變...
    def test_connection(self) -> Dict[str, Any]:
        """測試 Gerrit 連線和認證"""
        result = {
            'success': False,
            'message': '',
            'details': {},
            'tests_performed': []
        }
        
        try:
            # 1. 測試基本連線
            self.logger.info("測試 Gerrit 基本連線...")
            base_url = f"{self.base_url}/gerrit/plugins/gitiles/"
            
            try:
                response = self._make_request(base_url, timeout=10)
                result['tests_performed'].append(f"基本連線 (HTTP {response.status_code})")
                if response.status_code in [200, 302]:  # 302 redirect 也算正常
                    self.logger.info("Gerrit 基本連線成功")
                else:
                    result['message'] = f"無法連接到 Gerrit 伺服器 - HTTP {response.status_code}"
                    return result
            except Exception as e:
                result['message'] = f"網路連線失敗: {str(e)}"
                return result
            
            # 2. 測試 API 認證
            self.logger.info("測試 Gerrit API 認證...")
            
            api_endpoints = [
                f"{self.api_url}/accounts/self",
                f"{self.base_url}/a/accounts/self", 
                f"{self.base_url}/gerrit/a/accounts/self"
            ]
            
            for i, api_url in enumerate(api_endpoints):
                try:
                    self.logger.info(f"嘗試 API 端點 {i+1}: {api_url}")
                    response = self._make_request(api_url, timeout=30)
                    result['tests_performed'].append(f"API 端點 {i+1} (HTTP {response.status_code})")
                    
                    if response.status_code == 200:
                        content = response.text
                        if content.startswith(")]}'\n"):
                            content = content[5:]
                        
                        try:
                            import json
                            user_info = json.loads(content)
                            
                            result['success'] = True
                            result['message'] = f"Gerrit 連線測試成功 (端點 {i+1})"
                            result['details']['username'] = user_info.get('username', 'Unknown')
                            result['details']['name'] = user_info.get('name', 'Unknown') 
                            result['details']['email'] = user_info.get('email', 'Unknown')
                            result['details']['successful_endpoint'] = api_url
                            self.logger.info(f"API 認證成功 - 用戶: {user_info.get('name', 'Unknown')}")
                            
                            # 3. 測試檔案下載（使用新的 API 方法）
                            self.logger.info("測試檔案下載...")
                            test_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml"
                            
                            # 測試 API 風格下載
                            api_download_url = self._convert_to_api_url(test_url)
                            if api_download_url:
                                test_response = self._make_request(api_download_url, timeout=10)
                                if test_response.status_code == 200:
                                    result['tests_performed'].append(f"檔案下載測試 (API 成功)")
                                    result['details']['download_method'] = 'API'
                                else:
                                    result['tests_performed'].append(f"檔案下載測試 (API 失敗 HTTP {test_response.status_code})")
                                    result['details']['download_method'] = 'API 失敗'
                            else:
                                result['tests_performed'].append(f"檔案下載測試 (URL 轉換失敗)")
                                result['details']['download_method'] = 'URL 轉換失敗'
                            
                            return result
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"JSON 解析失敗: {str(e)}")
                            continue
                            
                    elif response.status_code == 401:
                        result['message'] = "認證失敗 - 請檢查帳號密碼"
                        break
                    elif response.status_code == 403:
                        result['message'] = "權限不足 - 請檢查帳號權限"
                        break
                        
                except Exception as e:
                    self.logger.warning(f"API 端點 {i+1} 測試失敗: {str(e)}")
                    continue
            
            if not result['success']:
                if not result['message']:
                    result['message'] = "所有 API 端點都無法存取"
            
            return result
            
        except Exception as e:
            result['message'] = f"連線測試過程發生錯誤: {str(e)}"
            self.logger.error(result['message'])
            return result

    # 其他方法保持不變...
    def query_branches(self, project_name: str) -> List[str]:
        """查詢專案的所有分支"""
        try:
            import urllib.parse
            encoded_project = urllib.parse.quote(project_name, safe='')
            
            api_paths = [
                f"{self.base_url}/gerrit/a/projects/{encoded_project}/branches/",
                f"{self.api_url}/projects/{encoded_project}/branches/",
                f"{self.base_url}/a/projects/{encoded_project}/branches/"
            ]
            
            for api_path in api_paths:
                try:
                    self.logger.debug(f"嘗試查詢路徑: {api_path}")
                    response = self._make_request(api_path, timeout=10)
                    
                    if response.status_code == 200:
                        content = response.text
                        if content.startswith(")]}'\n"):
                            content = content[5:]
                        
                        import json
                        branches_data = json.loads(content)
                        
                        branches = [branch['ref'].replace('refs/heads/', '') for branch in branches_data]
                        self.logger.debug(f"查詢到 {len(branches)} 個分支: {project_name}")
                        return branches
                    elif response.status_code == 404:
                        self.logger.debug(f"專案不存在或無權限: {project_name}")
                        continue
                    else:
                        self.logger.debug(f"查詢分支失敗 - HTTP {response.status_code}: {api_path}")
                        continue
                            
                except Exception as e:
                    self.logger.debug(f"查詢路徑異常 {api_path}: {str(e)}")
                    continue
                    
            return self._query_branches_via_gitiles(project_name)
                
        except Exception as e:
            self.logger.error(f"查詢分支失敗: {str(e)}")
            return []

    def _query_branches_via_gitiles(self, project_name: str) -> List[str]:
        """透過 gitiles 查詢分支"""
        try:
            self.logger.debug(f"嘗試透過 gitiles 查詢分支: {project_name}")
            
            gitiles_url = f"{self.base_url}/gerrit/plugins/gitiles/{project_name}/+refs"
            
            response = self._make_request(gitiles_url, timeout=10)
            
            if response.status_code == 200:
                import re
                branch_pattern = r'refs/heads/([^"<>\s]+)'
                matches = re.findall(branch_pattern, response.text)
                
                branches = list(set(matches))
                self.logger.debug(f"透過 gitiles 找到 {len(branches)} 個分支: {project_name}")
                return branches
            else:
                self.logger.debug(f"gitiles 查詢失敗 - HTTP {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.debug(f"gitiles 查詢異常: {str(e)}")
            return []

    def check_branch_exists_and_get_revision(self, project_name: str, branch_name: str) -> Dict[str, Any]:
        """檢查分支是否存在並取得 revision"""
        result = {
            'exists': False,
            'revision': '',
            'method': ''
        }
        
        try:
            branch_info = self._get_branch_info_api(project_name, branch_name)
            if branch_info['success']:
                result['exists'] = True
                result['revision'] = branch_info['revision']
                result['method'] = 'Branch API'
                return result
            
            branches = self.query_branches(project_name)
            if branch_name in branches:
                result['exists'] = True
                result['method'] = 'Branches List'
                
                revision = self._get_branch_revision_alternative(project_name, branch_name)
                result['revision'] = revision
                return result
            
            revision = self._get_revision_via_gitiles(project_name, branch_name)
            if revision:
                result['exists'] = True
                result['revision'] = revision
                result['method'] = 'Gitiles'
                return result
            
            self.logger.debug(f"分支不存在: {project_name} - {branch_name}")
            
        except Exception as e:
            self.logger.debug(f"檢查分支存在性失敗: {project_name} - {branch_name}: {str(e)}")
        
        return result

    def _get_revision_via_gitiles(self, project_name: str, branch_name: str) -> str:
        """透過 gitiles 取得 revision"""
        try:
            gitiles_url = f"{self.base_url}/gerrit/plugins/gitiles/{project_name}/+/refs/heads/{branch_name}"
            
            response = self._make_request(gitiles_url, timeout=5)
            
            if response.status_code == 200:
                import re
                patterns = [
                    r'commit\s+([a-f0-9]{40})',
                    r'<span[^>]*>([a-f0-9]{40})</span>',
                    r'([a-f0-9]{40})'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, response.text)
                    if matches:
                        return matches[0][:8]
            
            return ''
            
        except Exception:
            return ''
        
    def _get_branch_revision_alternative(self, project_name: str, branch_name: str) -> str:
        """替代方法取得分支 revision"""
        try:
            commit_url = f"{self.base_url}/gerrit/plugins/gitiles/{project_name}/+/{branch_name}"
            
            response = self._make_request(commit_url, timeout=5)
            
            if response.status_code == 200:
                import re
                hash_pattern = r'commit\s+([a-f0-9]{40})'
                match = re.search(hash_pattern, response.text)
                
                if match:
                    return match.group(1)[:8]
            
            return ''
            
        except Exception:
            return ''
        
    def _get_branch_info_api(self, project_name: str, branch_name: str) -> Dict[str, Any]:
        """透過 Branch API 取得分支資訊"""
        try:
            import urllib.parse
            
            encoded_project = urllib.parse.quote(project_name, safe='')
            encoded_branch = urllib.parse.quote(f"refs/heads/{branch_name}", safe='')
            
            api_paths = [
                f"{self.base_url}/gerrit/a/projects/{encoded_project}/branches/{encoded_branch}",
                f"{self.api_url}/projects/{encoded_project}/branches/{encoded_branch}",
                f"{self.base_url}/a/projects/{encoded_project}/branches/{encoded_branch}"
            ]
            
            for api_path in api_paths:
                try:
                    response = self._make_request(api_path, timeout=5)
                    
                    if response.status_code == 200:
                        content = response.text
                        if content.startswith(")]}'\n"):
                            content = content[5:]
                        
                        import json
                        branch_info = json.loads(content)
                        revision = branch_info.get('revision', '')
                        
                        if revision:
                            return {
                                'success': True,
                                'revision': revision[:8]
                            }
                            
                except Exception:
                    continue
            
            return {'success': False, 'revision': ''}
            
        except Exception:
            return {'success': False, 'revision': ''}
                    
    def create_branch(self, project_name: str, branch_name: str, revision: str) -> Dict[str, Any]:
        """建立新分支"""
        result = {
            'success': False,
            'message': '',
            'exists': False
        }
        
        try:
            branches = self.query_branches(project_name)
            if branch_name in branches:
                result['exists'] = True
                result['message'] = f"分支 {branch_name} 已存在"
                self.logger.info(result['message'])
                return result
            
            import urllib.parse
            encoded_project = urllib.parse.quote(project_name, safe='')
            encoded_branch = urllib.parse.quote(branch_name, safe='')
            
            url = f"{self.api_url}/projects/{encoded_project}/branches/{encoded_branch}"
            
            data = {
                'revision': revision
            }
            
            response = self._make_request(url, method='PUT', json=data, timeout=30)
            
            if response.status_code in [200, 201]:
                result['success'] = True
                result['message'] = f"成功建立分支 {branch_name}"
                self.logger.info(result['message'])
            else:
                result['message'] = f"建立分支失敗 - HTTP {response.status_code}"
                self.logger.warning(result['message'])
            
            return result
            
        except Exception as e:
            result['message'] = f"建立分支發生錯誤: {str(e)}"
            self.logger.error(result['message'])
            return result

    def query_tag(self, project_name: str, tag_name: str) -> Dict[str, Any]:
        """查詢專案的指定 tag 是否存在並取得 revision"""
        result = {
            'exists': False,
            'revision': '',
            'method': ''
        }
        
        try:
            self.logger.debug(f"查詢 Tag: {project_name} - {tag_name}")
            
            tag_info = self._get_tag_info_api(project_name, tag_name)
            if tag_info['success']:
                result['exists'] = True
                result['revision'] = tag_info['revision']
                result['method'] = 'Tag API'
                return result
            
            tags = self.query_tags(project_name)
            if tag_name in tags:
                result['exists'] = True
                result['method'] = 'Tags List'
                
                revision = self._get_tag_revision_alternative(project_name, tag_name)
                result['revision'] = revision
                return result
            
            revision = self._get_tag_revision_via_gitiles(project_name, tag_name)
            if revision:
                result['exists'] = True
                result['revision'] = revision
                result['method'] = 'Gitiles'
                return result
            
            self.logger.debug(f"Tag 不存在: {project_name} - {tag_name}")
            
        except Exception as e:
            self.logger.debug(f"查詢 Tag 存在性失敗: {project_name} - {tag_name}: {str(e)}")
        
        return result

    def query_tags(self, project_name: str) -> List[str]:
        """查詢專案的所有 tags"""
        try:
            import urllib.parse
            encoded_project = urllib.parse.quote(project_name, safe='')
            
            api_paths = [
                f"{self.base_url}/gerrit/a/projects/{encoded_project}/tags/",
                f"{self.api_url}/projects/{encoded_project}/tags/",
                f"{self.base_url}/a/projects/{encoded_project}/tags/"
            ]
            
            for api_path in api_paths:
                try:
                    self.logger.debug(f"嘗試查詢 Tags 路徑: {api_path}")
                    response = self._make_request(api_path, timeout=10)
                    
                    if response.status_code == 200:
                        content = response.text
                        if content.startswith(")]}'\n"):
                            content = content[5:]
                        
                        import json
                        tags_data = json.loads(content)
                        
                        if isinstance(tags_data, dict):
                            tags = list(tags_data.keys())
                        else:
                            tags = [tag['ref'].replace('refs/tags/', '') for tag in tags_data if 'ref' in tag]
                        
                        self.logger.debug(f"查詢到 {len(tags)} 個 tags: {project_name}")
                        return tags
                    elif response.status_code == 404:
                        self.logger.debug(f"專案不存在或無權限: {project_name}")
                        continue
                    else:
                        self.logger.debug(f"查詢 tags 失敗 - HTTP {response.status_code}: {api_path}")
                        continue
                            
                except Exception as e:
                    self.logger.debug(f"查詢路徑異常 {api_path}: {str(e)}")
                    continue
                    
            return self._query_tags_via_gitiles(project_name)
                
        except Exception as e:
            self.logger.error(f"查詢 tags 失敗: {str(e)}")
            return []

    def _query_tags_via_gitiles(self, project_name: str) -> List[str]:
        """透過 gitiles 查詢 tags"""
        try:
            self.logger.debug(f"嘗試透過 gitiles 查詢 tags: {project_name}")
            
            gitiles_url = f"{self.base_url}/gerrit/plugins/gitiles/{project_name}/+refs"
            
            response = self._make_request(gitiles_url, timeout=10)
            
            if response.status_code == 200:
                import re
                tag_pattern = r'refs/tags/([^"<>\s]+)'
                matches = re.findall(tag_pattern, response.text)
                
                tags = list(set(matches))
                self.logger.debug(f"透過 gitiles 找到 {len(tags)} 個 tags: {project_name}")
                return tags
            else:
                self.logger.debug(f"gitiles 查詢失敗 - HTTP {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.debug(f"gitiles 查詢異常: {str(e)}")
            return []

    def _get_tag_info_api(self, project_name: str, tag_name: str) -> Dict[str, Any]:
        """透過 Tag API 取得 tag 資訊"""
        try:
            import urllib.parse
            
            encoded_project = urllib.parse.quote(project_name, safe='')
            encoded_tag = urllib.parse.quote(f"refs/tags/{tag_name}", safe='')
            
            api_paths = [
                f"{self.base_url}/gerrit/a/projects/{encoded_project}/tags/{encoded_tag}",
                f"{self.api_url}/projects/{encoded_project}/tags/{encoded_tag}",
                f"{self.base_url}/a/projects/{encoded_project}/tags/{encoded_tag}"
            ]
            
            for api_path in api_paths:
                try:
                    response = self._make_request(api_path, timeout=5)
                    
                    if response.status_code == 200:
                        content = response.text
                        if content.startswith(")]}'\n"):
                            content = content[5:]
                        
                        import json
                        tag_info = json.loads(content)
                        
                        revision = tag_info.get('object', tag_info.get('revision', ''))
                        
                        if revision:
                            return {
                                'success': True,
                                'revision': revision[:8]
                            }
                            
                except Exception:
                    continue
            
            return {'success': False, 'revision': ''}
            
        except Exception:
            return {'success': False, 'revision': ''}

    def _get_tag_revision_alternative(self, project_name: str, tag_name: str) -> str:
        """替代方法取得 tag revision"""
        try:
            tag_url = f"{self.base_url}/gerrit/plugins/gitiles/{project_name}/+/refs/tags/{tag_name}"
            
            response = self._make_request(tag_url, timeout=5)
            
            if response.status_code == 200:
                import re
                
                hash_patterns = [
                    r'commit\s+([a-f0-9]{40})',
                    r'object\s+([a-f0-9]{40})',
                    r'<span[^>]*>([a-f0-9]{40})</span>',
                    r'([a-f0-9]{40})'
                ]
                
                for pattern in hash_patterns:
                    matches = re.findall(pattern, response.text)
                    if matches:
                        return matches[0][:8]
            
            return ''
            
        except Exception:
            return ''

    def _get_tag_revision_via_gitiles(self, project_name: str, tag_name: str) -> str:
        """透過 gitiles 取得 tag revision"""
        try:
            gitiles_url = f"{self.base_url}/gerrit/plugins/gitiles/{project_name}/+/refs/tags/{tag_name}"
            
            response = self._make_request(gitiles_url, timeout=5)
            
            if response.status_code == 200:
                import re
                
                patterns = [
                    r'tag\s+([a-f0-9]{40})',
                    r'object\s+([a-f0-9]{40})',
                    r'commit\s+([a-f0-9]{40})',
                    r'<span[^>]*>([a-f0-9]{40})</span>',
                    r'([a-f0-9]{40})'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, response.text)
                    if matches:
                        return matches[0][:8]
            
            return ''
            
        except Exception:
            return ''