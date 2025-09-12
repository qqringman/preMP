#!/usr/bin/env python3
"""
增強版 Manifest 轉換工具 - 支援 XML 和 TXT 檔案
包含配置設定和轉換功能的完整工具
支援將 manifest 檔案在不同的 code line 之間轉換
新增 TXT 檔案 Branch 轉換功能
修正版本：新增 dest-branch、upstream 處理和 upgrade 版本識別
"""

import os
import sys
import argparse
import xml.etree.ElementTree as ET
import re
from typing import Optional, Dict, List, Tuple
import logging

# =====================================
# ===== 配置設定部分 =====
# =====================================

# =====================================
# ===== Android 版本設定 =====
# =====================================

# 📥 當前 Android 版本（用於動態替換）
CURRENT_ANDROID_VERSION = '14'

def get_current_android_version() -> str:
    """取得當前使用的 Android 版本"""
    return CURRENT_ANDROID_VERSION

def get_android_path(template: str) -> str:
    """
    將模板中的 {android_version} 替換為當前版本
    
    Args:
        template: 包含 {android_version} 的模板字符串
        
    Returns:
        替換後的字符串
    """
    return template.format(android_version=CURRENT_ANDROID_VERSION)

def get_default_premp_branch() -> str:
    """取得預設的 premp 分支"""
    return f'realtek/android-{CURRENT_ANDROID_VERSION}/premp.google-refplus'

def get_default_android_master_branch() -> str:
    """取得預設的 Android master 分支"""
    return f'realtek/android-{CURRENT_ANDROID_VERSION}/master'

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
    """
    return template.format(linux_ver=linux_version, android_version=CURRENT_ANDROID_VERSION)

# 🆕 新增：取得前一個 Android 版本（用於 upgrade 邏輯）
def get_current_android_prev_version() -> str:
    """取得前一個 Android 版本號（用於 upgrade 轉換）"""
    current_ver = int(CURRENT_ANDROID_VERSION)
    return str(current_ver - 1)  # 14 -> 13

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

# =====================================
# ===== 專案轉換跳過設定 =====
# =====================================

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

# =====================================
# ===== 自定義專案轉換規則設定 =====
# =====================================

FEATURE_THREE_CUSTOM_CONVERSIONS = {
    'master_to_premp': {
    },
    
    'premp_to_mp': {
    },
    
    'mp_to_mpbackup': {
        # 🆕 支援陣列格式：同一個 name pattern 可以有多個不同的 path 條件
        # 例如：
        # '.*tvconfigs_prebuilt': [
        #     {
        #         'path_pattern': '.*refplus2.*',
        #         'target': 'realtek/android-14/mp.google-refplus.wave.backup.upgrade-11'
        #     }
        # ]
    }
}

# =====================================
# ===== 轉換類型對應的檔案映射 =====
# =====================================

CONVERSION_TYPE_INFO = {
    'master_to_premp': {
        'source_file': 'atv-google-refplus.xml',
        'target_file': 'atv-google-refplus-premp.xml',
        'description': 'Master to PreMP'
    },
    'premp_to_mp': {
        'source_file': 'atv-google-refplus-premp.xml',
        'target_file': 'atv-google-refplus-wave.xml',
        'description': 'PreMP to MP'
    },
    'mp_to_mpbackup': {
        'source_file': 'atv-google-refplus-wave.xml',
        'target_file': 'atv-google-refplus-wave-backup.xml',
        'description': 'MP to MP Backup'
    }
}

# =====================================
# ===== 轉換工具實現部分 =====
# =====================================

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class EnhancedManifestConverter:
    """增強版 Manifest 轉換器 - 支援 XML 和 TXT 檔案，修正版本，支援 dest-branch、upstream 和 upgrade 識別"""
    
    def __init__(self):
        self.logger = logger
        
        # 轉換類型映射
        self.conversion_types = {
            '1': 'master_to_premp',
            '2': 'premp_to_mp', 
            '3': 'mp_to_mpbackup'
        }
        
        # 轉換描述
        self.conversion_descriptions = {
            'master_to_premp': 'Master → PreMP',
            'premp_to_mp': 'PreMP → MP',
            'mp_to_mpbackup': 'MP → MP Backup'
        }
    
    def detect_file_type(self, file_path: str) -> str:
        """偵測檔案類型"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                f.seek(0)
                content = f.read(1000)  # 讀取前1000字符進行判斷
            
            # 檢查是否為 XML 檔案
            if first_line.startswith('<?xml') or '<manifest' in content or '<project' in content:
                return 'xml'
            
            # 檢查是否為 TXT 檔案（包含 Branch: 或 GIT Project:）
            if 'Branch:' in content or 'GIT Project:' in content:
                return 'txt'
            
            # 根據副檔名判斷
            if file_path.lower().endswith('.xml'):
                return 'xml'
            elif file_path.lower().endswith('.txt'):
                return 'txt'
            
            # 預設為 xml
            return 'xml'
            
        except Exception as e:
            self.logger.warning(f"無法偵測檔案類型: {str(e)}")
            return 'xml'  # 預設為 xml
    
    def convert_file(self, input_file: str, conversion_type: str, output_file: str = None) -> bool:
        """
        轉換檔案（支援 XML 和 TXT）
        
        Args:
            input_file: 輸入檔案路徑
            conversion_type: 轉換類型
            output_file: 輸出檔案路徑（可選）
            
        Returns:
            是否轉換成功
        """
        try:
            # 檢查輸入檔案
            if not os.path.exists(input_file):
                self.logger.error(f"輸入檔案不存在: {input_file}")
                return False
            
            # 檢查轉換類型
            if conversion_type not in self.conversion_descriptions:
                self.logger.error(f"不支援的轉換類型: {conversion_type}")
                return False
            
            # 偵測檔案類型
            file_type = self.detect_file_type(input_file)
            self.logger.info(f"偵測到檔案類型: {file_type.upper()}")
            
            # 生成輸出檔案名稱
            if not output_file:
                output_file = self._generate_output_filename(input_file, conversion_type, file_type)
            
            self.logger.info(f"開始轉換: {self.conversion_descriptions[conversion_type]}")
            self.logger.info(f"輸入檔案: {input_file}")
            self.logger.info(f"輸出檔案: {output_file}")
            
            # 根據檔案類型選擇轉換方法
            if file_type == 'xml':
                success = self._convert_xml_file(input_file, conversion_type, output_file)
            elif file_type == 'txt':
                success = self._convert_txt_file(input_file, conversion_type, output_file)
            else:
                self.logger.error(f"不支援的檔案類型: {file_type}")
                return False
            
            if success:
                # 顯示使用說明
                self._show_usage_instructions(conversion_type, output_file, file_type)
            
            return success
            
        except Exception as e:
            self.logger.error(f"轉換失敗: {str(e)}")
            return False
    
    def _convert_xml_file(self, input_file: str, conversion_type: str, output_file: str) -> bool:
        """轉換 XML 檔案（原有邏輯）"""
        try:
            # 讀取XML檔案
            with open(input_file, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # 進行轉換
            converted_content, conversion_info = self._convert_revisions(xml_content, conversion_type)
            
            # 寫入輸出檔案
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(converted_content)
            
            # 顯示轉換統計
            converted_count = sum(1 for info in conversion_info if info.get('changed', False))
            total_count = len(conversion_info)
            
            # 🆕 統計各種轉換類型
            revision_changes = sum(1 for info in conversion_info 
                                 if info.get('converted_revision') != info.get('original_revision'))
            upstream_changes = sum(1 for info in conversion_info 
                                 if info.get('converted_upstream', '') != info.get('original_upstream', ''))
            dest_branch_changes = sum(1 for info in conversion_info 
                                    if info.get('converted_dest_branch', '') != info.get('original_dest_branch', ''))
            
            self.logger.info(f"XML 轉換完成！")
            self.logger.info(f"總專案數: {total_count}")
            self.logger.info(f"有變化的專案: {converted_count}")
            self.logger.info(f"  - revision 轉換: {revision_changes} 個")
            self.logger.info(f"  - upstream 轉換: {upstream_changes} 個")
            self.logger.info(f"  - dest-branch 轉換: {dest_branch_changes} 個")
            self.logger.info(f"未轉換: {total_count - converted_count}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"XML 轉換失敗: {str(e)}")
            return False
    
    def _convert_txt_file(self, input_file: str, conversion_type: str, output_file: str) -> bool:
        """轉換 TXT 檔案（新增功能）"""
        try:
            # 讀取TXT檔案
            with open(input_file, 'r', encoding='utf-8') as f:
                txt_content = f.read()
            
            # 進行轉換
            converted_content, conversion_info = self._convert_txt_branches(txt_content, conversion_type)
            
            # 寫入輸出檔案
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(converted_content)
            
            # 顯示轉換統計
            converted_count = len([info for info in conversion_info if info['changed']])
            total_count = len(conversion_info)
            
            self.logger.info(f"TXT 轉換完成！")
            self.logger.info(f"總 Branch 數: {total_count}")
            self.logger.info(f"已轉換: {converted_count}")
            self.logger.info(f"未轉換: {total_count - converted_count}")
            
            # 詳細轉換記錄
            for info in conversion_info:
                if info['changed']:
                    self.logger.debug(f"轉換: {info['original']} → {info['converted']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"TXT 轉換失敗: {str(e)}")
            return False
    
    def _convert_txt_branches(self, txt_content: str, conversion_type: str) -> Tuple[str, List[Dict]]:
        """轉換 TXT 檔案中的 Branch 資訊"""
        try:
            lines = txt_content.split('\n')
            conversion_info = []
            
            # 逐行處理
            for i, line in enumerate(lines):
                if line.strip().startswith('Branch:'):
                    # 提取 Branch 值
                    branch_match = re.match(r'Branch:\s*(.+)', line.strip())
                    if branch_match:
                        original_branch = branch_match.group(1).strip()
                        
                        # 移除可能的前綴（如 rtk/）
                        clean_branch = original_branch
                        prefix = ''
                        if original_branch.startswith('rtk/'):
                            prefix = 'rtk/'
                            clean_branch = original_branch[4:]  # 移除 'rtk/' 前綴
                        
                        # 應用轉換規則
                        converted_branch = self._convert_single_revision(clean_branch, conversion_type)
                        
                        # 重新加上前綴
                        final_converted_branch = prefix + converted_branch
                        
                        # 記錄轉換信息
                        changed = original_branch != final_converted_branch
                        conversion_info.append({
                            'line_number': i + 1,
                            'original': original_branch,
                            'converted': final_converted_branch,
                            'changed': changed
                        })
                        
                        # 更新行內容
                        if changed:
                            lines[i] = f'Branch: {final_converted_branch}'
                            self.logger.debug(f"第 {i+1} 行轉換: {original_branch} → {final_converted_branch}")
            
            converted_content = '\n'.join(lines)
            return converted_content, conversion_info
            
        except Exception as e:
            self.logger.error(f"TXT Branch 轉換失敗: {str(e)}")
            return txt_content, []
    
    def _generate_output_filename(self, input_file: str, conversion_type: str, file_type: str) -> str:
        """生成輸出檔案名稱"""
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        if file_type == 'xml':
            return f"{base_name}_{conversion_type}_manifest.xml"
        elif file_type == 'txt':
            return f"{base_name}_{conversion_type}_converted.txt"
        else:
            return f"{base_name}_{conversion_type}_converted.{file_type}"
    
    # =====================================
    # ===== XML 轉換相關方法（保持原有邏輯）=====
    # =====================================
    
    def _convert_revisions(self, xml_content: str, conversion_type: str) -> tuple:
        """轉換revisions - 修正版本，支援 dest-branch、upstream 和 upgrade 識別"""
        try:
            self.logger.info(f"開始進行 revision 轉換: {conversion_type}")
            
            # 解析XML
            root = ET.fromstring(xml_content)
            self._current_xml_root = root  # 供自定義轉換規則使用
            
            # 獲取default值
            default_remote = ''
            default_revision = ''
            default_element = root.find('default')
            if default_element is not None:
                default_remote = default_element.get('remote', '')
                default_revision = default_element.get('revision', '')
                self.logger.info(f"找到預設值 - remote: {default_remote}, revision: {default_revision}")
            
            self.default_remote = default_remote
            self.default_revision = default_revision
            
            conversion_info = []
            conversion_count = 0
            skipped_no_revision = 0
            skipped_projects_count = 0
            
            # 建立轉換後的內容
            converted_content = xml_content
            
            # 遍歷所有project元素
            for project in root.findall('project'):
                project_name = project.get('name', '')
                project_remote = project.get('remote', '') or default_remote
                original_revision = project.get('revision', '')
                original_upstream = project.get('upstream', '')
                original_dest_branch = project.get('dest-branch', '')
                
                # 🆕 新增：解析 groups 來識別 upgrade 版本
                groups = project.get('groups', '')
                upgrade_version = self._extract_upgrade_version_from_groups(groups)
                
                # 檢查是否應該跳過轉換
                should_skip = self._should_skip_project_conversion(project_name, conversion_type)
                
                # 如果沒有revision，記錄但跳過轉換
                if not original_revision:
                    skipped_no_revision += 1
                    conversion_info.append({
                        'name': project_name,
                        'original_revision': '',
                        'converted_revision': '',
                        'original_upstream': original_upstream,
                        'converted_upstream': original_upstream,
                        'original_dest_branch': original_dest_branch,
                        'converted_dest_branch': original_dest_branch,
                        'changed': False,
                        'skipped': False,
                        'skip_reason': 'no_revision'
                    })
                    continue
                
                # 如果專案在跳過清單中
                if should_skip:
                    skipped_projects_count += 1
                    self.logger.debug(f"跳過專案轉換: {project_name}")
                    
                    conversion_info.append({
                        'name': project_name,
                        'original_revision': original_revision,
                        'converted_revision': original_revision,
                        'original_upstream': original_upstream,
                        'converted_upstream': original_upstream,
                        'original_dest_branch': original_dest_branch,
                        'converted_dest_branch': original_dest_branch,
                        'changed': False,
                        'skipped': True,
                        'skip_reason': 'in_skip_list'
                    })
                    continue
                
                # 🔥 重新設計轉換邏輯
                
                # revision 轉換邏輯：只有非hash才轉換
                if self._is_revision_hash(original_revision):
                    new_revision = original_revision  # hash保持不變
                    self.logger.debug(f"保持 hash revision: {project_name} - {original_revision}")
                else:
                    # 非hash的revision，直接轉換
                    new_revision = self._convert_single_revision(original_revision, conversion_type, project_name, upgrade_version)
                
                # upstream 轉換邏輯：總是轉換（如果有值）
                if original_upstream:
                    new_upstream = self._convert_single_revision(original_upstream, conversion_type, project_name, upgrade_version)
                else:
                    new_upstream = original_upstream
                
                # 🆕 dest-branch 轉換邏輯：總是轉換（如果有值）
                if original_dest_branch:
                    new_dest_branch = self._convert_single_revision(original_dest_branch, conversion_type, project_name, upgrade_version)
                else:
                    new_dest_branch = original_dest_branch
                
                # 記錄轉換資訊
                conversion_info.append({
                    'name': project_name,
                    'original_revision': original_revision,
                    'converted_revision': new_revision,
                    'original_upstream': original_upstream,
                    'converted_upstream': new_upstream,
                    'original_dest_branch': original_dest_branch,
                    'converted_dest_branch': new_dest_branch,
                    'changed': new_revision != original_revision or new_upstream != original_upstream or new_dest_branch != original_dest_branch,
                    'skipped': False,
                    'skip_reason': None
                })
                
                # 進行所有必要的替換
                changes_made = False
                
                # 替換 revision
                if new_revision != original_revision:
                    replacement_success = self._safe_replace_revision_in_xml(
                        converted_content, project_name, original_revision, new_revision
                    )
                    if replacement_success:
                        converted_content = replacement_success
                        changes_made = True
                        self.logger.debug(f"轉換 revision: {project_name} - {original_revision} → {new_revision}")
                
                # 🆕 替換 upstream
                if new_upstream != original_upstream and original_upstream:
                    replacement_success = self._safe_replace_upstream_in_xml(
                        converted_content, project_name, original_upstream, new_upstream
                    )
                    if replacement_success:
                        converted_content = replacement_success
                        changes_made = True
                        self.logger.debug(f"轉換 upstream: {project_name} - {original_upstream} → {new_upstream}")
                
                # 🆕 替換 dest-branch
                if new_dest_branch != original_dest_branch and original_dest_branch:
                    replacement_success = self._safe_replace_dest_branch_in_xml(
                        converted_content, project_name, original_dest_branch, new_dest_branch
                    )
                    if replacement_success:
                        converted_content = replacement_success
                        changes_made = True
                        self.logger.debug(f"轉換 dest-branch: {project_name} - {original_dest_branch} → {new_dest_branch}")
                
                if changes_made:
                    conversion_count += 1
            
            self.logger.info(f"revision 轉換完成，共轉換 {conversion_count} 個專案")
            self.logger.info(f"跳過沒有revision的專案: {skipped_no_revision} 個")
            if skipped_projects_count > 0:
                self.logger.info(f"跳過在跳過清單中的專案: {skipped_projects_count} 個")
            
            return converted_content, conversion_info
            
        except Exception as e:
            self.logger.error(f"revision 轉換失敗: {str(e)}")
            return xml_content, []
    
    def _extract_upgrade_version_from_groups(self, groups: str) -> Optional[str]:
        """
        從 groups 中提取 upgrade 版本號
        
        Args:
            groups: groups 屬性字串，如 "google_upload,trigger_2851f_upgrade_11,tpv"
            
        Returns:
            upgrade 版本號，如 "11"，如果沒有則返回 None
        """
        if not groups:
            return None
        
        try:
            import re
            # 尋找 trigger_xxxx_upgrade_xx 格式
            match = re.search(r'trigger_\w+_upgrade_(\d+)', groups)
            if match:
                upgrade_ver = match.group(1)
                self.logger.debug(f"從 groups 中找到 upgrade 版本: {upgrade_ver}")
                return upgrade_ver
            return None
        except Exception as e:
            self.logger.warning(f"解析 groups 失敗: {str(e)}")
            return None
    
    def _should_skip_project_conversion(self, project_name: str, conversion_type: str) -> bool:
        """檢查專案是否應該跳過轉換"""
        try:
            skip_config = FEATURE_THREE_SKIP_PROJECTS
            skip_projects = skip_config.get(conversion_type, [])
            
            if not skip_projects:
                return False
            
            for skip_pattern in skip_projects:
                try:
                    if re.search(skip_pattern, project_name):
                        return True
                except re.error:
                    if skip_pattern in project_name:
                        return True
                except Exception:
                    if skip_pattern in project_name:
                        return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"檢查跳過專案失敗: {str(e)}")
            return False
    
    def _is_revision_hash(self, revision: str) -> bool:
        """判斷revision是否為commit hash"""
        if not revision:
            return False
        
        revision = revision.strip()
        
        # 排除refs/開頭的
        if revision.startswith('refs/'):
            return False
        
        # 40字符的完整hash
        if len(revision) == 40 and all(c in '0123456789abcdefABCDEF' for c in revision):
            return True
        
        # 7-12字符的短hash
        if 7 <= len(revision) <= 12 and all(c in '0123456789abcdefABCDEF' for c in revision):
            return True
        
        return False
    
    def _convert_single_revision(self, revision: str, conversion_type: str, project_name: str = '', upgrade_version: str = None) -> str:
        """轉換單一revision - 修正版本，支援 upgrade 版本"""
        # 檢查是否應該跳過轉換
        if project_name and self._should_skip_project_conversion(project_name, conversion_type):
            return revision
        
        # 檢查自定義轉換規則
        if project_name:
            custom_result = self._check_custom_conversion_rules(project_name, conversion_type)
            if custom_result:
                return custom_result
        
        # 標準轉換邏輯
        if conversion_type == 'master_to_premp':
            return self._convert_master_to_premp(revision, upgrade_version)
        elif conversion_type == 'premp_to_mp':
            return self._convert_premp_to_mp(revision)
        elif conversion_type == 'mp_to_mpbackup':
            return self._convert_mp_to_mpbackup(revision)
        else:
            return revision
    
    def _check_custom_conversion_rules(self, project_name: str, conversion_type: str) -> Optional[str]:
        """檢查自定義轉換規則"""
        try:
            custom_rules = FEATURE_THREE_CUSTOM_CONVERSIONS.get(conversion_type, {})
            
            for pattern, rule_config in custom_rules.items():
                try:
                    # 檢查name是否匹配
                    name_matches = bool(re.search(pattern, project_name))
                    if not name_matches:
                        continue
                    
                    # 支援多種配置格式
                    if isinstance(rule_config, list):
                        for rule_item in rule_config:
                            if not isinstance(rule_item, dict):
                                continue
                            target_branch = rule_item.get('target', '')
                            path_pattern = rule_item.get('path_pattern', '')
                            
                            if not target_branch:
                                continue
                            
                            if path_pattern:
                                project_path = self._get_project_path_for_conversion(project_name)
                                if not project_path:
                                    continue
                                
                                try:
                                    path_matches = bool(re.search(path_pattern, project_path))
                                except re.error:
                                    path_matches = path_pattern in project_path
                                
                                if path_matches:
                                    self.logger.info(f"使用自定義轉換規則: {project_name} → {target_branch}")
                                    return target_branch
                            else:
                                self.logger.info(f"使用自定義轉換規則: {project_name} → {target_branch}")
                                return target_branch
                    
                    elif isinstance(rule_config, dict):
                        target_branch = rule_config.get('target', '')
                        if target_branch:
                            self.logger.info(f"使用自定義轉換規則: {project_name} → {target_branch}")
                            return target_branch
                    
                    else:
                        # 簡單格式：直接是target branch字符串
                        target_branch = str(rule_config)
                        self.logger.info(f"使用自定義轉換規則: {project_name} → {target_branch}")
                        return target_branch
                
                except Exception as e:
                    self.logger.error(f"處理自定義轉換規則 '{pattern}' 時發生錯誤: {str(e)}")
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"檢查自定義轉換規則失敗: {str(e)}")
            return None
    
    def _get_project_path_for_conversion(self, project_name: str) -> str:
        """取得專案的path屬性用於自定義轉換規則檢查"""
        try:
            if hasattr(self, '_current_xml_root'):
                for project in self._current_xml_root.findall('project'):
                    if project.get('name') == project_name:
                        return project.get('path', '')
            return ''
        except Exception:
            return ''
    
    def _convert_master_to_premp(self, revision: str, upgrade_version: str = None) -> str:
        """
        master → premp 轉換規則 - 修正版本，支援 upgrade 版本和完整 linux 路徑
        """
        if not revision:
            return revision
        
        original_revision = revision.strip()
        
        # 跳過Google開頭的項目
        if original_revision.startswith('google/'):
            self.logger.debug(f"跳過 Google 項目: {original_revision}")
            return original_revision
        
        # 跳過特殊項目
        if self._should_skip_revision_conversion(original_revision):
            return original_revision
        
        # 精確匹配轉換規則
        exact_mappings = {
            'realtek/master': get_default_premp_branch(),
            'realtek/gaia': get_default_premp_branch(),
            'realtek/gki/master': get_default_premp_branch(),
            get_default_android_master_branch(): get_default_premp_branch(),
            'realtek/mp.google-refplus': get_default_premp_branch(),
            get_android_path('realtek/android-{android_version}/mp.google-refplus'): get_default_premp_branch(),
        }
        
        # 檢查精確匹配
        if original_revision in exact_mappings:
            result = exact_mappings[original_revision]
            self.logger.debug(f"精確匹配轉換: {original_revision} → {result}")
            return result
        
        # 模式匹配轉換規則
        import re
        
        # 🆕 vX.X.X/mp.google-refplus 版本轉換 - 支援 upgrade
        pattern_version_mp = r'realtek/(v\d+\.\d+(?:\.\d+)?)/mp\.google-refplus$'
        match_version_mp = re.match(pattern_version_mp, original_revision)
        if match_version_mp:
            version = match_version_mp.group(1)
            if upgrade_version:
                result = f'realtek/{version}/premp.google-refplus.upgrade-{upgrade_version}'
                self.logger.debug(f"版本 mp 格式轉換（含 upgrade）: {original_revision} → {result}")
            else:
                # 🆕 沒有 upgrade 版本時，使用前一個 Android 版本作為 upgrade
                prev_version = get_current_android_prev_version()
                result = f'realtek/{version}/premp.google-refplus.upgrade-{prev_version}'
                self.logger.debug(f"版本 mp 格式轉換（預設 upgrade）: {original_revision} → {result}")
            return result
        
        # vX.X.X 版本轉換 - 保留版本號
        pattern_version = r'realtek/(v\d+\.\d+(?:\.\d+)?)/master$'
        match_version = re.match(pattern_version, original_revision)
        if match_version:
            version = match_version.group(1)
            result = f'realtek/{version}/premp.google-refplus'
            self.logger.debug(f"版本格式轉換: {original_revision} → {result}")
            return result
        
        # 規則 1: mp.google-refplus.upgrade-11.rtdXXXX → premp.google-refplus.upgrade-11.rtdXXXX
        pattern1 = r'realtek/android-(\d+)/mp\.google-refplus\.upgrade-(\d+)\.(rtd\w+)'
        match1 = re.match(pattern1, original_revision)
        if match1:
            android_ver, upgrade_ver, rtd_chip = match1.groups()
            if android_ver == get_current_android_version():
                result = get_premp_branch_with_upgrade(upgrade_ver, rtd_chip)
            else:
                result = f'realtek/android-{android_ver}/premp.google-refplus.upgrade-{upgrade_ver}.{rtd_chip}'
            self.logger.debug(f"模式1轉換: {original_revision} → {result}")
            return result
        
        # 規則 2: mp.google-refplus.upgrade-11 → premp.google-refplus.upgrade-11
        pattern2 = r'realtek/android-(\d+)/mp\.google-refplus\.upgrade-(\d+)$'
        match2 = re.match(pattern2, original_revision)
        if match2:
            android_ver, upgrade_ver = match2.groups()
            if android_ver == get_current_android_version():
                result = get_premp_branch_with_upgrade(upgrade_ver)
            else:
                result = f'realtek/android-{android_ver}/premp.google-refplus.upgrade-{upgrade_ver}'
            self.logger.debug(f"模式2轉換: {original_revision} → {result}")
            return result
        
        # 🔥 修正規則 3: linux-X.X/master → linux-X.X/android-{current_version}/premp.google-refplus
        pattern3 = r'realtek/linux-([\d.]+)/master$'
        match3 = re.match(pattern3, original_revision)
        if match3:
            linux_ver = match3.group(1)
            result = get_linux_android_path(
                linux_ver, 'realtek/linux-{linux_ver}/android-{android_version}/premp.google-refplus'
            )
            self.logger.debug(f"模式3轉換（保留 linux 前綴）: {original_revision} → {result}")
            return result
        
        # 🔥 修正規則 4: linux-X.X/android-Y/master → linux-X.X/android-{current_version}/premp.google-refplus
        pattern4 = r'realtek/linux-([\d.]+)/android-(\d+)/master$'
        match4 = re.match(pattern4, original_revision)
        if match4:
            linux_ver, android_ver = match4.groups()
            result = get_linux_android_path(
                linux_ver, 'realtek/linux-{linux_ver}/android-{android_version}/premp.google-refplus'
            )
            self.logger.debug(f"模式4轉換（保留 linux 前綴）: {original_revision} → {result}")
            return result
        
        # 規則 5: linux-X.X/android-Y/mp.google-refplus → linux-X.X/android-{current_version}/premp.google-refplus
        pattern5 = r'realtek/linux-([\d.]+)/android-(\d+)/mp\.google-refplus$'
        match5 = re.match(pattern5, original_revision)
        if match5:
            linux_ver, android_ver = match5.groups()
            result = get_linux_android_path(
                linux_ver, 'realtek/linux-{linux_ver}/android-{android_version}/premp.google-refplus'
            )
            self.logger.debug(f"模式5轉換（保留 linux 前綴）: {original_revision} → {result}")
            return result
        
        # 規則 6: linux-X.X/android-Y/mp.google-refplus.rtdXXXX → linux-X.X/android-{current_version}/premp.google-refplus.rtdXXXX
        pattern6 = r'realtek/linux-([\d.]+)/android-(\d+)/mp\.google-refplus\.(rtd\w+)'
        match6 = re.match(pattern6, original_revision)
        if match6:
            linux_ver, android_ver, rtd_chip = match6.groups()
            base_path = get_linux_android_path(
                linux_ver, 'realtek/linux-{linux_ver}/android-{android_version}/premp.google-refplus'
            )
            result = f"{base_path}.{rtd_chip}"
            self.logger.debug(f"模式6轉換（保留 linux 前綴）: {original_revision} → {result}")
            return result
        
        # 規則 7: android-Y/mp.google-refplus → android-{current_version}/premp.google-refplus
        pattern7 = r'realtek/android-(\d+)/mp\.google-refplus$'
        match7 = re.match(pattern7, original_revision)
        if match7:
            result = get_default_premp_branch()
            self.logger.debug(f"模式7轉換: {original_revision} → {result}")
            return result
        
        # 規則 8: 晶片特定的master分支 → premp.google-refplus.rtdXXXX
        for chip, rtd_model in CHIP_TO_RTD_MAPPING.items():
            if f'realtek/{chip}/master' == original_revision:
                result = get_premp_branch_with_chip(rtd_model)
                self.logger.debug(f"晶片轉換: {original_revision} → {result}")
                return result
        
        # 智能轉換備案
        return self._smart_conversion_fallback(original_revision)
    
    def _convert_premp_to_mp(self, revision: str) -> str:
        """premp → mp 轉換規則"""
        return revision.replace('premp.google-refplus', 'mp.google-refplus.wave')
    
    def _convert_mp_to_mpbackup(self, revision: str) -> str:
        """mp → mpbackup 轉換規則"""
        if not revision:
            return revision
        
        original_revision = revision.strip()
        
        # 檢查是否已經是backup格式
        if 'mp.google-refplus.wave.backup' in original_revision:
            return original_revision
        
        # 主要轉換邏輯
        if 'mp.google-refplus.wave' in original_revision and 'backup' not in original_revision:
            result = original_revision.replace('mp.google-refplus.wave', 'mp.google-refplus.wave.backup')
            return result
        
        # 處理以.wave結尾但沒有backup的情況
        if original_revision.endswith('.wave') and 'mp.google-refplus' in original_revision and 'backup' not in original_revision:
            result = original_revision + '.backup'
            return result
        
        return original_revision
    
    def _should_skip_revision_conversion(self, revision: str) -> bool:
        """判斷是否應該跳過revision轉換"""
        if not revision:
            return True
        
        if revision.startswith('google/'):
            return True
        
        if revision.startswith('refs/tags/'):
            return True
        
        return False
    
    def _smart_conversion_fallback(self, revision: str) -> str:
        """智能轉換備案"""
        # 如果包含mp.google-refplus，嘗試替換為premp.google-refplus
        if 'mp.google-refplus' in revision:
            result = revision.replace('mp.google-refplus', 'premp.google-refplus')
            return result
        
        # 如果是master但沒有匹配到特定規則
        if '/master' in revision and 'realtek/' in revision:
            result = get_default_premp_branch()
            return result
        
        # 如果完全沒有匹配，返回當前版本的預設值
        result = get_default_premp_branch()
        return result
    
    def _safe_replace_revision_in_xml(self, xml_content: str, project_name: str, 
                                     old_revision: str, new_revision: str) -> str:
        """安全的XML字串替換 - revision"""
        try:
            lines = xml_content.split('\n')
            modified = False
            
            for i, line in enumerate(lines):
                # 檢查這一行是否包含目標專案
                if f'name="{project_name}"' in line and 'revision=' in line:
                    # 找到目標行，進行替換
                    if f'revision="{old_revision}"' in line:
                        lines[i] = line.replace(f'revision="{old_revision}"', f'revision="{new_revision}"')
                        modified = True
                        break
                    elif f"revision='{old_revision}'" in line:
                        lines[i] = line.replace(f"revision='{old_revision}'", f"revision='{new_revision}'")
                        modified = True
                        break
            
            if modified:
                return '\n'.join(lines)
            else:
                return xml_content
                
        except Exception as e:
            self.logger.error(f"安全替換 revision 失敗: {str(e)}")
            return xml_content
    
    def _safe_replace_upstream_in_xml(self, xml_content: str, project_name: str, 
                                     old_upstream: str, new_upstream: str) -> str:
        """安全的XML字串替換 - upstream"""
        try:
            lines = xml_content.split('\n')
            modified = False
            
            for i, line in enumerate(lines):
                # 檢查這一行是否包含目標專案
                if f'name="{project_name}"' in line and 'upstream=' in line:
                    # 找到目標行，進行替換
                    if f'upstream="{old_upstream}"' in line:
                        lines[i] = line.replace(f'upstream="{old_upstream}"', f'upstream="{new_upstream}"')
                        modified = True
                        break
                    elif f"upstream='{old_upstream}'" in line:
                        lines[i] = line.replace(f"upstream='{old_upstream}'", f"upstream='{new_upstream}'")
                        modified = True
                        break
            
            if modified:
                return '\n'.join(lines)
            else:
                return xml_content
                
        except Exception as e:
            self.logger.error(f"安全替換 upstream 失敗: {str(e)}")
            return xml_content
    
    def _safe_replace_dest_branch_in_xml(self, xml_content: str, project_name: str, 
                                        old_dest_branch: str, new_dest_branch: str) -> str:
        """安全的XML字串替換 - dest-branch"""
        try:
            lines = xml_content.split('\n')
            modified = False
            
            for i, line in enumerate(lines):
                # 檢查這一行是否包含目標專案
                if f'name="{project_name}"' in line and 'dest-branch=' in line:
                    # 找到目標行，進行替換
                    if f'dest-branch="{old_dest_branch}"' in line:
                        lines[i] = line.replace(f'dest-branch="{old_dest_branch}"', f'dest-branch="{new_dest_branch}"')
                        modified = True
                        break
                    elif f"dest-branch='{old_dest_branch}'" in line:
                        lines[i] = line.replace(f"dest-branch='{old_dest_branch}'", f"dest-branch='{new_dest_branch}'")
                        modified = True
                        break
            
            if modified:
                return '\n'.join(lines)
            else:
                return xml_content
                
        except Exception as e:
            self.logger.error(f"安全替換 dest-branch 失敗: {str(e)}")
            return xml_content

    def _show_usage_instructions(self, conversion_type: str, output_file: str, file_type: str):
        """顯示使用說明"""
        print("\n" + "="*60)
        print("🎉 轉換完成！以下是使用轉換後檔案的說明：")
        print("="*60)
        
        if file_type == 'xml':
            # 取得對應的target檔案
            target_info = CONVERSION_TYPE_INFO.get(conversion_type, {})
            target_file = target_info.get('target_file', 'unknown.xml')
            
            # 從輸出檔案名稱產生工作目錄名稱
            base_name = os.path.splitext(os.path.basename(output_file))[0]
            work_dir = f"{base_name}_workspace"
            
            if conversion_type == 'master_to_premp':
                print(f"""
📋 Master to PreMP 轉換完成

[1] mkdir -p {work_dir} && cd {work_dir}
[2] repo init -u ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest -b realtek/android-14/master -m {target_file}
[3] cp -a ../{output_file} .repo/manifests/
[4] repo init -m {output_file}
[5] repo sync
""")
            
            elif conversion_type == 'premp_to_mp':
                print(f"""
📋 PreMP to MP 轉換完成

[1] mkdir -p {work_dir} && cd {work_dir}
[2] repo init -u ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest -b realtek/android-14/master -m {target_file}
[3] cp -a ../{output_file} .repo/manifests/
[4] repo init -m {output_file}
[5] repo sync
""")
            
            elif conversion_type == 'mp_to_mpbackup':
                print(f"""
📋 MP to MP Backup 轉換完成

[1] mkdir -p {work_dir} && cd {work_dir}
[2] repo init -u ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest -b realtek/android-14/master -m {target_file}
[3] cp -a ../{output_file} .repo/manifests/
[4] repo init -m {output_file}
[5] repo sync
""")
            
            print("="*60)
            print(f"提示：請確保轉換後的檔案 {output_file} 在當前目錄中")
            print("="*60)
        
        elif file_type == 'txt':
            print(f"""
📋 TXT Branch 轉換完成

轉換後的檔案已產生：{output_file}

使用方式：
1. 檢查轉換結果是否正確
2. 可以直接使用轉換後的檔案進行後續操作
3. 或根據 Branch 資訊進行相應的 git 操作

檔案差異比較：
diff -u [原檔案] {output_file}
""")
            print("="*60)
            print(f"提示：TXT 檔案已完成 Branch 資訊轉換")
            print("="*60)

def interactive_mode():
    """互動模式"""
    converter = EnhancedManifestConverter()
    
    print("="*60)
    print("🔧 增強版 Manifest 轉換工具 - 互動模式")
    print("支援 XML 和 TXT 檔案")
    print("="*60)
    
    # 選擇輸入檔案
    while True:
        input_file = input("\n請輸入檔案路徑 (支援 XML 或 TXT): ").strip()
        if os.path.exists(input_file):
            break
        else:
            print(f"❌ 檔案不存在: {input_file}")
    
    # 選擇轉換類型
    print("\n請選擇轉換類型:")
    print("1. Master → PreMP")
    print("2. PreMP → MP")  
    print("3. MP → MP Backup")
    
    while True:
        choice = input("\n請選擇 (1-3): ").strip()
        if choice in converter.conversion_types:
            conversion_type = converter.conversion_types[choice]
            break
        else:
            print("❌ 無效選擇，請重新輸入")
    
    # 選擇輸出檔案（可選）
    output_file = input(f"\n請輸入輸出檔案名稱（留空使用預設名稱）: ").strip()
    if not output_file:
        output_file = None
    
    # 執行轉換
    print(f"\n開始轉換: {converter.conversion_descriptions[conversion_type]}")
    success = converter.convert_file(input_file, conversion_type, output_file)
    
    if success:
        print("\n✅ 轉換成功完成！")
    else:
        print("\n❌ 轉換失敗！")
    
    return success

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='增強版 Manifest 轉換工具 - 支援 XML 和 TXT')
    parser.add_argument('input_file', nargs='?', help='輸入檔案 (XML 或 TXT)')
    parser.add_argument('-t', '--type', choices=['master_to_premp', 'premp_to_mp', 'mp_to_mpbackup'],
                       help='轉換類型')
    parser.add_argument('-o', '--output', help='輸出檔案路徑')
    parser.add_argument('-i', '--interactive', action='store_true', help='使用互動模式')
    
    args = parser.parse_args()
    
    # 如果沒有參數或指定互動模式，進入互動模式
    if args.interactive or (not args.input_file and not args.type):
        return interactive_mode()
    
    # 命令列模式
    if not args.input_file:
        parser.error("請指定輸入檔案")
    
    if not args.type:
        parser.error("請指定轉換類型")
    
    converter = EnhancedManifestConverter()
    success = converter.convert_file(args.input_file, args.type, args.output)
    
    if success:
        print("✅ 轉換成功完成！")
        return True
    else:
        print("❌ 轉換失敗！")
        return False

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n用戶中斷操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程式執行失敗: {str(e)}")
        sys.exit(1)