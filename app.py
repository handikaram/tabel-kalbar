import streamlit as st
import pandas as pd
import requests
import datetime
import re

# ==========================================
# 1. KONFIGURASI HALAMAN & STATE
# ==========================================
st.set_page_config(page_title="Monitoring Tabel BPS", layout="wide")
API_KEY = st.secrets["BPS_API_KEY"]

if 'df_master' not in st.session_state:
    st.session_state.df_master = pd.DataFrame()

# Inisialisasi Memori Filter Waktu
if 'start_d' not in st.session_state:
    st.session_state.start_d = datetime.date.today()
if 'end_d' not in st.session_state:
    st.session_state.end_d = datetime.date.today()
if 'start_t' not in st.session_state:
    st.session_state.start_t = datetime.time(0, 0)
if 'end_t' not in st.session_state:
    st.session_state.end_t = datetime.time(23, 59)

# Fungsi Tombol Waktu
def set_start_to_today():
    st.session_state.start_d = datetime.date.today()
    st.session_state.start_t = datetime.time(0, 0)

def set_start_to_oldest():
    if not st.session_state.df_master.empty:
        min_date = st.session_state.df_master['last_update'].min()
        if pd.notna(min_date):
            st.session_state.start_d = min_date.date()
            st.session_state.start_t = datetime.time(0, 0)

def set_end_to_today():
    st.session_state.end_d = datetime.date.today()
    st.session_state.end_t = datetime.time(23, 59)

# ==========================================
# 2. FUNGSI PEMROSESAN DATA
# ==========================================
def buat_link_tabel(row):
    tbl_source = str(row.get('tablesource', ''))
    tbl_id = str(row.get('id', ''))
    title = str(row.get('title', ''))
    kode_wil = str(row.get('kode_wilayah', '6100'))
    
    # Kamus pemetaan subdomain wilayah BPS se-Kalimantan Barat
    subdomain_map = {
        '6100': 'kalbar',
        '6101': 'sambaskab',
        '6102': 'bengkayangkab',
        '6103': 'landakkab',
        '6104': 'mempawahkab',
        '6105': 'sanggaukab',
        '6106': 'ketapangkab',
        '6107': 'sintangkab',
        '6108': 'kapuashulukab',
        '6109': 'sekadaukab',
        '6110': 'melawikab',
        '6111': 'kayongutarakab',
        '6112': 'kuburayakab',
        '6171': 'pontianakkota',
        '6172': 'singkawangkota'
    }
    
    # Ambil subdomain sesuai kode wilayah, default ke 'kalbar'
    subdomain = subdomain_map.get(kode_wil, 'kalbar')
    
    title_bersih = re.sub(r'[^a-zA-Z0-9]', '-', title.lower())
    base_url = f"https://{subdomain}.bps.go.id/id/statistics-table/{tbl_source}/{tbl_id}/{title_bersih}.html"
    
    if tbl_source == '3':
        latest_period = row.get('latest_period')
        if pd.notna(latest_period):
            try:
                tahun = int(latest_period)
                return f"{base_url}?year={tahun}"
            except ValueError:
                return base_url
    return base_url

@st.dialog("Tarik Data dari API BPS")
def dialog_tarik_data():
    daftar_wilayah_kalbar = [6100, 6101, 6102, 6103, 6104, 6105, 6106, 6107, 6108, 6109, 6110, 6111, 6112, 6171, 6172]
    
    st.write("Pilih wilayah yang ingin ditarik:")
    wilayah_dipilih = st.multiselect("Daftar Kode Wilayah", daftar_wilayah_kalbar, default=[6100])
    
    if st.button("Mulai Tarik Data", type="primary"):
        if not wilayah_dipilih:
            st.warning("Centang minimal satu wilayah.")
            return
            
        headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
        df_list = []
        progress_bar = st.progress(0)
        
        for idx, kode in enumerate(wilayah_dipilih):
            base_url = f"https://webapi.bps.go.id/v1/api/list/domain/{kode}/model/tablestatistic/page/{{}}/perpage/100/key/{API_KEY}/"
            
            try:
                res = requests.get(base_url.format(1), headers=headers)
                data = res.json()
                total_pages = data["data"][0]["pages"]
            except Exception:
                st.error(f"Gagal membaca metadata {kode}. Lanjut ke wilayah berikutnya.")
                continue

            for page in range(1, total_pages + 1):
                res = requests.get(base_url.format(page), headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    if len(data["data"]) > 1 and isinstance(data["data"][1], list):
                        df_temp = pd.DataFrame(data["data"][1])
                        # Pastikan format kode konsisten agar dictionary map berfungsi
                        df_temp["kode_wilayah"] = str(kode) 
                        df_list.append(df_temp)
                
                total_langkah = len(wilayah_dipilih) * total_pages
                langkah_sekarang = (idx * total_pages) + page
                progress_bar.progress(langkah_sekarang / total_langkah, text=f"Menarik {kode} (Hal {page}/{total_pages})")
        
        if df_list:
            df_new = pd.concat(df_list, ignore_index=True)
            df_new['Link'] = df_new.apply(buat_link_tabel, axis=1)
            df_new['last_update'] = pd.to_datetime(df_new['last_update'], errors='coerce')
            
            if st.session_state.df_master.empty:
                st.session_state.df_master = df_new
            else:
                df_existing = st.session_state.df_master
                df_existing = df_existing[~df_existing['kode_wilayah'].isin([str(w) for w in wilayah_dipilih])]
                st.session_state.df_master = pd.concat([df_existing, df_new], ignore_index=True)
            
            # Otomatis set tanggal ke yang paling tua
            min_date = st.session_state.df_master['last_update'].min()
            if pd.notna(min_date):
                st.session_state.start_d = min_date.date()
                
            st.success("Berhasil ditarik dan diperbarui!")
            st.rerun()

# ==========================================
# 3. SIDEBAR (PANEL KIRI UNTUK FILTER)
# ==========================================
if st.session_state.df_master.empty:
    st.title("📊 Monitoring Tabel se-Kalimantan Barat")
    st.info("Tabel masih kosong. Silakan klik tombol 'Tarik Data' di bawah ini.")
    if st.button("🔄 Tarik Data API (Pilih Wilayah)", type="primary"):
        dialog_tarik_data()
    st.stop()

df = st.session_state.df_master.copy()

with st.sidebar:
    st.title("⚙️ Pengaturan Filter")
    
    st.markdown("### 1. Filter Kategori")
    opsi_wil = sorted(df['kode_wilayah'].unique())
    f_wilayah = st.multiselect("Kode Wilayah", opsi_wil, default=opsi_wil)
    
    opsi_sub = sorted(df['subject'].dropna().unique())
    f_subject = st.multiselect("Subject", opsi_sub)
    
    opsi_subcat = sorted(df['subcat_name'].dropna().unique())
    f_subcat = st.multiselect("Subcat Name", opsi_subcat)
    
    opsi_tbl = sorted(df['tablesource'].dropna().unique())
    f_tbl = st.multiselect("Kode Tabel (tablesource)", opsi_tbl)
    
    st.markdown("---")
    st.markdown("### 2. Pencarian Judul & Waktu")
    f_title = st.text_input("Cari Judul Tabel (Ketik kata...)", placeholder="Misal: penduduk, PDB")
    
    # Filter Mulai
    st.write("**Mulai Dari:**")
    st.date_input("Tanggal Mulai", key="start_d")
    st.time_input("Jam Mulai", key="start_t")
    
    col_oldest, col_today_start = st.columns(2)
    with col_oldest: st.button("⏪ Oldest", on_click=set_start_to_oldest, use_container_width=True, key="btn_start_oldest")
    with col_today_start: st.button("📅 Hari Ini", on_click=set_start_to_today, use_container_width=True, key="btn_start_today")

    st.markdown("")
    
    # Filter Selesai
    st.write("**Sampai Dengan:**")
    st.date_input("Tanggal Selesai", key="end_d")
    st.time_input("Jam Selesai", key="end_t")
    st.button("📅 Hari Ini", on_click=set_end_to_today, use_container_width=True, key="btn_end_today")

# ==========================================
# 4. TERAPKAN FILTER KE DATAFRAME
# ==========================================
df_tampil = df.copy()

if f_wilayah: df_tampil = df_tampil[df_tampil['kode_wilayah'].isin(f_wilayah)]
else: df_tampil = df_tampil.iloc[0:0]

if f_subject: df_tampil = df_tampil[df_tampil['subject'].isin(f_subject)]
if f_subcat: df_tampil = df_tampil[df_tampil['subcat_name'].isin(f_subcat)]
if f_tbl: df_tampil = df_tampil[df_tampil['tablesource'].isin(f_tbl)]

if f_title:
    df_tampil = df_tampil[df_tampil['title'].str.contains(f_title, case=False, na=False)]

start_dt = pd.to_datetime(f"{st.session_state.start_d} {st.session_state.start_t}")
end_dt = pd.to_datetime(f"{st.session_state.end_d} {st.session_state.end_t}")
df_tampil = df_tampil.dropna(subset=['last_update'])
df_tampil = df_tampil[(df_tampil['last_update'] >= start_dt) & (df_tampil['last_update'] <= end_dt)]

# ==========================================
# 5. ANTARMUKA UTAMA (LAYAR KANAN)
# ==========================================
st.title("📊 Monitoring Tabel se-Kalimantan Barat")

col_btn, col_metric = st.columns([1, 4])
with col_btn:
    if st.button("🔄 Tarik / Perbarui Data", type="primary"):
        dialog_tarik_data()
with col_metric:
    st.write(f"<h4 style='margin-top:5px; color:#4a4a4a;'>Total Tabel Ditemukan: {len(df_tampil)} baris</h4>", unsafe_allow_html=True)

with st.expander("🛠️ Pengaturan Tampilan Kolom"):
    semua_kolom = df.columns.tolist()
    kolom_disembunyikan = ['id', 'id_subject', 'subject', 'id_subcat', 'subcat_name']
    kolom_default = [k for k in semua_kolom if k not in kolom_disembunyikan]
    kolom_dipilih = st.multiselect("Pilih Kolom Tabel yang Ditampilkan:", semua_kolom, default=kolom_default)

if kolom_dipilih:
    df_tampil = df_tampil[kolom_dipilih]
else:
    df_tampil = pd.DataFrame()

st.dataframe(
    df_tampil,
    column_config={
        "Link": st.column_config.LinkColumn("Akses Tabel", display_text="Buka Tautan"),
        "title": st.column_config.TextColumn("Judul Tabel"),
        "oldest_period": st.column_config.TextColumn("Tahun Awal"),
        "latest_period": st.column_config.TextColumn("Tahun Terakhir"),
        "kode_wilayah": st.column_config.TextColumn("Kode Wilayah"),
        "last_update": st.column_config.DatetimeColumn("Terakhir Diperbarui", format="YYYY-MM-DD HH:mm:ss"),
        "tablesource": st.column_config.NumberColumn(
            "Kode Tabel", 
            help="1 = Tabel Statis, 2 = Tabel Dinamis, 3 = Tabel SIMDASI",
            format="%d"
        )
    },
    width="stretch",
    hide_index=True
)