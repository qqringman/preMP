"""
Gerrit 下載診斷工具 - 增強版 (支援認證)
測試不同的下載方式，找出正確的下載方法
"""
import requests
import base64
import os
import sys

# 加入上一層目錄到路徑以載入 config
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

def diagnose_gerrit_download():
    """診斷 Gerrit 檔案下載問題 - 支援認證"""
    
    # 載入認證資訊
    try:
        import config
        user = getattr(config, 'GERRIT_USER', '')
        password = getattr(config, 'GERRIT_PW', '')
        base_url = getattr(config, 'GERRIT_BASE', 'https://mm2sd.rtkbf.com/').rstrip('/')
        
        print("🔍 Gerrit 下載診斷工具 (支援認證)")
        print("=" * 60)
        print(f"認證用戶: {user}")
        print(f"密碼長度: {len(password)} 字符")
        print(f"Base URL: {base_url}")
        
        if not user or not password:
            print("❌ 缺少認證資訊，請檢查 config.py 中的 GERRIT_USER 和 GERRIT_PW")
            return False
            
    except ImportError:
        print("❌ 無法載入 config.py，請確保檔案存在")
        return False
    
    # 設定認證
    auth = (user, password)
    
    # 測試 URL
    test_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-wave.xml"
    
    print(f"測試 URL: {test_url}")
    print()
    
    # 方法 1: 瀏覽器模式 + 認證
    print("📋 方法 1: 模擬瀏覽器訪問 + 認證")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        }
        
        response = requests.get(test_url, headers=headers, auth=auth, timeout=30)
        print(f"  狀態碼: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('content-type', 'N/A')}")
        print(f"  Content-Length: {len(response.text)}")
        print(f"  行數: {response.text.count(chr(10)) + 1}")
        print(f"  內容開頭: {response.text[:100]}...")
        
        if response.status_code == 200:
            # 檢查是否為有效 XML
            content = response.text.strip()
            if content.startswith('<?xml') or content.startswith('<manifest'):
                print("  ✅ 成功：內容看起來是有效的 XML")
                
                # 保存測試檔案
                with open('test_browser_auth_download.xml', 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  💾 已保存為: test_browser_auth_download.xml")
                return True
            else:
                print("  ❌ 內容不是有效的 XML")
        else:
            print(f"  ❌ HTTP 錯誤: {response.status_code}")
            
    except Exception as e:
        print(f"  ❌ 異常: {str(e)}")
    
    print()
    
    # 方法 2: ?format=TEXT + 認證
    print("📋 方法 2: 使用 ?format=TEXT 參數 + 認證")
    try:
        text_url = test_url + "?format=TEXT"
        
        response = requests.get(text_url, headers=headers, auth=auth, timeout=30)
        print(f"  URL: {text_url}")
        print(f"  狀態碼: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('content-type', 'N/A')}")
        print(f"  Content-Length: {len(response.text)}")
        print(f"  行數: {response.text.count(chr(10)) + 1}")
        print(f"  內容開頭: {response.text[:100]}...")
        
        if response.status_code == 200:
            # 嘗試 Base64 解碼
            try:
                decoded = base64.b64decode(response.text)
                decoded_text = decoded.decode('utf-8')
                print(f"  Base64 解碼後長度: {len(decoded_text)}")
                print(f"  Base64 解碼後行數: {decoded_text.count(chr(10)) + 1}")
                print(f"  解碼後開頭: {decoded_text[:100]}...")
                
                if decoded_text.strip().startswith('<?xml') or decoded_text.strip().startswith('<manifest'):
                    print("  ✅ Base64 解碼成功：內容是有效的 XML")
                    
                    # 保存測試檔案
                    with open('test_base64_auth_download.xml', 'w', encoding='utf-8') as f:
                        f.write(decoded_text)
                    print(f"  💾 已保存為: test_base64_auth_download.xml")
                    return True
                else:
                    print("  ❌ Base64 解碼後不是有效的 XML")
                    
            except Exception as decode_error:
                print(f"  ❌ Base64 解碼失敗: {str(decode_error)}")
        else:
            print(f"  ❌ HTTP 錯誤: {response.status_code}")
            
    except Exception as e:
        print(f"  ❌ 異常: {str(e)}")
    
    print()
    
    # 方法 3: API 風格 URL + 認證 (這是之前成功的方法)
    print("📋 方法 3: 使用 API 風格 URL + 認證 (成功方法)")
    try:
        import urllib.parse
        project_encoded = urllib.parse.quote('realtek/android/manifest', safe='')
        branch_encoded = urllib.parse.quote('realtek/android-14/master', safe='')
        file_encoded = urllib.parse.quote('atv-google-refplus-wave.xml', safe='')
        
        api_url = f"{base_url}/gerrit/a/projects/{project_encoded}/branches/{branch_encoded}/files/{file_encoded}/content"
        
        response = requests.get(api_url, headers=headers, auth=auth, timeout=30)
        print(f"  URL: {api_url}")
        print(f"  狀態碼: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('content-type', 'N/A')}")
        print(f"  Content-Length: {len(response.text)}")
        print(f"  行數: {response.text.count(chr(10)) + 1}")
        print(f"  內容開頭: {response.text[:100]}...")
        
        if response.status_code == 200:
            # API 通常返回 Base64
            try:
                decoded = base64.b64decode(response.text)
                decoded_text = decoded.decode('utf-8')
                print(f"  Base64 解碼後長度: {len(decoded_text)}")
                print(f"  Base64 解碼後行數: {decoded_text.count(chr(10)) + 1}")
                print(f"  解碼後開頭: {decoded_text[:100]}...")
                
                if decoded_text.strip().startswith('<?xml') or decoded_text.strip().startswith('<manifest'):
                    print("  ✅ API 方式成功：內容是有效的 XML")
                    
                    # 保存測試檔案
                    with open('test_api_auth_download.xml', 'w', encoding='utf-8') as f:
                        f.write(decoded_text)
                    print(f"  💾 已保存為: test_api_auth_download.xml")
                    
                    # 進行詳細分析
                    print(f"\n  📊 詳細分析:")
                    print(f"    - 專案數量: {decoded_text.count('<project ')}")
                    print(f"    - 包含 dest-branch: {decoded_text.count('dest-branch=')}")
                    print(f"    - 包含 revision: {decoded_text.count('revision=')}")
                    print(f"    - 包含 upstream: {decoded_text.count('upstream=')}")
                    print(f"    - 包含 refs/tags/: {decoded_text.count('refs/tags/')}")
                    
                    return True
                else:
                    print("  ❌ API 解碼後不是有效的 XML")
                    
            except Exception as decode_error:
                print(f"  ❌ API Base64 解碼失敗: {str(decode_error)}")
        else:
            print(f"  ❌ API HTTP 錯誤: {response.status_code}")
            
    except Exception as e:
        print(f"  ❌ API 異常: {str(e)}")
    
    print()
    
    # 方法 4: 測試多個不同的 API 路徑格式
    print("📋 方法 4: 測試其他 API 路徑格式")
    
    alternative_apis = [
        f"{base_url}/a/projects/{project_encoded}/branches/{branch_encoded}/files/{file_encoded}/content",
        f"{base_url}/gerrit/a/projects/{project_encoded}/branches/refs%2Fheads%2F{branch_encoded}/files/{file_encoded}/content",
        f"{base_url}/a/projects/{project_encoded}/branches/refs%2Fheads%2F{branch_encoded}/files/{file_encoded}/content"
    ]
    
    for i, alt_url in enumerate(alternative_apis, 1):
        try:
            print(f"  🔸 API 變體 {i}: {alt_url}")
            response = requests.get(alt_url, headers=headers, auth=auth, timeout=30)
            print(f"    狀態碼: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    decoded = base64.b64decode(response.text)
                    decoded_text = decoded.decode('utf-8')
                    if decoded_text.strip().startswith('<?xml') or decoded_text.strip().startswith('<manifest'):
                        print(f"    ✅ API 變體 {i} 成功！")
                        with open(f'test_api_variant_{i}_download.xml', 'w', encoding='utf-8') as f:
                            f.write(decoded_text)
                        print(f"    💾 已保存為: test_api_variant_{i}_download.xml")
                except:
                    pass
            else:
                print(f"    ❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ 異常: {str(e)}")
    
    print()
    print("📋 診斷總結:")
    print("檢查生成的測試檔案，找出內容正確的下載方法。")
    print("正確的檔案應該包含完整的 XML manifest 內容。")
    
    return False

if __name__ == "__main__":
    diagnose_gerrit_download()