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
st.set_page_config(page_title="NCI BleedGuard AI", page_icon="🛡️", layout="wide")
bkk_tz = pytz.timezone('Asia/Bangkok')

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; }
    .risk-banner { padding: 20px; border-radius: 15px; color: white; text-align: center; margin-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. โหลดโมเดล AI ---
@st.cache_resource
def load_bleed_model():
    try: return joblib.load("bleedguard_model.pkl")
    except: return None

ai_model = load_bleed_model()

# --- 3. เชื่อมต่อ Google Sheets ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_history = conn.read(worksheet="Sheet1", ttl=0)
except:
    df_history = pd.DataFrame()

# --- 4. ส่วนหัวแอป ---
st.markdown("<h2 style='text-align: center; color: #004d99;'>🛡️ NCI BleedGuard-AI</h2>", unsafe_allow_html=True)
st.divider()

# --- 5. ส่วนบันทึกและประเมินผล (ย้ายเข็มมาไว้ที่นี่) ---
with st.container():
    with st.form("triage_form", clear_on_submit=False):
        st.markdown("### ➕ บันทึกเคสใหม่")
        col1, col2 = st.columns(2)
        with col1:
            case_id = st.text_input("Case_ID (รหัสเคส)")
            age = st.number_input("Age (อายุ)", min_value=1, value=45)
            sex = st.selectbox("Sex (เพศ)", ["หญิง", "ชาย"])
            medication = st.selectbox("Medication (ยาละลายลิ่มเลือด)", ["ไม่ใช่", "ใช่"])
            location = st.selectbox("loc_right (ตำแหน่ง)", ["ลำไส้ใหญ่ฝั่งซ้าย", "ลำไส้ใหญ่ฝั่งขวา"])
        with col2:
            procedure = st.selectbox("Procedure (วิธีตัด)", ["Biopsy Only", "Cold Snare", "Hot Polypectomy", "EMR"])
            hemoclip = st.selectbox("Clip (การใช้ Hemoclip)", ["ไม่ใส่", "ใส่"])
            surgery = st.selectbox("Surgery (ประวัติผ่าตัด)", ["ไม่ใช่", "ใช่"])
            radiation = st.selectbox("Radiation (ประวัติฉายแสง)", ["ไม่ใช่", "ใช่"])
            size = st.number_input("Size (ขนาด cm)", min_value=0.0, step=0.1, value=0.0)
            
        submit_button = st.form_submit_button("🚀 ประเมินความเสี่ยงและบันทึกข้อมูล")

# --- 6. ส่วนแสดงผลลัพธ์ทันที (หน้าบันทึก) ---
if submit_button:
    if ai_model and case_id:
        try:
            # 13 Features
            input_data = [age, 1 if sex == "ชาย" else 0, size, 1 if location == "ลำไยใหญ่ฝั่งขวา" else 0,
                          1 if medication == "ใช่" else 0, 1 if surgery == "ใช่" else 0, 1 if radiation == "ใช่" else 0,
                          0, 1 if procedure == "Biopsy Only" else 0, # เพิ่ม dummy chemo เป็น 0
                          1 if procedure == "Cold Snare" else 0, 1 if procedure == "Hot Polypectomy" else 0,
                          1 if procedure == "EMR" else 0, 0]
            
            prob = ai_model.predict_proba(np.array([input_data]))[0][1]
            score_percent = prob * 100

            if prob >= 0.40: risk, color, action = "RED (เสี่ยงสูงมาก)", "#FF4B4B", "📢 โทรติดตามที่ 24, 48, 72 ชม."
            elif prob >= 0.11: risk, color, action = "YELLOW (เสี่ยงปานกลาง)", "#FFA500", "📢 โทรติดตามที่ 24, 48 ชม."
            else: risk, color, action = "GREEN (เสี่ยงต่ำ)", "#28A745", "✅ ให้คู่มือสังเกตอาการตามมาตรฐาน"

            # --- แสดงเข็ม Gauge และแถบสีทันที ---
            res_col1, res_col2 = st.columns([1.2, 1])
            
            with res_col1:
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = score_percent,
                    title = {'text': f"Risk Score: {case_id}", 'font': {'size': 20}},
                    gauge = {
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "black"},
                        'steps': [
                            {'range': [0, 11], 'color': "#28A745"},
                            {'range': [11, 40], 'color': "#FFA500"},
                            {'range': [40, 100], 'color': "#FF4B4B"}
                        ],
                        'threshold': {'line': {'color': "white", 'width': 4}, 'value': score_percent}
                    }))
                fig_gauge.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_gauge, use_container_width=True)

            with res_col2:
                st.markdown(f"""
                    <div style='background-color:{color}; padding:20px; border-radius:15px; text-align:center; color:white; margin-top:50px;'>
                        <h2 style='margin:0;'>{risk}</h2>
                        <p style='font-size: 1.3em; font-weight: bold;'>{action}</p>
                    </div>
                    """, unsafe_allow_html=True)

            # บันทึกลง Sheets
            new_entry = pd.DataFrame([{
                "Timestamp": datetime.now(bkk_tz).strftime("%Y-%m-%d %H:%M:%S"),
                "Case_ID": case_id, "Age": age, "Sex": sex, "Size": size,
                "loc_right": 1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0, "Medication": medication,
                "Clip": hemoclip, "Risk_Level": risk.split()[0], "Score": f"{score_percent:.2f}%", "Advice": action
            }])
            conn.update(worksheet="Sheet1", data=pd.concat([df_history, new_entry], ignore_index=True))
            st.toast("✅ บันทึกข้อมูลสำเร็จ")
            
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.warning("กรุณาระบุ Case ID")

# --- 7. DASHBOARD (เฉพาะสถิติและประวัติ) ---
st.divider()
if not df_history.empty:
    st.subheader("📊 ประวัติและการค้นหา")
    search_date = st.date_input("📅 ค้นหาวันที่", datetime.now(bkk_tz).date())
    df_history['Date_Only'] = pd.to_datetime(df_history['Timestamp']).dt.date
    df_filtered = df_history[df_history['Date_Only'] == search_date]
    
    st.dataframe(df_filtered.reset_index()[['Timestamp', 'Case_ID', 'Risk_Level', 'Score']], use_container_width=True, hide_index=True)
