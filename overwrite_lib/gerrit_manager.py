"""
Gerrit API 管理模組 - 修復版
處理所有 Gerrit 相關的 API 操作
主要修復：下載檔案時的 401 認證問題
"""
import os
import requests
import re
import base64
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
    """Gerrit API 管理類別 - 修復版"""
    
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
        從 Gerrit 連結下載檔案 - 修復版
        修復 URL 路徑問題
        """
        try:
            self.logger.info(f"開始下載檔案: {file_link}")
            
            # 策略 1: 直接使用原始 URL（無認證）
            if self._try_download_direct(file_link, output_path):
                return True
            
            # 策略 2: 直接使用原始 URL（有認證）
            if self._try_download_with_auth_direct(file_link, output_path):
                return True
            
            # 策略 3: 修正 URL 路徑後下載
            if self._try_download_with_corrected_paths(file_link, output_path):
                return True
            
            self.logger.error(f"所有下載策略都失敗: {file_link}")
            return False
            
        except Exception as e:
            self.logger.error(f"下載檔案失敗: {str(e)}")
            return False

    def _try_download_direct(self, file_link: str, output_path: str) -> bool:
        """策略 1: 直接下載（無認證）"""
        try:
            self.logger.info(f"策略 1: 直接下載（無認證）")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = requests.get(file_link, headers=headers, timeout=30)
            
            if response.status_code == 200:
                self.logger.info("策略 1 成功！")
                return self._save_response_to_file(response, output_path, file_link)
            else:
                self.logger.warning(f"策略 1 失敗 - HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.warning(f"策略 1 異常: {str(e)}")
            return False

    def _try_download_with_auth_direct(self, file_link: str, output_path: str) -> bool:
        """策略 2: 直接下載（有認證）"""
        try:
            self.logger.info(f"策略 2: 直接下載（有認證）")
            
            response = self._make_request(file_link, timeout=30)
            
            if response.status_code == 200:
                self.logger.info("策略 2 成功！")
                return self._save_response_to_file(response, output_path, file_link)
            else:
                self.logger.warning(f"策略 2 失敗 - HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.warning(f"策略 2 異常: {str(e)}")
            return False

    def _try_download_with_corrected_paths(self, file_link: str, output_path: str) -> bool:
        """策略 3: 使用修正的 URL 路徑"""
        try:
            self.logger.info(f"策略 3: 使用修正的 URL 路徑")
            
            # 根據 API 測試成功的經驗，這個 Gerrit 需要 /gerrit/ 前綴
            corrected_urls = []
            
            # 如果 URL 中沒有 /gerrit/，嘗試加入
            if '/gerrit/' not in file_link:
                # https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/... 
                # 保持現有格式，但確保有 /gerrit/ 前綴
                corrected_urls.append(file_link)  # 原始 URL 已經有 /gerrit/
            
            # 嘗試不同的 API 風格 URL
            if 'plugins/gitiles' in file_link:
                # 轉換為 API 風格
                # https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml
                # 轉換為:
                # https://mm2sd.rtkbf.com/gerrit/a/projects/realtek%2Fandroid%2Fmanifest/branches/realtek%2Fandroid-14%2Fmaster/files/atv-google-refplus.xml/content
                
                try:
                    import urllib.parse
                    # 解析路徑
                    parts = file_link.split('/gerrit/plugins/gitiles/')
                    if len(parts) == 2:
                        base_url = parts[0]
                        path_part = parts[1]
                        
                        # 解析路徑組件
                        # realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml
                        path_components = path_part.split('/')
                        if len(path_components) >= 7:
                            project_path = '/'.join(path_components[:3])  # realtek/android/manifest
                            ref_parts = path_components[4:]  # refs/heads/realtek/android-14/master/atv-google-refplus.xml
                            
                            if len(ref_parts) >= 5:
                                branch_path = '/'.join(ref_parts[2:-1])  # realtek/android-14/master
                                file_name = ref_parts[-1]  # atv-google-refplus.xml
                                
                                # 構建 API URL
                                project_encoded = urllib.parse.quote(project_path, safe='')
                                branch_encoded = urllib.parse.quote(branch_path, safe='')
                                file_encoded = urllib.parse.quote(file_name, safe='')
                                
                                api_url = f"{base_url}/gerrit/a/projects/{project_encoded}/branches/{branch_encoded}/files/{file_encoded}/content"
                                corrected_urls.append(api_url)
                except Exception as e:
                    self.logger.warning(f"構建 API URL 失敗: {str(e)}")
            
            # 嘗試這些修正的 URL
            for i, url in enumerate(corrected_urls, 1):
                self.logger.info(f"  嘗試修正 URL {i}: {url}")
                
                try:
                    # 無認證
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    }
                    response = requests.get(url, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        self.logger.info(f"  修正 URL {i} 成功（無認證）！")
                        return self._save_response_to_file(response, output_path, url)
                    
                    # 有認證
                    response = self._make_request(url, timeout=30)
                    
                    if response.status_code == 200:
                        self.logger.info(f"  修正 URL {i} 成功（有認證）！")
                        return self._save_response_to_file(response, output_path, url)
                    else:
                        self.logger.warning(f"  修正 URL {i} 失敗 - HTTP {response.status_code}")
                        
                except Exception as e:
                    self.logger.warning(f"  修正 URL {i} 異常: {str(e)}")
                    continue
            
            return False
            
        except Exception as e:
            self.logger.warning(f"策略 3 異常: {str(e)}")
            return False
    
    def _try_download_without_auth(self, file_link: str, output_path: str) -> bool:
        """策略 1: 無認證下載"""
        try:
            self.logger.info(f"策略 1: 無認證下載")
            
            # 建立無認證的 session
            no_auth_session = requests.Session()
            no_auth_session.headers.update(self.session.headers)
            
            response = no_auth_session.get(file_link, timeout=30)
            
            if response.status_code == 200:
                return self._save_response_to_file(response, output_path, file_link)
            else:
                self.logger.warning(f"策略 1 失敗 - HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.warning(f"策略 1 異常: {str(e)}")
            return False
    
    def _try_download_with_auth(self, file_link: str, output_path: str) -> bool:
        """策略 2: 使用認證下載"""
        try:
            self.logger.info(f"策略 2: 使用認證下載")
            
            response = self._make_request(file_link, timeout=30)
            
            if response.status_code == 200:
                return self._save_response_to_file(response, output_path, file_link)
            else:
                self.logger.warning(f"策略 2 失敗 - HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.warning(f"策略 2 異常: {str(e)}")
            return False
    
    def _try_download_with_format_text(self, file_link: str, output_path: str) -> bool:
        """策略 3: 強制使用 ?format=TEXT"""
        try:
            self.logger.info(f"策略 3: 強制 ?format=TEXT")
            
            # 確保有 ?format=TEXT
            if '?format=TEXT' not in file_link:
                if '?' in file_link:
                    text_link = f"{file_link}&format=TEXT"
                else:
                    text_link = f"{file_link}?format=TEXT"
            else:
                text_link = file_link
            
            # 先嘗試無認證
            no_auth_session = requests.Session()
            no_auth_session.headers.update(self.session.headers)
            
            response = no_auth_session.get(text_link, timeout=30)
            
            if response.status_code == 200:
                return self._save_response_to_file(response, output_path, text_link, is_base64=True)
            
            # 再嘗試有認證
            response = self._make_request(text_link, timeout=30)
            
            if response.status_code == 200:
                return self._save_response_to_file(response, output_path, text_link, is_base64=True)
            else:
                self.logger.warning(f"策略 3 失敗 - HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.warning(f"策略 3 異常: {str(e)}")
            return False
    
    def _try_alternative_urls(self, file_link: str, output_path: str) -> bool:
        """策略 4: 嘗試不同的 URL 格式"""
        try:
            self.logger.info(f"策略 4: 嘗試替代 URL 格式")
            
            alternative_urls = self._generate_alternative_urls(file_link)
            
            for i, alt_url in enumerate(alternative_urls, 1):
                self.logger.info(f"  嘗試替代 URL {i}: {alt_url}")
                try:
                    # 先無認證
                    no_auth_session = requests.Session()
                    no_auth_session.headers.update(self.session.headers)
                    response = no_auth_session.get(alt_url, timeout=30)
                    
                    if response.status_code == 200:
                        self.logger.info(f"  替代 URL {i} 成功 (無認證)！")
                        return self._save_response_to_file(response, output_path, alt_url)
                    
                    # 再有認證
                    response = self._make_request(alt_url, timeout=30)
                    
                    if response.status_code == 200:
                        self.logger.info(f"  替代 URL {i} 成功 (有認證)！")
                        return self._save_response_to_file(response, output_path, alt_url)
                    else:
                        self.logger.warning(f"  替代 URL {i} 失敗 - HTTP {response.status_code}")
                        
                except Exception as e:
                    self.logger.warning(f"  替代 URL {i} 異常: {str(e)}")
                    continue
            
            return False
            
        except Exception as e:
            self.logger.warning(f"策略 4 異常: {str(e)}")
            return False
    
    def _generate_alternative_urls(self, original_url: str) -> List[str]:
        """產生替代的 URL 格式"""
        alternatives = []
        
        try:
            # 原始: https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml
            
            # 替代 1: 移除 plugins/gitiles
            alt1 = original_url.replace('/gerrit/plugins/gitiles/', '/gerrit/')
            alternatives.append(alt1)
            
            # 替代 2: 使用 raw 格式
            alt2 = original_url.replace('/+/', '/raw/')
            alternatives.append(alt2)
            
            # 替代 3: 組合 raw 和移除 gitiles
            alt3 = original_url.replace('/gerrit/plugins/gitiles/', '/gerrit/').replace('/+/', '/raw/')
            alternatives.append(alt3)
            
            # 替代 4: 使用 plain 格式
            if '?format=TEXT' in original_url:
                alt4 = original_url.replace('?format=TEXT', '?format=PLAIN')
                alternatives.append(alt4)
            else:
                alt4 = f"{original_url}?format=PLAIN"
                alternatives.append(alt4)
            
            # 替代 5: 移除所有參數
            if '?' in original_url:
                alt5 = original_url.split('?')[0]
                alternatives.append(alt5)
            
            # 替代 6: 只保留基本路徑，去掉 plugins/gitiles
            if '/gerrit/plugins/gitiles/' in original_url:
                # 轉換為類似這樣的格式：https://mm2sd.rtkbf.com/realtek/android/manifest/blob/refs/heads/realtek/android-14/master/atv-google-refplus.xml
                parts = original_url.split('/gerrit/plugins/gitiles/')
                if len(parts) == 2:
                    base_part = parts[0]
                    path_part = parts[1].replace('/+/', '/blob/')
                    alt6 = f"{base_part}/{path_part}"
                    alternatives.append(alt6)
            
        except Exception as e:
            self.logger.error(f"產生替代 URL 失敗: {str(e)}")
        
        return alternatives
    
    def _save_response_to_file(self, response: requests.Response, output_path: str, 
                      source_url: str, is_base64: bool = None) -> bool:
        """儲存回應內容到檔案 - 修復 base64 檢測"""
        try:
            # 確保輸出目錄存在
            utils.ensure_dir(os.path.dirname(output_path))
            
            # 改進的 base64 檢測邏輯
            if is_base64 is None:
                # 檢查多種可能的 base64 情況
                is_base64 = (
                    '?format=TEXT' in source_url or  # 原有邏輯
                    '/files/' in source_url and '/content' in source_url or  # API 格式
                    'projects/' in source_url and 'branches/' in source_url  # API 路徑
                )
            
            content = response.text
            
            # 如果懷疑是 base64，先檢查內容特徵
            if is_base64 or self._looks_like_base64(content):
                try:
                    # 嘗試 base64 解碼
                    decoded_content = base64.b64decode(content)
                    content = decoded_content.decode('utf-8')
                    self.logger.info(f"成功解碼 base64 內容")
                except Exception as decode_error:
                    self.logger.warning(f"Base64 解碼失敗，使用原始內容: {str(decode_error)}")
                    # content 保持原樣
            
            # 如果是 XML 檔案，進行格式化
            if utils.is_xml_file(output_path):
                try:
                    formatted_content = utils.format_xml_content(content)
                    content = formatted_content
                    self.logger.info(f"XML 檔案已格式化為多行")
                except Exception as format_error:
                    self.logger.warning(f"XML 格式化失敗，保持原始格式: {str(format_error)}")
            
            # 儲存檔案
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 統計行數
            line_count = len(content.split('\n'))
            self.logger.info(f"成功儲存檔案: {output_path} ({line_count} 行)")
            return True
                    
        except Exception as e:
            self.logger.error(f"儲存檔案失敗: {str(e)}")
            return False

    def _looks_like_base64(self, content: str) -> bool:
        """檢查內容是否看起來像 base64 編碼"""
        try:
            # 如果內容很長但只有很少換行，可能是 base64
            if len(content) > 1000 and content.count('\n') < 3:
                return True
            
            # 檢查是否只包含 base64 字符
            import re
            base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
            lines = content.strip().split('\n')
            
            if len(lines) <= 2:  # base64 通常是 1-2 行
                for line in lines:
                    if line and not base64_pattern.match(line.strip()):
                        return False
                return True
            
            return False
        except:
            return False
            
    def check_file_exists(self, file_link: str) -> bool:
        """
        檢查 Gerrit 上的檔案是否存在 - 改進版
        參考 download_file_from_link 的成功策略
        """
        try:
            self.logger.info(f"檢查檔案是否存在: {file_link}")
            
            # 策略 1: 直接檢查（無認證）
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
            
            # 策略 2: 使用認證檢查（參考下載成功的方式）
            try:
                response = self._make_request(file_link, method='HEAD', timeout=10)
                if response.status_code == 200:
                    self.logger.info(f"檔案存在 (有認證): {file_link}")
                    return True
            except Exception as e:
                self.logger.debug(f"認證檢查失敗: {str(e)}")
            
            # 策略 3: 嘗試 GET 請求（有些伺服器不支援 HEAD）
            try:
                response = self._make_request(file_link, timeout=10)
                if response.status_code == 200:
                    self.logger.info(f"檔案存在 (GET請求): {file_link}")
                    return True
            except Exception as e:
                self.logger.debug(f"GET 請求檢查失敗: {str(e)}")
            
            self.logger.warning(f"檔案不存在或無法存取: {file_link}")
            return False
                
        except Exception as e:
            self.logger.error(f"檢查檔案存在性失敗: {str(e)}")
            return False
    
    def test_connection(self) -> Dict[str, Any]:
        """
        測試 Gerrit 連線和認證
        
        Returns:
            測試結果字典
        """
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
            
            # 2. 測試 API 認證 - 嘗試多個可能的端點
            self.logger.info("測試 Gerrit API 認證...")
            
            # 嘗試的 API 端點列表
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
                        # Gerrit API 返回的可能以 )]}' 開頭
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
                            
                            # 3. 測試檔案下載
                            self.logger.info("測試檔案下載...")
                            test_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml?format=TEXT"
                            
                            # 測試無認證下載
                            no_auth_session = requests.Session()
                            no_auth_session.headers.update(self.session.headers)
                            test_response = no_auth_session.get(test_url, timeout=10)
                            
                            if test_response.status_code == 200:
                                result['tests_performed'].append(f"檔案下載測試 (無認證成功)")
                                result['details']['download_method'] = '無認證'
                            else:
                                # 測試有認證下載
                                test_response = self._make_request(test_url, timeout=10)
                                if test_response.status_code == 200:
                                    result['tests_performed'].append(f"檔案下載測試 (有認證成功)")
                                    result['details']['download_method'] = '有認證'
                                else:
                                    result['tests_performed'].append(f"檔案下載測試 (失敗 HTTP {test_response.status_code})")
                                    result['details']['download_method'] = '失敗'
                            
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
            
            # 如果所有端點都失敗
            if not result['success']:
                if not result['message']:
                    result['message'] = "所有 API 端點都無法存取"
            
            return result
            
        except Exception as e:
            result['message'] = f"連線測試過程發生錯誤: {str(e)}"
            self.logger.error(result['message'])
            return result
    
    def query_branches(self, project_name: str) -> List[str]:
        """
        查詢專案的所有分支 - 改進版
        """
        try:
            # URL 編碼專案名稱
            import urllib.parse
            encoded_project = urllib.parse.quote(project_name, safe='')
            
            # 嘗試多個可能的 API 路徑
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
                        # Gerrit API 返回的 JSON 可能以 )]}' 開頭，需要移除
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
                    
            # 如果所有 API 都失敗，嘗試 gitiles 方法
            return self._query_branches_via_gitiles(project_name)
                
        except Exception as e:
            self.logger.error(f"查詢分支失敗: {str(e)}")
            return []

    def _query_branches_via_gitiles(self, project_name: str) -> List[str]:
        """透過 gitiles 查詢分支"""
        try:
            self.logger.debug(f"嘗試透過 gitiles 查詢分支: {project_name}")
            
            # gitiles refs URL
            gitiles_url = f"{self.base_url}/gerrit/plugins/gitiles/{project_name}/+refs"
            
            response = self._make_request(gitiles_url, timeout=10)
            
            if response.status_code == 200:
                # 解析 HTML 回應中的分支資訊
                import re
                
                # 尋找 refs/heads/ 的分支
                branch_pattern = r'refs/heads/([^"<>\s]+)'
                matches = re.findall(branch_pattern, response.text)
                
                branches = list(set(matches))  # 去重複
                self.logger.debug(f"透過 gitiles 找到 {len(branches)} 個分支: {project_name}")
                return branches
            else:
                self.logger.debug(f"gitiles 查詢失敗 - HTTP {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.debug(f"gitiles 查詢異常: {str(e)}")
            return []

    def check_branch_exists_and_get_revision(self, project_name: str, branch_name: str) -> Dict[str, Any]:
        """
        檢查分支是否存在並取得 revision - 新方法
        
        Returns:
            {
                'exists': bool,
                'revision': str,
                'method': str  # 查詢成功的方法
            }
        """
        result = {
            'exists': False,
            'revision': '',
            'method': ''
        }
        
        try:
            # 方法 1: 直接查詢特定分支 API
            branch_info = self._get_branch_info_api(project_name, branch_name)
            if branch_info['success']:
                result['exists'] = True
                result['revision'] = branch_info['revision']
                result['method'] = 'Branch API'
                return result
            
            # 方法 2: 查詢所有分支然後找目標分支
            branches = self.query_branches(project_name)
            if branch_name in branches:
                result['exists'] = True
                result['method'] = 'Branches List'
                
                # 嘗試取得 revision
                revision = self._get_branch_revision_alternative(project_name, branch_name)
                result['revision'] = revision
                return result
            
            # 方法 3: 透過 gitiles commit 查詢
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
            # gitiles commit URL
            gitiles_url = f"{self.base_url}/gerrit/plugins/gitiles/{project_name}/+/refs/heads/{branch_name}"
            
            response = self._make_request(gitiles_url, timeout=5)
            
            if response.status_code == 200:
                # 從回應中解析 commit hash
                import re
                
                # 多種可能的 commit hash 模式
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
            # 嘗試透過 commit API
            commit_url = f"{self.base_url}/gerrit/plugins/gitiles/{project_name}/+/{branch_name}"
            
            response = self._make_request(commit_url, timeout=5)
            
            if response.status_code == 200:
                # 從 HTML 中解析 commit hash
                import re
                
                # 尋找 commit hash 模式
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
            
            # URL 編碼
            encoded_project = urllib.parse.quote(project_name, safe='')
            encoded_branch = urllib.parse.quote(f"refs/heads/{branch_name}", safe='')
            
            # 嘗試多個 API 路徑
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
                                'revision': revision[:8]  # 只取前8個字符
                            }
                            
                except Exception:
                    continue
            
            return {'success': False, 'revision': ''}
            
        except Exception:
            return {'success': False, 'revision': ''}
                    
    def create_branch(self, project_name: str, branch_name: str, revision: str) -> Dict[str, Any]:
        """
        建立新分支
        
        Args:
            project_name: 專案名稱
            branch_name: 分支名稱
            revision: 基於的 revision
            
        Returns:
            建立結果
        """
        result = {
            'success': False,
            'message': '',
            'exists': False
        }
        
        try:
            # 首先檢查分支是否已存在
            branches = self.query_branches(project_name)
            if branch_name in branches:
                result['exists'] = True
                result['message'] = f"分支 {branch_name} 已存在"
                self.logger.info(result['message'])
                return result
            
            # URL 編碼
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
    
    def determine_branch_type(self, branch_name: str) -> str:
        """
        判斷分支類型
        
        Args:
            branch_name: 分支名稱
            
        Returns:
            分支類型: master, premp, mp, mpbackup
        """
        if not branch_name:
            return 'master'
        
        branch_lower = branch_name.lower()
        
        # 檢查是否包含 premp
        if 'premp' in branch_lower:
            return 'premp'
        
        # 檢查是否包含 wave.backup
        if 'wave.backup' in branch_lower or 'wave' in branch_lower and 'backup' in branch_lower:
            return 'mpbackup'
        
        # 檢查是否包含 wave (但不包含 backup)
        if 'wave' in branch_lower and 'backup' not in branch_lower:
            return 'mp'
        
        # 預設為 master
        return 'master'
    
    def convert_branch_name(self, source_branch: str, target_type: str) -> str:
        """
        轉換分支名稱
        
        Args:
            source_branch: 來源分支名稱
            target_type: 目標類型 (premp, mp, mpbackup)
            
        Returns:
            轉換後的分支名稱
        """
        if not source_branch:
            return source_branch
        
        try:
            if target_type == 'premp':
                # master -> premp: 加上 premp
                if 'premp' not in source_branch:
                    # 在適當位置插入 premp
                    parts = source_branch.split('/')
                    if len(parts) >= 3:
                        # realtek/android-14/master -> realtek/android-14/premp.google-refplus
                        parts[-1] = 'premp.google-refplus'
                    return '/'.join(parts)
                
            elif target_type == 'mp':
                # premp -> mp: 替換 premp 為 mp.google-refplus.wave
                result = source_branch.replace('premp.google-refplus', 'mp.google-refplus.wave')
                return result
                
            elif target_type == 'mpbackup':
                # mp -> mpbackup: 在 wave 後加上 .backup
                if 'wave' in source_branch and 'backup' not in source_branch:
                    result = source_branch.replace('wave', 'wave.backup')
                    return result
            
            return source_branch
            
        except Exception as e:
            self.logger.error(f"轉換分支名稱失敗: {str(e)}")
            return source_branch