"""
命令列介面
提供命令列操作功能
"""
import argparse
import sys
from gen_mapping_excel import GenMappingExcel
import utils

logger = utils.setup_logger(__name__)

class CLIInterface:
    """命令列介面類別"""
    
    def __init__(self):
        self.gen_mapping = GenMappingExcel()
        self.logger = logger
        
    def create_parser(self):
        """建立命令列解析器"""
        parser = argparse.ArgumentParser(
            description='Gen Mapping Excel - 產生映射 Excel 檔案',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        # 建立子命令
        subparsers = parser.add_subparsers(dest='command', help='可用的命令')
        
        # 功能1: chip-mapping
        parser_feature1 = subparsers.add_parser(
            'chip-mapping',
            help='功能1: 處理晶片映射表'
        )
        parser_feature1.add_argument(
            '-i', '--input',
            dest='input_file',
            help='輸入的 all_chip_mapping_table.xlsx 路徑',
            default='all_chip_mapping_table.xlsx'
        )
        parser_feature1.add_argument(
            '-db', '--database',
            dest='db_param',
            help='DB 參數 (例如: DB2302#196,DB2686#168)',
            default='all'
        )
        parser_feature1.add_argument(
            '-filter', '--filter',
            dest='filter_param',
            help='過濾參數 (例如: master_vs_premp, mac7p,merlin7)',
            default='all'
        )
        parser_feature1.add_argument(
            '-o', '--output',
            dest='output_dir',
            help='輸出目錄',
            default='./output'
        )
        
        # 功能2: prebuild-mapping
        parser_feature2 = subparsers.add_parser(
            'prebuild-mapping',
            help='功能2: 處理 Prebuild 映射'
        )
        parser_feature2.add_argument(
            '-i', '--input',
            dest='input_files',
            help='輸入檔案（逗號分隔的兩個檔案）',
            required=True
        )
        parser_feature2.add_argument(
            '-type', '--type',
            dest='compare_type',
            help='比較類型 (master_vs_premp, premp_vs_mp, mp_vs_mpbackup)',
            choices=['master_vs_premp', 'premp_vs_mp', 'mp_vs_mpbackup'],
            default='master_vs_premp'
        )
        parser_feature2.add_argument(
            '-o', '--output',
            dest='output_dir',
            help='輸出目錄',
            default='./output'
        )
        
        # 測試命令
        parser_test = subparsers.add_parser(
            'test',
            help='測試 SFTP 連線'
        )
        
        return parser
        
    def run_feature1(self, args):
        """執行功能1"""
        try:
            # 驗證輸入
            if not self.gen_mapping.validate_inputs(
                mode='feature1',
                input_file=args.input_file,
                filter_param=args.filter_param
            ):
                return False
                
            # 執行處理
            output_file = self.gen_mapping.process_chip_mapping(
                input_file=args.input_file,
                db_param=args.db_param,
                filter_param=args.filter_param,
                output_dir=args.output_dir
            )
            
            print(f"\n成功產生檔案: {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"執行失敗: {str(e)}")
            return False
            
    def run_feature2(self, args):
        """執行功能2"""
        try:
            # 驗證輸入
            if not self.gen_mapping.validate_inputs(
                mode='feature2',
                input_files=args.input_files,
                compare_type=args.compare_type
            ):
                return False
                
            # 執行處理
            output_file = self.gen_mapping.process_prebuild_mapping(
                input_files=args.input_files,
                compare_type=args.compare_type,
                output_dir=args.output_dir
            )
            
            print(f"\n成功產生檔案: {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"執行失敗: {str(e)}")
            return False
            
    def test_connection(self):
        """測試 SFTP 連線"""
        try:
            from sftp_manager import SFTPManager
            
            print("測試 SFTP 連線...")
            manager = SFTPManager()
            manager.connect()
            print("✓ SFTP 連線成功")
            manager.disconnect()
            return True
            
        except Exception as e:
            print(f"✗ SFTP 連線失敗: {str(e)}")
            return False
            
    def run(self):
        """執行主程式"""
        parser = self.create_parser()
        args = parser.parse_args()
        
        if not args.command:
            parser.print_help()
            return
            
        # 執行對應的命令
        if args.command == 'chip-mapping':
            success = self.run_feature1(args)
        elif args.command == 'prebuild-mapping':
            success = self.run_feature2(args)
        elif args.command == 'test':
            success = self.test_connection()
        else:
            print(f"未知的命令: {args.command}")
            parser.print_help()
            success = False
            
        # 返回執行結果
        sys.exit(0 if success else 1)

def main():
    """主程式入口"""
    cli = CLIInterface()
    cli.run()

if __name__ == '__main__':
    main()