"""
Gen Mapping Excel 主程式
整合功能1和功能2的主要介面
"""
import os
import sys
import shutil
from typing import Optional

# 加入父目錄到路徑
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from vp_libs.feature1_processor import Feature1Processor
from vp_libs.feature2_processor import Feature2Processor
import utils
import config

logger = utils.setup_logger(__name__)

class GenMappingExcel:
    """Gen Mapping Excel 主類別"""
    
    def __init__(self):
        self.logger = logger
        self.feature1_processor = Feature1Processor()
        self.feature2_processor = Feature2Processor()
        
    def process_chip_mapping(self, 
                            input_file: str = None,
                            db_param: str = 'all',
                            filter_param: str = 'all',
                            output_dir: str = './output') -> str:
        """
        功能1: 處理晶片映射表
        
        Args:
            input_file: 輸入的 all_chip_mapping_table.xlsx 路徑
            db_param: DB 參數（例如: DB2302#196,DB2686#168）
            filter_param: 過濾參數（例如: master_vs_premp, mac7p,merlin7）
            output_dir: 輸出目錄
            
        Returns:
            輸出檔案路徑
        """
        try:
            # 使用預設檔案名稱如果沒有指定
            if not input_file:
                input_file = config.ALL_CHIP_MAPPING_TABLE
                
            if not os.path.exists(input_file):
                raise FileNotFoundError(f"找不到輸入檔案: {input_file}")
            
            self.logger.info("=" * 50)
            self.logger.info("執行功能1: 處理晶片映射表")
            self.logger.info(f"輸入檔案: {input_file}")
            self.logger.info(f"DB 參數: {db_param}")
            self.logger.info(f"過濾參數: {filter_param}")
            self.logger.info(f"輸出目錄: {output_dir}")
            self.logger.info("=" * 50)
            
            # 執行處理
            output_file = self.feature1_processor.process(
                input_file=input_file,
                db_param=db_param,
                filter_param=filter_param,
                output_dir=output_dir
            )
            
            self.logger.info(f"功能1執行完成: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"功能1執行失敗: {str(e)}")
            raise
            
    def process_prebuild_mapping(self,
                                input_files: str,
                                filter_param: str = 'all',  # 改用 filter_param
                                output_dir: str = './output') -> str:
        """
        功能2: 處理 Prebuild 映射
        
        Args:
            input_files: 輸入檔案路徑（逗號分隔的兩個檔案）
            filter_param: 過濾參數（例如: master_vs_premp, mac7p）
            output_dir: 輸出目錄
            
        Returns:
            輸出檔案路徑
        """
        try:
            self.logger.info("=" * 50)
            self.logger.info("執行功能2: 處理 Prebuild 映射")
            self.logger.info(f"輸入檔案: {input_files}")
            self.logger.info(f"過濾參數: {filter_param}")
            self.logger.info(f"輸出目錄: {output_dir}")
            self.logger.info("=" * 50)
            
            # 執行處理
            output_file = self.feature2_processor.process(
                input_files=input_files,
                filter_param=filter_param,  # 傳遞 filter_param
                output_dir=output_dir
            )
            
            self.logger.info(f"功能2執行完成: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"功能2執行失敗: {str(e)}")
            raise
            
    def validate_inputs(self, mode: str, **kwargs) -> bool:
        """
        驗證輸入參數
        
        Args:
            mode: 執行模式（feature1 或 feature2）
            **kwargs: 相關參數
            
        Returns:
            是否驗證通過
        """
        try:
            if mode == 'feature1':
                # 驗證功能1的輸入
                input_file = kwargs.get('input_file', config.ALL_CHIP_MAPPING_TABLE)
                if not os.path.exists(input_file):
                    self.logger.error(f"輸入檔案不存在: {input_file}")
                    return False
                    
            elif mode == 'feature2':
                # 驗證功能2的輸入
                input_files = kwargs.get('input_files', '')
                if not input_files:
                    self.logger.error("必須提供輸入檔案")
                    return False
                    
                files = input_files.split(',')
                if len(files) != 2:
                    self.logger.error("功能2需要恰好 2 個輸入檔案")
                    return False
                    
                for file in files:
                    file = file.strip()
                    if not os.path.exists(file):
                        self.logger.error(f"輸入檔案不存在: {file}")
                        return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"驗證失敗: {str(e)}")
            return False