import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime
import math
import urllib3

# --- 變更點: 改為使用 YouBike 官方的直接資料源 ---
API_URL = "https://ybjson02.youbike.com.tw:60008/yb2/taichung/gwjs.json"

@st.cache_data(ttl=60)
def get_ubike_data():
    """
    從 YouBike 官方的 API 獲取 YouBike 2.0 的即時站點資料。
    """
    try:
        # 因 API 來源的 SSL 憑證問題，暫時關閉驗證與警告
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(API_URL, verify=False, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # 資料在 'retVal' key 裡面
        station_data = data.get('retVal')

        if not station_data:
            st.warning("API 回應的資料為空或格式不符，請稍後再試。")
            return pd.DataFrame()

        df = pd.DataFrame(station_data)
        
        st.success(f"成功載入 {len(df)} 筆站點資料")

        # --- 資料驗證 (與之前相同) ---
        required_cols = {'lat', 'lng', 'tot', 'sbi', 'bemp', 'mday', 'sna', 'sarea', 'ar'}
        actual_cols = set(df.columns)
        
        if not required_cols.issubset(actual_cols):
            missing_cols = required_cols - actual_cols
            st.error(f"資料格式不符，缺少必要的欄位：{', '.join(missing_cols)}")
            st.info(f"實際可用的欄位：{', '.join(actual_cols)}")
            return pd.DataFrame()

        # --- 資料清理與轉換 (與之前相同) ---
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
    if sbi == 0: return 'red'
    if sbi <= 3: return 'orange'
    return 'green'

def haversine(lat1, lon1, lat2, lon2):
    """計算兩個地理座標點之間的距離（公里）"""
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- Streamlit App UI ---
st.set_page_config(page_title="台中 YouBike 即時儀表板", layout="wide")

# --- Sidebar ---
st.sidebar.title("⚙️ 控制面板")
user_lat = st.sidebar.number_input("您的緯度 (Latitude)", value=24.1498, min_value=24.0, max_value=24.3, step=0.0001, format="%.4f")
user_lon = st.sidebar.number_input("您的經度 (Longitude)", value=120.6844, min_value=120.5, max_value=120.8, step=0.0001, format="%.4f")

df_all = get_ubike_data()

if not df_all.empty:
    # --- 變更點: 讓使用者選擇區域 ---
    available_areas = sorted(df_all['sarea'].dropna().unique())
    areas_with_all = ["所有區域"] + available_areas
    default_index = areas_with_all.index("北區") if "北區" in areas_with_all else 0
    selected_area = st.sidebar.selectbox("選擇區域", areas_with_all, index=default_index)

    # --- Main Panel ---
    st.title(f"🚲 台中市 YouBike 2.0 即時儀表板 - {selected_area}")
    st.markdown("資料來源：[台中市政府資料開放平台](https://opendata.taichung.gov.tw/dataset/OpenData/bc27c2f7-6ed7-4f1a-b3cc-1a3cc9cda34e)")

    # --- 變更點: 根據選擇的區域過濾資料 ---
    if selected_area == "所有區域":
        df = df_all.copy()
    else:
        df = df_all[df_all['sarea'] == selected_area].copy()

    if df.empty:
        st.warning(f"在「{selected_area}」找不到任何 YouBike 站點資料。")
    else:
        df['distance'] = df.apply(lambda row: haversine(user_lat, user_lon, row['lat'], row['lng']), axis=1)
        closest_station = df.loc[df['distance'].idxmin()]

        # --- Sidebar (Closest Station) ---
        st.sidebar.header("📍 最近的站點")
        st.sidebar.success(f"**{closest_station['sna']}**")
        st.sidebar.markdown(f"**地址：** {closest_station['ar']}")
        st.sidebar.markdown(f"**距離：** {closest_station['distance']:.2f} 公里")
        st.sidebar.markdown(f"**可借車輛：** {int(closest_station['sbi'])} 輛")
        st.sidebar.markdown(f"**可還空位：** {int(closest_station['bemp'])} 個")
        
        if df['mday'].notna().any():
            last_update_time = df['mday'].max().strftime('%Y-%m-%d %H:%M:%S')
            st.info(f"**資料最後更新時間：** {last_update_time}")

        # --- Metrics ---
        total_stations = len(df)
        total_bikes_available = int(df['sbi'].sum())
        total_docks_empty = int(df['bemp'].sum())

        col1, col2, col3 = st.columns(3)
        col1.metric(f"總站點數 ({selected_area})", f"{total_stations} 站")
        col2.metric(f"可借車輛 ({selected_area})", f"{total_bikes_available} 輛")
        col3.metric(f"可還空位 ({selected_area})", f"{total_docks_empty} 個")

        st.markdown("---")

        # --- Map and Data Table ---
        map_col, data_col = st.columns([2, 1])

        with map_col:
            st.subheader(f"🗺️ {selected_area} YouBike 站點地圖")
            
            # Map Legend
            st.markdown("""
            <div style="background-color:#f0f2f6;border:1px solid #dfe3e8;padding:10px;border-radius:5px;margin-bottom:10px;font-size:14px;">
                <b>圖例:</b>
                <div style="display:flex;align-items:center;margin-top:5px;"><div style="width:15px;height:15px;background-color:#79c879;margin-right:8px;border-radius:3px;"></div>車輛充足 (≥ 4)</div>
                <div style="display:flex;align-items:center;margin-top:5px;"><div style="width:15px;height:15px;background-color:#f7a364;margin-right:8px;border-radius:3px;"></div>車輛較少 (1-3)</div>
                <div style="display:flex;align-items:center;margin-top:5px;"><div style="width:15px;height:15px;background-color:#e56b6f;margin-right:8px;border-radius:3px;"></div>目前無車 (0)</div>
            </div>
            """, unsafe_allow_html=True)

            m = folium.Map(location=[df['lat'].mean(), df['lng'].mean()], zoom_start=14)

            folium.Marker(
                location=[user_lat, user_lon],
                popup="您的位置", tooltip="您的位置",
                icon=folium.Icon(color='blue', icon='user', prefix='fa')
            ).add_to(m)

            for _, station in df.iterrows():
                popup_html = f"""
                <b>{station['sna']}</b><hr style="margin:5px 0;">
                <b>可借/可還:</b> <font color='{get_marker_color(station['sbi'])}'><b>{int(station['sbi'])}</b></font> / {int(station['bemp'])}<br>
                <b>距離約:</b> {station['distance']:.2f} km
                """
                folium.Marker(
                    location=[station['lat'], station['lng']],
                    popup=folium.Popup(popup_html, max_width=200),
                    tooltip=f"{station['sna']} ({int(station['sbi'])} 輛)",
                    icon=folium.Icon(color=get_marker_color(station['sbi']), icon='bicycle', prefix='fa')
                ).add_to(m)
            
            st_folium(m, width='100%', height=500)

        with data_col:
            st.subheader(f"📊 {selected_area} 資料檢視 (依距離排序)")
            
            display_df = df[['sna', 'sbi', 'bemp', 'distance']].sort_values(by='distance')
            
            st.dataframe(
                display_df, height=500,
                column_config={
                    "sna": "站點名稱", "sbi": "可借", "bemp": "可還",
                    "distance": st.column_config.NumberColumn("距離(km)", format="%.2f")
                },
                hide_index=True
            )
else:
    st.warning("無法載入 YouBike 資料，請稍後再試或檢查 API 狀態。")
