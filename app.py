import streamlit as st
import numpy as np
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import pytz
import plotly.express as px
import plotly.graph_objects as go
import joblib

# --- 1. การตั้งค่าหน้าจอ (Mobile Friendly) ---
st.set_page_config(
    page_title="NCI Bleed Guard AI", 
    page_icon="🛡️", 
    layout="wide"
)

bkk_tz = pytz.timezone('Asia/Bangkok')

# CSS ตกแต่ง
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; }
    .metric-container { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. โหลดโมเดล AI ---
@st.cache_resource
def load_bleed_model():
    try: return joblib.load("bleedguard_model.pkl")
    except: return None

ai_model = load_bleed_model()

# --- 3. การเชื่อมต่อ Google Sheets ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_history = conn.read(worksheet="Sheet1", ttl=0)
except:
    df_history = pd.DataFrame()

# --- 4. ส่วนหัวแอป ---
st.markdown("<h2 style='text-align: center; color: #004d99;'>🛡️ ระบบคัดกรองความเสี่ยงหลังส่องกล้องลำไส้ใหญ่และตัดติ่งเนื้อ</h2>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; color: #004d99;'>(NCI Bleed Guard AI)</h3>", unsafe_allow_html=True)
st.divider()

# --- 5. ส่วนบันทึกข้อมูลและประเมินผล ---
with st.container():
    with st.form("triage_form", clear_on_submit=False):
        st.markdown("#### ➕ บันทึกข้อมูลหัตถการ")
        col_form1, col_form2 = st.columns(2)
        with col_form1:
            case_id = st.text_input("Case_ID (รหัสเคส)", value="ENDO-NCI-")
            age = st.number_input("Age (อายุ)", min_value=1, value=45)
            sex = st.selectbox("Sex (เพศ)", ["หญิง", "ชาย"])
            medication = st.selectbox("Medication (ยาละลายลิ่มเลือด)", ["ไม่ใช่", "ใช่"])
            location = st.selectbox("loc_right (ตำแหน่ง)", ["ลำไส้ใหญ่ฝั่งซ้าย", "ลำไส้ใหญ่ฝั่งขวา"])
            chemo = st.selectbox("Chemo (ประวัติเคมีบำบัด)", ["ไม่ใช่", "ใช่"])
        with col_form2:
            procedure = st.selectbox("Procedure (วิธีตัด)", ["Biopsy Only", "Cold Snare", "Hot Polypectomy", "EMR"])
            hemoclip = st.selectbox("Clip (การใช้ Hemoclip)", ["ไม่ใส่", "ใส่"])
            surgery = st.selectbox("Surgery (ประวัติผ่าตัด)", ["ไม่ใช่", "ใช่"])
            radiation = st.selectbox("Radiation (ประวัติฉายแสง)", ["ไม่ใช่", "ใช่"])
            size = st.number_input("Size (ขนาดติ่งเนื้อ cm)", min_value=0.0, step=0.1, value=0.0)
            
        submit_button = st.form_submit_button("🚀 ประเมินความเสี่ยงและบันทึกข้อมูล")

# --- 6. ส่วน
