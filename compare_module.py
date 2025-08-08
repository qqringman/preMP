# ===== compare_module.py - 修改比對結果儲存邏輯 =====

import os
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
import shutil
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class CompareModule:
    def __init__(self, task_id: str = None):
        self.task_id = task_id or self._generate_task_id()
        self.base_output_dir = Path('compare_results') / self.task_id
        self.results = {}
        
    def _generate_task_id(self) -> str:
        """生成唯一的任務 ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        return f"task_{timestamp}_{unique_id}"
    
    def compare_all_scenarios(self, source_dir: str, progress_callback=None) -> Dict:
        """執行所有比對情境，並分別儲存結果"""
        all_results = {
            'task_id': self.task_id,
            'source_dir': source_dir,
            'timestamp': datetime.now().isoformat(),
            'scenarios': {},
            'compare_results': {}  # 保持相容性
        }
        
        scenarios = [
            ('master_vs_premp', 'Master vs PreMP'),
            ('premp_vs_wave', 'PreMP vs Wave'),
            ('wave_vs_backup', 'Wave vs Backup')
        ]
        
        total_steps = len(scenarios)
        
        for idx, (scenario_key, scenario_name) in enumerate(scenarios):
            try:
                # 更新進度
                if progress_callback:
                    progress = int((idx / total_steps) * 100)
                    progress_callback(progress, f"正在比對 {scenario_name}...")
                
                # 執行單一情境比對
                scenario_result = self._compare_single_scenario(
                    source_dir, 
                    scenario_key,
                    scenario_name
                )
                
                # 儲存到各自的資料夾
                if scenario_result and scenario_result.get('success', 0) > 0:
                    self._save_scenario_results(scenario_key, scenario_result)
                
                # 加入總結果
                all_results['scenarios'][scenario_key] = scenario_result
                all_results['compare_results'][scenario_key] = {
                    'success': scenario_result.get('success', 0),
                    'failed': scenario_result.get('failed', 0),
                    'failed_modules': scenario_result.get('failed_modules', [])
                }
                
            except Exception as e:
                logger.error(f"比對 {scenario_name} 時發生錯誤: {str(e)}")
                all_results['scenarios'][scenario_key] = {
                    'error': str(e),
                    'success': 0,
                    'failed': 0
                }
                all_results['compare_results'][scenario_key] = {
                    'success': 0,
                    'failed': 0,
                    'error': str(e)
                }
        
        # 更新進度到 100%
        if progress_callback:
            progress_callback(100, "比對完成！")
        
        # 儲存總結果摘要
        self._save_summary(all_results)
        
        return all_results
    
    def _compare_single_scenario(self, source_dir: str, scenario_key: str, 
                                scenario_name: str) -> Dict:
        """執行單一情境的比對"""
        result = {
            'scenario': scenario_name,
            'scenario_key': scenario_key,
            'timestamp': datetime.now().isoformat(),
            'success': 0,
            'failed': 0,
            'failed_modules': [],
            'data': {}
        }
        
        try:
            # 根據不同的情境執行相應的比對邏輯
            if scenario_key == 'master_vs_premp':
                compare_data = self._compare_master_premp(source_dir)
            elif scenario_key == 'premp_vs_wave':
                compare_data = self._compare_premp_wave(source_dir)
            elif scenario_key == 'wave_vs_backup':
                compare_data = self._compare_wave_backup(source_dir)
            else:
                compare_data = {}
            
            # 更新結果
            result['data'] = compare_data
            result['success'] = compare_data.get('module_count', 0)
            result['failed'] = compare_data.get('failed_count', 0)
            result['failed_modules'] = compare_data.get('failed_modules', [])
            
        except Exception as e:
            logger.error(f"執行 {scenario_name} 比對時發生錯誤: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    def _save_scenario_results(self, scenario_key: str, scenario_result: Dict):
        """儲存單一情境的結果到獨立資料夾"""
        # 建立情境專屬資料夾
        scenario_dir = self.base_output_dir / scenario_key
        scenario_dir.mkdir(parents=True, exist_ok=True)
        
        # 儲存 JSON 結果
        json_path = scenario_dir / 'result.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(scenario_result, f, ensure_ascii=False, indent=2)
        
        # 生成並儲存 Excel 檔案
        excel_path = scenario_dir / f'{scenario_key}_compare.xlsx'
        self._generate_scenario_excel(scenario_result, excel_path)
        
        # 如果有差異資料，也生成詳細的 Excel
        if scenario_result.get('data'):
            self._generate_detailed_excel(scenario_result['data'], scenario_dir)
        
        logger.info(f"已儲存 {scenario_key} 結果到 {scenario_dir}")
    
    def _generate_scenario_excel(self, scenario_result: Dict, output_path: Path):
        """為單一情境生成 Excel 檔案"""
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # 摘要頁
                summary_data = {
                    '項目': ['情境名稱', '執行時間', '成功模組數', '失敗模組數'],
                    '值': [
                        scenario_result.get('scenario', ''),
                        scenario_result.get('timestamp', ''),
                        scenario_result.get('success', 0),
                        scenario_result.get('failed', 0)
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='摘要', index=False)
                
                # 如果有差異資料，加入各種差異的工作表
                data = scenario_result.get('data', {})
                
                # Revision 差異
                if 'revision_diff' in data and data['revision_diff']:
                    df = pd.DataFrame(data['revision_diff'])
                    df.to_excel(writer, sheet_name='Revision差異', index=False)
                
                # 分支錯誤
                if 'branch_errors' in data and data['branch_errors']:
                    df = pd.DataFrame(data['branch_errors'])
                    df.to_excel(writer, sheet_name='分支錯誤', index=False)
                
                # 新增/刪除專案
                if 'lost_projects' in data and data['lost_projects']:
                    df = pd.DataFrame(data['lost_projects'])
                    df.to_excel(writer, sheet_name='新增刪除專案', index=False)
                
                # 版本差異
                if 'version_diff' in data and data['version_diff']:
                    df = pd.DataFrame(data['version_diff'])
                    df.to_excel(writer, sheet_name='版本差異', index=False)
                
                # 失敗的模組
                if scenario_result.get('failed_modules'):
                    failed_df = pd.DataFrame([
                        {'序號': i+1, '模組名稱': module, '原因': '無法比對'}
                        for i, module in enumerate(scenario_result['failed_modules'])
                    ])
                    failed_df.to_excel(writer, sheet_name='失敗模組', index=False)
                
                logger.info(f"已生成 Excel 檔案: {output_path}")
                
        except Exception as e:
            logger.error(f"生成 Excel 檔案時發生錯誤: {str(e)}")
    
    def _generate_detailed_excel(self, data: Dict, output_dir: Path):
        """生成包含所有詳細資料的 Excel 檔案"""
        detailed_path = output_dir / 'detailed_compare.xlsx'
        
        try:
            with pd.ExcelWriter(detailed_path, engine='openpyxl') as writer:
                # 將所有資料寫入不同的工作表
                sheet_mapping = {
                    'revision_diff': 'Revision差異',
                    'branch_errors': '分支錯誤', 
                    'lost_projects': '新增刪除專案',
                    'version_diff': '版本差異',
                    'manifest_diff': 'Manifest差異',
                    'file_diff': '檔案差異'
                }
                
                for key, sheet_name in sheet_mapping.items():
                    if key in data and data[key]:
                        df = pd.DataFrame(data[key])
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        
                        # 調整欄寬
                        worksheet = writer.sheets[sheet_name]
                        for column in df.columns:
                            column_length = max(
                                df[column].astype(str).map(len).max(),
                                len(str(column))
                            )
                            col_idx = df.columns.get_loc(column)
                            worksheet.column_dimensions[
                                worksheet.cell(1, col_idx + 1).column_letter
                            ].width = min(column_length + 2, 50)
                
                logger.info(f"已生成詳細 Excel 檔案: {detailed_path}")
                
        except Exception as e:
            logger.error(f"生成詳細 Excel 檔案時發生錯誤: {str(e)}")
    
    def _save_summary(self, all_results: Dict):
        """儲存總摘要"""
        # 儲存總 JSON
        summary_path = self.base_output_dir / 'summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        
        # 生成總覽 Excel
        overview_path = self.base_output_dir / 'all_scenarios_overview.xlsx'
        self._generate_overview_excel(all_results, overview_path)
    
    def _generate_overview_excel(self, all_results: Dict, output_path: Path):
        """生成總覽 Excel 檔案"""
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # 總覽頁
                overview_data = []
                for scenario_key, scenario_data in all_results['scenarios'].items():
                    overview_data.append({
                        '情境': scenario_data.get('scenario', scenario_key),
                        '成功模組數': scenario_data.get('success', 0),
                        '失敗模組數': scenario_data.get('failed', 0),
                        '執行時間': scenario_data.get('timestamp', ''),
                        '狀態': '完成' if not scenario_data.get('error') else '錯誤'
                    })
                
                if overview_data:
                    overview_df = pd.DataFrame(overview_data)
                    overview_df.to_excel(writer, sheet_name='總覽', index=False)
                    
                    # 調整欄寬
                    worksheet = writer.sheets['總覽']
                    for column in overview_df.columns:
                        column_length = max(
                            overview_df[column].astype(str).map(len).max(),
                            len(str(column))
                        )
                        col_idx = overview_df.columns.get_loc(column)
                        worksheet.column_dimensions[
                            worksheet.cell(1, col_idx + 1).column_letter
                        ].width = column_length + 2
                
                logger.info(f"已生成總覽 Excel 檔案: {output_path}")
                
        except Exception as e:
            logger.error(f"生成總覽 Excel 檔案時發生錯誤: {str(e)}")
    
    def get_results_structure(self) -> Dict:
        """取得結果的資料夾結構"""
        structure = {
            'task_id': self.task_id,
            'base_path': str(self.base_output_dir),
            'scenarios': {}
        }
        
        if self.base_output_dir.exists():
            for scenario_dir in self.base_output_dir.iterdir():
                if scenario_dir.is_dir() and scenario_dir.name in ['master_vs_premp', 'premp_vs_wave', 'wave_vs_backup']:
                    files = []
                    for file in scenario_dir.iterdir():
                        if file.is_file():
                            files.append({
                                'name': file.name,
                                'path': str(file),
                                'size': file.stat().st_size
                            })
                    structure['scenarios'][scenario_dir.name] = {
                        'path': str(scenario_dir),
                        'files': files
                    }
        
        return structure

    # ... 其他比對邏輯方法 (_compare_master_premp, _compare_premp_wave, _compare_wave_backup) ...