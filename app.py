import streamlit as st
import numpy as np
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import pytz
import plotly.express as px
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

# --- 3. การเชื่อมต่อ Google Sheets (ล็อคชื่อไฟล์ใหม่) ---
# ตรวจสอบว่าใน Secrets ใส่ URL ของไฟล์ BleedGuard_NCI_Final ไว้แล้วนะครับ
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_history = conn.read(worksheet="Sheet1", ttl=0)
except:
    df_history = pd.DataFrame()

# --- 4. ส่วนหัวแอป ---
st.markdown("<h2 style='text-align: center;'>🛡️ NCI BleedGuard-AI</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>ศูนย์ส่องกล้องทางเดินอาหาร สถาบันมะเร็งแห่งชาติ</p>", unsafe_allow_html=True)
st.divider()

# --- 5. ฟอร์มรับข้อมูล ---
with st.expander("➕ บันทึกเคสใหม่และประเมินผล AI", expanded=True):
    with st.form("triage_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**👤 ข้อมูลผู้ป่วย**")
            case_id = st.text_input("Case_ID (รหัสเคส)")
            age = st.number_input("Age (อายุ)", min_value=1, value=45)
            sex = st.selectbox("Sex (เพศ)", ["หญิง", "ชาย"])
            medication = st.selectbox("Medication (ยาละลายลิ่มเลือด)", ["ไม่ใช่", "ใช่"])
        with col2:
            st.markdown("**🔍 ข้อมูลหัตถการ**")
            size = st.number_input("Size (ขนาด cm)", min_value=0.0, step=0.1, value=0.0)
            location = st.selectbox("loc_right (ตำแหน่ง)", ["ลำไส้ใหญ่ฝั่งซ้าย", "ลำไส้ใหญ่ฝั่งขวา"])
            procedure = st.selectbox("Procedure (วิธีตัด)", ["Biopsy Only", "Cold Snare", "Hot Polypectomy", "EMR"])
            hemoclip = st.selectbox("Clip (การใช้ Hemoclip)", ["ไม่ใส่", "ใส่"])
        with col3:
            st.markdown("**🏥 ประวัติเพิ่มเติม**")
            surgery = st.selectbox("Surgery (ประวัติผ่าตัด)", ["ไม่ใช่", "ใช่"])
            radiation = st.selectbox("Radiation (ประวัติฉายแสง)", ["ไม่ใช่", "ใช่"])
            chemo = st.selectbox("Chemo (ประวัติเคมีบำบัด)", ["ไม่ใช่", "ใช่"])
        
        submit_button = st.form_submit_button("🚀 ประเมินผลและบันทึกข้อมูล")

# --- 6. การประมวลผล AI (13 Features) ---
if submit_button:
    if ai_model is None:
        st.error("โมเดลไม่พร้อมใช้งาน")
    elif not case_id:
        st.warning("กรุณาใส่ Case ID")
    else:
        try:
            # 13 Features: age, sex, size, loc, med, sur, rad, che, bx, cold, hot, emr, dummy
            input_data = [
                age, 1 if sex == "ชาย" else 0, size,
                1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0,
                1 if medication == "ใช่" else 0,
                1 if surgery == "ใช่" else 0,
                1 if radiation == "ใช่" else 0,
                1 if chemo == "ใช่" else 0,
                1 if procedure == "Biopsy Only" else 0,
                1 if procedure == "Cold Snare" else 0,
                1 if procedure == "Hot Polypectomy" else 0,
                1 if procedure == "EMR" else 0,
                0 # dummy feature ตัวที่ 13
            ]
            
            features = np.array([input_data])
            prob = ai_model.predict_proba(features)[0][1]
            score_percent = prob * 100

            risk = "RED" if prob >= 0.40 else "YELLOW" if prob >= 0.11 else "GREEN"
            color = "#FF4B4B" if risk == "RED" else "#FFA500" if risk == "YELLOW" else "#28A745"
            advice = "📞 โทรติดตาม 24, 48, 72 ชม." if risk == "RED" else "📞 โทรติดตาม 24, 48 ชม." if risk == "YELLOW" else "✅ ให้คู่มือสังเกตอาการ"

            st.markdown(f"<div style='background-color:{color}; padding:20px; border-radius:10px; text-align:center; color:white;'><h2>{risk} (ความเสี่ยง: {score_percent:.2f}%)</h2><p>{advice}</p></div>", unsafe_allow_html=True)

            # เตรียมข้อมูลบันทึกลง Sheets ตามลำดับคอลัมน์ที่คุณพยาบาลต้องการ
            new_entry = pd.DataFrame([{
                "Timestamp": datetime.now(bkk_tz).strftime("%Y-%m-%d %H:%M:%S"),
                "Case_ID": case_id, "Age": age, "Sex": sex, "Size": size,
                "loc_right": 1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0,
                "Medication": medication, "Surgery": surgery, "Radiation": radiation, "Chemo": chemo,
                "BX": 1 if procedure == "Biopsy Only" else 0,
                "Cold_Poly": 1 if procedure == "Cold Snare" else 0,
                "Hot_Poly": 1 if procedure == "Hot Polypectomy" else 0,
                "EMR": 1 if procedure == "EMR" else 0,
                "Clip": hemoclip, "Risk_Level": risk, "Actual_Bleeding": "", 
                "Advice": advice, "Score": f"{score_percent:.2f}%"
            }])
            
            df_updated = pd.concat([df_history, new_entry], ignore_index=True)
            conn.update(worksheet="Sheet1", data=df_updated)
            st.toast("✅ บันทึกสำเร็จ!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")

# --- 7. DASHBOARD SECTION ---
st.divider()
if not df_history.empty:
    m1, m2, m3 = st.columns(3)
    m1.metric("เคสทั้งหมด", f"{len(df_history)} ราย")
    m2.metric("🔴 เสี่ยงสูง", len(df_history[df_history['Risk_Level'] == 'RED']))
    m3.metric("🟢 เสี่ยงต่ำ/ปานกลาง", len(df_history[df_history['Risk_Level'] != 'RED']))

    st.subheader("📋 ประวัติการบันทึกล่าสุด")
    st.dataframe(df_history.tail(10), use_container_width=True)
else:
    st.info("ยังไม่มีข้อมูลเพื่อแสดง Dashboard")
