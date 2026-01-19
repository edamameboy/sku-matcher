import streamlit as st
import pandas as pd
from thefuzz import fuzz
import re
from io import BytesIO

# --- KONFIGURASI DATABASE ---
SHEET_ID = "18CGqEdAxexoCNNFBJ9v3xgQBNm7h8ph7-phzz0jo1uA"
CONFIG = {
    "Lantai 2": {"gid": "0"},
    "Lantai 3": {"gid": "1940332847"},
    "Lantai 4": {"gid": "1016834167"}
}

def extract_number(text):
    match = re.search(r'#(\d+)', str(text))
    return match.group(1) if match else None

def check_special_keywords(str1, str2):
    keywords = ['glow', 'flocked', 'chase', 'metallic', 'exclusive', 'special edition', 'diamond', 'se']
    str1_l, str2_l = str(str1).lower(), str(str2).lower()
    for word in keywords:
        if (word in str1_l) != (word in str2_l): return False
    return True

@st.cache_data(ttl=3600)
def load_full_database():
    all_data = []
    for name, info in CONFIG.items():
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={info['gid']}"
        try:
            df = pd.read_csv(url, on_bad_lines='skip')
            df.columns = [str(c).strip() for c in df.columns]
            col_sku = next((c for c in df.columns if 'SKU' in c.upper()), None)
            col_nama = next((c for c in df.columns if 'NAMA' in c.upper() or 'PRODUCT' in c.upper()), None)
            if col_sku and col_nama:
                temp = df[[col_sku, col_nama]].copy()
                temp.columns = ['SKU', 'Nama Master']
                all_data.append(temp.dropna())
        except: continue
    return pd.concat(all_data, ignore_index=True).drop_duplicates() if all_data else pd.DataFrame()

# --- UI ---
st.set_page_config(page_title="Funko Matcher Pro (Debug Mode)", layout="wide")
st.title("🚀 Funko Bulk Matcher - Double Check Mode")

df_master = load_full_database()
st.sidebar.info(f"Database: {len(df_master)} SKU")

# Threshold minimal 30%
threshold = st.sidebar.slider("Akurasi Matching (%)", 30, 100, 70)

file_input = st.file_uploader("Upload Master Kelola TikTok (.xlsx)", type=['xlsx'])

if file_input:
    df_input = pd.read_excel(file_input)
    col_nama = df_input.columns[0]
    col_sku = df_input.columns[1]

    if st.button(f"Proses {len(df_input)} Data dengan Double Check"):
        sku_results = []
        score_results = []
        status_results = []
        
        progress_bar = st.progress(0)
        master_list = df_master.to_dict('records')
        total = len(df_input)

        with st.spinner('Mencocokkan data...'):
            for i, row in df_input.iterrows():
                p_name = str(row[col_nama]) if not pd.isna(row[col_nama]) else ""
                input_num = extract_number(p_name)
                
                best_sku, top_score = "", 0
                
                if len(p_name) > 3:
                    for m in master_list:
                        m_name, m_sku = str(m['Nama Master']), str(m['SKU'])
                        if input_num and extract_number(m_name) != input_num: continue
                        if not check_special_keywords(p_name, m_name): continue
                        
                        score = fuzz.token_sort_ratio(p_name, m_name)
                        if score > top_score and score >= threshold:
                            top_score, best_sku = score, m_sku
                            if score == 100: break 

                sku_results.append(best_sku)
                score_results.append(top_score)
                
                # Tentukan Status
                if top_score == 100: status = "PERFECT"
                elif top_score >= 80: status = "HIGH"
                elif top_score >= threshold: status = "LOW MATCH (Check!)"
                else: status = "NOT FOUND"
                status_results.append(status)
                
                if i % 100 == 0: progress_bar.progress((i + 1) / total)

        # Tambahkan kolom Double Check
        df_input[col_sku] = sku_results
        df_input['Match Score'] = score_results
        df_input['Match Status'] = status_results

        st.success("Proses Selesai!")
        
        # Tampilkan ringkasan audit
        st.dataframe(df_input[[col_nama, col_sku, 'Match Score', 'Match Status']].head(50))

        # EXPORT XLSX DENGAN FORMATTING
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_input.to_excel(writer, index=False, sheet_name='Master_Reference')
            workbook = writer.book
            worksheet = writer.sheets['Master_Reference']
            
            # Format warna
            red = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'}) # Skor rendah
            green = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'}) # Skor tinggi
            yellow = workbook.add_format({'bg_color': '#FFFF00'}) # Duplikat

            # Warnai baris berdasarkan skor di kolom Match Score (Asumsi kolom C)
            worksheet.conditional_format(1, 2, len(df_input), 2, {
                'type': 'cell', 'criteria': '<', 'value': 60, 'format': red
            })
            worksheet.conditional_format(1, 2, len(df_input), 2, {
                'type': 'cell', 'criteria': '>=', 'value': 90, 'format': green
            })

        st.download_button("📥 Download Hasil (Double Check Mode)", output.getvalue(), 
                           "Master_Reference_DoubleCheck.xlsx", 
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
