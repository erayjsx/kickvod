import re
import requests
import json
import os
import pathlib
from datetime import datetime, timedelta

def time_str_to_seconds(time_str):
    """HH:MM:SS formatındaki zamanı saniyeye çevirir"""
    h, m, s = time_str.split(':')
    return int(h) * 3600 + int(m) * 60 + int(s)


def seconds_to_time_str(seconds):
    """Saniyeyi HH:MM:SS formatına çevirir"""
    return str(timedelta(seconds=seconds))


def extract_video_id(url):
    """Kick.com video URL'sinden video ID'sini çıkarır"""
    # Regex ile video ID'sini bul
    pattern = r'(?:videos|video)/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
    match = re.search(pattern, url)
    
    if match:
        return match.group(1)
    return None


def get_m3u8_url_from_kick_api(video_url):
    """Kick.com video URL'sinden m3u8 URL'sini alır"""
    video_id = extract_video_id(video_url)
    
    if not video_id:
        raise ValueError("Geçersiz Kick.com video URL'si. Video ID bulunamadı.")
    
    # API isteği
    api_url = f"https://kick.com/api/v1/video/{video_id}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',
        'Origin': 'https://kick.com',
        'Referer': 'https://kick.com/'
    }
    
    response = requests.get(api_url, headers=headers)
    if response.status_code != 200:
        raise ValueError(f"API isteği başarısız oldu. Durum kodu: {response.status_code}")
    
    # JSON verisini ayrıştır
    data = response.json()
    
    # başlık ve thumbnail bilgisini al
    if 'livestream' in data:
        # Yeni API yapısı
        livestream = data.get('livestream', {})
        video_title = livestream.get('session_title', 'İsimsiz Yayın')
        thumbnail = livestream.get('thumbnail', None)
        created_at = livestream.get('created_at', datetime.now().isoformat())
        streamer = data.get('streamer', {}).get('username', 'bilinmeyen') if 'streamer' in data else 'bilinmeyen'
    else:
        # Eski API yapısı
        video_title = data.get('title', 'İsimsiz Yayın')
        streamer = data.get('streamer', {}).get('username', 'bilinmeyen')
        thumbnail = data.get('thumbnail', {}).get('url', None)
        created_at = data.get('created_at', datetime.now().isoformat())
    
    # source URL'sini al
    if 'source' in data and data['source']:
        return data['source'], {
            'title': video_title,
            'streamer': streamer,
            'thumbnail': thumbnail,
            'created_at': created_at,
            'video_id': video_id
        }
    else:
        raise ValueError("API yanıtında m3u8 URL'si bulunamadı")


def get_download_directory():
    """İndirme dizinini döndürür, yoksa oluşturur"""
    # Kullanıcının Documents klasörünü al
    home = pathlib.Path.home()
    documents = home / "Documents"
    
    # kickvod klasörünü oluştur
    kickvod_dir = documents / "kickvod"
    kickvod_dir.mkdir(exist_ok=True)
    
    return str(kickvod_dir)


def get_download_path(video_info, start_time_seconds, end_time_seconds, custom_title=None):
    """İndirme dosyası yolunu döndürür"""
    download_dir = get_download_directory()
    
    # Video bilgilerini kullanarak dosya adı oluştur
    streamer = video_info.get('streamer', 'unknown')
    video_id = video_info.get('video_id', 'unknown')
    
    # Özel başlık varsa onu kullan, yoksa video başlığını kullan
    title = custom_title if custom_title else video_info.get('title', 'untitled')
    
    # Geçersiz dosya adı karakterlerini temizle
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    
    # Zaman bilgisini dahil et - HH_MM_SS-HH_MM_SS formatında
    start_time_str = seconds_to_time_str(start_time_seconds).replace(':', '_')
    end_time_str = seconds_to_time_str(end_time_seconds).replace(':', '_')
    time_range = f"{start_time_str}-{end_time_str}"
    
    # Dosya adını oluştur
    filename = f"{streamer}_{title}_{time_range}.mp4"
    
    # Dosya yolunu oluştur
    file_path = os.path.join(download_dir, filename)
    
    return file_path


class DownloadHistoryManager:
    """İndirme geçmişini yönetir"""
    HISTORY_KEY = "download_history"
    MAX_HISTORY_ITEMS = 50
    
    def __init__(self, page):
        self.page = page
    
    def save_download(self, video_info, file_path, start_time, end_time):
        """İndirme geçmişine yeni bir kayıt ekler"""
        # Mevcut geçmişi al
        history = self.get_history()
        
        # Yeni indirme bilgisini ekle
        history.insert(0, {
            'title': video_info.get('title', 'İsimsiz Yayın'),
            'streamer': video_info.get('streamer', 'bilinmeyen'),
            'thumbnail': video_info.get('thumbnail', None),
            'created_at': video_info.get('created_at', datetime.now().isoformat()),
            'video_id': video_info.get('video_id', None),
            'file_path': file_path,
            'start_time': start_time,
            'end_time': end_time,
            'download_date': datetime.now().isoformat()
        })
        
        # Geçmişi sınırla (en son 50 indirme)
        history = history[:self.MAX_HISTORY_ITEMS]
        
        # Client storage'a kaydet
        self.page.client_storage.set(self.HISTORY_KEY, json.dumps(history))
        
        return history
    
    def get_history(self):
        """İndirme geçmişini döndürür"""
        history_json = self.page.client_storage.get(self.HISTORY_KEY)
        
        if history_json:
            try:
                return json.loads(history_json)
            except:
                return []
        else:
            return []
    
    def clear_history(self):
        """İndirme geçmişini temizler"""
        self.page.client_storage.remove(self.HISTORY_KEY)
        
    def migrate_from_file(self):
        """Dosya tabanlı geçmişi client storage'a taşır"""
        download_dir = get_download_directory()
        history_file = os.path.join(download_dir, "download_history.json")
        
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    
                # Client storage'a kaydet
                self.page.client_storage.set(self.HISTORY_KEY, json.dumps(history))
                
                # Eski dosyayı yedekle
                backup_file = os.path.join(download_dir, "download_history.json.bak")
                os.rename(history_file, backup_file)
                
                return True
            except Exception as e:
                print(f"Geçmiş taşıma hatası: {str(e)}")
                return False
        
        return False


# Geriye dönük uyumluluk için eski fonksiyonları koruyoruz
# Bu fonksiyonlar artık kullanılmayacak ama mevcut kodun çalışması için
def save_download_history(video_info, file_path, start_time, end_time):
    """
    Geriye dönük uyumluluk için. Bu fonksiyonu kullanmayın.
    Bunun yerine DownloadHistoryManager.save_download kullanın.
    """
    print("UYARI: save_download_history kullanım dışı. DownloadHistoryManager kullanın.")
    return []

def get_download_history():
    """
    Geriye dönük uyumluluk için. Bu fonksiyonu kullanmayın.
    Bunun yerine DownloadHistoryManager.get_history kullanın.
    """
    print("UYARI: get_download_history kullanım dışı. DownloadHistoryManager kullanın.")
    return []