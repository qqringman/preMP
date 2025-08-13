#!/usr/bin/env python3
"""
測試 Master to PreMP Manifest 轉換規則
比對轉換結果與正確版 PreMP，輸出差異報告
🔥 修正：使用 name + path 作為 composite key 避免重複項目遺失
🔥 修正：統一 Excel 格式，支援其他轉換類型比較
"""

import os
import sys
import xml.etree.ElementTree as ET
import pandas as pd
from typing import Dict, List, Tuple, Optional
import argparse
from datetime import datetime
import logging

# 添加專案路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from overwrite_lib.feature_three import FeatureThree
from excel_handler import ExcelHandler
import utils

# 設定日誌
logger = utils.setup_logger(__name__)

class ManifestConversionTester:
    """Manifest 轉換規則測試器 - 修正版（支援 name+path composite key）"""
    
    def __init__(self):
        self.feature_three = FeatureThree()
        self.excel_handler = ExcelHandler()
        self.logger = logger
        
        # 統計資料
        self.stats = {
            'total_projects': 0,
            'matched': 0,
            'mismatched': 0,
            'not_found_in_target': 0,
            'extra_in_target': 0,
            'no_revision_projects': 0,
            'revision_projects': 0,
            'skipped_special_projects': 0,
            'same_revision_projects': 0
        }
        
        # 存儲失敗案例的詳細資訊
        self.failed_cases = []
        
    def parse_manifest(self, file_path: str) -> Dict[str, Dict]:
        """
        解析 manifest.xml 檔案 - 🔥 修正版：使用 name+path 作為 composite key
        
        Args:
            file_path: manifest.xml 檔案路徑
            
        Returns:
            字典，key 是 "name|path" 組合，value 是專案屬性
        """
        try:
            self.logger.info(f"解析 manifest 檔案: {file_path}")
            
            # 檢查檔案是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"檔案不存在: {file_path}")
            
            # 解析 XML
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 提取所有專案 - 🔥 使用 name+path 作為 composite key
            projects = {}
            name_duplicates = {}  # 追踪重複的 name
            
            for project in root.findall('project'):
                name = project.get('name', '')
                path = project.get('path', '')
                
                if not name:
                    continue
                
                # 🔥 建立 composite key: name|path
                composite_key = f"{name}|{path}"
                
                # 🔥 追踪 name 重複情況
                if name in name_duplicates:
                    name_duplicates[name] += 1
                else:
                    name_duplicates[name] = 1
                    
                projects[composite_key] = {
                    'name': name,
                    'path': path,
                    'revision': project.get('revision', ''),
                    'upstream': project.get('upstream', ''),
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project.get('remote', ''),
                    'composite_key': composite_key  # 方便後續使用
                }
            
            # 🔥 報告重複 name 的情況
            duplicate_names = [name for name, count in name_duplicates.items() if count > 1]
            if duplicate_names:
                self.logger.info(f"🔍 發現重複 project name: {len(duplicate_names)} 個")
                for name in duplicate_names[:5]:  # 只顯示前5個
                    count = name_duplicates[name]
                    self.logger.info(f"  - {name}: {count} 個不同 path")
                if len(duplicate_names) > 5:
                    self.logger.info(f"  ... 還有 {len(duplicate_names) - 5} 個重複 name")
            
            self.logger.info(f"成功解析 {len(projects)} 個專案 (使用 name+path composite key)")
            return projects
            
        except Exception as e:
            self.logger.error(f"解析 manifest 檔案失敗: {str(e)}")
            raise
    
    def convert_revision(self, revision: str, conversion_type: str = 'master_to_premp') -> str:
        """
        🔥 新增：支援多種轉換類型的 revision 轉換
        
        Args:
            revision: 原始 revision
            conversion_type: 轉換類型
            
        Returns:
            轉換後的 revision
        """
        try:
            if conversion_type == 'master_to_premp':
                return self.feature_three._convert_master_to_premp(revision)
            elif conversion_type == 'premp_to_mp':
                return self.feature_three._convert_premp_to_mp(revision)
            elif conversion_type == 'mp_to_mpbackup':
                return self.feature_three._convert_mp_to_mpbackup(revision)
            else:
                # 對於其他比較類型，不進行轉換
                return revision
        except Exception as e:
            self.logger.error(f"轉換 revision 失敗: {revision}, 錯誤: {str(e)}")
            return revision
    
    def compare_manifests(self, source_projects: Dict, target_projects: Dict, 
                         comparison_type: str = 'master_vs_premp') -> List[Dict]:
        """
        🔥 修正版：比對兩個 manifest 的差異，支援多種比較類型
        使用 name+path composite key 避免重複項目遺失
        
        Args:
            source_projects: 源 manifest 專案字典 (key: name|path)
            target_projects: 目標 manifest 專案字典 (key: name|path) 
            comparison_type: 比較類型
            
        Returns:
            差異列表
        """
        all_results = []
        self.failed_cases = []
        
        # 重置統計
        self.stats = {
            'total_projects': len(source_projects),
            'matched': 0,
            'mismatched': 0,
            'not_found_in_target': 0,
            'extra_in_target': 0,
            'no_revision_projects': 0,
            'revision_projects': 0,
            'skipped_special_projects': 0,
            'same_revision_projects': 0
        }
        
        # 🔥 設定欄位名稱（根據比較類型）
        source_name, target_name = self._get_comparison_names(comparison_type)
        
        # 🔥 判斷是否需要轉換邏輯（只有特定類型才需要）
        need_conversion = comparison_type in ['master_vs_premp', 'premp_vs_mp', 'mp_vs_mpbackup']
        
        self.logger.info(f"🔄 開始 {comparison_type} 比對...")
        self.logger.info(f"📊 源專案數: {len(source_projects)}, 目標專案數: {len(target_projects)}")
        if need_conversion:
            self.logger.info(f"🔧 將執行 {comparison_type} 轉換邏輯")
        else:
            self.logger.info(f"📋 純差異比較，不執行轉換")
        
        # 比對源 manifest 中的每個專案
        for composite_key, source_proj in source_projects.items():
            source_revision = source_proj['revision']
            sn = len(all_results) + 1
            
            # 🔥 檢查是否有 revision 屬性（只在需要轉換時才檢查）
            if need_conversion and (not source_revision or source_revision.strip() == ''):
                self.stats['no_revision_projects'] += 1
                self._add_no_revision_result(all_results, sn, source_proj, target_projects, 
                                          composite_key, source_name, target_name)
                continue
            
            # 🔥 檢查是否為特殊項目（只在需要轉換時才檢查）
            if need_conversion and self._should_skip_conversion(source_revision, comparison_type):
                self.stats['skipped_special_projects'] += 1
                self._add_skipped_result(all_results, sn, source_proj, target_projects, 
                                       composite_key, source_revision, source_name, target_name, comparison_type)
                continue
            
            # 🔥 有 revision 且需要處理的專案
            if need_conversion:
                self.stats['revision_projects'] += 1
            
            # 在目標 manifest 中查找對應專案
            if composite_key in target_projects:
                target_proj = target_projects[composite_key]
                target_revision = target_proj['revision']
                
                if need_conversion:
                    # 需要轉換的比較類型
                    self._process_conversion_comparison(
                        all_results, sn, source_proj, target_proj, source_revision, 
                        target_revision, composite_key, comparison_type, source_name, target_name
                    )
                else:
                    # 純差異比較
                    self._process_direct_comparison(
                        all_results, sn, source_proj, target_proj, source_revision,
                        target_revision, composite_key, source_name, target_name
                    )
            else:
                # 目標中不存在的專案
                self.stats['not_found_in_target'] += 1
                self._add_not_found_result(all_results, sn, source_proj, source_revision, 
                                         composite_key, comparison_type, source_name, target_name, need_conversion)
        
        # 處理僅存在於目標的專案
        for composite_key in target_projects:
            if composite_key not in source_projects:
                self.stats['extra_in_target'] += 1
                sn = len(all_results) + 1
                target_proj = target_projects[composite_key]
                
                all_results.append({
                    'SN': sn,
                    '專案名稱': target_proj['name'],
                    '專案路徑': target_proj['path'],
                    f'{source_name} Revision': 'N/A (專案不存在)',
                    '轉換後 Revision': 'N/A' if need_conversion else 'N/A',
                    f'{target_name} Revision': target_proj['revision'],
                    '狀態': f'🔶 僅存在於{target_name}',
                    '比較結果': 'N/A',
                    '差異說明': f'專案僅存在於 {target_name} manifest 中',
                    'Composite Key': composite_key,
                    'Upstream': target_proj.get('upstream', ''),
                    'Dest-Branch': target_proj.get('dest-branch', ''),
                    'Groups': target_proj.get('groups', ''),
                    'Remote': target_proj.get('remote', '')
                })
        
        self.logger.info(f"📊 比對完成: 匹配={self.stats['matched']}, 不匹配={self.stats['mismatched']}")
        return all_results

    def _get_comparison_names(self, comparison_type: str) -> Tuple[str, str]:
        """根據比較類型取得源和目標的名稱"""
        mapping = {
            'master_vs_premp': ('Master', 'PreMP'),
            'premp_vs_mp': ('PreMP', 'MP'),
            'mp_vs_mpbackup': ('MP', 'MP Backup'),
            'custom': ('檔案1', '檔案2')
        }
        return mapping.get(comparison_type, ('源檔案', '目標檔案'))
    
    def _process_conversion_comparison(self, all_results: List, sn: int, source_proj: Dict, 
                                     target_proj: Dict, source_revision: str, target_revision: str,
                                     composite_key: str, comparison_type: str, source_name: str, target_name: str):
        """處理需要轉換的比較邏輯"""
        # 檢查源和目標的原始 revision 是否相同
        if source_revision == target_revision:
            self.stats['matched'] += 1
            self.stats['same_revision_projects'] += 1
            status = '✅ 匹配 (原始相同)'
            is_correct = '是'
            description = f'{source_name} 和 {target_name} 的原始 revision 相同: {source_revision}，無需轉換'
            final_converted_revision = source_revision
        else:
            # 進行轉換比對
            converted_revision = self.convert_revision(source_revision, comparison_type.replace('_vs_', '_to_'))
            
            if converted_revision == target_revision:
                self.stats['matched'] += 1
                status = '✅ 匹配'
                is_correct = '是'
                description = f'轉換結果與 {target_name} 正確版完全匹配'
                final_converted_revision = converted_revision
            else:
                self.stats['mismatched'] += 1
                status = '❌ 不匹配'
                is_correct = '否'
                description = f'期望: {target_revision}, 實際: {converted_revision}'
                final_converted_revision = converted_revision
                
                # 記錄失敗案例
                self.failed_cases.append({
                    'SN': sn,
                    '專案名稱': source_proj['name'],
                    '專案路徑': source_proj['path'],
                    f'{source_name} Revision': source_revision,
                    '轉換後 Revision': converted_revision,
                    f'{target_name} Revision': target_revision,
                    '差異說明': description,
                    '轉換規則類型': self._identify_rule_type(source_revision, converted_revision, comparison_type),
                    'Composite Key': composite_key,
                    'Upstream': source_proj.get('upstream', ''),
                    'Dest-Branch': source_proj.get('dest-branch', ''),
                    'Groups': source_proj.get('groups', ''),
                    'Remote': source_proj.get('remote', '')
                })
        
        all_results.append({
            'SN': sn,
            '專案名稱': source_proj['name'],
            '專案路徑': source_proj['path'],
            f'{source_name} Revision': source_revision,
            '轉換後 Revision': final_converted_revision,
            f'{target_name} Revision': target_revision,
            '狀態': status,
            '比較結果': is_correct,
            '差異說明': description,
            'Composite Key': composite_key,
            'Upstream': source_proj.get('upstream', ''),
            'Dest-Branch': source_proj.get('dest-branch', ''),
            'Groups': source_proj.get('groups', ''),
            'Remote': source_proj.get('remote', '')
        })
    
    def _process_direct_comparison(self, all_results: List, sn: int, source_proj: Dict,
                                 target_proj: Dict, source_revision: str, target_revision: str,
                                 composite_key: str, source_name: str, target_name: str):
        """處理純差異比較邏輯"""
        if source_revision == target_revision:
            self.stats['matched'] += 1
            status = '✅ 相同'
            is_correct = '是'
            description = f'{source_name} 和 {target_name} 的 revision 完全相同'
        else:
            self.stats['mismatched'] += 1
            status = '❌ 不同'
            is_correct = '否'
            description = f'{source_name}: {source_revision}, {target_name}: {target_revision}'
        
        all_results.append({
            'SN': sn,
            '專案名稱': source_proj['name'],
            '專案路徑': source_proj['path'],
            f'{source_name} Revision': source_revision,
            '轉換後 Revision': 'N/A (純比較)',
            f'{target_name} Revision': target_revision,
            '狀態': status,
            '比較結果': is_correct,
            '差異說明': description,
            'Composite Key': composite_key,
            'Upstream': source_proj.get('upstream', ''),
            'Dest-Branch': source_proj.get('dest-branch', ''),
            'Groups': source_proj.get('groups', ''),
            'Remote': source_proj.get('remote', '')
        })
    
    def _add_no_revision_result(self, all_results: List, sn: int, source_proj: Dict,
                              target_projects: Dict, composite_key: str, source_name: str, target_name: str):
        """添加無 revision 的結果"""
        if composite_key in target_projects:
            target_proj = target_projects[composite_key]
            target_revision = target_proj['revision']
            
            all_results.append({
                'SN': sn,
                '專案名稱': source_proj['name'],
                '專案路徑': source_proj['path'],
                f'{source_name} Revision': '無 (沒有 revision 屬性)',
                '轉換後 Revision': 'N/A (跳過轉換)',
                f'{target_name} Revision': target_revision if target_revision else '無',
                '狀態': f'🔵 無需轉換 ({source_name}無revision)',
                '比較結果': 'N/A',
                '差異說明': f'{source_name} 專案沒有 revision 屬性，跳過轉換比對',
                'Composite Key': composite_key,
                'Upstream': source_proj.get('upstream', ''),
                'Dest-Branch': source_proj.get('dest-branch', ''),
                'Groups': source_proj.get('groups', ''),
                'Remote': source_proj.get('remote', '')
            })
        else:
            all_results.append({
                'SN': sn,
                '專案名稱': source_proj['name'],
                '專案路徑': source_proj['path'],
                f'{source_name} Revision': '無 (沒有 revision 屬性)',
                '轉換後 Revision': 'N/A (跳過轉換)',
                f'{target_name} Revision': 'N/A (專案不存在)',
                '狀態': f'🔵 無需轉換 ({source_name}無revision且{target_name}不存在)',
                '比較結果': 'N/A',
                '差異說明': f'{source_name} 專案沒有 revision 且 {target_name} 中不存在此專案',
                'Composite Key': composite_key,
                'Upstream': source_proj.get('upstream', ''),
                'Dest-Branch': source_proj.get('dest-branch', ''),
                'Groups': source_proj.get('groups', ''),
                'Remote': source_proj.get('remote', '')
            })
    
    def _add_skipped_result(self, all_results: List, sn: int, source_proj: Dict, target_projects: Dict,
                          composite_key: str, source_revision: str, source_name: str, target_name: str, comparison_type: str):
        """添加跳過的特殊項目結果"""
        if composite_key in target_projects:
            target_proj = target_projects[composite_key]
            target_revision = target_proj['revision']
            
            all_results.append({
                'SN': sn,
                '專案名稱': source_proj['name'],
                '專案路徑': source_proj['path'],
                f'{source_name} Revision': source_revision,
                '轉換後 Revision': 'N/A (跳過特殊項目)',
                f'{target_name} Revision': target_revision,
                '狀態': '🟣 跳過轉換 (特殊項目)',
                '比較結果': 'N/A',
                '差異說明': self._get_skip_reason(source_revision, comparison_type),
                'Composite Key': composite_key,
                'Upstream': source_proj.get('upstream', ''),
                'Dest-Branch': source_proj.get('dest-branch', ''),
                'Groups': source_proj.get('groups', ''),
                'Remote': source_proj.get('remote', '')
            })
        else:
            all_results.append({
                'SN': sn,
                '專案名稱': source_proj['name'],
                '專案路徑': source_proj['path'],
                f'{source_name} Revision': source_revision,
                '轉換後 Revision': 'N/A (跳過特殊項目)',
                f'{target_name} Revision': 'N/A (專案不存在)',
                '狀態': f'🟣 跳過轉換 (特殊項目且{target_name}不存在)',
                '比較結果': 'N/A',
                '差異說明': f'{self._get_skip_reason(source_revision, comparison_type)}，且 {target_name} 中不存在此專案',
                'Composite Key': composite_key,
                'Upstream': source_proj.get('upstream', ''),
                'Dest-Branch': source_proj.get('dest-branch', ''),
                'Groups': source_proj.get('groups', ''),
                'Remote': source_proj.get('remote', '')
            })
    
    def _add_not_found_result(self, all_results: List, sn: int, source_proj: Dict, source_revision: str,
                            composite_key: str, comparison_type: str, source_name: str, target_name: str, need_conversion: bool):
        """添加目標中不存在的專案結果"""
        if need_conversion:
            converted_revision = self.convert_revision(source_revision, comparison_type.replace('_vs_', '_to_'))
        else:
            converted_revision = 'N/A (純比較)'
            
        all_results.append({
            'SN': sn,
            '專案名稱': source_proj['name'],
            '專案路徑': source_proj['path'],
            f'{source_name} Revision': source_revision,
            '轉換後 Revision': converted_revision,
            f'{target_name} Revision': 'N/A (專案不存在)',
            '狀態': f'🔶 {target_name}中不存在',
            '比較結果': 'N/A',
            '差異說明': f'專案在 {target_name} manifest 中不存在，無法驗證比較結果',
            'Composite Key': composite_key,
            'Upstream': source_proj.get('upstream', ''),
            'Dest-Branch': source_proj.get('dest-branch', ''),
            'Groups': source_proj.get('groups', ''),
            'Remote': source_proj.get('remote', '')
        })

    def _should_skip_conversion(self, revision: str, comparison_type: str) -> bool:
        """判斷是否應該跳過轉換的特殊項目"""
        if not revision:
            return False
        
        revision = revision.strip()
        
        # 只在 master_to_premp 轉換時跳過 Google 項目
        if comparison_type == 'master_vs_premp' and revision.startswith('google/'):
            return True
        
        # 所有轉換類型都跳過 refs/tags/
        if revision.startswith('refs/tags/'):
            return True
        
        return False
        
    def _get_skip_reason(self, revision: str, comparison_type: str) -> str:
        """取得跳過轉換的原因說明"""
        if not revision:
            return '未知原因'
        
        revision = revision.strip()
        
        if revision.startswith('google/'):
            return 'Google 項目不需要轉換'
        elif revision.startswith('refs/tags/'):
            return 'Git tags 不需要轉換'
        else:
            return '特殊項目，完全跳過轉換'
    
    def _identify_rule_type(self, source_rev: str, converted_rev: str, comparison_type: str) -> str:
        """識別使用的轉換規則類型"""
        if comparison_type == 'master_vs_premp':
            # 使用原有的 master_to_premp 規則識別邏輯
            return self._identify_master_to_premp_rule(source_rev, converted_rev)
        elif comparison_type == 'premp_vs_mp':
            return self._identify_premp_to_mp_rule(source_rev, converted_rev)
        elif comparison_type == 'mp_vs_mpbackup':
            return self._identify_mp_to_mpbackup_rule(source_rev, converted_rev)
        else:
            return "純差異比較"
    
    def _identify_master_to_premp_rule(self, master_rev: str, converted_rev: str) -> str:
        """識別 master_to_premp 轉換規則"""
        # 檢查是否跳過 Google 項目
        if master_rev.startswith('google/'):
            return "Google項目跳過"
        
        # 檢查是否使用精確匹配
        if hasattr(config, 'MASTER_TO_PREMP_EXACT_MAPPING') and master_rev in config.MASTER_TO_PREMP_EXACT_MAPPING:
            return "精確匹配"
        
        # 檢查是否保持不變
        if master_rev == converted_rev:
            return "保持不變"
        
        # 檢查 Linux kernel 轉換
        if 'linux-' in master_rev and '/master' in master_rev:
            return "Linux Kernel Master轉換"
        
        # 檢查晶片轉換
        if hasattr(config, 'CHIP_TO_RTD_MAPPING'):
            for chip in config.CHIP_TO_RTD_MAPPING.keys():
                if f'/{chip}/' in master_rev:
                    return f"晶片轉換 ({chip})"
        
        # 檢查 upgrade 版本轉換
        if 'upgrade' in master_rev or 'upgrade' in converted_rev:
            return "Upgrade版本轉換"
        
        # 檢查 mp 到 premp 轉換
        if 'mp.google-refplus' in master_rev and 'premp.google-refplus' in converted_rev:
            return "MP到PreMP轉換"
        
        return "智能推斷或預設"
    
    def _identify_premp_to_mp_rule(self, premp_rev: str, converted_rev: str) -> str:
        """識別 premp_to_mp 轉換規則"""
        if 'premp.google-refplus' in premp_rev and 'mp.google-refplus.wave' in converted_rev:
            return "PreMP到MP Wave轉換"
        elif premp_rev == converted_rev:
            return "保持不變"
        else:
            return "其他轉換規則"
    
    def _identify_mp_to_mpbackup_rule(self, mp_rev: str, converted_rev: str) -> str:
        """識別 mp_to_mpbackup 轉換規則"""
        if 'mp.google-refplus.wave' in mp_rev and 'mp.google-refplus.wave.backup' in converted_rev:
            if mp_rev.endswith('.wave') and converted_rev.endswith('.wave.backup'):
                return "MP Wave到Backup轉換"
            else:
                return "MP到Backup轉換（複雜）"
        elif mp_rev == converted_rev:
            return "保持不變"
        else:
            return "其他轉換規則"
                
    def generate_excel_report(self, differences: List[Dict], output_file: str, 
                    source_file: str, target_file: str, comparison_type: str = 'master_vs_premp') -> bool:
        """
        🔥 修正版：生成統一格式的 Excel 測試報告，支援多種比較類型
        """
        try:
            source_name, target_name = self._get_comparison_names(comparison_type)
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # 頁籤 1: 比較摘要（統一格式）
                summary_data = [{
                    '比較時間': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    f'{source_name} Manifest': os.path.basename(source_file),
                    f'{target_name} Manifest': os.path.basename(target_file),
                    '比較類型': comparison_type,
                    '總專案數': self.stats['total_projects'],
                    '🔵 有revision專案數': self.stats['revision_projects'],
                    '⚪ 無revision專案數': self.stats['no_revision_projects'],
                    '🟢 原始相同專案數': self.stats['same_revision_projects'],
                    '✅ 匹配數': self.stats['matched'],
                    '❌ 不匹配數': self.stats['mismatched'],
                    f'⚠️ {target_name}中不存在': self.stats['not_found_in_target'],
                    f'🔶 僅存在於{target_name}': self.stats['extra_in_target'],
                    '成功率': f"{(self.stats['matched'] / max(self.stats['revision_projects'], 1) * 100):.2f}%",
                    '備註': f"使用 name+path composite key 避免重複項目遺失"
                }]
                
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='比較摘要', index=False)
                
                # 頁籤 2: 需要關注的項目（統一格式）
                if differences:
                    df_diff = pd.DataFrame(differences)
                    
                    need_attention = df_diff[
                        (~df_diff['狀態'].str.contains('無需轉換', na=False)) &
                        (df_diff['狀態'] != '✅ 匹配') &
                        (df_diff['狀態'] != '✅ 匹配 (原始相同)') &
                        (df_diff['狀態'] != '✅ 相同')
                    ]
                    
                    if not need_attention.empty:
                        need_attention.to_excel(writer, sheet_name='需要關注的項目', index=False)
                    
                    # 頁籤 3: 無需轉換的專案（僅在有轉換邏輯時）
                    if comparison_type in ['master_vs_premp', 'premp_vs_mp', 'mp_vs_mpbackup']:
                        no_conversion_needed = df_diff[
                            df_diff['狀態'].str.contains('無需轉換', na=False)
                        ]
                        
                        if not no_conversion_needed.empty:
                            no_conversion_needed.to_excel(writer, sheet_name='無需轉換專案', index=False)
                    
                    # 頁籤 4: 失敗案例詳細對照（僅在有失敗案例時）
                    if self.failed_cases and len(self.failed_cases) > 0:
                        df_failed = pd.DataFrame(self.failed_cases)
                        df_failed.to_excel(writer, sheet_name='失敗案例詳細對照', index=False)
                        self.logger.info(f"✅ 已創建失敗案例詳細對照頁籤，包含 {len(self.failed_cases)} 個案例")
                    
                    # 頁籤 5: 僅顯示差異
                    diff_only = df_diff[
                        (df_diff['狀態'] == '❌ 不匹配') | 
                        (df_diff['狀態'] == '❌ 不同') |
                        (df_diff['狀態'].str.contains('不存在', na=False))
                    ]
                    if not diff_only.empty:
                        diff_only.to_excel(writer, sheet_name='僅顯示差異', index=False)
                    
                    # 頁籤 6: 所有專案對照表（統一格式）
                    all_comparisons = []
                    for diff in differences:
                        status_icon = '🔵' if '無需轉換' in diff['狀態'] else (
                            '✅' if ('匹配' in diff['狀態'] or '相同' in diff['狀態']) else '❌'
                        )
                        
                        all_comparisons.append({
                            'SN': diff['SN'],
                            '專案名稱': diff['專案名稱'],
                            '專案路徑': diff['專案路徑'],
                            '專案類型': '無revision' if '無需轉換' in diff['狀態'] else '有revision',
                            f'{source_name} Revision': diff[f'{source_name} Revision'],
                            '轉換後 Revision': diff['轉換後 Revision'],
                            f'{target_name} Revision': diff[f'{target_name} Revision'],
                            '結果': status_icon,
                            '狀態說明': diff['狀態'],
                            'Composite Key': diff['Composite Key']
                        })
                    
                    if all_comparisons:
                        df_all = pd.DataFrame(all_comparisons)
                        df_all.to_excel(writer, sheet_name='所有專案對照', index=False)
                    
                    # 頁籤 7: 轉換規則統計（僅在有轉換邏輯時）
                    if comparison_type in ['master_vs_premp', 'premp_vs_mp', 'mp_vs_mpbackup']:
                        rule_stats = self._analyze_conversion_rules(differences, comparison_type)
                        if rule_stats:
                            df_rules = pd.DataFrame(rule_stats)
                            df_rules.to_excel(writer, sheet_name='轉換規則統計', index=False)
                
                # 🔥 統一格式化所有工作表
                self._format_all_worksheets(writer, comparison_type)
            
            self.logger.info(f"✅ 成功生成 {comparison_type} 比較報告: {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"生成 Excel 報告失敗: {str(e)}")
            return False
    
    def _analyze_conversion_rules(self, differences: List[Dict], comparison_type: str) -> List[Dict]:
        """分析轉換規則的使用情況"""
        rule_usage = {}
        source_name, target_name = self._get_comparison_names(comparison_type)
        
        for diff in differences:
            source_rev = diff[f'{source_name} Revision']
            status = diff['狀態']
            
            # 跳過不需要統計的項目
            if (source_rev == 'N/A (專案不存在)' or 
                '無 (沒有 revision 屬性)' in source_rev or
                '無需轉換' in status or '跳過' in status or
                '不存在' in status or '僅存在於' in status):
                continue
                    
            # 分析使用了哪種轉換規則
            converted_rev = diff['轉換後 Revision']
            rule_type = self._identify_rule_type(source_rev, converted_rev, comparison_type)
            
            if rule_type not in rule_usage:
                rule_usage[rule_type] = {
                    '規則類型': rule_type,
                    '使用次數': 0,
                    '成功次數': 0,
                    '失敗次數': 0,
                    '失敗案例SN': [],
                    '失敗範例': []
                }
            
            rule_usage[rule_type]['使用次數'] += 1
            
            # 判斷成功/失敗
            if ('✅' in status):
                rule_usage[rule_type]['成功次數'] += 1
            elif ('❌' in status):
                rule_usage[rule_type]['失敗次數'] += 1
                rule_usage[rule_type]['失敗案例SN'].append(diff['SN'])
                
                if len(rule_usage[rule_type]['失敗範例']) < 3:
                    rule_usage[rule_type]['失敗範例'].append(f"{source_rev} → {converted_rev}")
        
        # 轉換為列表並計算成功率
        result = []
        for rule_type, stats in rule_usage.items():
            actual_judged = stats['成功次數'] + stats['失敗次數']
            if actual_judged > 0:
                stats['成功率'] = f"{(stats['成功次數'] / actual_judged * 100):.1f}%"
            else:
                stats['成功率'] = 'N/A'
                
            stats['失敗範例詳情'] = '\n'.join(stats['失敗範例']) if stats['失敗範例'] else 'N/A'
            
            if stats['失敗案例SN']:
                sn_list = [str(sn) for sn in stats['失敗案例SN']]
                if len(sn_list) <= 10:
                    stats['失敗案例SN列表'] = ', '.join(sn_list)
                else:
                    stats['失敗案例SN列表'] = ', '.join(sn_list[:10]) + f' ...等{len(sn_list)}個'
            else:
                stats['失敗案例SN列表'] = 'N/A'
            
            del stats['失敗案例SN']
            del stats['失敗範例']
            
            result.append(stats)
        
        return result
    
    def _format_all_worksheets(self, writer, comparison_type: str):
        """🔥 統一格式化所有工作表"""
        from openpyxl.styles import PatternFill, Font, Alignment
        from openpyxl.utils import get_column_letter
        
        # 定義統一顏色方案
        colors = {
            'header': PatternFill(start_color="366092", end_color="366092", fill_type="solid"),
            'match': PatternFill(start_color="E6FFE6", end_color="E6FFE6", fill_type="solid"),      # 淺綠
            'mismatch': PatternFill(start_color="FFE6E6", end_color="FFE6E6", fill_type="solid"),   # 淺紅
            'not_found': PatternFill(start_color="FFFACD", end_color="FFFACD", fill_type="solid"),  # 淺黃
            'no_conversion': PatternFill(start_color="E6F3FF", end_color="E6F3FF", fill_type="solid"), # 淺藍
            'failed_cases': PatternFill(start_color="FFE4B5", end_color="FFE4B5", fill_type="solid")  # 淺橘
        }
        
        header_font = Font(color="FFFFFF", bold=True)
        
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            
            # 設定標題格式
            for cell in worksheet[1]:
                cell.fill = colors['header']
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center')
            
            # 根據頁籤設定內容格式
            if sheet_name in ['需要關注的項目', '無需轉換專案', '所有專案對照', '僅顯示差異']:
                self._format_comparison_sheet(worksheet, colors)
            elif sheet_name == '失敗案例詳細對照':
                self._format_failed_cases_sheet(worksheet, colors)
            elif sheet_name == '轉換規則統計':
                self._format_rules_sheet(worksheet, colors)
            
            # 自動調整欄寬
            self._auto_adjust_columns(worksheet)
    
    def _format_comparison_sheet(self, worksheet, colors):
        """格式化比較頁籤"""
        for row in range(2, worksheet.max_row + 1):
            status_cell = None
            for col in range(1, worksheet.max_column + 1):
                header = worksheet.cell(row=1, column=col).value
                if header and ('狀態' in str(header) or '結果' in str(header)):
                    status_cell = worksheet.cell(row=row, column=col)
                    break
            
            if status_cell and status_cell.value:
                status_value = str(status_cell.value)
                fill_color = None
                
                if '不匹配' in status_value or '不同' in status_value or '❌' in status_value:
                    fill_color = colors['mismatch']
                elif '匹配' in status_value or '相同' in status_value or '✅' in status_value:
                    fill_color = colors['match']
                elif '不存在' in status_value or '⚠️' in status_value or '🔶' in status_value:
                    fill_color = colors['not_found']
                elif '無需轉換' in status_value or '🔵' in status_value:
                    fill_color = colors['no_conversion']
                
                if fill_color:
                    for col in range(1, worksheet.max_column + 1):
                        worksheet.cell(row=row, column=col).fill = fill_color
    
    def _format_failed_cases_sheet(self, worksheet, colors):
        """格式化失敗案例頁籤"""
        for row in range(2, worksheet.max_row + 1):
            for col in range(1, worksheet.max_column + 1):
                worksheet.cell(row=row, column=col).fill = colors['failed_cases']
    
    def _format_rules_sheet(self, worksheet, colors):
        """格式化規則統計頁籤"""
        for row in range(2, worksheet.max_row + 1):
            failure_count_cell = None
            for col in range(1, worksheet.max_column + 1):
                header = worksheet.cell(row=1, column=col).value
                if header and '失敗次數' in str(header):
                    failure_count_cell = worksheet.cell(row=row, column=col)
                    break
            
            if failure_count_cell and failure_count_cell.value and int(failure_count_cell.value) > 0:
                for col in range(1, worksheet.max_column + 1):
                    worksheet.cell(row=row, column=col).fill = colors['mismatch']
    
    def _auto_adjust_columns(self, worksheet):
        """自動調整欄寬"""
        for column in worksheet.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            
            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 60)  # 增加最大寬度到60
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    def test_conversion(self, source_file: str, target_file: str, output_file: str, 
                       comparison_type: str = 'master_vs_premp') -> bool:
        """
        🔥 修正版：執行轉換/比較測試，支援多種比較類型
        """
        try:
            source_name, target_name = self._get_comparison_names(comparison_type)
            
            self.logger.info("="*80)
            self.logger.info(f"開始執行 {comparison_type} 比較")
            self.logger.info("="*80)
            
            # 步驟 1: 解析 manifest 檔案
            self.logger.info(f"\n📋 步驟 1: 解析 manifest 檔案（使用 name+path composite key）")
            source_projects = self.parse_manifest(source_file)
            target_projects = self.parse_manifest(target_file)
            
            # 步驟 2: 比對結果
            self.logger.info(f"\n🔍 步驟 2: 執行 {comparison_type} 比對")
            differences = self.compare_manifests(source_projects, target_projects, comparison_type)
            
            # 步驟 3: 生成報告
            self.logger.info(f"\n📊 步驟 3: 生成 {comparison_type} 比較報告")
            self.generate_excel_report(differences, output_file, source_file, target_file, comparison_type)
            
            # 步驟 4: 顯示結果
            self._show_comparison_results(comparison_type, source_name, target_name)
            
            # 判斷是否成功
            comparison_passed = (self.stats['mismatched'] == 0)
            return comparison_passed
            
        except Exception as e:
            self.logger.error(f"{comparison_type} 比較執行失敗: {str(e)}")
            return False
    
    def _show_comparison_results(self, comparison_type: str, source_name: str, target_name: str):
        """顯示比較結果統計"""
        self.logger.info(f"\n📈 {comparison_type} 比較結果統計:")
        self.logger.info(f"  總專案數: {self.stats['total_projects']}")
        
        if comparison_type in ['master_vs_premp', 'premp_vs_mp', 'mp_vs_mpbackup']:
            self.logger.info(f"  🔵 有revision專案: {self.stats['revision_projects']}")
            self.logger.info(f"  ⚪ 無revision專案: {self.stats['no_revision_projects']} (跳過轉換)")
            self.logger.info(f"  🟢 原始相同專案: {self.stats['same_revision_projects']} ({source_name}={target_name})")
        
        self.logger.info(f"  ✅ 匹配/相同: {self.stats['matched']}")
        self.logger.info(f"  ❌ 不匹配/不同: {self.stats['mismatched']}")
        self.logger.info(f"  ⚠️ {target_name}中不存在: {self.stats['not_found_in_target']}")
        self.logger.info(f"  🔶 僅存在於{target_name}: {self.stats['extra_in_target']}")
        
        # 計算成功率
        if self.stats['revision_projects'] > 0:
            success_rate = (self.stats['matched'] / self.stats['revision_projects'] * 100)
            self.logger.info(f"  📊 成功率: {success_rate:.2f}%")
        
        # 顯示失敗案例
        if self.failed_cases:
            self.logger.info(f"\n❌ 失敗案例分析:")
            self.logger.info(f"  失敗案例數: {len(self.failed_cases)}")
            self.logger.info(f"  詳細對照已添加到 '失敗案例詳細對照' 頁籤")
        
        # 結論
        if self.stats['mismatched'] == 0:
            self.logger.info(f"\n✅ {comparison_type} 比較測試通過！")
        else:
            self.logger.warning(f"\n⚠️ 發現 {self.stats['mismatched']} 個差異")
        
        self.logger.info("="*80)


def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='Manifest 比較工具 - 支援多種比較類型')
    parser.add_argument('source_file', help='源 manifest.xml 檔案路徑')
    parser.add_argument('target_file', help='目標 manifest.xml 檔案路徑')
    parser.add_argument('-o', '--output', default='manifest_comparison_report.xlsx',
                       help='輸出 Excel 檔案名稱')
    parser.add_argument('-t', '--type', default='master_vs_premp',
                       choices=['master_vs_premp', 'premp_vs_mp', 'mp_vs_mpbackup', 'custom'],
                       help='比較類型')
    
    args = parser.parse_args()
    
    # 確保輸出目錄存在
    output_dir = os.path.dirname(args.output) or '.'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 執行測試
    tester = ManifestConversionTester()
    success = tester.test_conversion(args.source_file, args.target_file, args.output, args.type)
    
    # 返回狀態碼
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()