import flet as ft
from services.downloader import KickDownloader
from utils import (time_str_to_seconds, get_m3u8_url_from_kick_api, 
                  get_download_directory, get_download_path, 
                  DownloadHistoryManager)
from ui.components import open_local_file
import os
import json

class AppHandlers:
    def __init__(self, page):
        self.page = page
        self.downloader = None
        self.video_info = None
        # İndirme geçmişi yöneticisini oluştur
        self.history_manager = DownloadHistoryManager(page)
        
        # Eski dosya tabanlı geçmişi client storage'a taşı
        self.history_manager.migrate_from_file()
        
        # İndirme geçmişini al
        self.download_history = self.history_manager.get_history()
        
    def close_app(self, event):
        self.page.window.close()
    
    def minimize_app(self, event):
        self.page.window.minimized = True
        
    def update_progress(self, value):
        self.progress_bar.value = value / 100
        self.page.update()

    def update_status(self, message):
        self.status_text.value = message
        self.page.update()

    def download_complete(self, output_path):
        # UI güncelle
        self.download_button.disabled = False
        self.cancel_button.disabled = True
        
        # İndirme geçmişini kaydet
        if self.video_info:
            start_time_seconds = time_str_to_seconds(self.start_time.value)
            end_time_seconds = time_str_to_seconds(self.end_time.value)
            # Client storage'a kaydet
            self.download_history = self.history_manager.save_download(
                self.video_info, output_path, start_time_seconds, end_time_seconds
            )
            
            # Son indirilenler listesini güncelle
            self.update_download_history_ui()
        
        # Diyalog penceresini kapat ve form verilerini sıfırla
        self.reset_form()
        self.page.close(self.dlg)
        self.page.update()
        
        # Tamamlandı mesajı göster
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(f"İndirme tamamlandı: {output_path}"),
            action="Tamam"
        )
        self.page.snack_bar.open = True
        self.page.update()

    def update_download_history_ui(self):
        """Son indirilenler listesini günceller"""
        # Eğer indirme listesi container'ı varsa güncelle
        if hasattr(self, 'downloads_container') and self.downloads_container:
            from ui.components import create_recent_downloads_list
            
            # Client storage'dan güncel geçmişi al
            self.download_history = self.history_manager.get_history()
            
            # Mevcut listeyi temizle ve yenisini oluştur
            self.downloads_container.content = create_recent_downloads_list(
                self.download_history, 
                self.open_file_from_history,
                self.open_file_in_folder,
                self.delete_video_file
            ).content
            
            self.page.update()
    
    def open_file_from_history(self, file_path):
        """Dosyayı geçmişten açar"""
        from ui.components import open_local_file
        open_local_file(file_path)

    def open_file_in_folder(self, file_path):
        """Dosyayı içeren klasörü açar"""
        if os.path.exists(file_path):
            folder_path = os.path.dirname(file_path)
            from ui.components import open_local_file
            open_local_file(folder_path)
            
    def delete_video_file(self, file_path, video_id):
        """Video dosyasını siler ve indirme geçmişinden kaldırır"""
        try:
            # Dosyayı sil
            if os.path.exists(file_path):
                os.remove(file_path)
                
            # Geçmişten kaldır
            history = self.history_manager.get_history()
            updated_history = [item for item in history if item.get('video_id') != video_id]
            
            # Güncellenen geçmişi kaydet
            self.page.client_storage.set(self.history_manager.HISTORY_KEY, json.dumps(updated_history))
            self.download_history = updated_history
            
            # UI'ı güncelle
            self.update_download_history_ui()
            
            # Bildirim göster
            self.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("Video başarıyla silindi"),
                    action="Tamam",
                    action_color=ft.colors.GREEN
                )
            )
            return True
        except Exception as e:
            # Hata mesajı göster
            self.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text(f"Video silinirken hata oluştu: {str(e)}"),
                    action="Tamam",
                    action_color=ft.colors.RED
                )
            )
            return False

    def start_download(self, e):
        """Video indirme işlemini başlatır"""
        # Boş URL kontrolü
        if not self.url_input.value:
            self.update_status("Hazır")
            self.show_error("Lütfen bir Kick.com video URL'si girin")
            return
        
        # UI'yi güncelle
        self.update_status("M3U8 URL alınıyor...")
        
        # Video URL'sinden m3u8 URL çıkar
        try:
            video_url = self.url_input.value
            m3u8_url, video_info = get_m3u8_url_from_kick_api(video_url)
        except Exception as error:
            self.update_status("Hazır")
            self.show_error(f"M3U8 URL çıkarılamadı: {str(error)}")
            return
        
        # Video bilgisini sakla
        self.video_info = video_info
            
        # Zamanları saniyeye çevir
        try:
            start_time_seconds = time_str_to_seconds(self.start_time.value)
            end_time_seconds = time_str_to_seconds(self.end_time.value)
        except:
            self.download_button.disabled = False
            self.update_status("Hazır")
            self.show_error("Geçersiz zaman formatı. HH:MM:SS kullanın")
            return
            
        if end_time_seconds <= start_time_seconds:
            self.download_button.disabled = False
            self.update_status("Hazır")
            self.show_error("Bitiş zamanı başlangıç zamanından büyük olmalıdır")
            return
            
        # Başlığı al
        custom_title = self.title_input.value if self.title_input.value else None
            
        # İndirme yolunu oluştur
        output_path = get_download_path(video_info, start_time_seconds, end_time_seconds, custom_title)
            
        # Arayüzü güncelle
        self.download_button.disabled = True
        self.cancel_button.disabled = False
        self.progress_bar.value = 0
        self.page.update()
        
        # İndirme işlemini başlat
        self.downloader = KickDownloader(
            url=m3u8_url,
            start_time=start_time_seconds,
            end_time=end_time_seconds,
            output_path=output_path,
            progress_callback=self.update_progress,
            status_callback=self.update_status,
            complete_callback=self.download_complete
        )
        self.downloader.start()

    def show_error(self, message):
        """Hata mesajı göster"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            action="Tamam"
        )
        self.page.snack_bar.open = True
        self.page.update()

    def cancel_download(self, e):
        # Formu sıfırla ve dialog'u kapat
        self.reset_form()
        self.page.close(self.dlg)
        
        if self.downloader:
            self.downloader.stop()
            self.update_status("İndirme iptal edildi")
        
        self.download_button.disabled = False
        self.cancel_button.disabled = True
        self.progress_bar.value = 0
        self.page.update()

    def open_file(self, e):
        path = e.control.data
        open_local_file(path)
        
    def set_ui_elements(self, url_input, start_time, end_time, title_input, output_dir_text, 
                       progress_bar, status_text, download_button, cancel_button, 
                       dlg, downloads_container):
        """UI elementlerini ayarlar"""
        self.url_input = url_input
        self.start_time = start_time
        self.end_time = end_time
        self.title_input = title_input
        self.output_dir_text = output_dir_text
        self.progress_bar = progress_bar
        self.status_text = status_text
        self.download_button = download_button
        self.cancel_button = cancel_button
        self.dlg = dlg
        self.downloads_container = downloads_container
        
        # İndirme klasörünü göster
        self.output_dir_text.value = str(get_download_directory())

    def reset_form(self):
        """Form alanlarını sıfırlar"""
        self.url_input.value = ""
        self.start_time.value = "00:00:00"
        self.end_time.value = "00:30:00"
        self.title_input.value = ""
        self.status_text.value = "Hazır"
        self.progress_bar.value = 0
        self.video_info = None
        self.downloader = None
