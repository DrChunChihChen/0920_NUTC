import requests
import pandas as pd
import urllib3

def get_taichung_youbike_data():
    """
    從台中市政府開放資料平台獲取 YouBike 2.0 的即時站點資料。
    (新版) API 已改為直接回傳 JSON 格式。
    """
    
    # API 的基本位址和新的資源 ID
    API_URL = "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download"
    RESOURCE_ID = "8be7c670-3f42-4764-ad44-28e28eeaa0a7"
    
    # 準備請求參數
    params = {
        "rid": RESOURCE_ID,
        "limit": 2000 
    }
    
    print("🚀 開始從 API 獲取資料...")
    
    try:
        # 因 API 來源的 SSL 憑證問題，暫時關閉驗證與警告
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 發送 GET 請求
        response = requests.get(API_URL, params=params, verify=False, timeout=10)
        
        # 確保請求成功 (HTTP 狀態碼 200)
        response.raise_for_status()
        
        print("✅ API 請求成功，正在解析 JSON 資料...")

        # --- 核心解析步驟 (已簡化) ---
        # 1. API 直接回傳 JSON，使用 .json() 方法即可解析
        station_data = response.json()
        
        # 2. 將解析後的資料轉換成 DataFrame
        final_df = pd.DataFrame(station_data)
        
        print(f"🎉 成功載入 {len(final_df)} 筆 YouBike 站點資料！")
        
        return final_df

    except requests.exceptions.RequestException as e:
        print(f"❌ 網路請求失敗：{e}")
        return None
    except requests.exceptions.JSONDecodeError as e:
        # response.json() 可能會在此處失敗
        print(f"❌ JSON 解析失敗，API 回應的可能不是標準 JSON 格式。錯誤：{e}")
        print(f"   回應內容前 200 字元：{response.text[:200]}")
        return None
    except Exception as e:
        print(f"❌ 處理過程中發生未知錯誤：{e}")
        return None

# --- 主程式執行區塊 ---
if __name__ == "__main__":
    # 呼叫函式來獲取資料
    youbike_df = get_taichung_youbike_data()
    
    # 如果成功獲取 DataFrame，則顯示前 5 筆資料和整體資訊
    if youbike_df is not None:
        print("\n--- 資料預覽 (前 5 筆) ---")
        print(youbike_df.head())
        
        print("\n--- 資料基本資訊 ---")
        youbike_df.info()
