import streamlit as st

st.header("🌍 企業碳盤查儀表板")
st.markdown("輸入您的活動數據，以計算溫室氣體排放量")

st.subheader("📈 碳盤查結果分析")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        label="總排放量 (噸CO2e)",
        value="11.17"
    )
with col2:
    st.metric(
        label="範疇一排放量 (噸CO2e)",
        value="3.74"
    )
with col3:
    st.metric(
        label="範疇二排放量 (噸CO2e)",
        value="7.42"
    )
