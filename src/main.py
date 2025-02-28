import flet as ft
from handlers.app_handlers import AppHandlers
from ui.components import create_app_bar, create_download_dialog, create_recent_downloads_list
from utils import get_download_directory

def main(page: ft.Page):
    page.title = "kickvod"
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.GREEN,
        font_family="DupletRegular"
    )
    page.resizable = False
    page.window.title_bar_hidden = True
    page.window.bgcolor = "#12130F"
    page.bgcolor = "#12130F"
    page.window.frameless = True
    page.window.width = 1080
    page.window.height = 666
    page.window.resizable = False
    page.window.alignment = page.window.center

    page.fonts = {
        "DupletSemibold": "/fonts/Duplet-Semibold.otf",
        "DupletRegular": "/fonts/Duplet-Regular.otf",
    }

    # Olay işleyicileri oluştur
    handlers = AppHandlers(page)
    
    # İndirme geçmişini AppHandlers sınıfından al
    download_history = handlers.download_history
    
    # UI bileşenlerini tanımla
    url_input = ft.TextField(
        hint_text="https://kick.com/ilkinsan/videos/bd70d614-45cd-4bad-b17c-5f3f13b2161d", 
        width=700,
        helper_text="Kick.com video sayfası URL'sini girin"
    )
    start_time = ft.TextField(label="Başlangıç", value="00:00:00")
    end_time = ft.TextField(label="Bitiş", value="00:30:00")
    title_input = ft.TextField(
        hint_text="İndirilen video için isteğe bağlı başlık",
        label="Başlık"
    )
    output_dir_text = ft.TextField(
        read_only=True,
        border=ft.InputBorder.OUTLINE,
        expand=True
    )
    progress_bar = ft.ProgressBar(value=0, width=560)
    status_text = ft.Text("Hazır", style=ft.TextStyle(italic=True))
    download_button = ft.ElevatedButton("İndir", on_click=handlers.start_download)
    cancel_button = ft.TextButton("İptal", on_click=handlers.cancel_download)
    
    # Diyalog oluştur
    dlg = create_download_dialog(
        url_input, start_time, end_time, output_dir_text, title_input, progress_bar, 
        status_text, download_button, cancel_button, 
        handlers.cancel_download, handlers.start_download, handlers.reset_form
    )
    
    # Son indirilenler listesini oluştur
    downloads_container = create_recent_downloads_list(
        download_history, 
        handlers.open_file_from_history,
        handlers.open_file_in_folder,
        handlers.delete_video_file
    )
    
    # UI elementlerini işleyiciye bağla
    handlers.set_ui_elements(
        url_input, start_time, end_time, output_dir_text, title_input,  progress_bar, 
        status_text, download_button, cancel_button, dlg, downloads_container
    )

    # App bar oluştur
    page.appbar = create_app_bar(page, handlers.minimize_app, handlers.close_app)

    # Floating action button ekle
    page.floating_action_button = ft.FloatingActionButton(
        icon=ft.Icons.ADD,
        text="Yeni Kesit İndir",
        on_click=lambda _: page.open(dlg)
    )

    # Son indirilen videolar listesi ekle
    page.add(downloads_container)


ft.app(main, assets_dir="assets")
