import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import re
from datetime import datetime
from weasyprint import HTML # PDF oluşturma kütüphanesi
from io import BytesIO

# -----------------------------------------------------
# 1. Sabit Tanımlamalar ve Ayarlar
# -----------------------------------------------------

st.set_page_config(page_title="Dinamik Etkinlik Raporlama", layout="wide")

# Sheets Bağlantı Bilgileri
SPREADSHEET_ID = st.secrets.get("sheets_id")
WORKSHEET_NAME = "Form Yanıtları 1" 
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Not: Sütun isimleri, Sheets dosyanızın ilk satırındaki (header) tam metin olmalıdır.
# Aşağıdaki başlıklar, [köşeli parantez içindeki] harflerin bulunduğu tam metin olarak varsayılmıştır.

# Açık Uçlu Sütunlar (Örnek başlıklar, lütfen kendi başlıklarınızla değiştirin!)
OPEN_ENDED_COLUMNS = [
    'Soru 1 [F]', 
    'Soru 2 [G]', 
    'Etkinlik Mekanının/Ortamının uygunluğu [J]' # J hem derecelendirme hem açık uçlu soru varsayımıyla eklenmiştir
]

# Grafik Sütunları: Düzgün Sayfalama için 3 ve 2 olarak ayrıldı.
GRAPH_COLUMNS_PAGE_2 = {
    'Etkinlik Süresinin Yeterliliği [D]': 'Etkinlik Süresinin Yeterliliği',
    'Etkinlikte kullanılan yöntem ve tekniklerin uygunluğu [E]': 'Etkinlikte Kullanılan Yöntem ve Teknikler',
    'Etkinlikten yararlanma düzeyiniz [H]': 'Etkinlikten Yararlanma Düzeyi',
}
GRAPH_COLUMNS_PAGE_3 = {
    'Etkinliğin beklentilerinizi karşılama düzeyi [I]': 'Etkinliğin Beklentileri Karşılama Düzeyi',
    'Etkinlik Mekanının/Ortamının uygunluğu [J]': 'Etkinlik Mekanının/Ortamının Uygunluğu'
}

# -----------------------------------------------------
# 2. Yardımcı Fonksiyonlar
# -----------------------------------------------------

@st.cache_data(ttl=3600) 
def load_data():
    """Google Sheets verisini çeker ve DataFrame olarak döndürür."""
    if not SPREADSHEET_ID:
        st.error("Sheets ID bulunamadı. Lütfen secrets.toml dosyasını kontrol edin.")
        return pd.DataFrame()
    
    st.info("Google Sheets verisi çekiliyor...")
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
        st.error(f"Veri çekilirken kritik bir hata oluştu: {e}")
        return pd.DataFrame()

def extract_title(raw_header):
    """Köşeli parantez içindeki metni çeker, yoksa başlığın kendisini döndürür."""
    match = re.search(r'\[(.*?)\]', raw_header)
    if match: return match.group(1).strip()
    return raw_header

# PDF OLUŞTURMA FONKSİYONU
def create_pdf_report(html_content):
    """HTML içeriğini WeasyPrint ile PDF'e çevirir."""
    # BytesIO kullanarak bellek üzerinde işlem yapma
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes

# -----------------------------------------------------
# 3. Uygulama Ana Akışı ve Arayüz
# -----------------------------------------------------

raw_df = load_data()
st.title("📊 Dinamik Etkinlik Raporlama Sistemi")

if raw_df.empty: st.stop() 

# Veri ön işleme ve sütun tanımlama
df = raw_df.copy()
timestamp_col = df.columns[0] # A Sütunu
event_type_col = df.columns[11] # L Sütunu

# Tarih formatına dönüştürme
if pd.api.types.is_string_dtype(df[timestamp_col]):
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors='coerce', dayfirst=True)

# Soru Başlıklarını Formatlama
formatted_columns = {col: extract_title(col) for col in df.columns}

# ----------------------------------------
# Arayüz Filtreleme (Sidebar)
# ----------------------------------------
with st.sidebar:
    st.header("🔍 Rapor Filtreleri")
    
    # 1. Etkinlik Türü Filtresi (L Sütunu)
    unique_events = df[event_type_col].dropna().unique().tolist()
    event_options = ["Tüm Kayıtlar"] + unique_events
    selected_event = st.selectbox("1. Etkinlik Türü Seçin", options=event_options, index=0)
    st.markdown("---")

    # 2. Dinamik Tarih Filtresi (A Sütunu) - Etkinlik Türüne Bağlı
    filtered_dates_df = df.copy()
    if selected_event != "Tüm Kayıtlar":
        filtered_dates_df = filtered_dates_df[filtered_dates_df[event_type_col] == selected_event]
        
    if pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
        # Tekrarlanan gün/ay/yıl kayıtlarını kaldırma (Benzersiz Tarihler)
        all_dates = filtered_dates_df[timestamp_col].dt.normalize().dropna().unique()
        all_dates_list = pd.to_datetime(all_dates).tolist()
        
        # Seçenekleri büyükten küçüğe sırala
        date_options = ["Tüm Dönemler"] + sorted(all_dates_list, reverse=True)
        
        selected_date = st.selectbox(
            "2. Tarih Seçin", 
            options=date_options, 
            index=0, 
            format_func=lambda x: x.strftime('%d/%m/%Y') if isinstance(x, pd.Timestamp) else x
        )
    else:
        st.warning(f"'{timestamp_col}' sütunu geçerli tarih formatında değil.")
        selected_date = "Tüm Dönemler"

    st.markdown("---")
    
    generate_report = st.button("🚀 Rapor Oluştur")

# --- Oturum Durumunu Yönetme ---
if generate_report:
    # Filtre değerlerini oturum durumuna kaydet
    st.session_state['report_generated'] = True
    st.session_state['selected_event'] = selected_event
    st.session_state['selected_date'] = selected_date
    st.session_state['filtered_df'] = None # Önceki filtreyi temizle

if 'report_generated' not in st.session_state:
    st.session_state['report_generated'] = False
    
# ----------------------------------------
# 4. Filtreleme ve Raporlama Mantığı
# ----------------------------------------

if st.session_state['report_generated']:
    selected_event = st.session_state['selected_event']
    selected_date = st.session_state['selected_date']

    # Filtreleme İşlemi (Sadece buton tetiklendiğinde çalışır)
    filtered_df = df.copy()

    if selected_event != "Tüm Kayıtlar":
        filtered_df = filtered_df[filtered_df[event_type_col] == selected_event]

    if selected_date != "Tüm Dönemler":
        date_to_filter = selected_date.normalize()
        filtered_df = filtered_df[filtered_df[timestamp_col].dt.normalize() == date_to_filter]
        
    # Başarılı Filtreleme Özeti
    criteria_summary = f"Etkinlik: **{selected_event}** | Tarih: **{selected_date.strftime('%d/%m/%Y') if selected_date != 'Tüm Dönemler' else 'Tüm Dönemler'}** | Toplam Yanıt: **{len(filtered_df)}**"
    st.subheader("✅ Rapor Hazır")
    st.info(criteria_summary)

    if filtered_df.empty:
        st.warning("Seçilen kriterlere uygun yanıt bulunamadı.")
    else:
        # PDF ve Ekran çıktısı için HTML yapısını tutan değişken
        report_html = "" 
        
        # ----------------------------------------
        # PDF Kapak Sayfası (Sayfa 1)
        # ----------------------------------------
        report_html += f"""
        <div style="text-align: center; height: 100vh; display: flex; flex-direction: column; justify-content: center; page-break-after: always;">
            <h1 style="color: #4CAF50; font-size: 36px;">DİNAMİK ETKİNLİK RAPORU</h1>
            <h2 style="color: #333;">{datetime.now().strftime('%d %B %Y')}</h2>
            <hr style="width: 50%; margin: 20px auto;">
            <p style="font-size: 18px; line-height: 1.8;">
                <strong>Kriterler:</strong> {criteria_summary.replace('**', '').replace('|', '<br>')} <br>
                <strong>Hazırlayan:</strong> Otomatik Raporlama Sistemi <br>
            </p>
        </div>
        """
        
        # ----------------------------------------
        # Grafik Oluşturma Döngüsü (Sayfa 2 ve 3)
        # ----------------------------------------
        
        all_graphs = {**GRAPH_COLUMNS_PAGE_2, **GRAPH_COLUMNS_PAGE_3}
        graph_counter = 0
        graph_html_container = "" 
        
        st.subheader("Grafik ve Özet Rapor")

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
                # Plotly HTML çıktısı embed edilir.
                graph_html_container += f"""
                <div style="height: 350px; margin-bottom: 20px;">
                    <h3 style="text-align: center;">{actual_title}</h3>
                    {fig.to_html(full_html=False, include_plotlyjs='cdn')}
                </div>
                """
                
                # Sayfa sonu mantığı: Sayfa 2 (3 grafik) ve Sayfa 3 (2 grafik)
                if graph_counter == 3:
                    report_html += f"<div style='page-break-after: always;'>{graph_html_container}</div>"
                    graph_html_container = ""
                elif graph_counter == 5:
                    report_html += f"<div>{graph_html_container}</div>"
                    
            except KeyError:
                st.warning(f"Grafik oluşturulurken hata: '{col_name}' sütunu veri setinde bulunamadı. Lütfen app.py'deki sabitleri Sheets'ten gelen tam metinlerle güncelleyin.")
            except Exception as e:
                st.error(f"Grafik oluşturulurken genel hata: {e}")
                
        # ----------------------------------------
        # Açık Uçlu Yanıtlar (Sayfa 4+)
        # ----------------------------------------
        
        st.subheader("Açık Uçlu Yanıtlar")
        
        report_html += f"<h2 style='page-break-before: always; text-align: center; color: #007bff;'>Açık Uçlu Yanıtlar</h2>"
        
        for col_name in OPEN_ENDED_COLUMNS:
            try:
                question_title = formatted_columns.get(col_name, f"{col_name} Sütunu")
                
                st.markdown(f"**💬 {question_title}**")
                
                open_ended_answers = filtered_df[col_name].dropna().reset_index(drop=True)
                
                # Ekran Çıktısı (Streamlit)
                if not open_ended_answers.empty:
                    # En fazla 10 yanıtı ekranda göster, diğerlerini PDF'te
                    for i, answer in open_ended_answers.head(10).items():
                        st.markdown(f"> *{answer}*")
                    
                    if len(open_ended_answers) > 10:
                        st.caption(f"Ve {len(open_ended_answers) - 10} adet daha fazla yanıt (PDF'te yer alacaktır).")
                        
                    # PDF Çıktısı (HTML)
                    report_html += f"""
                    <h3 style='margin-top: 20px;'>{question_title}</h3>
                    <ul style="list-style-type: disc; padding-left: 20px;">
                    """
                    for answer in open_ended_answers:
                        # Yanıt metinlerinin A4'e sığması için sade format
                        report_html += f"<li style='margin-bottom: 10px; line-height: 1.5;'>{answer}</li>"
                    report_html += f"</ul>"
                    
                else:
                    st.info(f"Bu soru için yanıt bulunamadı.")
            except KeyError:
                st.warning(f"Açık Uçlu Yanıt sütunu ('{col_name}') bulunamadı.")
            except Exception as e:
                st.error(f"Açık Uçlu Rapor oluşturulurken hata: {e}")

        # ----------------------------------------
        # PDF İndirme Butonu
        # ----------------------------------------
        
        try:
            pdf_data = create_pdf_report(report_html)
            st.markdown("---")
            st.download_button(
                label="⬇️ Raporu PDF Olarak İndir",
                data=pdf_data,
                file_name=f"Etkinlik_Raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"PDF indirme düğmesi oluşturulurken hata: {e}")
            st.warning("Bu, Weasyprint'in sistem bağımlılıklarının hala eksik olmasından kaynaklanabilir (packages.txt kontrol edin).")


# ----------------------------------------
# Başlangıç Durumu
# ----------------------------------------
else:
    st.info("Lütfen sol menüden filtreleme kriterlerini seçin ve '🚀 Rapor Oluştur' butonuna tıklayın.")