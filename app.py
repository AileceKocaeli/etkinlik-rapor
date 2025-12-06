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


# Güncellenmiş load_data() fonksiyonunun SADECE ÇEKİRDEĞİ
@st.cache_data(ttl=3600) 
def load_data():
    st.info("Google Sheets verisi çekiliyor...")
    
    try:
        # 1. Credentials (Kimlik Bilgilerini) oluşturma
        creds_json = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(
            creds_json, scopes=SCOPES
        )
        
        # 2. gspread ile bağlantı kurma
        gc = gspread.authorize(creds)
        
        # 3. Sheets ve Sayfayı açma
        worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        
        # 4. Tüm veriyi çekme
        data = worksheet.get_all_records()
        
        # 5. Pandas DataFrame'e dönüştürme
        df = pd.DataFrame(data)
        
        return df

    except KeyError:
        st.error("GCP Secrets yüklenemedi. Lütfen 'secrets.toml' dosyasını kontrol edin.")
        return pd.DataFrame()
    
    except Exception as e:
        st.error(f"Veri çekilirken kritik bir hata oluştu: {e}")
        st.warning("Sheets ID veya Sayfa Adı hatalı olabilir, ya da Service Account'ın erişimi yoktur.")
        return pd.DataFrame()

# -----------------------------------------------------
# 2. Arayüz
# -----------------------------------------------------
st.title("📊 Dinamik Raporlama Uygulaması")
data_df = load_data()

if not data_df.empty:
    st.success("Test verisi yüklendi.")
    st.dataframe(data_df, use_container_width=True)