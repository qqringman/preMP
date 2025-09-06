#!/usr/bin/env python3
"""
Manifest 取代工具 - Debug版本
"""

import re
import os
import sys
import argparse
from typing import List, Dict, Tuple
import shutil
from datetime import datetime


class ManifestManager:
    def __init__(self):
        self.source_lines = []
        self.dest_lines = []
        
    def load_manifest_lines(self, file_path: str) -> List[str]:
        """載入 manifest.xml 文件，按行返回"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            return lines
        except Exception as e:
            print(f"載入文件錯誤: {e}")
            return None
    
    def get_user_input_paths(self) -> Tuple[str, str, str]:
        """取得用戶輸入的文件路徑和輸出資料夾"""
        print("Manifest 取代工具")
        print("="*50)
        
        while True:
            source_path = input("請輸入來源 manifest.xml 的路徑: ").strip()
            if not source_path:
                print("請輸入檔案路徑")
                continue
            if os.path.exists(source_path):
                break
            print(f"文件不存在 '{source_path}'，請重新輸入")
        
        while True:
            dest_path = input("請輸入目的 manifest.xml 的路徑: ").strip()
            if not dest_path:
                print("請輸入檔案路徑")
                continue
            if os.path.exists(dest_path):
                break
            print(f"文件不存在 '{dest_path}'，請重新輸入")
        
        output_folder = input("請輸入輸出資料夾路徑 (預設: ./output): ").strip()
        if not output_folder:
            output_folder = "./output"
            print(f"使用預設輸出路徑: {output_folder}")
        
        return source_path, dest_path, output_folder
    
    def ensure_output_dir(self, output_folder: str):
        """確保輸出資料夾存在"""
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
    
    def copy_files_to_output(self, source_path: str, dest_path: str, output_folder: str) -> Dict[str, str]:
        """複製來源和目的檔案到輸出資料夾"""
        copied_files = {}
        self.ensure_output_dir(output_folder)
        
        source_filename = os.path.basename(source_path)
        source_copy_path = os.path.join(output_folder, source_filename)
        shutil.copy2(source_path, source_copy_path)
        copied_files['source'] = source_copy_path
        
        dest_filename = os.path.basename(dest_path)
        dest_copy_path = os.path.join(output_folder, dest_filename)
        shutil.copy2(dest_path, dest_copy_path)
        copied_files['dest'] = dest_copy_path
        
        print(f"已複製檔案到輸出資料夾")
        return copied_files
    
    def get_name_pattern_selection(self) -> str:
        """取得 name 匹配模式"""
        print("\n" + "="*60)
        print("請選擇 project name 匹配方式")
        print("="*60)
        print("1. 預設模式: 匹配包含 'tvconfigs_prebuilt' 的 name")
        print("2. 自定義正規表達式")
        print("3. 返回上層")
        
        while True:
            choice = input("\n請選擇 (1-3): ").strip()
            
            if choice == '1':
                pattern = ".*tvconfigs_prebuilt.*"
                print(f"使用預設模式: {pattern}")
                return pattern
            elif choice == '2':
                pattern = input("請輸入正規表達式 (例如: .*tvconfigs_prebuilt.*): ").strip()
                if not pattern:
                    print("請輸入有效的正規表達式")
                    continue
                
                try:
                    re.compile(pattern)
                    print(f"使用自定義模式: {pattern}")
                    return pattern
                except re.error as e:
                    print(f"正規表達式錯誤: {e}")
                    continue
            elif choice == '3':
                return None
            else:
                print("請輸入 1-3")
    
    def compare_and_show_differences(self, source_matches: List[Dict], dest_matches: List[Dict]):
        """比較並顯示差異 - 簡化版"""
        dest_by_key = {p['unique_key']: p for p in dest_matches}
        
        differences_found = False
        for source_project in source_matches:
            key = source_project['unique_key']
            if key in dest_by_key:
                dest_project = dest_by_key[key]
                
                if source_project['revision'] != dest_project['revision']:
                    differences_found = True
                    print(f"發現差異: {source_project['name']}")
                    print(f"  路徑: {source_project['path']}")
                    print(f"  來源版本: {source_project['revision']}")
                    print(f"  目的版本: {dest_project['revision']}")
                # 移除相同項目的打印
        
        return differences_found
    
    def process_lines(self, dest_lines: List[str], source_matches: List[Dict], dest_matches: List[Dict]) -> List[str]:    
        """最終版替換邏輯 - 添加新增項目統計"""
        result_lines = dest_lines.copy()
        dest_by_key = {p['unique_key']: p for p in dest_matches}
        
        replacements = []
        additions = []
        
        # 分類替換和新增項目
        for source_project in source_matches:
            key = source_project['unique_key']
            if key in dest_by_key:
                dest_project = dest_by_key[key]
                replacements.append({
                    'source': source_project,
                    'dest': dest_project
                })
            else:
                additions.append(source_project)
        
        print(f"\n處理統計:")
        print(f"  替換項目: {len(replacements)} 個")
        print(f"  新增項目: {len(additions)} 個")
        
        # 顯示新增項目詳細信息
        if additions:
            print(f"\n新增項目列表:")
            for i, source_project in enumerate(additions, 1):
                print(f"  {i}. {source_project['name']}")
                print(f"     路徑: {source_project['path']}")
                print(f"     版本: {source_project['revision']}")
        
        # 按行號從大到小排序執行替換
        replacements.sort(key=lambda x: x['dest']['start_line_idx'], reverse=True)
        
        # 執行替換
        for replacement in replacements:
            source_proj = replacement['source']
            dest_proj = replacement['dest']
            
            start_idx = dest_proj['start_line_idx']
            end_idx = dest_proj['end_line_idx']
            
            # 直接替換
            result_lines[start_idx:end_idx+1] = source_proj['lines']
        
        # 處理新增項目
        if additions:
            # 找到最後一個 project 的位置
            last_project_end = -1
            for i in range(len(result_lines) - 1, -1, -1):
                line = result_lines[i].strip()
                if '/>' in line or '</project>' in line:
                    for j in range(i, -1, -1):
                        if '<project ' in result_lines[j]:
                            last_project_end = i
                            break
                    if last_project_end != -1:
                        break
            
            if last_project_end != -1:
                insert_pos = last_project_end + 1
                for source_project in additions:
                    result_lines[insert_pos:insert_pos] = source_project['lines']
                    insert_pos += len(source_project['lines'])
        
        return result_lines
    
    def generate_output_filename(self, dest_path: str) -> str:
        """生成輸出檔案名稱"""
        base_name = os.path.splitext(os.path.basename(dest_path))[0]
        return f"{base_name}_overwrite.xml"
    
    def save_lines(self, lines: List[str], file_path: str):
        """保存行列表到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            print(f"已保存修改後的檔案")
        except Exception as e:
            print(f"保存文件錯誤: {e}")
            raise

    def debug_first_match(self, source_matches: List[Dict], dest_matches: List[Dict], dest_lines: List[str]):
        """debug第一個匹配項目的完整過程"""
        if not source_matches or not dest_matches:
            print("沒有匹配項目可以debug")
            return
        
        dest_by_key = {p['unique_key']: p for p in dest_matches}
        
        # 找第一個有對應關係的項目
        for source_proj in source_matches:
            key = source_proj['unique_key']
            if key in dest_by_key:
                dest_proj = dest_by_key[key]
                
                print(f"\n=== DEBUG 第一個匹配項目 ===")
                print(f"項目名稱: {source_proj['name']}")
                print(f"項目路徑: {source_proj['path']}")
                print(f"複合鍵: {key}")
                print(f"目的檔案行號: {dest_proj['start_line_idx']}-{dest_proj['end_line_idx']}")
                
                # 顯示目的檔案原始內容
                print(f"\n目的檔案原始內容:")
                for i in range(dest_proj['start_line_idx'], dest_proj['end_line_idx'] + 1):
                    print(f"  行{i}: {dest_lines[i].rstrip()}")
                
                # 顯示來源檔案內容
                print(f"\n來源檔案內容:")
                for i, line in enumerate(source_proj['lines']):
                    print(f"  來源行{i}: {line.rstrip()}")
                
                # 模擬替換
                test_lines = dest_lines.copy()
                start_idx = dest_proj['start_line_idx']
                end_idx = dest_proj['end_line_idx']
                
                print(f"\n執行模擬替換...")
                print(f"替換前行數: {len(test_lines)}")
                print(f"替換範圍: 行{start_idx}到{end_idx} (共{end_idx-start_idx+1}行)")
                print(f"替換成: {len(source_proj['lines'])}行")
                
                test_lines[start_idx:end_idx+1] = source_proj['lines']
                
                print(f"替換後行數: {len(test_lines)}")
                print(f"替換後內容:")
                for i in range(start_idx, start_idx + len(source_proj['lines'])):
                    if i < len(test_lines):
                        print(f"  行{i}: {test_lines[i].rstrip()}")
                
                # 檢查是否真的不同
                original_content = ''.join(dest_lines[start_idx:end_idx+1])
                new_content = ''.join(source_proj['lines'])
                
                print(f"\n內容比較:")
                print(f"原始內容長度: {len(original_content)}")
                print(f"新內容長度: {len(new_content)}")
                print(f"內容是否相同: {original_content == new_content}")
                
                if original_content != new_content:
                    print(f"發現差異!")
                    # 找出具體差異
                    for i, (orig_char, new_char) in enumerate(zip(original_content, new_content)):
                        if orig_char != new_char:
                            print(f"  位置{i}: 原始'{repr(orig_char)}' vs 新'{repr(new_char)}'")
                            break
                else:
                    print(f"警告: 內容完全相同，替換無效果")
                
                break
                
    def process_with_params(self, source_path: str, dest_path: str, output_folder: str, 
                      name_pattern: str = None, interactive: bool = True) -> bool:
        """簡化版處理流程"""
        try:
            print("\n" + "="*70)
            print("Manifest 取代工具")
            print("="*70)
            
            # 載入文件
            self.source_lines = self.load_manifest_lines(source_path)
            self.dest_lines = self.load_manifest_lines(dest_path)
            
            if not self.source_lines or not self.dest_lines:
                print("文件載入失敗")
                return False
            
            # 複製檔案
            copied_files = self.copy_files_to_output(source_path, dest_path, output_folder)
            
            # 取得匹配模式
            if interactive and not name_pattern:
                name_pattern = self.get_name_pattern_selection()
                if not name_pattern:
                    print("操作已取消")
                    return False
            elif not name_pattern:
                name_pattern = ".*tvconfigs_prebuilt.*"
            
            # 找到匹配項目
            print(f"\n分析檔案...")
            source_matches = self.find_project_blocks(self.source_lines, name_pattern)
            dest_matches = self.find_project_blocks(self.dest_lines, name_pattern)
            
            if not source_matches:
                print("來源檔案中沒有找到匹配的 projects")
                return False
            
            print(f"使用匹配模式: {name_pattern}")
            print(f"來源檔案找到: {len(source_matches)} 個匹配項目")
            print(f"目的檔案找到: {len(dest_matches)} 個匹配項目")
            
            # 執行替換
            result_lines = self.process_lines(self.dest_lines, source_matches, dest_matches)
            
            # 保存結果
            output_filename = self.generate_output_filename(dest_path)
            output_path = os.path.join(output_folder, output_filename)
            
            self.save_lines(result_lines, output_path)
            
            print(f"\n處理完成:")
            print(f"  輸出檔案: {output_path}")
            print(f"  已完成所有替換和新增操作")
            
            return True
            
        except Exception as e:
            print(f"處理過程發生錯誤: {str(e)}")
            return False

    def find_project_blocks(self, lines: List[str], name_pattern: str) -> List[Dict]:
        """簡化版 project 搜尋"""
        matching_projects = []
        name_regex = re.compile(name_pattern, re.IGNORECASE)
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('<project '):
                project_lines = []
                start_line_idx = i
                
                while i < len(lines):
                    current_line = lines[i]
                    project_lines.append(current_line)
                    
                    if '/>' in current_line or '</project>' in current_line:
                        break
                    i += 1
                
                full_project_text = ''.join(project_lines)
                
                # 提取資訊
                name_match = re.search(r'name\s*=\s*["\']([^"\']*)["\']', full_project_text)
                path_match = re.search(r'path\s*=\s*["\']([^"\']*)["\']', full_project_text)
                revision_match = re.search(r'revision\s*=\s*["\']([^"\']*)["\']', full_project_text)
                
                if name_match:
                    project_name = name_match.group(1)
                    project_path = path_match.group(1) if path_match else ""
                    project_revision = revision_match.group(1) if revision_match else ""
                    
                    if name_regex.search(project_name):
                        unique_key = f"{project_name}###{project_path}"
                        
                        matching_projects.append({
                            'name': project_name,
                            'path': project_path,
                            'revision': project_revision,
                            'unique_key': unique_key,
                            'lines': project_lines,
                            'start_line_idx': start_line_idx,
                            'end_line_idx': i,
                            'full_text': full_project_text.strip()
                        })
            
            i += 1
        
        return matching_projects
            
    def run(self):
        """主要執行流程"""
        try:
            source_path, dest_path, output_folder = self.get_user_input_paths()
            success = self.process_with_params(source_path, dest_path, output_folder, interactive=True)
            if not success:
                print("處理失敗")
        except KeyboardInterrupt:
            print("\n\n程式被用戶中斷")
        except Exception as e:
            print(f"程式執行錯誤: {e}")


def main():
    """主函數"""
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description='Manifest 取代工具')
        parser.add_argument('source', help='來源 manifest.xml 檔案路徑')
        parser.add_argument('dest', help='目的 manifest.xml 檔案路徑')
        parser.add_argument('-o', '--output', default='./output', help='輸出資料夾路徑')
        parser.add_argument('-p', '--pattern', default='.*tvconfigs_prebuilt.*', help='name 匹配的正規表達式')
        parser.add_argument('--non-interactive', action='store_true', help='非互動模式')
        
        args = parser.parse_args()
        
        manager = ManifestManager()
        success = manager.process_with_params(
            source_path=args.source,
            dest_path=args.dest,
            output_folder=args.output,
            name_pattern=args.pattern,
            interactive=not args.non_interactive
        )
        
        sys.exit(0 if success else 1)
    else:
        manager = ManifestManager()
        manager.run()


if __name__ == "__main__":
    main()