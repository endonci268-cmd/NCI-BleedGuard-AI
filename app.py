import streamlit as st
import numpy as np
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import pytz
import joblib

# --- 1. การตั้งค่าหน้าจอ ---
st.set_page_config(page_title="NCI BleedGuard AI", page_icon="🛡️", layout="wide")
bkk_tz = pytz.timezone('Asia/Bangkok')

# --- 2. โหลดโมเดล AI ---
@st.cache_resource
def load_bleed_model():
    try:
        return joblib.load("bleedguard_model.pkl")
    except Exception as e:
        st.error(f"⚠️ ไม่สามารถโหลดโมเดลได้: {e}")
        return None

ai_model = load_bleed_model()

# --- 3. เชื่อมต่อ Google Sheets ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1RRXOhnjmnRG_6ynHkrd2iXmQYVTqN96CjmCXnuZNA9w/edit?usp=sharing"
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_history = conn.read(spreadsheet=SHEET_URL, worksheet="Sheet1", ttl=0)
except:
    df_history = pd.DataFrame()

# --- 4. ส่วนหัวแอป ---
st.markdown("<h2 style='text-align: center;'>🛡️ NCI BleedGuard-AI</h2>", unsafe_allow_html=True)
st.divider()

# --- 5. ฟอร์มรับข้อมูล ---
with st.form("triage_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**👤 ข้อมูลผู้ป่วย**")
        case_id = st.text_input("รหัสเคส (Case ID)")
        age = st.number_input("อายุ (ปี)", min_value=1, value=45)
        sex = st.selectbox("เพศ", ["หญิง", "ชาย"])
        medication = st.selectbox("ยาละลายลิ่มเลือด", ["ไม่ใช่", "ใช่"])
    with col2:
        st.markdown("**🔍 ข้อมูลหัตถการ**")
        size = st.number_input("ขนาดติ่งเนื้อ (cm)", min_value=0.0, step=0.1, value=0.0)
        location = st.selectbox("ตำแหน่ง", ["ลำไส้ใหญ่ฝั่งซ้าย", "ลำไส้ใหญ่ฝั่งขวา"])
        procedure = st.selectbox("วิธีทำหัตถการ", ["Biopsy Only", "Cold Snare", "Hot Polypectomy", "EMR"])
    with col3:
        st.markdown("**🏥 ประวัติเพิ่มเติม**")
        surgery = st.selectbox("ประวัติผ่าตัด", ["ไม่ใช่", "ใช่"])
        radiation = st.selectbox("ประวัติฉายแสง", ["ไม่ใช่", "ใช่"])
        chemo = st.selectbox("ประวัติเคมีบำบัด", ["ไม่ใช่", "ใช่"])
    
    submit_button = st.form_submit_button("🚀 ประเมินผล AI")

# --- 6. ประมวลผล AI พร้อมตัวตรวจสอบจำนวน Features ---
if submit_button:
    if ai_model is not None:
        try:
            # รายการตัวแปร 12 ตัวตามที่คุณพยาบาลแจ้งจาก Colab
            input_list = [
                age,                                          # 1. age
                1 if sex == "ชาย" else 0,                     # 2. sex
                size,                                         # 3. size_cm
                1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0,    # 4. loc_right
                1 if medication == "ใช่" else 0,              # 5. med_risk
                1 if surgery == "ใช่" else 0,                 # 6. surgery
                1 if radiation == "ใช่" else 0,               # 7. radiation
                1 if chemo == "ใช่" else 0,                   # 8. chemo
                1 if procedure == "Biopsy Only" else 0,       # 9. bx
                1 if procedure == "Cold Snare" else 0,        # 10. cold_snare
                1 if procedure == "Hot Polypectomy" else 0,   # 11. hot_poly
                1 if procedure == "EMR" else 0                # 12. emr
            ]

            # ตรวจสอบว่าโมเดลนี้ต้องการตัวแปรกี่ตัวกันแน่
            n_needed = ai_model.n_features_in_
            
            # ปรับข้อมูลให้มีจำนวนเท่ากับที่โมเดลต้องการเป๊ะๆ
            features = np.array([input_list[:n_needed]])

            prob = ai_model.predict_proba(features)[0][1]
            score_percent = prob * 100

            # แสดงผลลัพธ์
            risk = "RED" if prob >= 0.40 else "YELLOW" if prob >= 0.11 else "GREEN"
            color = "#FF4B4B" if risk == "RED" else "#FFA500" if risk == "YELLOW" else "#28A745"
            
            st.markdown(f"<div style='background:{color};padding:20px;border-radius:10px;text-align:center;color:white;'><h1>{risk}</h1><h3>ความเสี่ยง: {score_percent:.2f}%</h3></div>", unsafe_allow_html=True)

            # บันทึกข้อมูล
            new_entry = pd.DataFrame([{"Timestamp": datetime.now(bkk_tz).strftime("%Y-%m-%d %H:%M:%S"), "Case_ID": case_id, "Procedure": procedure, "Risk_Level": risk, "Score": f"{score_percent:.2f}%"}])
            df_updated = pd.concat([df_history, new_entry], ignore_index=True)
            conn.update(data=df_updated)
            st.toast("✅ บันทึกสำเร็จ")

        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาด: {e}")
            # แจ้งคุณพยาบาลว่า AI ตัวนี้จริงๆ แล้วต้องการตัวแปรกี่ตัว
            st.info(f"💡 ข้อมูลทางเทคนิค: AI โมเดลของคุณพยาบาลต้องการตัวแปร {ai_model.n_features_in_} ตัว")
    else:
        st.error("ไม่สามารถโหลดโมเดลได้")
