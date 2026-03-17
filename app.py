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
st.set_page_config(page_title="NCI Bleed Guard AI", page_icon="🛡️", layout="wide")
bkk_tz = pytz.timezone('Asia/Bangkok')

# CSS ตกแต่งปุ่มและ Metric
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; }
    .metric-container { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; text-align: center; }
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

# --- 4. ส่วนหัวแอป (Official Title) ---
st.markdown("<h2 style='text-align: center; color: #004d99;'>🛡️ ระบบคัดกรองความเสี่ยงคนไข้หลังส่องกล้องลำไส้ใหญ่และตัดติ่งเนื้อ</h2>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; color: #004d99;'>(NCI Bleed Guard AI)</h3>", unsafe_allow_html=True)
st.divider()

# --- 5. ส่วนบันทึกและประเมินผล ---
with st.container():
    with st.form("triage_form", clear_on_submit=False):
        st.markdown("#### ➕ บันทึกเคสใหม่")
        col_form1, col_form2 = st.columns(2)
        with col_form1:
            # ค้างคำว่า ENDO-NCI- ไว้ในช่อง Case ID
            case_id = st.text_input("Case_ID (รหัสเคส)", value="ENDO-NCI-")
            age = st.number_input("Age (อายุ)", min_value=1, value=45)
            sex = st.selectbox("Sex (เพศ)", ["หญิง", "ชาย"])
            medication = st.selectbox("Medication (ยาละลายลิ่มเลือด)", ["ไม่ใช่", "ใช่"])
            location = st.selectbox("loc_right (ตำแหน่ง)", ["ลำไส้ใหญ่ฝั่งซ้าย", "ลำไส้ใหญ่ฝั่งขวา"])
        with col_form2:
            procedure = st.selectbox("Procedure (วิธีตัด)", ["Biopsy Only", "Cold Snare", "Hot Polypectomy", "EMR"])
            hemoclip = st.selectbox("Clip (การใช้ Hemoclip)", ["ไม่ใส่", "ใส่"])
            surgery = st.selectbox("Surgery (ประวัติผ่าตัด)", ["ไม่ใช่", "ใช่"])
            radiation = st.selectbox("Radiation (ประวัติฉายแสง)", ["ไม่ใช่", "ใช่"])
            size = st.number_input("Size (ขนาดติ่งเนื้อ cm)", min_value=0.0, step=0.1, value=0.0)
            
        submit_button = st.form_submit_button("🚀 ประเมินความเสี่ยงและบันทึกข้อมูล")

# --- 6. แสดงผลลัพธ์ทันที (เข็ม Risk และแถบสีการปฏิบัติ) ---
if submit_button:
    if ai_model and case_id != "ENDO-NCI-":
        try:
            # 13 Features logic
            input_data = [age, 1 if sex == "ชาย" else 0, size, 1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0,
                          1 if medication == "ใช่" else 0, 1 if surgery == "ใช่" else 0, 1 if radiation == "ใช่" else 0,
                          0, 1 if procedure == "Biopsy Only" else 0, 1 if procedure == "Cold Snare" else 0, 
                          1 if procedure == "Hot Polypectomy" else 0, 1 if procedure == "EMR" else 0, 0]
            
            prob = ai_model.predict_proba(np.array([input_data]))[0][1]
            score_percent = prob * 100

            if prob >= 0.40: risk, color, action = "RED (เสี่ยงสูงมาก)", "#FF4B4B", "🚨 โทรติดตามที่ 24, 48, 72 ชม."
            elif prob >= 0.11: risk, color, action = "YELLOW (เสี่ยงปานกลาง)", "#FFA500", "⚠️ โทรติดตามที่ 24, 48 ชม."
            else: risk, color, action = "GREEN (เสี่ยงต่ำ)", "#28A745", "✅ ให้คู่มือสังเกตอาการตามมาตรฐาน"

            res_col1, res_col2 = st.columns([1.2, 1])
            with res_col1:
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = score_percent,
                    title = {'text': f"Risk Score: {case_id}", 'font': {'size': 20}},
                    gauge = {
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "black"},
                        'steps': [{'range': [0, 11], 'color': "#28A745"},
                                   {'range': [11, 40], 'color': "#FFA500"},
                                   {'range': [40, 100], 'color': "#FF4B4B"}],
                        'threshold': {'line': {'color': "white", 'width': 4}, 'value': score_percent}
                    }))
                fig_gauge.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_gauge, use_container_width=True)

            with res_col2:
                st.markdown(f"""
                    <div style='background-color:{color}; padding:25px; border-radius:15px; text-align:center; color:white; margin-top:40px; border: 2px solid white;'>
                        <h2 style='margin:0;'>{risk}</h2>
                        <h3 style='margin:10px;'>โอกาสเลือดออก: {score_percent:.2f}%</h3>
                        <p style='font-size: 1.4em; font-weight: bold;'>{action}</p>
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
            st.toast(f"บันทึกเคส {case_id} สำเร็จ")
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.warning("กรุณาระบุรหัสเคสต่อท้าย ENDO-NCI-")

# --- 7. DASHBOARD (สรุปผลรายวันและกราฟสถิติ) ---
st.divider()
st.markdown("### 📊 Dashboard สรุปผลการคัดกรอง")

if not df_history.empty:
    df_history['Date_Only'] = pd.to_datetime(df_history['Timestamp']).dt.date
    today = datetime.now(bkk_tz).date()
    
    # ส่วนค้นหาข้อมูลย้อนหลัง
    search_date = st.date_input("📅 เลือกวันที่เพื่อดูสถิติ", today)
    df_filtered = df_history[df_history['Date_Only'] == search_date]
    
    # แสดงช่องแบ่ง เขียว/เหลือง/แดง ในแต่ละวัน
    st.markdown(f"#### 🏥 สรุปเคสประจำวันที่ {search_date}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("รวมทั้งหมด", f"{len(df_filtered)} เคส")
    c2.markdown(f"<div class='metric-container' style='border-top: 5px solid #28A745;'><b>🟢 เสี่ยงต่ำ (GREEN)</b><br><span style='font-size:24px;'>{len(df_filtered[df_filtered['Risk_Level'] == 'GREEN'])}</span></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-container' style='border-top: 5px solid #FFA500;'><b>🟡 ปานกลาง (YELLOW)</b><br><span style='font-size:24px;'>{len(df_filtered[df_filtered['Risk_Level'] == 'YELLOW'])}</span></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='metric-container' style='border-top: 5px solid #FF4B4B;'><b>🔴 เสี่ยงสูง (RED)</b><br><span style='font-size:24px;'>{len(df_filtered[df_filtered['Risk_Level'] == 'RED'])}</span></div>", unsafe_allow_html=True)

    # กราฟสถิติ
    st.markdown("---")
    g1, g2 = st.columns(2)
    with g1:
        st.write("📈 สถิติความเสี่ยงย้อนหลัง")
        daily_trend = df_history.groupby(['Date_Only', 'Risk_Level']).size().reset_index(name='Count')
        fig_trend = px.bar(daily_trend, x='Date_Only', y='Count', color='Risk_Level',
                           color_discrete_map={'RED': '#FF4B4B', 'YELLOW': '#FFA500', 'GREEN': '#28A745'},
                           barmode='stack', height=350)
        st.plotly_chart(fig_trend, use_container_width=True)
    with g2:
        st.write("📋 รายการบันทึกของวัน")
        st.dataframe(df_filtered.reset_index()[['Timestamp', 'Case_ID', 'Risk_Level', 'Score']], use_container_width=True, hide_index=True)
else:
    st.info("ยังไม่มีข้อมูลบันทึกในระบบ")
