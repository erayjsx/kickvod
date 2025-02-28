import os
import threading
import tempfile
import shutil
import requests
import m3u8
import subprocess
from urllib.parse import urljoin
from utils import seconds_to_time_str


class KickDownloader:
    def __init__(self, url, start_time, end_time, output_path, progress_callback, status_callback, complete_callback):
        self.url = url
        self.start_time = start_time  # saniye cinsinden
        self.end_time = end_time  # saniye cinsinden
        self.output_path = output_path
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.complete_callback = complete_callback
        self.is_running = False
        self.thread = None
        self.temp_dir = None

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._download_process)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass

    def _download_process(self):
        try:
            self.status_callback("Yayın bilgileri alınıyor...")

            # M3U8 içeriğini alma
            headers = self._get_request_headers()
            
            response = requests.get(self.url, headers=headers)
            if response.status_code != 200:
                self.status_callback(f"Hata: Yayın bilgileri alınamadı. Durum kodu: {response.status_code}")
                return

            # M3U8 verilerini analiz et
            try:
                master_playlist = m3u8.loads(response.text)
            except Exception as e:
                self.status_callback(f"M3U8 ayrıştırma hatası: {str(e)}")
                return

            # Alt playlist ve base URL'yi al
            playlist, base_url = self._process_playlist(master_playlist, headers)
            
            # Segmentleri kontrol et
            if not playlist.segments:
                self.status_callback("Hata: Yayın segmentleri bulunamadı. Playlist içeriği: " + response.text[:200])
                return

            # Geçici dizin oluştur
            self.temp_dir = tempfile.mkdtemp()
            
            # İndirilecek segmentleri hesapla
            segments_to_download, segment_duration = self._calculate_segments(playlist)
            
            if not segments_to_download:
                self.status_callback("Hata: İndirilebilecek segment bulunamadı.")
                return

            # Segmentleri indir
            segment_files = self._download_segments(segments_to_download, base_url, headers)
            
            if not self.is_running:
                self.status_callback("İndirme iptal edildi.")
                return
                
            if not segment_files:
                self.status_callback("Hata: Hiçbir segment indirilemedi.")
                return
                
            # Segmentleri birleştir
            self._merge_segments(segment_files)
            
            # Tamamlandı bilgisini gönder
            self.complete_callback(self.output_path)
            
            # Geçici dosyaları temizle
            self._cleanup_temp_files()
            
        except Exception as e:
            self.status_callback(f"Beklenmeyen hata: {str(e)}")
            self.progress_callback(0)
    
    def _get_request_headers(self):
        """İstek başlıklarını döndürür"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Origin': 'https://kick.com',
            'Referer': 'https://kick.com/'
        }
    
    def _process_playlist(self, master_playlist, headers):
        """Master playlist işleme ve alt playlist elde etme"""
        if master_playlist.is_variant:
            # Master playlist ise, en yüksek kaliteyi seç
            playlists = sorted(master_playlist.playlists, 
                              key=lambda x: x.stream_info.bandwidth if x.stream_info else 0, 
                              reverse=True)
            
            if not playlists:
                raise Exception("Uygun yayın kalitesi bulunamadı.")
            
            # En yüksek kaliteyi içeren playlist URL'sini al
            variant_url = playlists[0].uri
            
            # URL'yi normalize et (göreceli ise tam URL'ye çevir)
            if not variant_url.startswith('http'):
                base_url = '/'.join(self.url.split('/')[:-1]) + '/'
                variant_url = urljoin(base_url, variant_url)
            
            # Alt playlist'i indir
            self.status_callback("Alt playlist indiriliyor...")
            variant_response = requests.get(variant_url, headers=headers)
            if variant_response.status_code != 200:
                raise Exception(f"Alt playlist alınamadı. Durum kodu: {variant_response.status_code}")
            
            # Alt playlist'i analiz et
            playlist = m3u8.loads(variant_response.text)
            base_url = '/'.join(variant_url.split('/')[:-1]) + '/'
        else:
            # Zaten segment playlist'i ise
            playlist = master_playlist
            base_url = '/'.join(self.url.split('/')[:-1]) + '/'
        
        return playlist, base_url
    
    def _calculate_segments(self, playlist):
        """İndirilecek segmentleri hesaplar"""
        # Her segmentin süresini tespit et (ortalama)
        segment_duration = playlist.target_duration or 6  # varsayılan 6 saniye
        
        # Hesaplanan segment indekslerini bul
        total_segments = len(playlist.segments)
        total_duration = total_segments * segment_duration
        
        # Zaman aralığını kontrol et
        if self.end_time > total_duration:
            self.end_time = total_duration
            self.status_callback(f"Uyarı: Bitiş zamanı yayın süresinden uzun. {seconds_to_time_str(total_duration)} olarak ayarlandı.")
        
        # Segment indekslerini hesapla
        start_segment = min(int(self.start_time / segment_duration), total_segments - 1)
        end_segment = min(int(self.end_time / segment_duration), total_segments)
        
        segments_to_download = playlist.segments[start_segment:end_segment]
        
        return segments_to_download, segment_duration
    
    def _download_segments(self, segments, base_url, headers):
        """Segmentleri indirir ve dosya yollarını döndürür"""
        self.status_callback(f"Toplam {len(segments)} segment indirilecek...")
        segment_files = []
        
        for i, segment in enumerate(segments):
            if not self.is_running:
                break
            
            segment_url = segment.uri
            if not segment_url.startswith('http'):
                # Göreceli URL'yi tam URL'ye dönüştür
                segment_url = urljoin(base_url, segment_url)
            
            segment_file = os.path.join(self.temp_dir, f"segment_{i:05d}.ts")
            
            # Segmenti indir
            self.status_callback(f"Segment indiriliyor {i+1}/{len(segments)}...")
            self.progress_callback(int((i / len(segments)) * 50))
            
            try:
                segment_response = requests.get(segment_url, headers=headers)
                if segment_response.status_code != 200:
                    self.status_callback(f"Segment indirme hatası: {segment_response.status_code}")
                    continue
                    
                with open(segment_file, "wb") as f:
                    f.write(segment_response.content)
                segment_files.append(segment_file)
            except Exception as e:
                self.status_callback(f"Segment indirme hatası: {str(e)}")
                continue
        
        return segment_files
    
    def _merge_segments(self, segment_files):
        """Segmentleri birleştirir ve MP4 formatına dönüştürür"""
        self.status_callback("Segmentler birleştiriliyor...")
        self.progress_callback(60)
        
        # Önce TS dosyalarını birleştir
        temp_ts_path = os.path.join(self.temp_dir, "combined.ts")
        with open(temp_ts_path, 'wb') as outfile:
            for segment_file in segment_files:
                if os.path.exists(segment_file):
                    with open(segment_file, 'rb') as infile:
                        outfile.write(infile.read())
        
        self.progress_callback(70)
        
        # TS dosyasını MP4'e dönüştür
        output_file = self.output_path
        
        # Çıktı dosyasının uzantısını kontrol et ve gerekirse düzelt
        if not output_file.lower().endswith('.mp4'):
            output_file = os.path.splitext(output_file)[0] + '.mp4'
            self.output_path = output_file
            
        self.status_callback("MP4 formatına dönüştürülüyor...")
        
        try:
            # FFmpeg kontrolü
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                self.status_callback("FFmpeg bulunamadı. TS formatında kaydediliyor...")
                shutil.copy(temp_ts_path, self.output_path)
                self.progress_callback(90)
                self.status_callback("İşlem tamamlandı!")
                self.progress_callback(100)
                return
                
            # FFmpeg ile dönüştürme
            cmd = [
                'ffmpeg',
                '-i', temp_ts_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-y',  # Varolan dosyanın üzerine yaz
                output_file
            ]
            
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode != 0:
                self.status_callback(f"Dönüştürme hatası: {process.stderr}")
                # Hata olursa TS dosyasını kopyala
                shutil.copy(temp_ts_path, self.output_path)
            else:
                self.status_callback("Dönüştürme başarılı!")
                
        except Exception as e:
            self.status_callback(f"Dönüştürme hatası: {str(e)}")
            # Hata olursa TS dosyasını kopyala
            shutil.copy(temp_ts_path, self.output_path)
        
        self.progress_callback(90)
        self.status_callback("İşlem tamamlandı!")
        self.progress_callback(100)
    
    def _cleanup_temp_files(self):
        """Geçici dosyaları temizler"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                self.status_callback(f"Geçici dosya temizleme hatası: {str(e)}")