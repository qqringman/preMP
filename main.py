"""
SFTP 下載與比較系統 - 主程式
提供互動式介面和命令列參數支援
"""
import os
import sys
import argparse
import shutil
from typing import Optional
import utils
import config
from sftp_downloader import SFTPDownloader
from file_comparator import FileComparator
from zip_packager import ZipPackager

logger = utils.setup_logger(__name__)

class SFTPCompareSystem:
    """SFTP 下載與比較系統主類別"""
    
    def __init__(self):
        self.logger = logger
        self.downloader = None
        self.comparator = FileComparator()
        self.packager = ZipPackager()
        
    def interactive_mode(self):
        """互動式模式"""
        while True:
            print("\n" + "="*50)
            print("SFTP 下載與比較系統")
            print("="*50)
            print("1. 下載 SFTP 檔案並產生報表")
            print("2. 比較模組檔案差異")
            print("3. 打包比對結果成 ZIP")
            print("4. 測試 SFTP 連線")
            print("5. 清除暫存檔案")
            print("6. 退出")
            print("="*50)
            
            choice = input("請選擇功能 (1-6): ").strip()
            
            if choice == '1':
                self._interactive_download()
            elif choice == '2':
                self._interactive_compare()
            elif choice == '3':
                self._interactive_package()
            elif choice == '4':
                self._test_connection()
            elif choice == '5':
                self._clean_temp_files()
            elif choice == '6':
                print("感謝使用，再見！")
                break
            else:
                print("無效的選擇，請重新輸入")
                
    def _interactive_download(self):
        """互動式下載功能"""
        print("\n--- 下載 SFTP 檔案 ---")
        
        # 列出當前目錄的 xlsx 檔案
        xlsx_files = [f for f in os.listdir('.') if f.endswith('.xlsx')]
        
        if xlsx_files:
            print("\n當前目錄的 Excel 檔案：")
            for i, file in enumerate(xlsx_files, 1):
                print(f"{i}. {file}")
            print("\n您可以輸入檔案編號或完整路徑")
        
        # 取得 Excel 檔案路徑（預設選 1）
        excel_input = input("請輸入 Excel 檔案路徑或編號 (預設: 1): ").strip()
        
        # 如果空白且有 xlsx 檔案，預設選第一個
        if not excel_input and xlsx_files:
            excel_input = "1"
        
        # 檢查是否輸入編號
        if excel_input.isdigit() and xlsx_files:
            index = int(excel_input) - 1
            if 0 <= index < len(xlsx_files):
                excel_path = xlsx_files[index]
            else:
                print(f"錯誤：編號超出範圍")
                return
        else:
            excel_path = excel_input
        
        if not os.path.exists(excel_path):
            print(f"錯誤：檔案不存在 - {excel_path}")
            return
            
        # 取得 SFTP 設定
        use_default = input("使用預設 SFTP 設定？(Y/n): ").strip().lower()
        
        if use_default != 'n':
            host = config.SFTP_HOST
            port = config.SFTP_PORT
            username = config.SFTP_USERNAME
            password = config.SFTP_PASSWORD
        else:
            host = input(f"SFTP 伺服器 (預設: {config.SFTP_HOST}): ").strip() or config.SFTP_HOST
            port_str = input(f"SFTP 連接埠 (預設: {config.SFTP_PORT}): ").strip()
            port = int(port_str) if port_str else config.SFTP_PORT
            username = input(f"使用者名稱 (預設: {config.SFTP_USERNAME}): ").strip() or config.SFTP_USERNAME
            password = input("密碼: ").strip() or config.SFTP_PASSWORD
            
        # 取得輸出目錄
        output_dir = input(f"輸出目錄 (預設: {config.DEFAULT_OUTPUT_DIR}): ").strip()
        output_dir = output_dir or config.DEFAULT_OUTPUT_DIR
        
        # 詢問是否要跳過已存在的檔案
        skip_existing = input("跳過已存在的檔案？(Y/n): ").strip().lower() != 'n'
        
        # 執行下載
        try:
            # 暫時修改設定
            original_skip = config.SKIP_EXISTING_FILES
            config.SKIP_EXISTING_FILES = skip_existing
            
            try:
                self.downloader = SFTPDownloader(host, port, username, password)
                report_path = self.downloader.download_from_excel(excel_path, output_dir)
                print(f"\n下載完成！報表已儲存至: {report_path}")
            finally:
                # 恢復原始設定
                config.SKIP_EXISTING_FILES = original_skip
                
        except Exception as e:
            print(f"\n錯誤：{str(e)}")
            
    def _interactive_compare(self):
        """互動式比較功能"""
        print("\n--- 比較模組檔案差異 ---")
        
        # 取得來源目錄
        default_source = config.DEFAULT_OUTPUT_DIR.replace('./', '')  # 移除 ./
        source_dir = input(f"請輸入來源目錄路徑 (預設: {default_source}): ").strip()
        source_dir = source_dir or default_source
        
        if not os.path.exists(source_dir):
            print(f"錯誤：目錄不存在 - {source_dir}")
            return
            
        # 取得輸出目錄
        default_output = config.DEFAULT_COMPARE_DIR.replace('./', '')  # 移除 ./
        output_dir = input(f"輸出目錄 (預設: {default_output}): ").strip()
        output_dir = output_dir or default_output
        
        # 詢問要使用哪個資料夾作為 base
        print("\n選擇要作為基準(base)的資料夾類型：")
        print("1. 預設 (RDDB-XXX)")
        print("2. premp (RDDB-XXX-premp)")
        print("3. wave (RDDB-XXX-wave)")
        print("4. wave.backup (RDDB-XXX-wave.backup)")
        print("5. 自動選擇 (使用第一個資料夾)")
        
        choice = input("\n請選擇 (1-5，預設: 1): ").strip()
        
        # 如果空白，預設選 1
        if not choice:
            choice = '1'
        
        base_folder_suffix = None
        if choice == '1':
            base_folder_suffix = 'default'
        elif choice == '2':
            base_folder_suffix = 'premp'
        elif choice == '3':
            base_folder_suffix = 'wave'
        elif choice == '4':
            base_folder_suffix = 'wave.backup'
        
        # 執行比較
        try:
            compare_files = self.comparator.compare_all_modules(source_dir, output_dir, base_folder_suffix)
            print(f"\n比較完成！產生了 {len(compare_files)} 個比較報表")
            print(f"整合報表已儲存至: {os.path.join(output_dir, 'all_compare.xlsx')}")
        except Exception as e:
            print(f"\n錯誤：{str(e)}")
            
    def _interactive_package(self):
        """互動式打包功能"""
        print("\n--- 打包比對結果成 ZIP ---")
        
        # 讓使用者選擇要打包的目錄
        print("\n選擇要打包的目錄：")
        print("1. downloads (下載的原始檔案)")
        print("2. compare_results (比較結果報表)")
        print("3. downloads + compare_results (全部打包)")
        print("4. 自訂目錄")
        
        choice = input("\n請選擇 (1-4，預設: 3): ").strip()
        
        # 如果空白，預設選 3（全部打包）
        if not choice:
            choice = '3'
        
        # 根據選擇決定來源目錄
        if choice == '1':
            source_dir = config.DEFAULT_OUTPUT_DIR.replace('./', '')
            print(f"將打包: {source_dir}")
            default_name = f"downloads_{utils.get_timestamp()}.zip"
        elif choice == '2':
            source_dir = config.DEFAULT_COMPARE_DIR.replace('./', '')
            print(f"將打包: {source_dir}")
            default_name = f"compare_results_{utils.get_timestamp()}.zip"
        elif choice == '3':
            # 打包多個目錄
            downloads_dir = config.DEFAULT_OUTPUT_DIR.replace('./', '')
            compare_dir = config.DEFAULT_COMPARE_DIR.replace('./', '')
            print(f"將打包: {downloads_dir} 和 {compare_dir}")
            default_name = f"all_results_{utils.get_timestamp()}.zip"
        elif choice == '4':
            source_dir = input("請輸入自訂目錄路徑: ").strip()
            default_name = f"package_{utils.get_timestamp()}.zip"
        else:
            print("無效的選擇")
            return
        
        # 檢查目錄是否存在
        if choice == '3':
            # 檢查兩個目錄
            missing_dirs = []
            if not os.path.exists(downloads_dir):
                missing_dirs.append(downloads_dir)
            if not os.path.exists(compare_dir):
                missing_dirs.append(compare_dir)
            
            if missing_dirs:
                print(f"錯誤：以下目錄不存在 - {', '.join(missing_dirs)}")
                return
        else:
            # 檢查單一目錄
            if not os.path.exists(source_dir):
                print(f"錯誤：目錄不存在 - {source_dir}")
                return
            
        # 詢問打包選項
        include_excel = input("包含 Excel 報表？(Y/n): ").strip().lower() != 'n'
        include_source = input("包含原始檔案 (txt/xml)？(Y/n): ").strip().lower() != 'n'
        
        # 取得輸出檔名
        zip_name = input(f"ZIP 檔案名稱 (預設: {default_name}): ").strip()
        zip_name = zip_name or default_name
        
        # 確保 ZIP 輸出目錄存在
        zip_output_dir = config.DEFAULT_ZIP_DIR
        if not os.path.exists(zip_output_dir):
            os.makedirs(zip_output_dir)
            print(f"已建立輸出目錄: {zip_output_dir}")
        
        # 完整的 ZIP 檔案路徑
        zip_path = os.path.join(zip_output_dir, zip_name)
        
        # 執行打包
        try:
            if choice == '3':
                # 打包多個目錄
                # 需要建立臨時目錄來合併內容
                import tempfile
                import shutil
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    # 複製 downloads 目錄內容
                    if os.path.exists(downloads_dir):
                        shutil.copytree(downloads_dir, os.path.join(temp_dir, "downloads"))
                    
                    # 複製 compare_results 目錄內容
                    if os.path.exists(compare_dir):
                        shutil.copytree(compare_dir, os.path.join(temp_dir, "compare_results"))
                    
                    # 打包臨時目錄
                    zip_path = self.packager.create_compare_results_zip(
                        temp_dir, zip_path, include_excel, include_source
                    )
            else:
                # 打包單一目錄
                zip_path = self.packager.create_compare_results_zip(
                    source_dir, zip_path, include_excel, include_source
                )
                
            print(f"\n打包完成！ZIP 檔案已儲存至: {zip_path}")
        except Exception as e:
            print(f"\n錯誤：{str(e)}")
            
    def _test_connection(self):
        """測試 SFTP 連線"""
        print("\n--- 測試 SFTP 連線 ---")
        
        # 取得 SFTP 設定
        use_default = input("使用預設 SFTP 設定？(Y/n): ").strip().lower()
        
        if use_default != 'n':
            host = config.SFTP_HOST
            port = config.SFTP_PORT
            username = config.SFTP_USERNAME
            password = config.SFTP_PASSWORD
        else:
            host = input(f"SFTP 伺服器 (預設: {config.SFTP_HOST}): ").strip() or config.SFTP_HOST
            port_str = input(f"SFTP 連接埠 (預設: {config.SFTP_PORT}): ").strip()
            port = int(port_str) if port_str else config.SFTP_PORT
            username = input(f"使用者名稱 (預設: {config.SFTP_USERNAME}): ").strip() or config.SFTP_USERNAME
            password = input("密碼: ").strip() or config.SFTP_PASSWORD
            
        # 測試連線
        try:
            self.downloader = SFTPDownloader(host, port, username, password)
            if self.downloader.test_connection():
                print("\n✓ SFTP 連線測試成功！")
            else:
                print("\n✗ SFTP 連線測試失敗！")
        except Exception as e:
            print(f"\n✗ SFTP 連線測試失敗：{str(e)}")
            
    def _clean_temp_files(self):
        """清除暫存檔案"""
        print("\n--- 清除暫存檔案 ---")
        
        # 定義要清除的目錄
        temp_dirs = [
            config.DEFAULT_OUTPUT_DIR,
            config.DEFAULT_COMPARE_DIR,
            config.DEFAULT_ZIP_DIR
        ]
        
        print("\n將清除以下目錄：")
        for dir_path in temp_dirs:
            if os.path.exists(dir_path):
                print(f"- {dir_path}")
        
        confirm = input("\n確定要清除這些目錄嗎？(y/N): ").strip().lower()
        
        if confirm == 'y':
            removed_count = 0
            for dir_path in temp_dirs:
                if os.path.exists(dir_path):
                    try:
                        shutil.rmtree(dir_path)
                        print(f"✓ 已刪除: {dir_path}")
                        removed_count += 1
                    except Exception as e:
                        print(f"✗ 刪除失敗 {dir_path}: {str(e)}")
            
            if removed_count > 0:
                print(f"\n清除完成！已刪除 {removed_count} 個目錄")
            else:
                print("\n沒有需要清除的目錄")
        else:
            print("\n取消清除操作")
            
    def command_line_mode(self, args):
        """命令列模式"""
        if args.function == 'download':
            self._cmd_download(args)
        elif args.function == 'compare':
            self._cmd_compare(args)
        elif args.function == 'package':
            self._cmd_package(args)
            
    def _cmd_download(self, args):
        """命令列下載功能"""
        try:
            # 如果有 force 參數，暫時修改設定
            original_skip = config.SKIP_EXISTING_FILES
            if args.force:
                config.SKIP_EXISTING_FILES = False
                
            try:
                self.downloader = SFTPDownloader(
                    args.host, args.port, args.username, args.password
                )
                report_path = self.downloader.download_from_excel(
                    args.excel, args.output_dir
                )
                print(f"下載完成！報表已儲存至: {report_path}")
            finally:
                # 恢復原始設定
                config.SKIP_EXISTING_FILES = original_skip
                
        except Exception as e:
            logger.error(f"下載失敗：{str(e)}")
            sys.exit(1)
            
    def _cmd_compare(self, args):
        """命令列比較功能"""
        try:
            compare_files = self.comparator.compare_all_modules(
                args.source_dir, args.output_dir, args.base_folder
            )
            print(f"比較完成！產生了 {len(compare_files)} 個比較報表")
        except Exception as e:
            logger.error(f"比較失敗：{str(e)}")
            sys.exit(1)
            
    def _cmd_package(self, args):
        """命令列打包功能"""
        try:
            zip_path = self.packager.create_zip(
                args.source_dir, args.zip_name
            )
            print(f"打包完成！ZIP 檔案已儲存至: {zip_path}")
        except Exception as e:
            logger.error(f"打包失敗：{str(e)}")
            sys.exit(1)

def create_parser():
    """建立命令列參數解析器"""
    parser = argparse.ArgumentParser(
        description='SFTP 下載與比較系統',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 建立子命令
    subparsers = parser.add_subparsers(dest='function', help='功能選擇')
    
    # 下載功能
    download_parser = subparsers.add_parser('download', help='下載 SFTP 檔案')
    download_parser.add_argument('--excel', required=True, help='Excel 檔案路徑')
    download_parser.add_argument('--host', default=config.SFTP_HOST, help='SFTP 伺服器')
    download_parser.add_argument('--port', type=int, default=config.SFTP_PORT, help='SFTP 連接埠')
    download_parser.add_argument('--username', default=config.SFTP_USERNAME, help='使用者名稱')
    download_parser.add_argument('--password', default=config.SFTP_PASSWORD, help='密碼')
    download_parser.add_argument('--output-dir', default=config.DEFAULT_OUTPUT_DIR, help='輸出目錄')
    download_parser.add_argument('--force', action='store_true', help='強制重新下載已存在的檔案')
    
    # 比較功能
    compare_parser = subparsers.add_parser('compare', help='比較檔案差異')
    compare_parser.add_argument('--source-dir', required=True, help='來源目錄')
    compare_parser.add_argument('--output-dir', help='輸出目錄（預設：與來源目錄相同）')
    compare_parser.add_argument('--base-folder', choices=['default', 'premp', 'wave', 'wave.backup'], 
                               help='選擇作為基準的資料夾類型')
    
    # 打包功能
    package_parser = subparsers.add_parser('package', help='打包成 ZIP')
    package_parser.add_argument('--source-dir', required=True, help='要打包的目錄')
    package_parser.add_argument('--zip-name', help='ZIP 檔案名稱')
    
    return parser

def main():
    """主程式進入點"""
    parser = create_parser()
    args = parser.parse_args()
    
    system = SFTPCompareSystem()
    
    if args.function:
        # 命令列模式
        system.command_line_mode(args)
    else:
        # 互動式模式
        system.interactive_mode()

if __name__ == '__main__':
    main()