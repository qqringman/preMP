#!/bin/bash
# 測試分支操作的腳本

PROJECT="realtek/dante/common/misc"
TEST_BRANCH="vp/test-branch"
REVISION1="f8e835c1c36fa3ca6f06c3d0a059eec8be4d7ac6"
REVISION2="ce372d1d212b0dd580233db760e92fd251950bd6"  # 替換為另一個有效的 commit hash

echo "========================================="
echo "測試分支操作"
echo "專案: $PROJECT"
echo "分支: $TEST_BRANCH"
echo "========================================="
echo

# 1. 查詢現有分支
echo "1. 查詢現有分支..."
python3 branch_operations.py query --project "$PROJECT" | head -20
echo

# 2. 建立測試分支
echo "2. 建立測試分支..."
python3 branch_operations.py create --project "$PROJECT" --branch "$TEST_BRANCH" --revision "$REVISION1"
echo

# 3. 查詢新建立的分支
echo "3. 確認分支已建立..."
python3 branch_operations.py query --project "$PROJECT" --branch "$TEST_BRANCH"
echo

# 4. 測試更新（不強制）- 可能會失敗
echo "4. 測試更新分支（快進式）..."
python3 branch_operations.py update --project "$PROJECT" --branch "$TEST_BRANCH" --revision "$REVISION2"
echo

# 5. 測試強制更新
echo "5. 測試強制更新分支..."
python3 branch_operations.py update --project "$PROJECT" --branch "$TEST_BRANCH" --revision "$REVISION2" --force
echo

# 6. 確認更新後的分支
echo "6. 確認分支已更新..."
python3 branch_operations.py query --project "$PROJECT" --branch "$TEST_BRANCH"
echo

# 7. 刪除測試分支
echo "7. 刪除測試分支..."
echo "y" | python3 branch_operations.py delete --project "$PROJECT" --branch "$TEST_BRANCH"
echo

# 8. 確認分支已刪除
echo "8. 確認分支已刪除..."
python3 branch_operations.py query --project "$PROJECT" --branch "$TEST_BRANCH"
echo

echo "========================================="
echo "測試完成"
echo "========================================="