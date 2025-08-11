#!/usr/bin/env python3
"""
分支操作命令列工具
支援 create, delete, update, query 操作
"""
import argparse
from gerrit_manager import GerritManager
from feature_two import FeatureTwo

def main():
    parser = argparse.ArgumentParser(description='Branch 操作工具')
    parser.add_argument('operation', choices=['create', 'delete', 'update', 'query'],
                       help='操作類型')
    parser.add_argument('--project', required=True, help='專案名稱')
    parser.add_argument('--branch', help='分支名稱')
    parser.add_argument('--revision', help='Revision (commit hash)')
    parser.add_argument('--force', action='store_true', help='強制更新（用於 update）')
    parser.add_argument('--verbose', action='store_true', help='顯示詳細資訊')
    
    args = parser.parse_args()
    
    # 設定日誌等級
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    gerrit = GerritManager()
    
    if args.operation == 'create':
        if not args.branch or not args.revision:
            print("錯誤：create 操作需要 --branch 和 --revision 參數")
            return
            
        result = gerrit.create_branch(args.project, args.branch, args.revision)
        print(f"建立結果: {result['success']}")
        print(f"訊息: {result['message']}")
        
    elif args.operation == 'delete':
        if not args.branch:
            print("錯誤：delete 操作需要 --branch 參數")
            return
            
        # 確認刪除
        confirm = input(f"確定要刪除分支 {args.branch}? (y/N): ")
        if confirm.lower() != 'y':
            print("取消刪除")
            return
            
        result = gerrit.delete_branch(args.project, args.branch)
        print(f"刪除結果: {result['success']}")
        print(f"訊息: {result['message']}")
        
    elif args.operation == 'update':
        if not args.branch or not args.revision:
            print("錯誤：update 操作需要 --branch 和 --revision 參數")
            return
            
        result = gerrit.update_branch(args.project, args.branch, args.revision, args.force)
        print(f"更新結果: {result['success']}")
        print(f"訊息: {result['message']}")
        if result['success']:
            print(f"  舊 Revision: {result['old_revision']}")
            print(f"  新 Revision: {result['new_revision']}")
        
    elif args.operation == 'query':
        branches = gerrit.query_branches(args.project)
        if branches:
            print(f"找到 {len(branches)} 個分支:")
            for branch in branches:
                # 如果指定了特定分支，只顯示該分支
                if args.branch:
                    if args.branch in branch:
                        # 取得該分支的詳細資訊
                        branch_info = gerrit.check_branch_exists_and_get_revision(args.project, branch)
                        print(f"  - {branch} (revision: {branch_info.get('revision', 'unknown')})")
                else:
                    print(f"  - {branch}")
        else:
            print("沒有找到分支或無法存取專案")

if __name__ == '__main__':
    main()