import flet as ft
import os
import sys
from datetime import datetime

def create_app_bar(page, minimize_app, close_app):
    """Ana uygulama barını oluşturur"""
    return ft.AppBar(
        leading_width=40,
        title=ft.Container(
            ft.Image(src="https://i.ibb.co/SDcV5Fnb/image.png", height=32, width=132, fit=ft.ImageFit.CONTAIN,),
            padding=ft.Padding(
                left=10,
                right=0,
                top=0,
                bottom=0,
            ),
        ),
        center_title=False,
        bgcolor=ft.Colors.TRANSPARENT,
        actions=[
            ft.PopupMenuButton(
                items=[
                    ft.PopupMenuItem(text=ft.Text("Ayarlar", size=10).value,),
                    ft.PopupMenuItem(text=ft.Text("Kapat", size=10).value,),
                ]
            ),
            ft.IconButton(ft.Icons.HORIZONTAL_RULE_OUTLINED, on_click=minimize_app),
            ft.Container(
                ft.IconButton(ft.Icons.CLOSE, on_click=close_app),
                padding=ft.Padding(
                    right=10,
                    left=0,
                    top=0,
                    bottom=0,
                ),
            )
        ],
    )

def create_download_dialog(url_input, start_time, end_time, output_dir_text, title_input, progress_bar, 
                          status_text, download_button, cancel_button, 
                          cancel_download, start_download, reset_form):
    """İndirme diyalog penceresini oluşturur"""
    return ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Text("Yayın Kesiti İndir", size=20),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        content=ft.Column(
            width=700,
            controls=[
                ft.Text("Yayın Linki:", weight=ft.FontWeight.BOLD),
                url_input,

                ft.Text("Süre:", weight=ft.FontWeight.BOLD),
                ft.Row([
                    start_time,
                    end_time
                ]),
                
                ft.Text("Başlık (İsteğe Bağlı):", weight=ft.FontWeight.BOLD),
                title_input,

                ft.Text("İndirme Klasörü:", weight=ft.FontWeight.BOLD),
                output_dir_text,
                
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("İlerleme:", weight=ft.FontWeight.BOLD),
                            progress_bar
                        ],
                        spacing=5
                    ),
                    padding=ft.padding.only(top=20, bottom=10)
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Durum:", weight=ft.FontWeight.BOLD),
                            status_text
                        ],
                        spacing=5
                    ),
                    padding=10
                ),
                
                ft.Container(
                    content=ft.Text(
                        "Not: Bu uygulamayı sadece erişim iznine sahip olduğunuz içerikler için kullanın.",
                        italic=True,
                        size=12,
                        color=ft.colors.GREY
                    ),
                    padding=ft.padding.only(top=30)
                ),
            ]
        ),
        actions=[
            cancel_button,
            download_button
        ],  
        actions_alignment=ft.MainAxisAlignment.END,
        on_dismiss=lambda e: reset_form()
    )

def create_download_history_item(history_item, on_click_handler, open_folder_handler=None, delete_handler=None):
    """İndirme geçmişi öğesi oluşturur"""
    # Tarih biçimlendirme
    try:
        download_date = datetime.fromisoformat(history_item.get('download_date', ''))
        date_str = download_date.strftime("%d.%m.%Y")
    except:
        date_str = "Bilinmeyen tarih"
    
    # Thumbnail veya varsayılan
    thumbnail_url = history_item.get('thumbnail')
    if not thumbnail_url:
        thumbnail_url = "https://via.placeholder.com/150?text=No+Thumbnail"
    
    # Başlık
    title = f"{history_item.get('streamer', '')}: {history_item.get('title', 'İsimsiz Yayın')}"
    
    # Video kimliği ve dosya yolu
    file_path = history_item.get('file_path', '')
    video_id = history_item.get('video_id', '')
    
    # Popup menüsü için buton
    menu_button = ft.PopupMenuButton(
        icon=ft.icons.MORE_VERT,
        items=[
            ft.PopupMenuItem(
                text="Klasörde Göster",
                icon=ft.icons.FOLDER_OPEN,
                on_click=lambda e: open_folder_handler(file_path) if open_folder_handler else None
            ),
            ft.PopupMenuItem(
                text="Videoyu Sil",
                icon=ft.icons.DELETE,
                on_click=lambda e: delete_handler(file_path, video_id) if delete_handler else None
            ),
        ]
    )
    
    return ft.ListTile(
        leading=ft.Image(src=thumbnail_url, width=100, height=60, fit=ft.ImageFit.COVER),
        title=ft.Text(title, size=14),
        subtitle=ft.Text(date_str, size=12),
        on_click=lambda e: on_click_handler(file_path),
        trailing=menu_button
    )

def create_recent_downloads_list(history_items, open_file_handler, open_folder_handler=None, delete_handler=None):
    """Son indirilen videoları içeren listeyi oluşturur"""
    list_items = []
    
    # Başlık ekle
    list_items.append(
        ft.Container(
            ft.Text("Son İndirilenler", size=16),
            padding=ft.Padding(
                left=14,
                top=10,
                right=0,
                bottom=10
            )
        )
    )
    
    # Geçmiş öğeleri yoksa mesaj göster
    if not history_items:
        list_items.append(
            ft.Container(
                ft.Text("Henüz indirilmiş video bulunmuyor", 
                      italic=True, 
                      color=ft.colors.GREY),
                padding=ft.padding.only(left=20, top=10)
            )
        )
    else:
        # Her geçmiş öğesi için bir liste öğesi oluştur
        for item in history_items:
            list_items.append(create_download_history_item(
                item, 
                open_file_handler,
                open_folder_handler,
                delete_handler
            ))
    
    return ft.SafeArea(
        ft.Column(controls=list_items),
        expand=True,
    )

def open_local_file(path):
    """Sistem dosya yöneticisinde dosyayı açar"""
    if os.path.exists(path):
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':  # macOS
            os.system(f'open "{path}"')
        else:  # Linux
            os.system(f'xdg-open "{path}"')
