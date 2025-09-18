import streamlit as st
import pandas as pd
import requests
import json
import urllib3

# API設定
API_URL = "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download"
RESOURCE_ID = "7d7dade7-2f75-4cf9-8467-6c26c447c6ca"

@st.cache_data(ttl=60)
def get_data():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    response = requests.get(API_URL, params={"rid": RESOURCE_ID}, verify=False)
    data = response.json()
    stations = json.loads(data["retVal"])
    df = pd.DataFrame(stations)
    
    # 轉換數值欄位
    numeric_cols = ['sbi', 'bemp', 'tot', 'lat', 'lng']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

# 頁面設定
st.set_page_config(page_title="台中 YouBike", layout="wide")
st.title("🚲 台中市 YouBike 2.0 即時資訊")

# 取得資料
try:
    df = get_data()
    st.success(f"載入 {len(df)} 個站點")
    
    # 選擇區域
    areas = df['sarea'].unique()
    selected_area = st.selectbox("選擇區域", areas)
    
    # 篩選資料
    filtered_df = df[df['sarea'] == selected_area]
    
    # 顯示統計
    col1, col2, col3 = st.columns(3)
    col1.metric("站點數", len(filtered_df))
    col2.metric("可借車輛", int(filtered_df['sbi'].sum()))
    col3.metric("可還空位", int(filtered_df['bemp'].sum()))
    
    # 顯示資料表
    st.dataframe(
        filtered_df[['sna', 'ar', 'sbi', 'bemp', 'tot']],
        column_config={
            "sna": "站點名稱",
            "ar": "地址", 
            "sbi": "可借",
            "bemp": "可還",
            "tot": "總位"
        },
        use_container_width=True
    )
    
except Exception as e:
    st.error(f"載入失敗: {e}")
