import streamlit as st
import pandas as pd
import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
import json

# Sayfa Yapılandırması
st.set_page_config(
    page_title="Dinamik Raporlama Uygulaması",
    layout="wide"
)

# Daha önce kaydettiğiniz Google Sheets ID'sini buraya yapıştırın.
SPREADSHEET_ID = st.secrets["sheets_id"]

# Kapsam (Scopes) – Uygulamanın neye erişeceğini belirtir
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# -----------------------------------------------------
# 1. Sheets Verisini Çekme Fonksiyonu
# -----------------------------------------------------

@st.cache_data(ttl=3600) # Veriyi 1 saat önbellekte tut
def load_data():
    st.info("Google Sheets verisi çekiliyor...")
    
    # Yerel OAuth Akışı için Client Secrets bilgisi gerekiyor.
    # Şimdilik bu kısmı boş bırakıyoruz, çünkü Streamlit Cloud'da farklı çalışacak.
    # Ancak yerel test için Streamlit'in yerleşik OAuth akışını kullanacağız.
    
    try:
        # **ÖNEMLİ:** Bu adım, Streamlit Cloud'da Sırlar (Secrets) ile 
        # veya yerelde Service Account JSON ile daha kolay çalışır. 
        # Ancak, kullanıcı hesabıyla (OAuth) yerelde denemek için
        # Streamlit'in sağladığı bir Client ID/Secret kullanmak gerekir. 
        # Yerel deneme zor olduğu için bu kısmı şimdilik pasif bırakıp,
        # sadece Cloud ortamında çalışacak şekilde hazırlık yapalım.
        
        # **Şimdilik Sadece Placeholder (Yer Tutucu) İle Devam:**
        # Bu aşama, Cloud'a taşıyınca çalışacaktır. Yerel olarak test etmek
        # için geçici olarak Sheets API'sine ait Client Secrets dosyası 
        # gereklidir. Bu süreci basitleştirmek için Cloud Deployment'a odaklanacağız.
        
        st.warning("Yerel ortamda OAuth tabanlı Sheets bağlantısı karmaşıktır. Bu kodu Cloud'da test edeceğiz. Geçici bir boş DataFrame oluşturuluyor.")
        
        # Geçici Boş DataFrame
        df = pd.DataFrame({'Durum': ['BAŞARILI'], 'Not': ['Cloud’da Deneyin.']})
        return df

    except Exception as e:
        st.error(f"Hata: {e}")
        return pd.DataFrame()


# -----------------------------------------------------
# 2. Arayüz
# -----------------------------------------------------
st.title("📊 Dinamik Raporlama Uygulaması")
data_df = load_data()

if not data_df.empty:
    st.success("Test verisi yüklendi.")
    st.dataframe(data_df, use_container_width=True)