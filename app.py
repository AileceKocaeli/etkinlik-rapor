import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import re
from datetime import datetime
from io import BytesIO
from weasyprint import HTML, CSS # PDF oluşturma kütüphaneleri

# -----------------------------------------------------
# 1. Sabit Tanımlamalar ve Ayarlar
# -----------------------------------------------------

st.set_page_config(page_title="Dinamik Raporlama Sistemi", layout="wide")

SPREADSHEET_ID = st.secrets["sheets_id"]
WORKSHEET_NAME = "Form Yanıtları 1" 
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
OPEN_ENDED_COLUMNS = ['F', 'G', 'J']

# Grafik Sütunları: Düzgün Sayfalama için 3 ve 2 olarak ayrıldı.
GRAPH_COLUMNS_PAGE_2 = {
    'D': 'Etkinlik Süresinin Yeterliliği',
    'E': 'Etkinlikte Kullanılan Yöntem ve Tekniklerin Uygunluğu',
    'H': 'Etkinlikten Yararlanma Düzeyiniz',
}
GRAPH_COLUMNS_PAGE_3 = {
    'I': 'Etkinliğin Beklentilerinizi Karşılama Düzeyi',
    'J': 'Etkinlik Mekanının/Ortamının Uygunluğu'
}

# -----------------------------------------------------
# 2. Yardımcı Fonksiyonlar
# -----------------------------------------------------

@st.cache_data(ttl=3600) 
def load_data():
    # ... (Veri çekme kodu önceki mesajdaki gibi aynı kalmıştır) ...
    # Kodu burada tekrar etmiyoruz, mevcut app.py dosyanızdaki haliyle çalıştığını varsayıyoruz.
    try:
        creds_json = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
        gc = gspread.authorize(creds)
        worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        st.success(f"Veri başarıyla çekildi! Toplam {len(df)} yanıt bulundu.")
        return df

    except Exception as e:
        st.error(f"Veri çekilirken hata: {e}")
        return pd.DataFrame()

def extract_title(raw_header):
    match = re.search(r'\[(.*?)\]', raw_header)
    if match: return match.group(1).strip()
    return raw_header

# PDF OLUŞTURMA FONKSİYONU
def create_pdf_report(html_content):
    """HTML içeriğini WeasyPrint ile PDF'e çevirir."""
    # WeasyPrint, A4 sayfalamasını ve temel CSS'i yönetecektir.
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes

# -----------------------------------------------------
# 3. Uygulama Ana Akışı ve Arayüz
# -----------------------------------------------------

raw_df = load_data()
st.title("📊 Dinamik Etkinlik Raporlama Sistemi")

if raw_df.empty: st.stop() 

# Veri ön işleme
df = raw_df.copy()
timestamp_col = df.columns[0]
event_type_col = df.columns[11] 

if pd.api.types.is_string_dtype(df[timestamp_col]):
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors='coerce', dayfirst=True)

formatted_columns = {col: extract_title(col) for col in df.columns}

# --- Filtreleme Arayüzü ---
with st.sidebar:
    st.header("🔍 Rapor Filtreleri")
    
    unique_events = df[event_type_col].dropna().unique().tolist()
    event_options = ["Tüm Kayıtlar"] + unique_events
    selected_event = st.selectbox("Etkinlik Türü Seçin", options=event_options, index=0)
    
    if pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
        all_dates = df[timestamp_col].dt.normalize().dropna().unique()
        all_dates_list = pd.to_datetime(all_dates).tolist()
        date_options = ["Tüm Dönemler"] + sorted(all_dates_list, reverse=True)
        selected_date = st.selectbox("Tarih Seçin", options=date_options, index=0, format_func=lambda x: x.strftime('%d/%m/%Y') if isinstance(x, pd.Timestamp) else x)
    else:
        selected_date = "Tüm Dönemler"

    st.markdown("---")
    
    # Rapor Tetikleme ve İndirme Butonu için oturum durumu
    generate_report = st.button("🚀 Rapor Oluştur")

# --- Oturum Durumunu Yönetme ---
if generate_report:
    st.session_state['report_generated'] = True
    st.session_state['selected_event'] = selected_event
    st.session_state['selected_date'] = selected_date

if 'report_generated' not in st.session_state:
    st.session_state['report_generated'] = False

# ----------------------------------------
# 4. Filtreleme ve Raporlama Mantığı
# ----------------------------------------

if st.session_state['report_generated']:
    selected_event = st.session_state['selected_event']
    selected_date = st.session_state['selected_date']

    filtered_df = df.copy()

    if selected_event != "Tüm Kayıtlar":
        filtered_df = filtered_df[filtered_df[event_type_col] == selected_event]

    if selected_date != "Tüm Dönemler":
        date_to_filter = selected_date.normalize()
        filtered_df = filtered_df[filtered_df[timestamp_col].dt.normalize() == date_to_filter]
        
    # PDF ve Ekran çıktısı için HTML yapısını tutan değişken
    report_html = "" 
    
    st.subheader(f"✅ Rapor Hazır")
    
    # Kriter özeti
    criteria_summary = f"Etkinlik: **{selected_event}** | Tarih: **{selected_date.strftime('%d/%m/%Y') if selected_date != 'Tüm Dönemler' else 'Tüm Dönemler'}** | Toplam Yanıt: **{len(filtered_df)}**"
    st.info(criteria_summary)
    
    # --- PDF İndirme Düğmesi (Modern Konum) ---
    if not filtered_df.empty:
        
        # Grafik/Veri oluşturma (HTML içeriği de dahil)
        
        # 4.1. Kapak Sayfası (Sayfa 1)
        report_html += f"""
        <div style="text-align: center; height: 100vh; display: flex; flex-direction: column; justify-content: center; page-break-after: always;">
            <h1 style="color: #4CAF50; font-size: 36px;">DİNAMİK ETKİNLİK RAPORU</h1>
            <h2 style="color: #333;">{datetime.now().strftime('%d %B %Y')}</h2>
            <hr style="width: 50%; margin: 20px auto;">
            <p style="font-size: 18px; line-height: 1.8;">
                <strong>Kriterler:</strong> {criteria_summary.replace('**', '')} <br>
                <strong>Hazırlayan:</strong> Otomatik Raporlama Sistemi <br>
            </p>
        </div>
        """
        st.subheader("Veri Grafikleri")
        
        # --- Sayfa 2 ve 3 Grafikler ---
        all_graphs = {**GRAPH_COLUMNS_PAGE_2, **GRAPH_COLUMNS_PAGE_3}
        
        graph_counter = 0
        current_page = 2
        
        # HTML yapısında sayfa sonlarını yönetmek için
        graph_html_container = "" 
        
        for col_name, title in all_graphs.items():
            graph_counter += 1
            
            try:
                actual_title = formatted_columns.get(col_name, title)
                rating_counts = filtered_df[col_name].value_counts(normalize=True).mul(100).rename('Yüzde').reset_index()
                rating_counts.columns = ['Derecelendirme', 'Yüzde']
                rating_counts['Derecelendirme'] = pd.to_numeric(rating_counts['Derecelendirme'], errors='coerce')
                rating_counts = rating_counts.sort_values(by='Derecelendirme')
                
                # Grafik oluşturma (Streamlit için)
                fig = px.bar(rating_counts, x='Derecelendirme', y='Yüzde', 
                             title=f"**{actual_title}** (Toplam Yanıt: {len(filtered_df)})", text='Yüzde', 
                             color='Derecelendirme')
                fig.update_traces(texttemplate='%{y:.1f}%', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
                
                # PDF için grafiği HTML'e çevirme
                graph_html_container += f"""
                <div style="height: 300px; margin-bottom: 20px;">
                    <h3>{actual_title}</h3>
                    {fig.to_html(full_html=False, include_plotlyjs='cdn')}
                </div>
                """
                
                # Sayfa sonu mantığı
                if graph_counter == 3:
                    # Sayfa 2 bitti, Sayfa 3'e geç
                    report_html += f"<div style='page-break-after: always;'>{graph_html_container}</div>"
                    graph_html_container = ""
                    current_page = 3
                elif graph_counter == 5:
                    # Sayfa 3 bitti, Açık Uçlulara geçiş öncesi (Sayfa 4)
                    report_html += f"<div>{graph_html_container}</div>"
                    current_page = 4
                    
            except Exception as e:
                st.warning(f"Grafik oluşturulurken hata: {col_name} -> {e}")

        # --- Sayfa 4+ Açık Uçlu Yanıtlar ---
        report_html += f"<h2 style='page-break-before: always;'>Açık Uçlu Yanıtlar</h2>"
        for col_name in OPEN_ENDED_COLUMNS:
            try:
                question_title = formatted_columns.get(col_name, f"{col_name} Sütunu")
                st.subheader(f"💬 {question_title}")
                
                open_ended_answers = filtered_df[col_name].dropna().reset_index(drop=True)
                
                # Ekran Çıktısı (Streamlit)
                if not open_ended_answers.empty:
                    for i, answer in open_ended_answers.items():
                        st.text_area(f"Yanıt {i+1}", value=answer, height=70, disabled=True)
                        
                    # PDF Çıktısı (HTML)
                    report_html += f"""
                    <h3>{question_title}</h3>
                    <ul style="list-style-type: none; padding-left: 0;">
                    """
                    for answer in open_ended_answers:
                        report_html += f"<li style='margin-bottom: 10px; border-left: 3px solid #ccc; padding-left: 10px;'>{answer}</li>"
                    report_html += f"</ul>"
                    
                else:
                    st.info(f"Bu soru için yanıt bulunamadı.")
            except Exception as e:
                st.error(f"Açık Uçlu Rapor oluşturulurken hata: {e}")

        # --- PDF İndirme Butonu ---
        pdf_data = create_pdf_report(report_html)
        
        st.markdown("---")
        st.download_button(
            label="⬇️ Raporu PDF Olarak İndir",
            data=pdf_data,
            file_name=f"Etkinlik_Raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf"
        )

# ----------------------------------------
# Başlangıç Durumu
# ----------------------------------------
else:
    st.info("Lütfen sol menüden filtreleme kriterlerini seçin ve '🚀 Rapor Oluştur' butonuna tıklayın.")