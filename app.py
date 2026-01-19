import streamlit as st
import pandas as pd
from thefuzz import fuzz
import re
from io import BytesIO

# --- KONFIGURASI ---
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
                temp.columns = ['SKU', 'Nama']
                all_data.append(temp.dropna())
        except: continue
    return pd.concat(all_data, ignore_index=True).drop_duplicates() if all_data else pd.DataFrame()

# --- UI ---
st.set_page_config(page_title="Funko Bulk Matcher", layout="wide")
st.title("🚀 Funko Bulk Data Processor")
st.write("Optimasi untuk 5.000+ data dengan threshold fleksibel.")

df_master = load_full_database()
st.sidebar.info(f"Database: {len(df_master)} SKU")

# Set threshold minimal 30% sesuai permintaan
threshold = st.sidebar.slider("Akurasi Matching (%)", 30, 100, 70)

file_input = st.file_uploader("Upload Master Kelola TikTok (.xlsx)", type=['xlsx'])

if file_input:
    df_input = pd.read_excel(file_input)
    col_nama = df_input.columns[0]
    col_sku = df_input.columns[1]

    if st.button(f"Proses {len(df_input)} Baris Data"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Optimasi: Convert master ke list of dict untuk iterasi cepat
        master_list = df_master.to_dict('records')
        total = len(df_input)

        with st.spinner('Sedang mencocokkan data... Mohon tunggu.'):
            for i, row in df_input.iterrows():
                p_name = str(row[col_nama]) if not pd.isna(row[col_nama]) else ""
                input_num = extract_number(p_name)
                
                best_sku, top_score = "", 0
                
                if len(p_name) > 3:
                    for m in master_list:
                        m_name, m_sku = str(m['Nama']), str(m['SKU'])
                        
                        # Filter Nomor Seri (Sangat penting meski threshold rendah)
                        if input_num and extract_number(m_name) != input_num: continue
                        
                        # Cek Keyword Spesifik
                        if not check_special_keywords(p_name, m_name): continue
                        
                        score = fuzz.token_sort_ratio(p_name, m_name)
                        if score > top_score and score >= threshold:
                            top_score, best_sku = score, m_sku
                            if score == 100: break # Optimasi: Jika perfect match, berhenti cari
                
                results.append(best_sku)
                
                # Update progress setiap 50 baris agar tidak lambat
                if i % 50 == 0 or i == total - 1:
                    progress_bar.progress((i + 1) / total)
                    status_text.text(f"Memproses baris ke-{i+1} dari {total}...")

        df_input[col_sku] = results
        st.success("Proses Selesai!")

        # Analisis Sederhana
        match_rate = (len(df_input[df_input[col_sku] != ""]) / total) * 100
        st.metric("Success Rate", f"{match_rate:.1f}%")

        # Export ke Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_input.to_excel(writer, index=False, sheet_name='Master_Reference')
            workbook = writer.book
            worksheet = writer.sheets['Master_Reference']
            yellow = workbook.add_format({'bg_color': '#FFFF00'})
            col_idx = df_input.columns.get_loc(col_sku)
            worksheet.conditional_format(1, col_idx, len(df_input), col_idx, {'type': 'duplicate', 'format': yellow})

        st.download_button("📥 Download Hasil Referensi", output.getvalue(), 
                           "Master_Reference_Output.xlsx", 
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")