#!/usr/bin/env python3
"""
測試 Master to PreMP Manifest 轉換規則
比對轉換結果與正確版 PreMP，輸出差異報告
修改：增加失敗案例詳細對照，改進特殊項目處理邏輯
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
    """Manifest 轉換規則測試器"""
    
    def __init__(self):
        self.feature_three = FeatureThree()
        self.excel_handler = ExcelHandler()
        self.logger = logger
        
        # 統計資料
        self.stats = {
            'total_projects': 0,
            'matched': 0,
            'mismatched': 0,
            'not_found_in_premp': 0,
            'extra_in_premp': 0,
            'no_revision_projects': 0,
            'revision_projects': 0,
            'skipped_special_projects': 0,
            'same_revision_projects': 0  # 新增：master和premp相同的專案數
        }
        
        # 存儲失敗案例的詳細資訊
        self.failed_cases = []
        
    def parse_manifest(self, file_path: str) -> Dict[str, Dict]:
        """
        解析 manifest.xml 檔案
        
        Args:
            file_path: manifest.xml 檔案路徑
            
        Returns:
            字典，key 是專案名稱，value 是專案屬性
        """
        try:
            self.logger.info(f"解析 manifest 檔案: {file_path}")
            
            # 檢查檔案是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"檔案不存在: {file_path}")
            
            # 解析 XML
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 提取所有專案
            projects = {}
            for project in root.findall('project'):
                name = project.get('name', '')
                if not name:
                    continue
                    
                projects[name] = {
                    'name': name,
                    'path': project.get('path', ''),
                    'revision': project.get('revision', ''),
                    'upstream': project.get('upstream', ''),
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project.get('remote', ''),
                }
            
            self.logger.info(f"成功解析 {len(projects)} 個專案")
            return projects
            
        except Exception as e:
            self.logger.error(f"解析 manifest 檔案失敗: {str(e)}")
            raise
    
    def convert_revision(self, revision: str) -> str:
        """
        使用 feature_three 的轉換邏輯轉換 revision
        
        Args:
            revision: 原始 revision
            
        Returns:
            轉換後的 revision
        """
        try:
            return self.feature_three._convert_master_to_premp(revision)
        except Exception as e:
            self.logger.error(f"轉換 revision 失敗: {revision}, 錯誤: {str(e)}")
            return revision
    
    def compare_manifests(self, master_projects: Dict, premp_projects: Dict) -> List[Dict]:
        """
        比對 master 轉換後與 premp 的差異
        修正：增加更詳細的調試資訊
        """
        all_results = []
        self.failed_cases = []  # 重置失敗案例列表
        
        # 統計
        self.stats['total_projects'] = len(master_projects)
        self.stats['no_revision_projects'] = 0
        self.stats['revision_projects'] = 0
        self.stats['skipped_special_projects'] = 0
        self.stats['same_revision_projects'] = 0
        
        # 計數器（用於調試）
        debug_counters = {
            'no_revision': 0,
            'skipped_special': 0,
            'same_revision': 0,
            'converted_match': 0,
            'converted_mismatch': 0,
            'not_found_in_premp': 0
        }
        
        # 比對 master 中的每個專案
        for name, master_proj in master_projects.items():
            master_revision = master_proj['revision']
            sn = len(all_results) + 1
            
            # 檢查是否有 revision 屬性
            if not master_revision or master_revision.strip() == '':
                debug_counters['no_revision'] += 1
                self.stats['no_revision_projects'] += 1
                
                # ... 無revision的處理邏輯保持不變 ...
                if name in premp_projects:
                    premp_proj = premp_projects[name]
                    premp_revision = premp_proj['revision']
                    
                    all_results.append({
                        'SN': sn,
                        '專案名稱': name,
                        '專案路徑': master_proj['path'],
                        'Master Revision': '無 (沒有 revision 屬性)',
                        '轉換後 Revision': 'N/A (跳過轉換)',
                        'PreMP Revision (正確版)': premp_revision if premp_revision else '無',
                        '狀態': '🔵 無需轉換 (Master無revision)',
                        '轉換是否正確': 'N/A',
                        '差異說明': 'Master 專案沒有 revision 屬性，跳過轉換比對',
                        'Upstream': master_proj.get('upstream', ''),
                        'Dest-Branch': master_proj.get('dest-branch', ''),
                        'Groups': master_proj.get('groups', ''),
                        'Remote': master_proj.get('remote', '')
                    })
                else:
                    all_results.append({
                        'SN': sn,
                        '專案名稱': name,
                        '專案路徑': master_proj['path'],
                        'Master Revision': '無 (沒有 revision 屬性)',
                        '轉換後 Revision': 'N/A (跳過轉換)',
                        'PreMP Revision (正確版)': 'N/A (專案不存在)',
                        '狀態': '🔵 無需轉換 (Master無revision且PreMP不存在)',
                        '轉換是否正確': 'N/A',
                        '差異說明': 'Master 專案沒有 revision 且 PreMP 中不存在此專案',
                        'Upstream': master_proj.get('upstream', ''),
                        'Dest-Branch': master_proj.get('dest-branch', ''),
                        'Groups': master_proj.get('groups', ''),
                        'Remote': master_proj.get('remote', '')
                    })
                continue
            
            # 檢查是否為完全跳過的特殊項目
            if self._should_skip_conversion(master_revision):
                debug_counters['skipped_special'] += 1
                self.stats['skipped_special_projects'] += 1
                
                # ... 跳過特殊項目的處理邏輯保持不變 ...
                if name in premp_projects:
                    premp_proj = premp_projects[name]
                    premp_revision = premp_proj['revision']
                    
                    all_results.append({
                        'SN': sn,
                        '專案名稱': name,
                        '專案路徑': master_proj['path'],
                        'Master Revision': master_revision,
                        '轉換後 Revision': 'N/A (跳過特殊項目)',
                        'PreMP Revision (正確版)': premp_revision,
                        '狀態': '🟣 跳過轉換 (特殊項目)',
                        '轉換是否正確': 'N/A',
                        '差異說明': self._get_skip_reason(master_revision),
                        'Upstream': master_proj.get('upstream', ''),
                        'Dest-Branch': master_proj.get('dest-branch', ''),
                        'Groups': master_proj.get('groups', ''),
                        'Remote': master_proj.get('remote', '')
                    })
                else:
                    all_results.append({
                        'SN': sn,
                        '專案名稱': name,
                        '專案路徑': master_proj['path'],
                        'Master Revision': master_revision,
                        '轉換後 Revision': 'N/A (跳過特殊項目)',
                        'PreMP Revision (正確版)': 'N/A (專案不存在)',
                        '狀態': '🟣 跳過轉換 (特殊項目且PreMP不存在)',
                        '轉換是否正確': 'N/A',
                        '差異說明': f'{self._get_skip_reason(master_revision)}，且 PreMP 中不存在此專案',
                        'Upstream': master_proj.get('upstream', ''),
                        'Dest-Branch': master_proj.get('dest-branch', ''),
                        'Groups': master_proj.get('groups', ''),
                        'Remote': master_proj.get('remote', '')
                    })
                continue
            
            # 有 revision 且需要轉換的專案
            self.stats['revision_projects'] += 1
            
            # 在 premp 中查找對應專案
            if name in premp_projects:
                premp_proj = premp_projects[name]
                premp_revision = premp_proj['revision']
                
                # 檢查 master 和 premp 的原始 revision 是否相同
                if master_revision == premp_revision:
                    debug_counters['same_revision'] += 1
                    self.stats['matched'] += 1
                    self.stats['same_revision_projects'] += 1
                    status = '✅ 匹配 (原始相同)'
                    is_correct = '是'
                    description = f'Master 和 PreMP 的原始 revision 相同: {master_revision}，無需轉換'
                    final_converted_revision = master_revision
                else:
                    # 進行轉換比對
                    converted_revision = self.convert_revision(master_revision)
                    
                    if converted_revision == premp_revision:
                        debug_counters['converted_match'] += 1
                        self.stats['matched'] += 1
                        status = '✅ 匹配'
                        is_correct = '是'
                        description = '轉換結果與 PreMP 正確版完全匹配'
                        final_converted_revision = converted_revision
                    else:
                        debug_counters['converted_mismatch'] += 1
                        self.stats['mismatched'] += 1
                        status = '❌ 不匹配'
                        is_correct = '否'
                        description = f'期望: {premp_revision}, 實際: {converted_revision}'
                        final_converted_revision = converted_revision
                        
                        # 🔥 只有真正的不匹配才加入failed_cases
                        self.failed_cases.append({
                            'SN': sn,
                            '專案名稱': name,
                            '專案路徑': master_proj['path'],
                            'Master Revision': master_revision,
                            '轉換後 Revision': converted_revision,
                            'PreMP Revision (正確版)': premp_revision,
                            '差異說明': description,
                            '轉換規則類型': self._identify_rule_type(master_revision, converted_revision),
                            'Upstream': master_proj.get('upstream', ''),
                            'Dest-Branch': master_proj.get('dest-branch', ''),
                            'Groups': master_proj.get('groups', ''),
                            'Remote': master_proj.get('remote', '')
                        })
                
                all_results.append({
                    'SN': sn,
                    '專案名稱': name,
                    '專案路徑': master_proj['path'],
                    'Master Revision': master_revision,
                    '轉換後 Revision': final_converted_revision,
                    'PreMP Revision (正確版)': premp_revision,
                    '狀態': status,
                    '轉換是否正確': is_correct,
                    '差異說明': description,
                    'Upstream': master_proj.get('upstream', ''),
                    'Dest-Branch': master_proj.get('dest-branch', ''),
                    'Groups': master_proj.get('groups', ''),
                    'Remote': master_proj.get('remote', '')
                })
            else:
                # PreMP中不存在的專案
                debug_counters['not_found_in_premp'] += 1
                converted_revision = self.convert_revision(master_revision)
                self.stats['not_found_in_premp'] += 1
                status = '🔶 PreMP中不存在 (非轉換錯誤)'
                
                all_results.append({
                    'SN': sn,
                    '專案名稱': name,
                    '專案路徑': master_proj['path'],
                    'Master Revision': master_revision,
                    '轉換後 Revision': converted_revision,
                    'PreMP Revision (正確版)': 'N/A (專案不存在)',
                    '狀態': status,
                    '轉換是否正確': 'N/A',
                    '差異說明': '專案在 PreMP manifest 中不存在，無法驗證轉換正確性',
                    'Upstream': master_proj.get('upstream', ''),
                    'Dest-Branch': master_proj.get('dest-branch', ''),
                    'Groups': master_proj.get('groups', ''),
                    'Remote': master_proj.get('remote', '')
                })
        
        # 處理僅存在於PreMP的專案
        for name in premp_projects:
            if name not in master_projects:
                self.stats['extra_in_premp'] += 1
                sn = len(all_results) + 1
                all_results.append({
                    'SN': sn,
                    '專案名稱': name,
                    '專案路徑': premp_projects[name]['path'],
                    'Master Revision': 'N/A (專案不存在)',
                    '轉換後 Revision': 'N/A',
                    'PreMP Revision (正確版)': premp_projects[name]['revision'],
                    '狀態': '🔶 僅存在於PreMP',
                    '轉換是否正確': 'N/A',
                    '差異說明': '專案僅存在於 PreMP manifest 中',
                    'Upstream': premp_projects[name].get('upstream', ''),
                    'Dest-Branch': premp_projects[name].get('dest-branch', ''),
                    'Groups': premp_projects[name].get('groups', ''),
                    'Remote': premp_projects[name].get('remote', '')
                })
        
        # 🔥 調試資訊
        self.logger.info(f"🔍 比對結果調試:")
        self.logger.info(f"  - 無revision: {debug_counters['no_revision']}")
        self.logger.info(f"  - 跳過特殊: {debug_counters['skipped_special']}")
        self.logger.info(f"  - 原始相同: {debug_counters['same_revision']}")
        self.logger.info(f"  - 轉換匹配: {debug_counters['converted_match']}")
        self.logger.info(f"  - 轉換不匹配: {debug_counters['converted_mismatch']}")
        self.logger.info(f"  - PreMP中不存在: {debug_counters['not_found_in_premp']}")
        self.logger.info(f"  - failed_cases數量: {len(self.failed_cases)}")
        self.logger.info(f"  - stats.mismatched: {self.stats['mismatched']}")
        
        return all_results

    def _should_skip_conversion(self, revision: str) -> bool:
        """
        判斷是否應該完全跳過轉換比對的特殊項目
        修改：新增 Google 項目跳過邏輯
        
        Args:
            revision: 專案的 revision
            
        Returns:
            是否應該跳過
        """
        if not revision:
            return False
        
        revision = revision.strip()
        
        # 🆕 跳過 Google 開頭的項目
        if revision.startswith('google/'):
            return True
        
        # 完全跳過轉換的項目（如 refs/tags）
        if revision.startswith('refs/tags/'):
            return True
        
        return False
        
    def _get_skip_reason(self, revision: str) -> str:
        """
        取得跳過轉換的原因說明
        修改：新增 Google 項目的跳過原因
        
        Args:
            revision: 專案的 revision
            
        Returns:
            跳過原因
        """
        if not revision:
            return '未知原因'
        
        revision = revision.strip()
        
        if revision.startswith('google/'):
            return 'Google 項目不需要轉換'
        elif revision.startswith('refs/tags/'):
            return 'Git tags 不需要轉換'
        else:
            return '特殊項目，完全跳過轉換'
                
    def generate_excel_report(self, differences: List[Dict], output_file: str, 
                    master_file: str, premp_file: str) -> bool:
        """
        生成 Excel 測試報告
        修正：增加failed_cases調試資訊
        """
        try:
            # 🔥 關鍵調試：檢查failed_cases狀態
            self.logger.info(f"🔍 Excel生成時 failed_cases 數量: {len(self.failed_cases)}")
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # 頁籤 1: 測試摘要
                summary_data = [{
                    '測試時間': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'Master Manifest': os.path.basename(master_file),
                    'PreMP Manifest (正確版)': os.path.basename(premp_file),
                    '總專案數': self.stats['total_projects'],
                    '🔵 有revision專案數': self.stats['revision_projects'],
                    '⚪ 無revision專案數': self.stats['no_revision_projects'],
                    '🟢 原始相同專案數': self.stats['same_revision_projects'],
                    '✅ 匹配數': self.stats['matched'],
                    '❌ 不匹配數': self.stats['mismatched'],
                    '⚠️ PreMP中不存在': self.stats['not_found_in_premp'],
                    '🔶 僅存在於PreMP': self.stats['extra_in_premp'],
                    '轉換成功率': f"{(self.stats['matched'] / self.stats['revision_projects'] * 100):.2f}%" if self.stats['revision_projects'] > 0 else '0%',
                    '備註': f"跳過 {self.stats['no_revision_projects']} 個無revision專案的轉換比對"
                }]
                
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='測試摘要', index=False)
                
                # 頁籤 2: 需要關注的項目
                if differences:
                    df_diff = pd.DataFrame(differences)
                    
                    need_attention = df_diff[
                        (~df_diff['狀態'].str.contains('無需轉換', na=False)) &
                        (df_diff['狀態'] != '✅ 匹配') &
                        (df_diff['狀態'] != '✅ 匹配 (原始相同)')
                    ]
                    
                    if not need_attention.empty:
                        need_attention.to_excel(writer, sheet_name='需要關注的項目', index=False)
                    
                    # 頁籤 3: 無需轉換的專案
                    no_conversion_needed = df_diff[
                        df_diff['狀態'].str.contains('無需轉換', na=False)
                    ]
                    
                    if not no_conversion_needed.empty:
                        no_conversion_needed.to_excel(writer, sheet_name='無需轉換專案', index=False)
                    
                    # 🔥 頁籤 4: 失敗案例詳細對照 - 修正條件判斷
                    self.logger.info(f"🔍 準備創建失敗案例頁籤，failed_cases數量: {len(self.failed_cases)}")
                    if self.failed_cases and len(self.failed_cases) > 0:
                        df_failed = pd.DataFrame(self.failed_cases)
                        df_failed.to_excel(writer, sheet_name='失敗案例詳細對照', index=False)
                        self.logger.info(f"✅ 已創建失敗案例詳細對照頁籤，包含 {len(self.failed_cases)} 個案例")
                    else:
                        self.logger.warning(f"⚠️ 未創建失敗案例詳細對照頁籤，failed_cases為空")
                
                # 頁籤 5: 所有專案對照表
                all_comparisons = []
                for diff in differences:
                    status_icon = '🔵' if '無需轉換' in diff['狀態'] else (
                        '✅' if '匹配' in diff['狀態'] else '❌'
                    )
                    
                    all_comparisons.append({
                        'SN': diff['SN'],
                        '專案名稱': diff['專案名稱'],
                        '專案類型': '無revision' if '無需轉換' in diff['狀態'] else '有revision',
                        'Master Revision': diff['Master Revision'],
                        '轉換後 Revision': diff['轉換後 Revision'],
                        'PreMP Revision (正確版)': diff['PreMP Revision (正確版)'],
                        '結果': status_icon,
                        '狀態說明': diff['狀態']
                    })
                
                if all_comparisons:
                    df_all = pd.DataFrame(all_comparisons)
                    df_all.to_excel(writer, sheet_name='所有專案對照', index=False)
                
                # 頁籤 6: 轉換規則統計
                rule_stats = self._analyze_conversion_rules(differences)
                if rule_stats:
                    df_rules = pd.DataFrame(rule_stats)
                    df_rules.to_excel(writer, sheet_name='轉換規則統計', index=False)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self._format_worksheet(worksheet, sheet_name)
            
            self.logger.info(f"✅ 成功生成測試報告: {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"生成 Excel 報告失敗: {str(e)}")
            return False
    
    def _analyze_conversion_rules(self, differences: List[Dict]) -> List[Dict]:
        """
        分析轉換規則的使用情況 - 修正版本，確保失敗判斷邏輯一致
        修正：只有真正的轉換錯誤才算失敗，排除"PreMP中不存在"等非轉換錯誤
        """
        rule_usage = {}
        
        for diff in differences:
            # 🔥 修正：跳過更多不需要統計的項目
            master_rev = diff['Master Revision']
            status = diff['狀態']
            
            # 跳過沒有 revision 的專案
            if (master_rev == 'N/A (專案不存在)' or 
                '無 (沒有 revision 屬性)' in master_rev):
                continue
                
            # 🔥 跳過無需轉換的專案（新增）
            if '無需轉換' in status:
                continue
                
            # 🔥 跳過特殊項目（新增）
            if '跳過' in status:
                continue
            
            # 🔥 跳過非轉換錯誤的項目（關鍵修正）
            if 'PreMP中不存在' in status or '僅存在於PreMP' in status:
                continue
                    
            # 分析使用了哪種轉換規則
            converted_rev = diff['轉換後 Revision']
            
            # 判斷規則類型
            rule_type = self._identify_rule_type(master_rev, converted_rev)
            
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
            
            # 🔥 修正：更精確的成功/失敗判斷
            if status == '✅ 匹配' or status == '✅ 匹配 (原始相同)':
                rule_usage[rule_type]['成功次數'] += 1
            elif status == '❌ 不匹配':
                # 🔥 只有真正的不匹配才算失敗
                rule_usage[rule_type]['失敗次數'] += 1
                rule_usage[rule_type]['失敗案例SN'].append(diff['SN'])
                
                # 記錄失敗範例（最多3個）
                if len(rule_usage[rule_type]['失敗範例']) < 3:
                    rule_usage[rule_type]['失敗範例'].append(f"{master_rev} → {converted_rev}")
            else:
                # 🔥 其他狀態（如PreMP中不存在）不算成功也不算失敗，只記錄使用次數
                self.logger.debug(f"跳過狀態統計: {status} - {master_rev}")
                continue
        
        # 轉換為列表並加入成功率和失敗案例SN
        result = []
        for rule_type, stats in rule_usage.items():
            # 🔥 修正：只有實際進行成功/失敗判斷的項目才計算成功率
            actual_judged = stats['成功次數'] + stats['失敗次數']
            if actual_judged > 0:
                stats['成功率'] = f"{(stats['成功次數'] / actual_judged * 100):.1f}%"
            else:
                stats['成功率'] = 'N/A'
                
            stats['失敗範例詳情'] = '\n'.join(stats['失敗範例']) if stats['失敗範例'] else 'N/A'
            
            # 格式化失敗案例SN列表
            if stats['失敗案例SN']:
                sn_list = [str(sn) for sn in stats['失敗案例SN']]
                if len(sn_list) <= 10:
                    stats['失敗案例SN列表'] = ', '.join(sn_list)
                else:
                    stats['失敗案例SN列表'] = ', '.join(sn_list[:10]) + f' ...等{len(sn_list)}個'
            else:
                stats['失敗案例SN列表'] = 'N/A'
            
            # 清理不需要的欄位
            del stats['失敗案例SN']
            del stats['失敗範例']
            
            result.append(stats)
        
        # 🔥 新增：調試資訊
        total_failures = sum(r['失敗次數'] for r in result)
        self.logger.info(f"🔍 轉換規則統計分析完成:")
        self.logger.info(f"  - 規則類型數: {len(result)}")
        self.logger.info(f"  - 總失敗次數: {total_failures}")
        self.logger.info(f"  - mismatched統計: {self.stats.get('mismatched', 0)}")
        
        return result
    
    def _identify_rule_type(self, master_rev: str, converted_rev: str) -> str:
        """識別使用的轉換規則類型 - 新增版本"""
        # 🆕 檢查是否跳過 Google 項目
        if master_rev.startswith('google/'):
            return "Google項目跳過"
        
        # 檢查是否使用精確匹配
        if master_rev in config.MASTER_TO_PREMP_EXACT_MAPPING:
            return "精確匹配"
        
        # 🆕 檢查新增的精確匹配規則
        new_exact_rules = [
            'realtek/linux-5.15/android-14/master',
            'realtek/linux-4.14/android-14/master', 
            'realtek/mp.google-refplus',
            'realtek/android-14/mp.google-refplus'
        ]
        if master_rev in new_exact_rules:
            return "新增精確匹配"
        
        # 檢查是否保持不變
        if master_rev == converted_rev:
            return "保持不變"
        
        # 🆕 檢查 Linux kernel 轉換
        if 'linux-' in master_rev and '/master' in master_rev:
            return "Linux Kernel Master轉換"
        
        # 檢查是否是晶片轉換
        for chip in config.CHIP_TO_RTD_MAPPING.keys():
            if f'/{chip}/' in master_rev:
                return f"晶片轉換 ({chip})"
        
        # 檢查是否是 upgrade 版本轉換
        if 'upgrade' in master_rev or 'upgrade' in converted_rev:
            return "Upgrade版本轉換"
        
        # 檢查是否是 kernel 版本轉換
        if 'linux-' in master_rev:
            return "Kernel版本轉換"
        
        # 🆕 檢查是否是直接的 mp 到 premp 轉換
        if master_rev == 'realtek/mp.google-refplus' and 'premp.google-refplus' in converted_rev:
            return "直接MP到PreMP轉換"
        
        # 檢查是否是 mp 到 premp 轉換
        if 'mp.google-refplus' in master_rev and 'premp.google-refplus' in converted_rev:
            return "MP到PreMP轉換"
        
        # 預設
        return "智能推斷或預設"
    
    def _format_worksheet(self, worksheet, sheet_name: str):
        """格式化 Excel 工作表 - 增加失敗案例詳細對照的格式"""
        from openpyxl.styles import PatternFill, Font, Alignment
        from openpyxl.utils import get_column_letter
        
        # 定義顏色
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        
        # 差異顏色
        red_fill = PatternFill(start_color="FFE6E6", end_color="FFE6E6", fill_type="solid")      # 不匹配
        green_fill = PatternFill(start_color="E6FFE6", end_color="E6FFE6", fill_type="solid")    # 匹配
        yellow_fill = PatternFill(start_color="FFFACD", end_color="FFFACD", fill_type="solid")   # 不存在
        blue_fill = PatternFill(start_color="E6F3FF", end_color="E6F3FF", fill_type="solid")     # 無需轉換
        orange_fill = PatternFill(start_color="FFE4B5", end_color="FFE4B5", fill_type="solid")   # 失敗案例
        
        # 設定標題格式
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # 根據頁籤設定特定格式
        if sheet_name in ['需要關注的項目', '無需轉換專案', '所有專案對照']:
            # 為不同狀態設定背景色
            for row in range(2, worksheet.max_row + 1):
                # 找到狀態欄位（可能在不同位置）
                status_cell = None
                for col in range(1, worksheet.max_column + 1):
                    header = worksheet.cell(row=1, column=col).value
                    if header and ('狀態' in str(header) or '結果' in str(header)):
                        status_cell = worksheet.cell(row=row, column=col)
                        break
                
                if status_cell and status_cell.value:
                    status_value = str(status_cell.value)
                    fill_color = None
                    
                    if '不匹配' in status_value or '❌' in status_value:
                        fill_color = red_fill
                    elif '匹配' in status_value or '✅' in status_value:
                        fill_color = green_fill
                    elif '不存在' in status_value or '⚠️' in status_value:
                        fill_color = yellow_fill
                    elif '無需轉換' in status_value or '🔵' in status_value:
                        fill_color = blue_fill
                    
                    # 套用背景色到整行
                    if fill_color:
                        for col in range(1, worksheet.max_column + 1):
                            worksheet.cell(row=row, column=col).fill = fill_color
        
        # 🆕 失敗案例詳細對照頁籤的特殊格式
        elif sheet_name == '失敗案例詳細對照':
            for row in range(2, worksheet.max_row + 1):
                for col in range(1, worksheet.max_column + 1):
                    worksheet.cell(row=row, column=col).fill = orange_fill
        
        # 🆕 轉換規則統計頁籤的特殊格式
        elif sheet_name == '轉換規則統計':
            for row in range(2, worksheet.max_row + 1):
                # 找到失敗次數欄位
                failure_count_cell = None
                for col in range(1, worksheet.max_column + 1):
                    header = worksheet.cell(row=1, column=col).value
                    if header and '失敗次數' in str(header):
                        failure_count_cell = worksheet.cell(row=row, column=col)
                        break
                
                if failure_count_cell and failure_count_cell.value and int(failure_count_cell.value) > 0:
                    # 如果有失敗案例，整行用淺紅色標示
                    for col in range(1, worksheet.max_column + 1):
                        worksheet.cell(row=row, column=col).fill = red_fill
        
        # 自動調整欄寬
        for column in worksheet.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            
            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    def test_conversion(self, master_file: str, premp_file: str, output_file: str) -> bool:
        """
        執行轉換測試 - 修改結果顯示邏輯，增加相同revision統計
        """
        try:
            self.logger.info("="*80)
            self.logger.info("開始測試 Master to PreMP 轉換規則")
            self.logger.info("="*80)
            
            # 步驟 1: 解析 manifest 檔案
            self.logger.info("\n📋 步驟 1: 解析 manifest 檔案")
            master_projects = self.parse_manifest(master_file)
            premp_projects = self.parse_manifest(premp_file)
            
            # 步驟 2: 比對轉換結果
            self.logger.info("\n🔍 步驟 2: 比對轉換結果")
            differences = self.compare_manifests(master_projects, premp_projects)
            
            # 步驟 3: 生成報告
            self.logger.info("\n📊 步驟 3: 生成測試報告")
            self.generate_excel_report(differences, output_file, master_file, premp_file)
            
            # 步驟 4: 顯示測試結果 - 更新統計顯示
            self.logger.info("\n📈 測試結果統計:")
            self.logger.info(f"  總專案數: {self.stats['total_projects']}")
            self.logger.info(f"  🔵 有revision專案: {self.stats['revision_projects']}")
            self.logger.info(f"  ⚪ 無revision專案: {self.stats['no_revision_projects']} (跳過轉換)")
            self.logger.info(f"  🟢 原始相同專案: {self.stats['same_revision_projects']} (Master=PreMP)")
            self.logger.info(f"  ✅ 轉換匹配: {self.stats['matched']}")
            self.logger.info(f"  ❌ 轉換不匹配: {self.stats['mismatched']}")
            self.logger.info(f"  ⚠️ PreMP中不存在: {self.stats['not_found_in_premp']}")
            self.logger.info(f"  🔶 僅存在於PreMP: {self.stats['extra_in_premp']}")
            
            # 計算轉換成功率（只考慮有 revision 的專案）
            if self.stats['revision_projects'] > 0:
                conversion_rate = (self.stats['matched'] / self.stats['revision_projects'] * 100)
                self.logger.info(f"  📊 轉換成功率: {conversion_rate:.2f}%")
            
            # 🆕 顯示失敗案例資訊
            if self.failed_cases:
                self.logger.info(f"\n❌ 失敗案例分析:")
                self.logger.info(f"  失敗案例數: {len(self.failed_cases)}")
                self.logger.info(f"  詳細對照已添加到 '失敗案例詳細對照' 頁籤")
                
                # 按規則類型分組顯示失敗案例
                rule_failures = {}
                for case in self.failed_cases:
                    rule_type = case['轉換規則類型']
                    if rule_type not in rule_failures:
                        rule_failures[rule_type] = []
                    rule_failures[rule_type].append(case['SN'])
                
                for rule_type, sn_list in rule_failures.items():
                    self.logger.info(f"    {rule_type}: SN {', '.join(map(str, sn_list))}")
            
            # 計算測試是否通過（只考慮有 revision 的專案）
            conversion_passed = (self.stats['mismatched'] == 0)
            
            if self.stats['no_revision_projects'] > 0:
                self.logger.info(f"\n💡 說明: 跳過了 {self.stats['no_revision_projects']} 個沒有 revision 屬性的專案")
                self.logger.info("    這些專案不需要進行轉換比對，只記錄狀態資訊")
            
            if self.stats['same_revision_projects'] > 0:
                self.logger.info(f"\n💡 說明: {self.stats['same_revision_projects']} 個專案的 Master 和 PreMP revision 完全相同")
                self.logger.info("    這些專案無需轉換，直接算作匹配成功")
            
            if conversion_passed:
                self.logger.info("\n✅ 所有需要轉換的專案規則測試通過！")
            else:
                self.logger.warning(f"\n⚠️ 發現 {self.stats['mismatched']} 個轉換錯誤")
                self.logger.info(f"詳細差異請查看: {output_file}")
                self.logger.info(f"特別查看 '失敗案例詳細對照' 和 '轉換規則統計' 頁籤")
            
            self.logger.info("="*80)
            return conversion_passed
            
        except Exception as e:
            self.logger.error(f"測試執行失敗: {str(e)}")
            return False


def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='測試 Master to PreMP Manifest 轉換規則')
    parser.add_argument('master_file', help='Master manifest.xml 檔案路徑')
    parser.add_argument('premp_file', help='PreMP manifest.xml 檔案路徑（正確版）')
    parser.add_argument('-o', '--output', default='conversion_test_report.xlsx',
                       help='輸出 Excel 檔案名稱（預設: conversion_test_report.xlsx）')
    
    args = parser.parse_args()
    
    # 確保輸出目錄存在
    output_dir = os.path.dirname(args.output) or '.'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 執行測試
    tester = ManifestConversionTester()
    success = tester.test_conversion(args.master_file, args.premp_file, args.output)
    
    # 返回狀態碼
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()