"""
Gerrit 認證診斷工具
"""
import requests
import base64
import os
import sys

# 加入上一層目錄到路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

def test_gerrit_auth():
    """測試 Gerrit 認證"""
    
    print("🔍 Gerrit 認證診斷工具")
    print("=" * 50)
    
    # 從 config 載入設定
    try:
        import config
        user = getattr(config, 'GERRIT_USER', '')
        password = getattr(config, 'GERRIT_PW', '')
        base_url = getattr(config, 'GERRIT_BASE', 'https://mm2sd.rtkbf.com/').rstrip('/')
        
        print(f"設定檢查:")
        print(f"  User: {user}")
        print(f"  Password: {'已設定' if password else '未設定'}")
        print(f"  Base URL: {base_url}")
        print()
        
    except ImportError:
        print("❌ 無法載入 config.py")
        return
    
    if not user or not password:
        print("❌ 請先在 config.py 中設定 GERRIT_USER 和 GERRIT_PW")
        return
    
    # 測試 URL
    test_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml?format=TEXT"
    
    # 瀏覽器標頭
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    
    print("測試不同的認證方式:")
    print()
    
    # 方法 1: HTTP 基本認證
    print("🧪 方法 1: HTTP 基本認證")
    try:
        response = requests.get(test_url, auth=(user, password), headers=headers, timeout=10)
        print(f"  狀態碼: {response.status_code}")
        if response.status_code == 200:
            print("  ✅ 成功！")
            # 檢查內容
            content_preview = response.text[:100]
            print(f"  內容預覽: {content_preview}...")
            return True
        else:
            print(f"  ❌ 失敗")
    except Exception as e:
        print(f"  ❌ 異常: {str(e)}")
    
    print()
    
    # 方法 2: 嘗試不同的認證標頭
    print("🧪 方法 2: Authorization 標頭")
    try:
        # 建立 base64 編碼的認證字串
        auth_string = f"{user}:{password}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers_with_auth = headers.copy()
        headers_with_auth['Authorization'] = f'Basic {auth_b64}'
        
        response = requests.get(test_url, headers=headers_with_auth, timeout=10)
        print(f"  狀態碼: {response.status_code}")
        if response.status_code == 200:
            print("  ✅ 成功！")
            content_preview = response.text[:100]
            print(f"  內容預覽: {content_preview}...")
            return True
        else:
            print(f"  ❌ 失敗")
    except Exception as e:
        print(f"  ❌ 異常: {str(e)}")
    
    print()
    
    # 方法 3: 測試 API 認證
    print("🧪 方法 3: 測試 API 認證")
    api_url = f"{base_url}/a/accounts/self"
    try:
        response = requests.get(api_url, auth=(user, password), headers=headers, timeout=10)
        print(f"  API URL: {api_url}")
        print(f"  狀態碼: {response.status_code}")
        if response.status_code == 200:
            print("  ✅ API 認證成功！")
            # 解析用戶資訊
            content = response.text
            if content.startswith(")]}'\n"):
                content = content[5:]
            
            try:
                import json
                user_info = json.loads(content)
                print(f"  用戶名: {user_info.get('name', 'Unknown')}")
                print(f"  郵箱: {user_info.get('email', 'Unknown')}")
            except:
                print(f"  回應內容: {content[:100]}...")
        else:
            print(f"  ❌ API 認證失敗")
            print(f"  回應內容: {response.text[:200]}...")
    except Exception as e:
        print(f"  ❌ 異常: {str(e)}")
    
    print()
    
    # 建議
    print("💡 建議解決方案:")
    print("1. 確認您的 Gerrit 帳號密碼正確")
    print("2. 檢查帳號是否有存取該專案的權限")
    print("3. 嘗試在瀏覽器中登出再重新登入 Gerrit")
    print("4. 聯絡 Gerrit 管理員確認帳號狀態")
    print()
    print("🔧 Chrome 瀏覽器檢查方法:")
    print("1. 在 Chrome 中開啟 F12 開發者工具")
    print("2. 前往 Network 分頁")
    print("3. 下載該檔案")
    print("4. 查看請求的 Headers")
    print("5. 複製 Authorization 或 Cookie 標頭")
    
    return False

if __name__ == "__main__":
    test_gerrit_auth()