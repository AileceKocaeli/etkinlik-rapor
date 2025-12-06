import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import re
from datetime import datetime
from weasyprint import HTML 
from io import BytesIO
import base64 

# --- ÖNEMLİ NOT ---
# Kaleido'nun çalışması için 'packages.txt' dosyanızda 'chromium' paketi olmalıdır.
# Sütun başlıkları, Sheets'ten gelen tam metinler olmalıdır.

# -----------------------------------------------------
# 1. Sabit Tanımlamalar ve Ayarlar
# -----------------------------------------------------

st.set_page_config(page_title="Dinamik Etkinlik Raporlama", layout="wide")

# Sheets Bağlantı Bilgileri
SPREADSHEET_ID = st.secrets.get("sheets_id")
WORKSHEET_NAME = "Form Yanıtları 1" 
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Derecelendirme Etiketleri Sözlüğü (Aritmetik hesaplama ve etiketleme için)
RATING_LABELS = {
    5: '5 - Çok İyi',
    4: '4 - İyi',
    3: '3 - Orta',
    2: '2 - Zayıf',
    1: '1 - Çok Zayıf'
}

# Sheets'ten gelen BİREBİR SÜTUN BAŞLIKLARI (KeyError almamak için kritik)
TIMESTAMP_COL = 'Zaman damgası' 
EVENT_TYPE_COL = 'Katıldığınız Etkinlik Türünü Seçiniz' 

# Tüm Sütunların Başlıkları (Nihai listeye göre kesinleştirilmiştir)
ALL_COLUMNS_MAPPING = {
    # DERECE GRAFİKLERİ (D, E, F, I, J)
    'D': 'Katıldığınız etkinliğin genel olarak değerlendirilmesi [Etkinlik süresinin yeterliliği]',
    'E': 'Katıldığınız etkinliğin genel olarak değerlendirilmesi [Etkinlikte kullanılan yöntem ve tekniklerin uygunluğu]',
    'F': 'Katıldığınız etkinliğin genel olarak değerlendirilmesi [Etkinlikten yararlanma düzeyiniz]', 
    'I': 'Katıldığınız etkinliğin genel olarak değerlendirilmesi [Etkinliğin beklentilerinizi karşılama düzeyi]',
    'J': 'Katıldığınız etkinliğin genel olarak değerlendirilmesi [Etkinlik mekanının/ortamının uygunluğu]',
    # AÇIK UÇLU SORULAR (G, H, K)
    'G': 'Katıldığınız etkinlikte elde ettiğiniz bilgileri, yeterlilikleri veya kazanımları yazınız.',
    'H': 'Katıldığınız etkinliğe dair görüş ve önerilerinizi yazınız. ', 
    'K': 'Etkinliğe çocuğunuzla beraber katılmak, ebeveyn-çocuk etkileşiminiz ve öğrenme deneyiminiz üzerinde nasıl bir etki yarattı? Lütfen değerlendiriniz. ' 
}

# Grafik Sütunları: Sayfalama için ayrıldı.
GRAPH_COLUMNS_PAGE_2 = {
    ALL_COLUMNS_MAPPING['D']: 'Etkinlik Süresinin Yeterliliği',
    ALL_COLUMNS_MAPPING['E']: 'Yöntem ve Tekniklerin Uygunluğu',
    ALL_COLUMNS_MAPPING['F']: 'Etkinlikten Yararlanma Düzeyi',
}
GRAPH_COLUMNS_PAGE_3 = {
    ALL_COLUMNS_MAPPING['I']: 'Beklentileri Karşılama Düzeyi',
    ALL_COLUMNS_MAPPING['J']: 'Mekanın/Ortamın Uygunluğu'
}
# Açık Uçlu Sütunlar
OPEN_ENDED_COLUMNS = [
    ALL_COLUMNS_MAPPING['G'], 
    ALL_COLUMNS_MAPPING['H'],
    ALL_COLUMNS_MAPPING['K'] 
]

# -----------------------------------------------------
# 2. Yardımcı Fonksiyonlar
# -----------------------------------------------------

@st.cache_data(ttl=3600) 
def load_data():
    """Google Sheets verisini çeker ve DataFrame olarak döndürür."""
    if not SPREADSHEET_ID:
        st.error("Sheets ID bulunamadı.")
        return pd.DataFrame()
    
    st.info("Google Sheets verisi çekiliyor...")
    try:
        # GCP Bağlantı Kodu
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
    """Sadece köşeli parantez içindeki metni çeker, yoksa başlığın kendisini döndürür."""
    match = re.search(r'\[(.*?)\]', raw_header)
    
    if match: 
        return match.group(1).strip()
    
    return raw_header.strip()

def create_pdf_report(html_content):
    """HTML içeriğini WeasyPrint ile PDF'e çevirir."""
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

# Tarih formatına dönüştürme
if pd.api.types.is_string_dtype(df.get(TIMESTAMP_COL)):
    df[TIMESTAMP_COL] = pd.to_datetime(df[TIMESTAMP_COL], errors='coerce', dayfirst=True)

# Soru Başlıklarını Formatlama (Sadece parantez içini alır)
formatted_columns = {col: extract_title(col) for col in df.columns}

# ----------------------------------------
# Arayüz Filtreleme (Sidebar)
# ----------------------------------------
with st.sidebar:
    st.header("🔍 Rapor Filtreleri")
    
    # 1. Etkinlik Türü Filtresi (L Sütunu)
    unique_events = df[EVENT_TYPE_COL].dropna().unique().tolist()
    event_options = ["Tüm Kayıtlar"] + unique_events
    selected_event = st.selectbox("1. Etkinlik Türü Seçin", options=event_options, index=0)
    st.markdown("---")

    # 2. Dinamik Tarih Filtresi (Etkinlik Türüne Bağlı)
    filtered_dates_df = df.copy()
    if selected_event != "Tüm Kayıtlar":
        filtered_dates_df = filtered_dates_df[filtered_dates_df[EVENT_TYPE_COL] == selected_event]
        
    if pd.api.types.is_datetime64_any_dtype(df.get(TIMESTAMP_COL)):
        all_dates = filtered_dates_df[TIMESTAMP_COL].dt.normalize().dropna().unique()
        all_dates_list = pd.to_datetime(all_dates).tolist()
        date_options = ["Tüm Dönemler"] + sorted(all_dates_list, reverse=True)
        
        selected_date = st.selectbox(
            "2. Tarih Seçin", 
            options=date_options, 
            index=0, 
            format_func=lambda x: x.strftime('%d/%m/%Y') if isinstance(x, pd.Timestamp) else x
        )
    else:
        selected_date = "Tüm Dönemler"

    st.markdown("---")
    
    generate_report = st.button("🚀 Rapor Oluştur")

if 'report_generated' not in st.session_state:
    st.session_state['report_generated'] = False
    
if generate_report:
    st.session_state['report_generated'] = True
    st.session_state['selected_event'] = selected_event
    st.session_state['selected_date'] = selected_date

# ----------------------------------------
# 4. Filtreleme ve Raporlama Mantığı
# ----------------------------------------

if st.session_state['report_generated']:
    selected_event = st.session_state['selected_event']
    selected_date = st.session_state['selected_date']

    filtered_df = df.copy()

    if selected_event != "Tüm Kayıtlar":
        filtered_df = filtered_df[filtered_df[EVENT_TYPE_COL] == selected_event]

    if selected_date != "Tüm Dönemler":
        date_to_filter = selected_date.normalize()
        filtered_df = filtered_df[filtered_df[TIMESTAMP_COL].dt.normalize() == date_to_filter]
        
    criteria_summary = f"Etkinlik: **{selected_event}** | Tarih: **{selected_date.strftime('%d/%m/%Y') if selected_date != 'Tüm Dönemler' else 'Tüm Dönemler'}** | Toplam Yanıt: **{len(filtered_df)}**"
    st.subheader("✅ Rapor Hazır")
    st.info(criteria_summary)
    
    if filtered_df.empty:
        st.warning("Seçilen kriterlere uygun yanıt bulunamadı.")
    else:
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
        
        st.subheader("Grafik ve Özet Rapor (Derecelendirmeler)")

        for col_name, title in all_graphs.items():
            graph_counter += 1
            
            try:
                actual_title = formatted_columns.get(col_name, title)
                
                # KRİTİK DÜZELTME: Sayısal değeri çekme (Örn: '5-Çok iyi' -> '5')
                rating_data = filtered_df[col_name].astype(str).str.extract(r'^(\d)').dropna()
                
                if rating_data.empty:
                    st.warning(f"'{actual_title}' için yanıt yok veya yanıt formatı hatalı.")
                    continue 

                # 1. Yüzde Hesaplama 
                rating_counts = rating_data[0].value_counts(normalize=True).mul(100).rename('Yüzde').reset_index()
                rating_counts.columns = ['Derecelendirme', 'Yüzde']
                
                # 2. Sayısal Dönüşüm, Sıralama ve Etiket Haritalama
                rating_counts['Derecelendirme'] = pd.to_numeric(rating_counts['Derecelendirme'])
                rating_counts = rating_counts.sort_values(by='Derecelendirme')
                rating_counts['Derecelendirme Etiketi'] = rating_counts['Derecelendirme'].map(RATING_LABELS)
                
                # Grafikteki en yüksek yanıtın indeksini bulma (Dilimi ayırmak için)
                max_percent_index = rating_counts['Yüzde'].idxmax()
                pull_values = [0.1 if i == max_percent_index else 0 for i in rating_counts.index] # Max dilimi ayır

                # Grafik oluşturma (AYRILMIŞ DİLİMLİ PASTA GRAFİK)
                fig = px.pie(rating_counts, names='Derecelendirme Etiketi', values='Yüzde', 
                             title=f"**{actual_title}**",
                             color='Derecelendirme Etiketi',
                             color_discrete_sequence=px.colors.sequential.Teal, 
                             template="plotly_white") 
                
                # 3D ve Estetik Düzenlemeler
                fig.update_traces(
                    textinfo='percent+label', 
                    textfont_size=14,
                    marker=dict(line=dict(color='#FFFFFF', width=2)), # Yumuşak hatlar
                    pull=pull_values # En yüksek dilimi ayırma (Explosion Effect)
                )

                # Merkez Metni: Toplam Yanıt Sayısını Gösterir
                fig.update_layout(
                    annotations=[dict(text=f'Toplam Yanıt:<br>{len(filtered_df)}', x=0.5, y=0.5, font_size=18, showarrow=False)],
                    margin=dict(t=50, b=50, l=100, r=100),
                    showlegend=True
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # --- PDF DÜZELTMESİ: Grafiği Base64 Görüntüsü Olarak Gömme ---
                try:
                    img_bytes = fig.to_image(format="png")
                    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                    
                    graph_html_container += f"""
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h3 style="margin-bottom: 10px; font-size: 16px;">{actual_title}</h3>
                        <img src="data:image/png;base64,{img_base64}" style="width: 90%; max-width: 600px; display: block; margin: 0 auto;"/>
                    </div>
                    """
                except ValueError as ve:
                    st.error(f"PDF Görüntü Hatası: Plotly grafiğini resme çevirmek için 'kaleido' kurulu olmalı. Hata: {ve}")
                    graph_html_container += f"<p style='color: red;'>GRAFİK EKLENEMEDİ (Kaleido Hatası)</p>"
                
                # Sayfa sonu mantığı: Sayfa 2 (3 grafik) ve Sayfa 3 (2 grafik)
                if graph_counter == 3:
                    report_html += f"<div style='page-break-after: always;'>{graph_html_container}</div>"
                    graph_html_container = ""
                elif graph_counter == 5:
                    report_html += f"<div>{graph_html_container}</div>"
                    
            except KeyError:
                st.error(f"Kritik Hata: '{col_name}' sütunu bulunamadı. Lütfen Sheets başlıklarını kontrol edin.")
            except Exception as e:
                st.error(f"Grafik oluşturulurken genel hata: {e}")
                
        # ----------------------------------------
        # Açık Uçlu Yanıtlar (Sayfa 4+)
        # ----------------------------------------
        
        st.subheader("Açık Uçlu Yanıtlar")
        
        report_html += f"<h2 style='page-break-before: always; text-align: center; color: #007bff;'>Açık Uçlu Yanıtlar</h2>"
        
        for col_name in OPEN_ENDED_COLUMNS:
            try:
                question_title = formatted_columns.get(col_name, "Açık Uçlu Soru")
                
                st.markdown(f"**💬 {question_title}**")
                
                open_ended_answers = filtered_df[col_name].dropna().reset_index(drop=True)
                
                # Ekran Çıktısı (Streamlit)
                if not open_ended_answers.empty:
                    for i, answer in open_ended_answers.head(10).items():
                        st.markdown(f"> *{answer}*")
                    
                    if len(open_ended_answers) > 10:
                        st.caption(f"Ve {len(open_ended_answers) - 10} adet daha fazla yanıt (PDF'te yer alacaktır).")
                        
                    # PDF Çıktısı (HTML)
                    report_html += f"""
                    <h3 style='margin-top: 20px; font-size: 18px;'>{question_title}</h3>
                    <ul style="list-style-type: disc; padding-left: 20px;">
                    """
                    for answer in open_ended_answers:
                        report_html += f"<li style='margin-bottom: 10px; line-height: 1.5;'>{answer}</li>"
                    report_html += f"</ul>"
                    
                else:
                    st.info(f"Bu soru için yanıt bulunamadı.")
            except KeyError:
                st.error(f"Açık Uçlu Sütun ('{col_name}') bulunamadı. Lütfen kontrol edin.")
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
            st.error(f"PDF oluşturma sırasında Weasyprint hatası: {e}")


# ----------------------------------------
# Başlangıç Durumu
# ----------------------------------------
else:
    st.info("Lütfen sol menüden filtreleme kriterlerini seçin ve '🚀 Rapor Oluştur' butonuna tıklayın.")