"""
Gerrit API 管理模組
處理所有 Gerrit 相關的 API 操作
"""
import os
import requests
import re
from typing import Optional, Dict, Any, List
import utils

# 載入設定
try:
    import config
    utils.setup_config()  # 設定環境變數
except ImportError:
    print("警告：無法載入 config 模組，使用預設設定")
    config = None

logger = utils.setup_logger(__name__)

class GerritManager:
    """Gerrit API 管理類別"""
    
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
        self.auth = (self.user, self.password)
        self.api_url = f"{self.base_url}{self.api_prefix}"
        
        self.logger.info(f"Gerrit Manager 初始化完成 - Base URL: {self.base_url}")
    
    def _make_request(self, url: str, method: str = 'GET', **kwargs) -> requests.Response:
        """統一的請求方法，自動處理認證"""
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
        從 Gerrit 連結下載檔案
        
        Args:
            file_link: Gerrit 檔案連結
            output_path: 輸出檔案路徑
            
        Returns:
            是否下載成功
        """
        try:
            # 轉換為原始檔案連結 (加上 ?format=TEXT)
            if '?format=TEXT' not in file_link:
                raw_link = f"{file_link}?format=TEXT"
            else:
                raw_link = file_link
            
            response = self._make_request(raw_link, timeout=30)
            
            if response.status_code == 200:
                # 確保輸出目錄存在
                utils.ensure_dir(os.path.dirname(output_path))
                
                # Gerrit 返回的是 base64 編碼，需要解碼
                import base64
                content = base64.b64decode(response.text)
                
                with open(output_path, 'wb') as f:
                    f.write(content)
                
                self.logger.info(f"成功下載檔案: {output_path}")
                return True
            else:
                self.logger.warning(f"下載失敗 - HTTP {response.status_code}: {file_link}")
                return False
                
        except Exception as e:
            self.logger.error(f"下載檔案失敗: {str(e)}")
            return False
    
    def check_file_exists(self, file_link: str) -> bool:
        """
        檢查 Gerrit 上的檔案是否存在
        
        Args:
            file_link: Gerrit 檔案連結
            
        Returns:
            檔案是否存在
        """
        try:
            response = self._make_request(file_link, method='HEAD', timeout=30)
            exists = response.status_code == 200
            
            if exists:
                self.logger.info(f"檔案存在: {file_link}")
            else:
                self.logger.warning(f"檔案不存在: {file_link}")
            
            return exists
            
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
                            
                            # 3. 測試專案查詢
                            self.logger.info("測試專案查詢...")
                            test_project = "realtek/android/manifest"
                            branches = self.query_branches(test_project)
                            result['tests_performed'].append(f"專案查詢 ({len(branches)} 個分支)")
                            result['details']['test_project'] = test_project
                            result['details']['branch_count'] = len(branches)
                            
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
        查詢專案的所有分支
        
        Args:
            project_name: 專案名稱
            
        Returns:
            分支列表
        """
        try:
            # URL 編碼專案名稱
            import urllib.parse
            encoded_project = urllib.parse.quote(project_name, safe='')
            
            # 嘗試多個可能的 API 路徑
            api_paths = [
                f"{self.api_url}/projects/{encoded_project}/branches/",
                f"{self.base_url}/a/projects/{encoded_project}/branches/",
                f"{self.base_url}/gerrit/a/projects/{encoded_project}/branches/"
            ]
            
            for api_path in api_paths:
                try:
                    self.logger.info(f"嘗試查詢路徑: {api_path}")
                    response = self._make_request(api_path, timeout=30)
                    
                    if response.status_code == 200:
                        # Gerrit API 返回的 JSON 可能以 )]}' 開頭，需要移除
                        content = response.text
                        if content.startswith(")]}'\n"):
                            content = content[5:]
                        
                        import json
                        branches_data = json.loads(content)
                        
                        branches = [branch['ref'].replace('refs/heads/', '') for branch in branches_data]
                        self.logger.info(f"查詢到 {len(branches)} 個分支")
                        return branches
                    else:
                        self.logger.warning(f"查詢分支失敗 - HTTP {response.status_code}: {api_path}")
                        
                except Exception as e:
                    self.logger.warning(f"查詢路徑失敗 {api_path}: {str(e)}")
                    continue
                    
            self.logger.warning("所有查詢路徑都失敗")
            return []
            
        except Exception as e:
            self.logger.error(f"查詢分支失敗: {str(e)}")
            return []
    
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