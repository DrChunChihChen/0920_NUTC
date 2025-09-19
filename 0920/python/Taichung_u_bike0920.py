import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime
import math
import urllib3

# --- 變更點 1: 更新為新的、正確的 API 資訊 ---
API_URL = "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download"
RESOURCE_ID = "8be7c670-3f42-4764-ad44-28e28eeaa0a7" # 已更新為 2025-09-19 的新 ID

# --- 變更點 2: 大幅簡化 get_ubike_data 函式以符合新的 API 格式 ---
@st.cache_data(ttl=60)
def get_ubike_data():
    """
    從台中市政府的開放資料 API 獲取 YouBike 2.0 的即時站點資料。
    (新版) API 已改為直接回傳 JSON 格式，因此大幅簡化此函式。
    """
    try:
        # 參數 limit 設高一點以確保抓取所有站點資料
        params = {"rid": RESOURCE_ID, "limit": 2000}
        
        # 因 API 來源的 SSL 憑證問題，暫時關閉驗證與警告
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(API_URL, params=params, verify=False, timeout=15)
        response.raise_for_status()
        
        # API 直接回傳 JSON，使用 .json() 即可解析
        station_data = response.json()
        df = pd.DataFrame(station_data)
        
        st.success(f"成功載入 {len(df)} 筆站點資料")

        if df.empty:
            st.warning("API 回應的資料為空，請稍後再試。")
            return pd.DataFrame()

        # --- 資料驗證 ---
        # 確保必要的欄位都存在
        required_cols = {'lat', 'lng', 'tot', 'sbi', 'bemp', 'mday', 'sna', 'sarea', 'ar'}
        actual_cols = set(df.columns)
        
        if not required_cols.issubset(actual_cols):
            missing_cols = required_cols - actual_cols
            st.error(f"資料格式不符，缺少必要的欄位：{', '.join(missing_cols)}")
            st.info(f"實際可用的欄位：{', '.join(actual_cols)}")
            return pd.DataFrame()

        # --- 資料清理與轉換 (這部分邏輯不變) ---
        numeric_cols = ['lat', 'lng', 'tot', 'sbi', 'bemp']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df.dropna(subset=['lat', 'lng', 'sna'], inplace=True)
        
        df['mday'] = pd.to_datetime(df['mday'], format='%Y%m%d%H%M%S', errors='coerce')

        return df

    except requests.exceptions.RequestException as e:
        st.error(f"錯誤：API 請求失敗 - {e}")
        return pd.DataFrame()
    except requests.exceptions.JSONDecodeError:
        st.error("錯誤：API 回應的不是有效的 JSON 格式，請檢查 API 狀態。")
        st.info(f"回應內容前 500 字元：{response.text[:500]}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"錯誤：處理資料時發生問題 - {e}")
        return pd.DataFrame()

def get_marker_color(sbi):
    """根據可借車輛數決定地圖標記的顏色"""
    sbi = int(sbi) # 確保 sbi 是整數
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

# --- Streamlit App UI (以下部分幾乎無變動) ---

st.set_page_config(page_title="台中 YouBike 即時儀表板 - 北區", layout="wide")

st.sidebar.title("📍 尋找最近的站點")
user_lat = st.sidebar.number_input("輸入您的緯度 (Latitude)", value=24.1498, min_value=24.0, max_value=24.3, step=0.0001, format="%.4f")
user_lon = st.sidebar.number_input("輸入您的經度 (Longitude)", value=120.6844, min_value=120.5, max_value=120.8, step=0.0001, format="%.4f")

st.title("🚲 台中市 YouBike 2.0 即時資訊儀表板 - 北區")
st.markdown("資料來源：[台中市政府資料開放平台](https://opendata.taichung.gov.tw/dataset/OpenData/bc27c2f7-6ed7-4f1a-b3cc-1a3cc9cda34e)")

df_all = get_ubike_data()

if not df_all.empty:
    df = df_all[df_all['sarea'] == '北區'].copy()

    if df.empty:
        st.warning("目前在北區找不到任何 YouBike 站點資料。")
        available_areas = sorted(df_all['sarea'].dropna().unique())
        st.info(f"可用的區域有：{', '.join(available_areas)}")
        st.info(f"總共有 {len(df_all)} 個站點")
        st.write("各區域站點數量：")
        st.write(df_all['sarea'].value_counts())
    else:
        df['distance'] = df.apply(lambda row: haversine(user_lat, user_lon, row['lat'], row['lng']), axis=1)
        closest_station = df.loc[df['distance'].idxmin()]

        st.sidebar.success("距離您最近的站點是：")
        st.sidebar.markdown(f"**{closest_station['sna']}**")
        st.sidebar.markdown(f"📍 **地址：** {closest_station['ar']}")
        st.sidebar.markdown(f"📏 **距離：** {closest_station['distance']:.2f} 公里")
        st.sidebar.markdown(f"🚲 **可借車輛：** {int(closest_station['sbi'])} 輛")
        st.sidebar.markdown(f"🅿️ **可還空位：** {int(closest_station['bemp'])} 個")
        
        if df['mday'].notna().any():
            last_update_time = df['mday'].max().strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"**資料最後更新時間：** {last_update_time}")

        total_stations = len(df)
        total_bikes_available = int(df['sbi'].sum())
        total_docks_empty = int(df['bemp'].sum())

        col1, col2, col3 = st.columns(3)
        col1.metric("總站點數 (北區)", f"{total_stations} 站")
        col2.metric("可借車輛 (北區)", f"{total_bikes_available} 輛")
        col3.metric("可還空位 (北區)", f"{total_docks_empty} 個")

        st.markdown("---")

        map_col, data_col = st.columns([2, 1])

        with map_col:
            st.subheader("📍 北區 YouBike 站點地圖")
            
            st.markdown("""
            <style>
            .legend { background-color: #f0f0f0; border: 1px solid #ccc; padding: 10px; border-radius: 5px; margin-bottom: 10px; font-size: 12px; }
            .legend-item { display: flex; align-items: center; margin-bottom: 5px; }
            .color-box { width: 15px; height: 15px; margin-right: 8px; border-radius: 3px; }
            </style>
            <div class="legend">
                <b>圖例說明：</b>
                <div class="legend-item"><div class="color-box" style="background-color: #79c879;"></div><span>車輛充足 (4 輛或以上)</span></div>
                <div class="legend-item"><div class="color-box" style="background-color: #f7a364;"></div><span>車輛較少 (1-3 輛)</span></div>
                <div class="legend-item"><div class="color-box" style="background-color: #e56b6f;"></div><span>目前無車 (0 輛)</span></div>
            </div>
            """, unsafe_allow_html=True)

            taichung_map = folium.Map(location=[user_lat, user_lon], zoom_start=15)

            folium.Marker(
                location=[user_lat, user_lon],
                popup="您的位置", tooltip="您的位置",
                icon=folium.Icon(color='blue', icon='user', prefix='fa')
            ).add_to(taichung_map)

            for _, station in df.iterrows():
                popup_html = f"""
                <b>站點名稱：</b>{station['sna']}<br><b>地址：</b>{station['ar']}<hr>
                <b>總車位數：</b>{int(station['tot'])}<br>
                <b>可借車輛：</b><font color="{get_marker_color(station['sbi'])}"><b>{int(station['sbi'])}</b></font><br>
                <b>可還空位：</b>{int(station['bemp'])}<br>
                <b>距離約：</b>{station['distance']:.2f} 公里
                """
                popup = folium.Popup(popup_html, max_width=300)
                folium.Marker(
                    location=[station['lat'], station['lng']],
                    popup=popup, tooltip=f"{station['sna']} ({station['distance']:.2f} km)",
                    icon=folium.Icon(color=get_marker_color(station['sbi']), icon='bicycle', prefix='fa')
                ).add_to(taichung_map)
            
            st_folium(taichung_map, width='100%', height=500)

        with data_col:
            st.subheader("📊 北區資料檢視 (依距離排序)")
            
            display_df = df[['sna', 'sbi', 'bemp', 'tot', 'distance']].sort_values(by='distance')
            
            st.dataframe(
                display_df, height=450,
                column_config={
                    "sna": "站點名稱", "sbi": "可借車輛",
                    "bemp": "可還空位", "tot": "總車位",
                    "distance": st.column_config.NumberColumn("距離(km)", format="%.2f")
                }
            )

else:
    st.warning("目前無法載入 YouBike 資料，請稍後再試。")
    
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
