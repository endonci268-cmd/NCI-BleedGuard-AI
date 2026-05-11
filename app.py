import streamlit as st
import numpy as np
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import pytz
import plotly.express as px
import plotly.graph_objects as go
import joblib

# --- 1. ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="NCI Bleed Guard AI", page_icon="🛡️", layout="wide")
bkk_tz = pytz.timezone('Asia/Bangkok')

# --- 2. โหลดโมเดล AI ---
@st.cache_resource
def load_bleed_model():
    try: return joblib.load("bleedguard_model.pkl")
    except: return None

ai_model = load_bleed_model()

# --- 3. ฟังก์ชันดึงข้อมูล (ดึงสดใหม่เสมอ) ---
def get_fresh_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        return conn.read(worksheet="Sheet1", ttl=0) # ttl=0 คือไม่ใช้ค่าเก่า
    except:
        return pd.DataFrame()

# ดึงข้อมูลครั้งแรกเมื่อเปิดแอป
df_history = get_fresh_data()

# ฟังก์ชันระบายสีตาราง
def highlight_risk(val):
    if val == 'RED': color, text = '#FF4B4B', 'white'
    elif val == 'YELLOW': color, text = '#FFCC00', 'black'
    elif val == 'GREEN': color, text = '#28A745', 'white'
    else: return ''
    return f'background-color: {color}; color: {text}; font-weight: bold;'

# --- 4. ส่วนหัวแอป ---
st.markdown("<h2 style='text-align: center; color: #004d99;'>🛡️ ระบบคัดกรองความเสี่ยงหลังส่องกล้องลำไส้ใหญ่และตัดติ่งเนื้อ</h2>", unsafe_allow_html=True)
st.divider()

# --- 5. ฟอร์มบันทึกข้อมูล ---
with st.form("triage_form", clear_on_submit=False):
    st.markdown("#### 📝 บันทึกข้อมูลหัตถการ")
    tab1, tab2, tab3 = st.tabs(["👤 ข้อมูลทั่วไป", "🔍 หัตถการ", "💊 ปัจจัยเสี่ยง"])
    
    with tab1:
        c1, c2 = st.columns(2)
        case_id = c1.text_input("Case_ID", value="ENDO-NCI-")
        age = c2.number_input("Age", min_value=1, value=45)
        sex = c1.selectbox("Sex", ["หญิง", "ชาย"])
    with tab2:
        c3, c4 = st.columns(2)
        procedure = c3.selectbox("Procedure", ["Biopsy Only", "Cold Snare", "Hot Polypectomy", "EMR"])
        size = c4.number_input("Size (cm)", min_value=0.0, step=0.1)
        location = c3.selectbox("Location", ["ลำไส้ใหญ่ฝั่งซ้าย", "ลำไส้ใหญ่ฝั่งขวา"])
    with tab3:
        c5, c6 = st.columns(2)
        medication = c5.selectbox("Medication (ยาละลายลิ่มเลือด)", ["ไม่ใช่", "ใช่"])
        hemoclip = c6.selectbox("Hemoclip (ติด Clip)", ["ไม่ใส่", "ใส่"])
        surgery = "ไม่ใช่"; radiation = "ไม่ใช่"; chemo = "ไม่ใช่" # ค่าเริ่มต้น

    submit_button = st.form_submit_button("🚀 ประเมินความเสี่ยงและบันทึกข้อมูล")

# --- 6. ส่วนประมวลผลและบันทึก (จุดที่แก้ปัญหาคอลัมน์ว่าง) ---
if submit_button:
    if ai_model and case_id != "ENDO-NCI-":
        try:
            # 1. คำนวณ AI
            input_data = [age, 1 if sex == "ชาย" else 0, size, 1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0,
                          1 if medication == "ใช่" else 0, 0, 0, 0, 
                          1 if procedure == "Biopsy Only" else 0, 1 if procedure == "Cold Snare" else 0, 
                          1 if procedure == "Hot Polypectomy" else 0, 1 if procedure == "EMR" else 0, 0]
            
            prob = ai_model.predict_proba(np.array([input_data]))[0][1]
            score_percent = prob * 100

            # 2. Clinical Override & Score Alignment (ดันเข็มไมล์ให้ตรงกับสี)
            if procedure == "EMR" or (medication == "ใช่" and hemoclip == "ใส่"):
                risk, color, text_color, action = "RED", "#FF4B4B", "white", "🚨 โทรติดตามที่ 24, 48, 72 ชม."
                if score_percent < 85: score_percent = 85.0
            elif hemoclip == "ใส่" or size >= 2.0:
                risk, color, text_color, action = "YELLOW", "#FFCC00", "black", "⚠️ โทรติดตามที่ 24, 48 ชม."
                if score_percent < 35: score_percent = 35.0
            elif prob >= 0.40: risk, color, text_color, action = "RED", "#FF4B4B", "white", "🚨 โทรติดตาม"
            elif prob >= 0.11: risk, color, text_color, action = "YELLOW", "#FFCC00", "black", "⚠️ โทรติดตาม"
            else: risk, color, text_color, action = "GREEN", "#28A745", "white", "✅ ให้คู่มือสังเกตอาการ"

            # 3. บันทึกข้อมูล (รวบรวมทุกช่องให้ครบ)
            new_entry = pd.DataFrame([{
                "Timestamp": datetime.now(bkk_tz).strftime("%Y-%m-%d %H:%M:%S"),
                "Case_ID": case_id, "Age": age, "Sex": sex, "Size": size,
                "Medication": medication, "Clip": hemoclip, 
                "Risk_Level": risk, 
                "Score": f"{score_percent:.2f}%",  # บันทึกคะแนนลงช่อง Score
                "Advice": action                   # บันทึกคำแนะนำลงช่อง Advice
            }])
            
            conn = st.connection("gsheets", type=GSheetsConnection)
            # สำคัญ: ต้องรวมข้อมูลเก่ากับใหม่ก่อนส่งไปบันทึก
            updated_data = pd.concat([df_history, new_entry], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_data)
            
            st.success(f"✅ บันทึกข้อมูล {case_id} ครบถ้วนแล้ว!")
            
            # 4. บังคับรีเฟรชหน้าจอ เพื่อให้ Dashboard ดึงข้อมูลล่าสุดมาโชว์ (แก้ปัญหาคอลัมน์ว่าง)
            if st.button("🔄 อัปเดต Dashboard และรับเคสถัดไป"):
                st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")

# --- 7. DASHBOARD (ดึงข้อมูลล่าสุดมาแสดง) ---
st.divider()
st.header("📊 Dashboard")
if not df_history.empty:
    # ตาราง 10 เคสล่าสุด (เรียงจากบนลงล่าง)
    st.write("📋 รายละเอียด 10 เคสล่าสุด")
    # ดึงข้อมูลสดอีกรอบเฉพาะส่วน Dashboard
    display_df = df_history.sort_index(ascending=False).head(10)
    st.dataframe(
        display_df.style.map(highlight_risk, subset=['Risk_Level']), 
        use_container_width=True, hide_index=True
    )
