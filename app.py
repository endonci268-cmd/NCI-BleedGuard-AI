import streamlit as st
import numpy as np
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import pytz
import plotly.express as px
import plotly.graph_objects as go
import joblib

# --- 1. การตั้งค่าหน้าจอ (รองรับ Mobile Friendly) ---
st.set_page_config(
    page_title="NCI BleedGuard AI", 
    page_icon="🛡️", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# สไตล์ CSS เพิ่มเติมเพื่อให้ปุ่มและตัวอักษรอ่านง่ายบนมือถือ
st.markdown("""
    <style>
    .main { font-family: 'Sarabun', sans-serif; }
    div[data-testid="stMetricValue"] { font-size: 25px; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

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

# --- 3. การเชื่อมต่อ Google Sheets ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # อ่านจากชื่อไฟล์ BleedGuard_NCI_Final และ Sheet1
    df_history = conn.read(worksheet="Sheet1", ttl=0)
except Exception as e:
    st.error(f"⚠️ การเชื่อมต่อ Google Sheets ขัดข้อง: {e}")
    df_history = pd.DataFrame()

# --- 4. ส่วนหัวของแอป ---
st.markdown("<h2 style='text-align: center; color: #004d99;'>🛡️ NCI BleedGuard-AI</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>ศูนย์ส่องกล้องทางเดินอาหาร สถาบันมะเร็งแห่งชาติ</p>", unsafe_allow_html=True)
st.divider()

# --- 5. ฟอร์มรับข้อมูล (บันทึกเคสใหม่) ---
with st.expander("➕ บันทึกเคสใหม่ / ประเมินความเสี่ยง", expanded=True):
    with st.form("triage_form", clear_on_submit=True):
        col1, col2 = st.columns([1, 1])
        with col1:
            case_id = st.text_input("Case_ID (รหัสเคส)")
            age = st.number_input("Age (อายุ)", min_value=1, value=45)
            sex = st.selectbox("Sex (เพศ)", ["หญิง", "ชาย"])
            medication = st.selectbox("Medication (ยาละลายลิ่มเลือด)", ["ไม่ใช่", "ใช่"])
            location = st.selectbox("loc_right (ตำแหน่ง)", ["ลำไส้ใหญ่ฝั่งซ้าย", "ลำไส้ใหญ่ฝั่งขวา"])
            procedure = st.selectbox("Procedure (วิธีตัด)", ["Biopsy Only", "Cold Snare", "Hot Polypectomy", "EMR"])

        with col2:
            hemoclip = st.selectbox("Clip (การใช้ Hemoclip)", ["ไม่ใส่", "ใส่"])
            surgery = st.selectbox("Surgery (ประวัติผ่าตัด)", ["ไม่ใช่", "ใช่"])
            radiation = st.selectbox("Radiation (ประวัติฉายแสง)", ["ไม่ใช่", "ใช่"])
            chemo = st.selectbox("Chemo (ประวัติเคมีบำบัด)", ["ไม่ใช่", "ใช่"])
            size = st.number_input("Size (ขนาดติ่งเนื้อ cm)", min_value=0.0, step=0.1, value=0.0)
            
        submit_button = st.form_submit_button("🚀 ประเมินและบันทึกข้อมูล")

# --- 6. ประมวลผล AI (13 Features) ---
if submit_button:
    if ai_model is None:
        st.error("ระบบไม่พร้อมใช้งานเนื่องจากโหลดโมเดลไม่ได้")
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
            
            prob = ai_model.predict_proba(np.array([input_data]))[0][1]
            score_percent = prob * 100

            # กำหนดเกณฑ์ RED/YELLOW/GREEN
            if prob >= 0.40: risk, color, advice = "RED", "#FF4B4B", "📞 โทรติดตาม 24, 48, 72 ชม. เข้มงวด"
            elif prob >= 0.11: risk, color, advice = "YELLOW", "#FFA500", "📞 โทรติดตาม 24, 48 ชม."
            else: risk, color, advice = "GREEN", "#28A745", "✅ ให้คู่มือสังเกตอาการตามมาตรฐาน"

            # บันทึกลง Google Sheets
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
            st.success(f"บันทึกเคส {case_id} สำเร็จ!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาดในการประมวลผล: {e}")

# --- 7. DASHBOARD & SEARCH SECTION (รองรับการเปิดบนมือถือ) ---
st.divider()
st.markdown("### 📊 Dashboard & ค้นหาข้อมูล")

if not df_history.empty:
    # ส่วนค้นหาด้วยปฏิทิน
    search_date = st.date_input("📅 เลือกวันที่ต้องการดูข้อมูล", datetime.now(bkk_tz).date())
    df_history['Date_Only'] = pd.to_datetime(df_history['Timestamp']).dt.date
    df_filtered = df_history[df_history['Date_Only'] == search_date]

    if not df_filtered.empty:
        # แสดงเข็ม Risk Gauge
        latest_case = df_filtered.iloc[-1]
        try:
            score_val = float(str(latest_case['Score']).replace('%', ''))
        except:
            score_val = 0.0
            
        # สร้างกราฟเข็ม (Gauge Chart)
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = score_val,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"ความเสี่ยงล่าสุด: {latest_case['Case_ID']}", 'font': {'size': 18}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1},
                'bar': {'color': "black"},
                'steps': [
                    {'range': [0, 11], 'color': "#28A745"},
                    {'range': [11, 40], 'color': "#FFA500"},
                    {'range': [40, 100], 'color': "#FF4B4B"}
                ],
                'threshold': {
                    'line': {'color': "white", 'width': 4},
                    'thickness': 0.75,
                    'value': score_val
                }
            }
        ))
        fig_gauge.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)

        # ตารางแสดงผลแบบสั้น (เหมาะกับมือถือ)
        st.write(f"📋 รายการบันทึกของวันที่ {search_date}")
        display_df = df_filtered.copy().reset_index()
        display_df['No.'] = display_df.index + 1
        st.dataframe(
            display_df[['No.', 'Timestamp', 'Risk_Level', 'Score']], 
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(f"ไม่พบข้อมูลในวันที่ {search_date}")

    # กราฟแท่งสรุปภาพรวมรายวัน
    st.divider()
    st.write("📈 สรุปจำนวนเคสแยกตามระดับความเสี่ยง (รวมทั้งหมด)")
    daily_summary = df_history.groupby(['Date_Only', 'Risk_Level']).size().reset_index(name='Count')
    fig_bar = px.bar(
        daily_summary, x='Date_Only', y='Count', color='Risk_Level',
        color_discrete_map={'RED': '#FF4B4B', 'YELLOW': '#FFA500', 'GREEN': '#28A745'},
        barmode='stack', height=300
    )
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("💡 ยังไม่มีข้อมูลในระบบ เริ่มบันทึกข้อมูลเพื่อแสดง Dashboard")
