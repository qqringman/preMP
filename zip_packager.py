"""
ZIP 打包模組
處理將比對結果打包成 ZIP 檔案
"""
import os
import zipfile
from typing import List, Optional
import utils
import config

logger = utils.setup_logger(__name__)

class ZipPackager:
    """ZIP 打包器類別"""
    
    def __init__(self):
        self.logger = logger
        
    def create_zip(self, source_dir: str, output_file: str = None, 
                   include_patterns: List[str] = None,
                   exclude_patterns: List[str] = None) -> str:
        """
        建立 ZIP 檔案
        
        Args:
            source_dir: 要打包的來源目錄
            output_file: 輸出的 ZIP 檔案路徑
            include_patterns: 要包含的檔案模式
            exclude_patterns: 要排除的檔案模式
            
        Returns:
            ZIP 檔案路徑
        """
        # 預設輸出檔名
        if not output_file:
            timestamp = utils.get_timestamp()
            output_file = f"compare_results_{timestamp}.zip"
            
        # 確保輸出目錄存在
        output_dir = os.path.dirname(output_file)
        if output_dir:
            utils.create_directory(output_dir)
            
        try:
            self.logger.info(f"開始打包: {source_dir} -> {output_file}")
            
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 遍歷來源目錄
                for root, dirs, files in os.walk(source_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        relative_path = utils.get_relative_path(file_path, source_dir)
                        
                        # 檢查是否應該包含此檔案
                        if self._should_include_file(relative_path, include_patterns, exclude_patterns):
                            self.logger.debug(f"加入檔案: {relative_path}")
                            zipf.write(file_path, relative_path)
                            
            # 取得檔案大小
            file_size = os.path.getsize(output_file)
            self.logger.info(f"打包完成: {output_file} ({utils.format_file_size(file_size)})")
            
            return output_file
            
        except Exception as e:
            self.logger.error(f"建立 ZIP 檔案失敗: {str(e)}")
            raise
            
    def _should_include_file(self, file_path: str, 
                           include_patterns: List[str] = None,
                           exclude_patterns: List[str] = None) -> bool:
        """
        判斷檔案是否應該被包含在 ZIP 中
        
        Args:
            file_path: 檔案路徑
            include_patterns: 包含模式
            exclude_patterns: 排除模式
            
        Returns:
            是否應該包含
        """
        # 如果有指定包含模式，檢查是否符合
        if include_patterns:
            included = False
            for pattern in include_patterns:
                if pattern in file_path:
                    included = True
                    break
            if not included:
                return False
                
        # 檢查是否應該排除
        if exclude_patterns:
            for pattern in exclude_patterns:
                if pattern in file_path:
                    return False
                    
        return True
        
    def create_module_zip(self, module_path: str, output_dir: str = None) -> str:
        """
        為單一模組建立 ZIP 檔案
        
        Args:
            module_path: 模組路徑
            output_dir: 輸出目錄
            
        Returns:
            ZIP 檔案路徑
        """
        output_dir = output_dir or config.DEFAULT_ZIP_DIR
        module_name = os.path.basename(module_path)
        output_file = os.path.join(output_dir, f"{module_name}.zip")
        
        return self.create_zip(module_path, output_file)
        
    def create_compare_results_zip(self, source_dir: str, 
                                 output_file: str = None,
                                 include_excel: bool = True,
                                 include_source_files: bool = True) -> str:
        """
        建立比較結果的 ZIP 檔案
        
        Args:
            source_dir: 來源目錄
            output_file: 輸出檔案路徑
            include_excel: 是否包含 Excel 報表
            include_source_files: 是否包含原始檔案
            
        Returns:
            ZIP 檔案路徑
        """
        include_patterns = []
        exclude_patterns = []
        
        # 設定包含/排除模式
        if include_excel:
            include_patterns.append('.xlsx')
            
        if include_source_files:
            include_patterns.extend(['.txt', '.xml'])
        else:
            exclude_patterns.extend(['.txt', '.xml'])
            
        return self.create_zip(source_dir, output_file, include_patterns, exclude_patterns)
        
    def extract_zip(self, zip_file: str, extract_to: str = None) -> str:
        """
        解壓縮 ZIP 檔案
        
        Args:
            zip_file: ZIP 檔案路徑
            extract_to: 解壓縮目標目錄
            
        Returns:
            解壓縮目錄路徑
        """
        if not extract_to:
            extract_to = os.path.splitext(zip_file)[0]
            
        try:
            self.logger.info(f"解壓縮: {zip_file} -> {extract_to}")
            
            with zipfile.ZipFile(zip_file, 'r') as zipf:
                zipf.extractall(extract_to)
                
            self.logger.info("解壓縮完成")
            return extract_to
            
        except Exception as e:
            self.logger.error(f"解壓縮失敗: {str(e)}")
            raise
            
    def list_zip_contents(self, zip_file: str) -> List[str]:
        """
        列出 ZIP 檔案內容
        
        Args:
            zip_file: ZIP 檔案路徑
            
        Returns:
            檔案列表
        """
        try:
            with zipfile.ZipFile(zip_file, 'r') as zipf:
                return zipf.namelist()
        except Exception as e:
            self.logger.error(f"讀取 ZIP 內容失敗: {str(e)}")
            raise