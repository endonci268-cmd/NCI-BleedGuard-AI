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

# --- 2. โหลดโมเดล AI (1,250 เคส) ---
@st.cache_resource
def load_bleed_model():
    try: return joblib.load("bleedguard_model.pkl")
    except: return None

ai_model = load_bleed_model()

# --- 3. การเชื่อมต่อ Google Sheets ---
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

# --- 6. ส่วนประมวลผล (AI + Clinical Override + Data Storage) ---
if submit_button:
    if ai_model and case_id != "ENDO-NCI-":
        try:
            # 1. AI คำนวณเบื้องต้น
            input_data = [age, 1 if sex == "ชาย" else 0, size, 1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0,
                          1 if medication == "ใช่" else 0, 1 if surgery == "ใช่" else 0, 1 if radiation == "ใช่" else 0,
                          1 if chemo == "ใช่" else 0, 1 if procedure == "Biopsy Only" else 0, 
                          1 if procedure == "Cold Snare" else 0, 1 if procedure == "Hot Polypectomy" else 0,
                          1 if procedure == "EMR" else 0, 0]
            
            prob = ai_model.predict_proba(np.array([input_data]))[0][1]
            score_percent = prob * 100

            # 2. Clinical Override & Score Alignment
            if procedure == "EMR" or (medication == "ใช่" and hemoclip == "ใส่") or radiation == "ใช่":
                risk, color, text_color, action = "RED", "#FF4B4B", "white", "🚨 โทรติดตามที่ 24, 48, 72 ชม. (High Risk Override)"
                if score_percent < 85: score_percent = 85.0
            elif hemoclip == "ใส่" or size >= 2.0:
                risk, color, text_color, action = "YELLOW", "#FFCC00", "black", "⚠️ โทรติดตามที่ 24, 48 ชม. (Monitoring Required)"
                if score_percent < 35: score_percent = 35.0
            elif prob >= 0.40: 
                risk, color, text_color, action = "RED", "#FF4B4B", "white", "🚨 โทรติดตามที่ 24, 48, 72 ชม."
            elif prob >= 0.11: 
                risk, color, text_color, action = "YELLOW", "#FFCC00", "black", "⚠️ โทรติดตามที่ 24, 48 ชม."
            else: 
                risk, color, text_color, action = "GREEN", "#28A745", "white", "✅ ให้คู่มือสังเกตอาการตามมาตรฐาน"

            # แสดงผล Gauge
            res_col1, res_col2 = st.columns([1.2, 1])
            with res_col1:
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = score_percent,
                    number = {'suffix': "%"},
                    title = {'text': f"Risk Score: {case_id}"},
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
                st.plotly_chart(fig_gauge, use_container_width=True)

            with res_col2:
                st.markdown(f"""
                    <div style='background-color:{color}; padding:25px; border-radius:15px; text-align:center; color:{text_color}; margin-top:40px; border: 2px solid #333;'>
                        <h2 style='margin:0;'>{risk}</h2>
                        <h3 style='margin:10px;'>ความเสี่ยงเชิงคลินิก: {score_percent:.2f}%</h3>
                        <p style='font-size: 1.2em; font-weight: bold;'>{action}</p>
                    </div>""", unsafe_allow_html=True)

            # 3. เตรียมข้อมูลบันทึกลง Google Sheets (ใส่ให้ครบทุกช่อง!)
            new_entry = pd.DataFrame([{
                "Timestamp": datetime.now(bkk_tz).strftime("%Y-%m-%d %H:%M:%S"),
                "Case_ID": case_id,
                "Age": age,
                "Sex": sex,
                "Size": size,
                "loc_right": 1 if location == "ลำไส้ใหญ่ฝั่งขวา" else 0, 
                "Medication": medication,
                "Surgery": surgery,     # ช่อง Surgery
                "Radiation": radiation, # ช่อง Radiation
                "Chemo": chemo,         # ช่อง Chemo
                "Clip": hemoclip,
                "BX": 1 if procedure == "Biopsy Only" else 0,
                "Cold_Poly": 1 if procedure == "Cold Snare" else 0,
                "Hot_Poly": 1 if procedure == "Hot Polypectomy" else 0,
                "EMR": 1 if procedure == "EMR" else 0,
                "Risk_Level": risk, 
                "Score": f"{score_percent:.2f}%", 
                "Advice": action
            }])
            
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(worksheet="Sheet1", data=pd.concat([df_history, new_entry], ignore_index=True))
            st.toast(f"✅ บันทึกข้อมูลเรียบร้อย ครบทุกช่องทาง")
            
            if st.button("🔄 บันทึกสำเร็จ! คลิกเพื่อรับเคสถัดไป"):
                st.rerun()

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
    else:
        st.warning("⚠️ กรุณาระบุรหัสเคสให้ครบถ้วน")

# --- 7. DASHBOARD ---
st.divider()
if not df_history.empty:
    df_history['Timestamp'] = pd.to_datetime(df_history['Timestamp'], errors='coerce')
    df_history['Date_Only'] = df_history['Timestamp'].dt.date
    today = datetime.now(bkk_tz).date()
    
    search_date = st.date_input("📅 ตรวจสอบสถิติรายวัน", today)
    df_filtered = df_history[df_history['Date_Only'] == search_date]
    
    st.markdown(f"#### 📊 สรุปเคสประจำวันที่ {search_date}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("เคสทั้งหมด", f"{len(df_filtered)}")
    c2.metric("🟢 ปกติ", len(df_filtered[df_filtered['Risk_Level'] == 'GREEN']))
    c3.metric("🟡 เสี่ยงปานกลาง", len(df_filtered[df_filtered['Risk_Level'] == 'YELLOW']))
    c4.metric("🔴 เสี่ยงสูง", len(df_filtered[df_filtered['Risk_Level'] == 'RED']))

    st.write("📋 ประวัติการประเมิน 10 เคสล่าสุด")
    show_cols = ['Timestamp', 'Case_ID', 'Risk_Level', 'Score', 'Advice']
    styled_df = df_filtered.sort_values('Timestamp', ascending=False).head(10)[show_cols]
    st.dataframe(
        styled_df.style.map(highlight_risk, subset=['Risk_Level']), 
        use_container_width=True, hide_index=True
    )
else:
    st.info("💡 ระบบพร้อมทำงาน... เริ่มบันทึกข้อมูลเคสแรกได้เลยครับ")
