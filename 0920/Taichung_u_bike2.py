import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime
import ast
import math

# API URL
API_URL = "https://datacenter.taichung.gov.tw/swagger/OpenData/bc27c2f7-6ed7-4f1a-b3cc-1a3cc9cda34e"

# 使用 Streamlit 的快取功能，設定每 60 秒更新一次資料
@st.cache_data(ttl=60)
def get_ubike_data():
    """
    從台中市政府的開放資料 API 獲取 YouBike 2.0 的即時站點資料。
    """
    try:
        response = requests.get(API_URL)
        response.raise_for_status()  # 如果請求失敗，會引發錯誤
        data = response.json()
        
        if not data:
            st.warning("API 回應為空，請稍後再試。")
            return pd.DataFrame()

        # --- 新的資料解析邏輯 ---
        # 建立一個臨時 DataFrame 來檢查 API 回應的結構
        temp_df = pd.DataFrame(data)

        # 檢查 'retVal' 欄位是否存在，因為實際站點資料被包在裡面
        if 'retVal' in temp_df.columns:
            
            def parse_ret_val(val):
                """安全地將 'retVal' 欄位中的字串轉換為字典"""
                if isinstance(val, dict):
                    return val
                if isinstance(val, str):
                    try:
                        # ast.literal_eval 可以安全地執行字串到 Python 物件的轉換
                        return ast.literal_eval(val)
                    except (ValueError, SyntaxError):
                        return {} # 如果解析失敗，返回空字典
                return {}

            # 將 'retVal' 欄位中的每個值都進行解析，然後建立新的 DataFrame
            station_data = temp_df['retVal'].apply(parse_ret_val).tolist()
            df = pd.DataFrame(station_data)
        else:
            # 如果 API 格式變回扁平結構，則直接使用臨時 DataFrame
            df = temp_df
        
        # --- 資料驗證 ---
        # 增加一個檢查，確保處理後的資料包含我們需要的欄位
        required_cols = {'lat', 'lng', 'tot', 'sbi', 'bemp', 'mday', 'sna', 'sarea', 'ar'}
        actual_cols = set(df.columns)
        
        if not required_cols.issubset(actual_cols):
            missing_cols = required_cols - actual_cols
            error_message = (
                f"資料格式不符，缺少必要的欄位：`{', '.join(missing_cols)}`。\n"
                f"資料轉換後，實際的欄位為：`{', '.join(actual_cols)}`"
            )
            # 這個錯誤會被下面的 ValueError exception 捕捉到並顯示在畫面上
            raise ValueError(error_message)

        # --- 資料清理與轉換 ---
        # 將經緯度、總車位、可借車輛、可還空位轉換為數值型態，錯誤的轉換為 NaN
        numeric_cols = ['lat', 'lng', 'tot', 'sbi', 'bemp']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 移除經緯度或站點資訊不完整的資料
        df.dropna(subset=['lat', 'lng', 'sna'], inplace=True)
        
        # 將時間格式轉換為 datetime 物件
        df['mday'] = pd.to_datetime(df['mday'], format='%Y%m%d%H%M%S', errors='coerce')
        
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"錯誤：API 請求失敗 - {e}")
        return pd.DataFrame() # 返回空的 DataFrame
    except (ValueError, KeyError) as e:
        st.error(f"錯誤：無法解析回傳的資料 - {e}")
        return pd.DataFrame() # 返回空的 DataFrame

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
# 預設座標為台中南區
user_lat = st.sidebar.number_input("輸入您的緯度 (Latitude)", value=24.12, min_value=24.0, max_value=24.3, step=0.0001, format="%.4f")
user_lon = st.sidebar.number_input("輸入您的經度 (Longitude)", value=120.67, min_value=120.5, max_value=120.8, step=0.0001, format="%.4f")

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
            .legend { ... } /* Style code hidden for brevity */
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
            st.dataframe(
                df[['sna', 'sbi', 'bemp', 'tot', 'distance']].sort_values(by='distance'),
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

# 24.1498 120.6844 國立臺中科技大學