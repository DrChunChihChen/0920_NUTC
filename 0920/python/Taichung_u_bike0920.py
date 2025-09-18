import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime
import json
import math
import urllib3
from io import StringIO

# Correct API URL
API_URL = "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download"
RESOURCE_ID = "7d7dade7-2f75-4cf9-8467-6c26c447c6ca"

# 使用 Streamlit 的快取功能，設定每 60 秒更新一次資料
@st.cache_data(ttl=60)
def get_ubike_data():
    """
    從台中市政府的開放資料 API 獲取 YouBike 2.0 的即時站點資料。
    """
    try:
        params = {"rid": RESOURCE_ID, "limit": 1000}
        # 一些 SSL 鬼問題，所以先關掉驗證
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(API_URL, params=params, verify=False)
        response.raise_for_status()
        
        # 檢查回應內容類型
        content_type = response.headers.get('content-type', '')
        
        if 'application/json' in content_type:
            # 如果是 JSON 格式
            data = response.json()
            
            # 檢查是否有 retVal 欄位（包含站點資料的 JSON 字串）
            if "retVal" in data:
                ret_val = data["retVal"]
                
                if isinstance(ret_val, str):
                    try:
                        # 解析 retVal 中的 JSON 字串
                        station_data = json.loads(ret_val)
                        df = pd.DataFrame(station_data)
                        st.success(f"成功載入 {len(df)} 筆站點資料")
                    except json.JSONDecodeError as e:
                        st.error(f"無法解析 retVal 中的 JSON 資料：{e}")
                        st.error(f"retVal 內容前 500 字元：{ret_val[:500]}")
                        return pd.DataFrame()
                elif isinstance(ret_val, list):
                    # 如果 retVal 已經是列表格式
                    df = pd.DataFrame(ret_val)
                    st.success(f"成功載入 {len(df)} 筆站點資料")
                else:
                    st.error(f"retVal 欄位格式不正確：{type(ret_val)}")
                    return pd.DataFrame()
            elif "records" in data:
                df = pd.DataFrame(data["records"])
            else:
                df = pd.DataFrame(data)
        else:
            # 如果是 CSV 格式，解析 CSV
            csv_data = response.text
            
            # 使用 pandas 讀取 CSV
            csv_df = pd.read_csv(StringIO(csv_data))
            
            if csv_df.empty:
                st.warning("CSV 資料為空，請稍後再試。")
                return pd.DataFrame()
            
            # 檢查是否有 retVal 欄位且包含 JSON 資料
            if 'retVal' in csv_df.columns:
                # 取得第一行的 retVal（包含所有站點的 JSON 字串）
                ret_val = csv_df.iloc[0]['retVal']
                
                if isinstance(ret_val, str):
                    try:
                        # 清理 JSON 字串，處理雙引號轉義問題
                        # 將 CSV 中的雙引號轉義格式 "" 轉換為正常的 "
                        cleaned_ret_val = ret_val.replace('""', '"')
                        
                        # 解析 JSON 字串
                        station_data = json.loads(cleaned_ret_val)
                        df = pd.DataFrame(station_data)
                        
                        st.success(f"成功載入 {len(df)} 筆站點資料")
                        
                    except json.JSONDecodeError as e:
                        st.error(f"無法解析 retVal 中的 JSON 資料：{e}")
                        st.error(f"retVal 內容前 500 字元：{ret_val[:500]}")
                        # 嘗試顯示清理後的內容
                        cleaned_ret_val = ret_val.replace('""', '"')
                        st.error(f"清理後的內容前 500 字元：{cleaned_ret_val[:500]}")
                        return pd.DataFrame()
                else:
                    st.error(f"retVal 欄位不是字串格式：{type(ret_val)}")
                    return pd.DataFrame()
            else:
                # 如果沒有 retVal 欄位，嘗試直接使用 CSV 資料
                df = csv_df

        if df.empty:
            st.warning("解析後的資料為空，請稍後再試。")
            return pd.DataFrame()

        # --- 資料驗證 ---
        required_cols = {'lat', 'lng', 'tot', 'sbi', 'bemp', 'mday', 'sna', 'sarea', 'ar'}
        actual_cols = set(df.columns)
        
        if not required_cols.issubset(actual_cols):
            missing_cols = required_cols - actual_cols
            # 顯示更詳細的錯誤資訊
            st.error(f"資料格式不符，缺少必要的欄位：{', '.join(missing_cols)}")
            st.info(f"實際可用的欄位：{', '.join(actual_cols)}")
            st.info(f"資料筆數：{len(df)}")
            if len(df) > 0:
                st.info(f"第一筆資料範例：{df.iloc[0].to_dict()}")
            return pd.DataFrame()

        # --- 資料清理與轉換 ---
        numeric_cols = ['lat', 'lng', 'tot', 'sbi', 'bemp']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df.dropna(subset=['lat', 'lng', 'sna'], inplace=True)
        
        # 將時間格式轉換為 datetime 物件
        df['mday'] = pd.to_datetime(df['mday'], format='%Y%m%d%H%M%S', errors='coerce')

        return df

    except requests.exceptions.RequestException as e:
        st.error(f"錯誤：API 請求失敗 - {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"錯誤：處理資料時發生問題 - {e}")
        return pd.DataFrame()

def get_marker_color(sbi):
    """根據可借車輛數決定地圖標記的顏色"""
    if sbi == 0:
        return 'red'    # 沒有車
    elif sbi <= 3:
        return 'orange' # 車輛少
    else:
        return 'green'  # 車輛充足

def haversine(lat1, lon1, lat2, lon2):
    """計算兩個地理座標點之間的距離（公里）"""
    R = 6371  # 地球半徑（公里）
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dLon / 2) * math.sin(dLon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

# --- Streamlit App UI ---

# 設定頁面標題與佈局
st.set_page_config(page_title="台中 YouBike 即時儀表板 - 北區", layout="wide")

# --- Sidebar ---
st.sidebar.title("📍 尋找最近的站點")
# 預設座標為台中北區（科技大學附近）
user_lat = st.sidebar.number_input("輸入您的緯度 (Latitude)", value=24.1498, min_value=24.0, max_value=24.3, step=0.0001, format="%.4f")
user_lon = st.sidebar.number_input("輸入您的經度 (Longitude)", value=120.6844, min_value=120.5, max_value=120.8, step=0.0001, format="%.4f")

# --- Main Page ---
# 標題
st.title("🚲 台中市 YouBike 2.0 即時資訊儀表板 - 北區")
st.markdown("資料來源：[台中市政府資料開放平台](https://opendata.taichung.gov.tw/dataset/OpenData/bc27c2f7-6ed7-4f1a-b3cc-1a3cc9cda34e)")

# 獲取資料
df_all = get_ubike_data()

if not df_all.empty:
    # --- 篩選資料：只保留北區 ---
    df = df_all[df_all['sarea'] == '北區'].copy()

    # 檢查篩選後是否有資料
    if df.empty:
        st.warning("目前在北區找不到任何 YouBike 站點資料。")
        # 顯示所有可用的區域
        available_areas = df_all['sarea'].unique()
        st.info(f"可用的區域有：{', '.join(sorted(available_areas))}")
        
        # 顯示總數據統計
        st.info(f"總共有 {len(df_all)} 個站點")
        
        # 顯示各區域的站點數量
        area_counts = df_all['sarea'].value_counts()
        st.write("各區域站點數量：")
        st.write(area_counts)
    else:
        # --- 計算距離並找到最近站點 ---
        df['distance'] = df.apply(lambda row: haversine(user_lat, user_lon, row['lat'], row['lng']), axis=1)
        closest_station = df.loc[df['distance'].idxmin()]

        # 在 Sidebar 顯示最近站點資訊
        st.sidebar.success("距離您最近的站點是：")
        st.sidebar.markdown(f"**{closest_station['sna']}**")
        st.sidebar.markdown(f"📍 **地址：** {closest_station['ar']}")
        st.sidebar.markdown(f"📏 **距離：** {closest_station['distance']:.2f} 公里")
        st.sidebar.markdown(f"🚲 **可借車輛：** {int(closest_station['sbi'])} 輛")
        st.sidebar.markdown(f"🅿️ **可還空位：** {int(closest_station['bemp'])} 個")
        
        # 顯示最後更新時間
        if df['mday'].notna().any():
            last_update_time = df['mday'].max().strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"**資料最後更新時間：** {last_update_time}")

        # --- 關鍵指標 (KPIs) ---
        total_stations = len(df)
        total_bikes_available = int(df['sbi'].sum())
        total_docks_empty = int(df['bemp'].sum())

        col1, col2, col3 = st.columns(3)
        col1.metric("總站點數 (北區)", f"{total_stations} 站")
        col2.metric("可借車輛 (北區)", f"{total_bikes_available} 輛")
        col3.metric("可還空位 (北區)", f"{total_docks_empty} 個")

        st.markdown("---")

        # --- 地圖與資料表 ---
        map_col, data_col = st.columns([2, 1]) # 地圖佔 2/3，資料表佔 1/3

        with map_col:
            st.subheader("📍 北區 YouBike 站點地圖")
            
            # --- 圖例說明 ---
            st.markdown("""
            <style>
            .legend {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 10px;
                font-size: 12px;
            }
            .legend-item {
                display: flex;
                align-items: center;
                margin-bottom: 5px;
            }
            .color-box {
                width: 15px;
                height: 15px;
                margin-right: 8px;
                border-radius: 3px;
            }
            </style>
            <div class="legend">
                <b>圖例說明：</b>
                <div class="legend-item">
                    <div class="color-box" style="background-color: #79c879;"></div>
                    <span>車輛充足 (4 輛或以上)</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background-color: #f7a364;"></div>
                    <span>車輛較少 (1-3 輛)</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background-color: #e56b6f;"></div>
                    <span>目前無車 (0 輛)</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 建立 Folium 地圖，中心點設為使用者輸入的位置
            taichung_map = folium.Map(location=[user_lat, user_lon], zoom_start=15)

            # 加入使用者位置標記
            folium.Marker(
                location=[user_lat, user_lon],
                popup="您的位置",
                tooltip="您的位置",
                icon=folium.Icon(color='blue', icon='user', prefix='fa')
            ).add_to(taichung_map)

            # 在地圖上加入各站點的標記
            for _, station in df.iterrows():
                # 設定彈出視窗的 HTML 內容
                popup_html = f"""
                <b>站點名稱：</b>{station['sna']}<br>
                <b>地址：</b>{station['ar']}<br>
                <hr>
                <b>總車位數：</b>{int(station['tot'])}<br>
                <b>可借車輛：</b><font color="{get_marker_color(station['sbi'])}"><b>{int(station['sbi'])}</b></font><br>
                <b>可還空位：</b>{int(station['bemp'])}<br>
                <b>距離約：</b>{station['distance']:.2f} 公里
                """
                
                popup = folium.Popup(popup_html, max_width=300)
                
                folium.Marker(
                    location=[station['lat'], station['lng']],
                    popup=popup,
                    tooltip=f"{station['sna']} ({station['distance']:.2f} km)",
                    icon=folium.Icon(color=get_marker_color(station['sbi']), icon='bicycle', prefix='fa')
                ).add_to(taichung_map)
            
            # 在 Streamlit 中顯示地圖
            st_folium(taichung_map, width='100%', height=500)

        with data_col:
            st.subheader("📊 北區資料檢視 (依距離排序)")
            
            # 顯示北區的資料，並按照距離排序
            display_df = df[['sna', 'sbi', 'bemp', 'tot', 'distance']].sort_values(by='distance')
            
            st.dataframe(
                display_df,
                height=450,
                column_config={
                    "sna": "站點名稱",
                    "sbi": "可借車輛",
                    "bemp": "可還空位",
                    "tot": "總車位",
                    "distance": st.column_config.NumberColumn("距離(km)", format="%.2f")
                }
            )

else:
    st.warning("目前無法載入 YouBike 資料，請稍後再試。")
    
    # 顯示除錯資訊
    if st.checkbox("顯示除錯資訊"):
        st.write("嘗試直接獲取原始資料以除錯...")
        try:
            params = {"rid": RESOURCE_ID, "limit": 10}
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(API_URL, params=params, verify=False)
            st.write(f"HTTP 狀態碼：{response.status_code}")
            st.write(f"回應標頭：{dict(response.headers)}")
            st.write(f"回應內容前 1000 字元：")
            st.text(response.text[:1000])
        except Exception as e:
            st.error(f"除錯時發生錯誤：{e}")
