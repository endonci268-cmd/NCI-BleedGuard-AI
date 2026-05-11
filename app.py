import streamlit as st
import numpy as np
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import pytz
import plotly.express as px
import plotly.graph_objects as go
import joblib

# --- 1. การตั้งค่าหน้าจอ ---
st.set_page_config(page_title="NCI Bleed Guard AI", page_icon="🛡️", layout="wide")
bkk_tz = pytz.timezone('Asia/Bangkok')

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; }
    .metric-container { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; border-radius: 5px 5px 0px 0px; padding: 10px 20px; }
    .stTabs [aria-selected="true"] { background-color: #007bff !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. โหลดโมเดล AI (ใช้ข้อมูลจาก 1,250 เคส) ---
@st.cache_resource
def load_bleed_model():
    try: 
        return joblib.load("bleedguard_model.pkl")
    except: 
        return None

ai_model = load_bleed_model()

# --- 3. การเชื่อมต่อ Google Sheets (ดึงข้อมูลล่าสุด) ---
def get_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        return conn.read(worksheet="Sheet1", ttl=0)
    except:
        return pd.DataFrame()

df_history = get_data()

# --- ฟังก์ชันระบายสีตาราง Dashboard ---
def highlight_risk(val):
    if val == 'RED': color, text = '#FF4B4B', 'white'
    elif val == 'YELLOW': color, text = '#FFCC00', 'black'
    elif val == 'GREEN': color, text = '#28A745', 'white'
    else: return ''
    return f'background-color: {color}; color: {text}; font-weight: bold;'

# --- 4. ส่วนหัวแอป ---
st.markdown("<h2 style='text-align: center; color: #004d99;'>🛡️ ระบบคัดกรองความเสี่ยงหลังส่องกล้องลำไส้ใหญ่และตัดติ่งเนื้อ</h2>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; color: #004d99;'>(NCI Bleed Guard AI - Expert Hybrid System)</h3>", unsafe_allow_html=True)
st.divider()

# --- 5. ส่วนบันทึกข้อมูล ---
with st.form("nci_triage_form_final", clear_on_submit=False):
    st.markdown("#### 📝 บันทึกข้อมูลแยกตามหมวดหมู่")
    tab1, tab2, tab3 = st.tabs(["👤 ข้อมูลทั่วไป & ประวัติ", "🔍 รายละเอียดหัตถการ", "💊 ปัจจัยเสี่ยง & Clip"])
    
    with tab1:
        c1, c2 = st.columns(2)
        case_id = c1.text_input("Case_ID (รหัสเคส)", value="ENDO-NCI-")
        age = c2.number_input("Age (อายุ)", min_value=1, value=45)
        sex = c1.selectbox("Sex (เพศ)", ["หญิง", "ชาย"])
        surgery = c2.selectbox("Surgery (ประวัติผ่าตัดช่องท้อง)", ["ไม่ใช่", "ใช่"])
        radiation = c1.selectbox("Radiation (ประวัติฉายแสง)", ["ไม่ใช่", "ใช่"])
        chemo = c2.selectbox("Chemo (ประวัติเคมีบำบัด)", ["ไม่ใช่", "ใช่"])
    with tab2:
        c3, c4 = st.columns(2)
        procedure = c3.selectbox("Procedure (วิธีทำหัตถการ)", ["Biopsy Only", "Cold Snare", "Hot Polypectomy", "EMR"])
        size = c4.number_input("Size (ขนาดติ่งเนื้อ cm)", min_value=0.0, step=0.1, value=0.0)
        location = c3.selectbox("loc_right (ตำแหน่งที่พบ)", ["ลำไส้ใหญ่ฝั่งซ้าย", "ลำไส้ใหญ่ฝั่งขวา"])
    with tab3:
        c5, c6 = st.columns(2)
        medication = c5.selectbox("Medication (ยาละลายลิ่มเลือด/ต้านเกล็ดเลือด)", ["ไม่ใช่", "ใช่"])
        hemoclip = c6.selectbox("Hemoclip (มีการติด Clip หรือไม่)", ["ไม่ใส่", "ใส่"])
    
    st.markdown("<br>", unsafe_allow_html=True)
    submit_button = st.form_submit_button("🚀 ประเมินความเสี่ยงและบันทึกข้อมูล")

# --- 6. ส่วนประมวลผล (Expert Hybrid Logic) ---
if submit_button:
    if ai_model and case_id != "ENDO-NCI-":
        try:
            # 1. AI ประมวลผลขั้นต้น
            input_data = [age, 1 if sex == "ชาย" else 0, size, 1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0,
                          1 if medication == "ใช่" else 0, 1 if surgery == "ใช่" else 0, 1 if radiation == "ใช่" else 0,
                          1 if chemo == "ใช่" else 0, 1 if procedure == "Biopsy Only" else 0, 
                          1 if procedure == "Cold Snare" else 0, 1 if procedure == "Hot Polypectomy" else 0,
                          1 if procedure == "EMR" else 0, 0]
            
            prob = ai_model.predict_proba(np.array([input_data]))[0][1]
            score_percent = prob * 100

            # 2. ปรับจูน Score และ Risk (Clinical Override)
            # เงื่อนไข RED
            if procedure == "EMR" or (medication == "ใช่" and hemoclip == "ใส่") or radiation == "ใช่":
                risk, color, text_color, action = "RED", "#FF4B4B", "white", "🚨 โทรติดตามที่ 24, 48, 72 ชม. (High Risk Override)"
                if score_percent < 85: score_percent = 85.0
            # เงื่อนไข YELLOW
            elif hemoclip == "ใส่" or size >= 2.0:
                risk, color, text_color, action = "YELLOW", "#FFCC00", "black", "⚠️ โทรติดตามที่ 24, 48 ชม. (เฝ้าระวังปัจจัยเสี่ยง)"
                if score_percent < 35: score_percent = 35.0
            # ผลตาม AI ปกติ
            elif prob >= 0.40: 
                risk, color, text_color, action = "RED", "#FF4B4B", "white", "🚨 โทรติดตามที่ 24, 48, 72 ชม."
            elif prob >= 0.11: 
                risk, color, text_color, action = "YELLOW", "#FFCC00", "black", "⚠️ โทรติดตามที่ 24, 48 ชม."
            else: 
                risk, color, text_color, action = "GREEN", "#28A745", "white", "✅ ให้คู่มือสังเกตอาการตามมาตรฐาน"

            # 3. การแสดงผล (UI Output)
            res_col1, res_col2 = st.columns([1.2, 1])
            with res_col1:
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = score_percent,
                    number = {'suffix': "%", 'font': {'size': 40}},
                    title = {'text': f"Risk Score: {case_id}", 'font': {'size': 20}},
                    gauge = {
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "black"},
                        'steps': [
                            {'range': [0, 11], 'color': "#28A745"},
                            {'range': [11, 40], 'color': "#FFCC00"},
                            {'range': [40, 100], 'color': "#FF4B4B"}
                        ]
                    }
                ))
                fig_gauge.update_layout(height=350, margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig_gauge, use_container_width=True)

            with res_col2:
                st.markdown(f"""
                    <div style='background-color:{color}; padding:30px; border-radius:15px; text-align:center; color:{text_color}; margin-top:40px; border: 3px solid #333;'>
                        <h1 style='margin:0;'>{risk}</h1>
                        <h3 style='margin:10px;'>โอกาสเลือดออก (Adj): {score_percent:.2f}%</h3>
