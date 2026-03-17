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

# --- 5. ส่วนบันทึกข้อมูลแบบแยก Tab ---
with st.form("triage_form", clear_on_submit=False):
    st.markdown("#### 📝 บันทึกข้อมูลแยกตามหมวดหมู่")
    
    # สร้าง Tabs เพื่อแยกสัดส่วนข้อมูล
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
        st.info("💡 ข้อมูลในส่วนนี้จะถูกนำไปวิเคราะห์ความเสี่ยงสะสมร่วมกับประวัติผู้ป่วย")

    st.markdown("<br>", unsafe_allow_html=True)
    submit_button = st.form_submit_button("🚀 ประเมินความเสี่ยงและบันทึกข้อมูลลงระบบ")

# --- 6. ส่วนแสดงผลลัพธ์ (หลังกดบันทึก) ---
if submit_button:
    if ai_model and case_id != "ENDO-NCI-":
        try:
            input_data = [age, 1 if sex == "ชาย" else 0, size, 1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0,
                          1 if medication == "ใช่" else 0, 1 if surgery == "ใช่" else 0, 1 if radiation == "ใช่" else 0,
                          1 if chemo == "ใช่" else 0, 1 if procedure == "Biopsy Only" else 0, 
                          1 if procedure == "Cold Snare" else 0, 1 if procedure == "Hot Polypectomy" else 0,
                          1 if procedure == "EMR" else 0, 0]
            
            prob = ai_model.predict_proba(np.array([input_data]))[0][1]
            score_percent = prob * 100

            if prob >= 0.40: 
                risk, color, text_color, action = "RED (เสี่ยงสูงมาก)", "#FF4B4B", "white", "🚨 โทรติดตามที่ 24, 48, 72 ชม."
            elif prob >= 0.11: 
                risk, color, text_color, action = "YELLOW (เสี่ยงปานกลาง)", "#FFCC00", "black", "⚠️ โทรติดตามที่ 24, 48 ชม."
            else: 
                risk, color, text_color, action = "GREEN (เสี่ยงต่ำ)", "#28A745", "white", "✅ ให้คู่มือสังเกตอาการตามมาตรฐาน"

            res_col1, res_col2 = st.columns([1.2, 1])
            with res_col1:
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = score_percent,
                    title = {'text': f"Risk Score: {case_id}"},
                    gauge = {
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "black"},
                        'steps': [{'range': [0, 11], 'color': "#28A745"},
                                   {'range': [11, 40], 'color': "#FFCC00"},
                                   {'range': [40, 100], 'color': "#FF4B4B"}]
                    }))
                fig_gauge.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_gauge, use_container_width=True)

            with res_col2:
                st.markdown(f"""
                    <div style='background-color:{color}; padding:25px; border-radius:15px; text-align:center; color:{text_color}; margin-top:40px; border: 2px solid #333;'>
                        <h2 style='margin:0;'>{risk}</h2>
                        <h3 style='margin:10px;'>โอกาสเลือดออก: {score_percent:.2f}%</h3>
                        <p style='font-size: 1.4em; font-weight: bold;'>{action}</p>
                    </div>
                    """, unsafe_allow_html=True)

            new_entry = pd.DataFrame([{
                "Timestamp": datetime.now(bkk_tz).strftime("%Y-%m-%d %H:%M:%S"),
                "Case_ID": case_id, "Age": age, "Sex": sex, "Size": size,
                "loc_right": 1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0, 
                "Medication": medication, "Chemo": chemo,
                "Clip": hemoclip, "Risk_Level": risk.split()[0], "Score": f"{score_percent:.2f}%", "Advice": action
            }])
            conn.update(worksheet="Sheet1", data=pd.concat([df_history, new_entry], ignore_index=True))
            st.toast(f"บันทึกข้อมูลเรียบร้อย")
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.warning("กรุณาระบุรหัสเคสต่อท้าย ENDO-NCI-")

# --- 7. DASHBOARD (ส่วนสรุปผล) ---
st.divider()
if not df_history.empty:
    df_history['Date_Only'] = pd.to_datetime(df_history['Timestamp']).dt.date
    today = datetime.now(bkk_tz).date()
    search_date = st.date_input("📅 ตรวจสอบสถิติย้อนหลัง", today)
    df_filtered = df_history[df_history['Date_Only'] == search_date]
    
    st.markdown(f"#### 📊 สรุปเคสประจำวันที่ {search_date}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("เคสทั้งหมด", f"{len(df_filtered)}")
    c2.markdown(f"<div class='metric-container' style='border-top: 5px solid #28A745;'><b>🟢 GREEN</b><br><span style='font-size:24px;'>{len(df_filtered[df_filtered['Risk_Level'] == 'GREEN'])}</span></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-container' style='border-top: 5px solid #FFCC00;'><b>🟡 YELLOW</b><br><span style='font-size:24px;'>{len(df_filtered[df_filtered['Risk_Level'] == 'YELLOW'])}</span></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='metric-container' style='border-top: 5px solid #FF4B4B;'><b>🔴 RED</b><br><span style='font-size:24px;'>{len(df_filtered[df_filtered['Risk_Level'] == 'RED'])}</span></div>", unsafe_allow_html=True)

    g1, g2 = st.columns(2)
    with g1:
        daily_trend = df_history.groupby(['Date_Only', 'Risk_Level']).size().reset_index(name='Count')
        fig_trend = px.bar(daily_trend, x='Date_Only', y='Count', color='Risk_Level',
                           color_discrete_map={'RED': '#FF4B4B', 'YELLOW': '#FFCC00', 'GREEN': '#28A745'}, barmode='stack', height=350)
        st.plotly_chart(fig_trend, use_container_width=True)
    with g2:
        st.dataframe(df_filtered.reset_index()[['Timestamp', 'Case_ID', 'Risk_Level', 'Score']], use_container_width=True, hide_index=True)
