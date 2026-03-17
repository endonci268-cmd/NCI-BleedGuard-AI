import streamlit as st
import numpy as np
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import pytz
import plotly.express as px
import joblib

# --- 1. การตั้งค่าหน้าจอ ---
st.set_page_config(page_title="NCI BleedGuard AI Dashboard", page_icon="🛡️", layout="wide")
bkk_tz = pytz.timezone('Asia/Bangkok')

# --- 2. โหลดโมเดล AI (.pkl) ---
@st.cache_resource
def load_bleed_model():
    try:
        # ชื่อไฟล์ต้องตรงกับที่อัปโหลดขึ้น GitHub
        return joblib.load("bleedguard_model.pkl")
    except Exception as e:
        st.error(f"⚠️ ไม่สามารถโหลดโมเดล AI ได้: {e}")
        return None

ai_model = load_bleed_model()

# --- 3. การเชื่อมต่อ Google Sheets ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1RRXOhnjmnRG_6ynHkrd2iXmQYVTqN96CjmCXnuZNA9w/edit?usp=sharing"

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_history = conn.read(spreadsheet=SHEET_URL, worksheet="Sheet1", ttl=0)
except Exception as e:
    st.error(f"⚠️ ไม่สามารถเชื่อมต่อ Google Sheets ได้: {e}")
    df_history = pd.DataFrame()

# --- 4. ระบบ Auto-increment Case ID ---
def get_next_id(df):
    prefix = "Endonci-"
    if df.empty or "Case_ID" not in df.columns:
        return f"{prefix}1"
    ids = df["Case_ID"].astype(str).str.extract(r'Endonci-(\d+)').dropna().astype(int)
    if ids.empty:
        return f"{prefix}1"
    next_num = ids.max().values[0] + 1
    return f"{prefix}{next_num}"

next_case_id = get_next_id(df_history)

# --- 5. ส่วนหัวของแอป ---
st.markdown("<h2 style='text-align: center;'>🛡️ NCI BleedGuard-AI: Smart Dashboard</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>ระบบวิเคราะห์ความเสี่ยงเลือดออกด้วย Artificial Intelligence (12-Features Model)<br>ศูนย์ส่องกล้องทางเดินอาหาร สถาบันมะเร็งแห่งชาติ</p>", unsafe_allow_html=True)
st.divider()

# --- 6. ฟอร์มรับข้อมูล (Input Section) ---
with st.expander(f"➕ บันทึกเคสใหม่ (ลำดับถัดไป: {next_case_id})", expanded=True):
    with st.form("triage_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**👤 ข้อมูลผู้ป่วย**")
            case_id = st.text_input("รหัสเคส (Case ID)", value=next_case_id)
            age = st.number_input("อายุ (ปี)", min_value=1, value=40)
            sex = st.selectbox("เพศ", ["หญิง", "ชาย"])
            medication = st.selectbox("ยาละลายลิ่มเลือด", ["ไม่ใช่", "ใช่"])
        with col2:
            st.markdown("**🔍 ข้อมูลหัตถการ**")
            size = st.number_input("ขนาดติ่งเนื้อ (cm)", min_value=0.1, step=0.1)
            location = st.selectbox("ตำแหน่ง", ["ลำไส้ใหญ่ฝั่งซ้าย", "ลำไส้ใหญ่ฝั่งขวา"])
            procedure = st.selectbox("วิธีตัดติ่งเนื้อ", ["Biopsy Only", "Cold Snare", "Hot Polypectomy", "EMR"])
            clip = st.selectbox("มีการใช้ Clip?", ["ไม่ใช่", "ใช่"])
        with col3:
            st.markdown("**🏥 ประวัติเพิ่มเติม**")
            surgery = st.selectbox("ประวัติผ่าตัดช่องท้อง", ["ไม่ใช่", "ใช่"])
            radiation = st.selectbox("ประวัติฉายแสง", ["ไม่ใช่", "ใช่"])
            chemo = st.selectbox("ประวัติเคมีบำบัด", ["ไม่ใช่", "ใช่"])
        
        submit_button = st.form_submit_button("🚀 ประเมินผลและบันทึกข้อมูล")

# --- 7. การประมวลผลด้วย AI Model (.pkl) ---
if submit_button:
    if ai_model is None:
        st.error("ระบบไม่พร้อมใช้งานเนื่องจากโหลดโมเดลไม่สำเร็จ")
    elif not df_history.empty and case_id in df_history["Case_ID"].values:
        st.error(f"❌ รหัส {case_id} ซ้ำ! กรุณาใช้รหัสใหม่")
    else:
        # เตรียมข้อมูลให้ตรงกับลำดับในโมเดล (12 ตัวแปรเป๊ะๆ)
        # ลำดับ: Age, Sex, Size, Medication, Location, Surgery, Radiation, Chemo, Cold, Hot, EMR, Clip
        features = np.array([[
            age, 
            1 if sex == "ชาย" else 0, 
            size,
            1 if medication == "ใช่" else 0, 
            1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0,
            1 if surgery == "ใช่" else 0, 
            1 if radiation == "ใช่" else 0, 
            1 if chemo == "ใช่" else 0,
            1 if procedure == "Cold Snare" else 0, 
            1 if procedure == "Hot Polypectomy" else 0, 
            1 if procedure == "EMR" else 0,
            1 if clip == "ใช่" else 1 if clip == "y" else 0 # รองรับทั้งการเลือก 'ใช่' และ 'y'
        ]])

        # ทำนายผลความน่าจะเป็น
        prob = ai_model.predict_proba(features)[0][1]
        score_percent = prob * 100

        # กำหนดระดับความเสี่ยง (Triage)
        if prob >= 0.40:
            risk, advice, color = "RED", "📞 โทรติดตาม 24, 48, 72 ชม. เข้มงวด", "#FF4B4B"
        elif prob >= 0.11:
            risk, advice, color = "YELLOW", "📞 โทรติดตาม 24, 48 ชม.", "#FFA500"
        else:
            risk, advice, color = "GREEN", "✅ ให้คู่มือสังเกตอาการตามปกติ", "#28A745"

        # แสดงผลลัพธ์
        st.markdown(f"""
            <div style='background-color:{color}; padding:25px; border-radius:15px; text-align:center; color:white;'>
                <h1 style='margin:0;'>ระดับความเสี่ยง: {risk}</h1>
                <h3 style='margin:10px;'>โอกาสเกิดเลือดออก: {score_percent:.2f}%</h3>
                <p style='font-size:18px;'>{advice}</p>
            </div>
        """, unsafe_allow_html=True)

        # บันทึกข้อมูล
        new_entry = pd.DataFrame([{
            "Timestamp": datetime.now(bkk_tz).strftime("%Y-%m-%d %H:%M:%S"),
            "Case_ID": case_id, "Age": age, "Sex": sex, "Size": size,
            "Risk_Score": f"{score_percent:.2f}%", "Risk_Level": risk, "Advice": advice
        }])
        
        try:
            df_updated = pd.concat([df_history, new_entry], ignore_index=True)
            conn.update(worksheet="Sheet1", data=df_updated)
            st.toast("✅ บันทึกข้อมูลสำเร็จ!")
            st.rerun()
        except:
            st.error("บันทึกข้อมูลลง Sheets ไม่สำเร็จ")

# --- 8. Dashboard สรุปผล ---
st.divider()
st.header("📊 Dashboard วิเคราะห์ข้อมูล")

if not df_history.empty:
    df_history['Timestamp'] = pd.to_datetime(df_history['Timestamp'])
    today = datetime.now(bkk_tz).date()
    df_today = df_history[df_history['Timestamp'].dt.date == today]
    
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("วันนี้ทั้งหมด", f"{len(df_today)} เคส")
    t2.metric("🔴 เสี่ยงสูง", len(df_today[df_today['Risk_Level'] == 'RED']))
    t3.metric("🟡 ปานกลาง", len(df_today[df_today['Risk_Level'] == 'YELLOW']))
    t4.metric("🟢 เสี่ยงต่ำ", len(df_today[df_today['Risk_Level'] == 'GREEN']))
    
    st.subheader("📋 ประวัติการบันทึกล่าสุด")
    st.dataframe(df_history.tail(10).sort_values(by='Timestamp', ascending=False), use_container_width=True)
