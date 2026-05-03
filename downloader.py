import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import datetime
import os
import re
import sys
import signal
import shutil
from urllib.parse import urlparse, parse_qs, urlencode

process = None
dark_mode = True
current_file = None
current_stage = None
current_index = 0
total_count = 0
current_tree_item = None
dark_mode = False

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
YTDLP_PATH = os.path.join(BASE_PATH, "yt-dlp.exe")


# ---------------- STAGE LOG ---------------- #
def stage_log(stage, msg):
    global current_stage
    if current_stage != stage:
        log(msg)
        current_stage = stage


# ---------------- LOG ---------------- #

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_box.insert(tk.END, f"[{timestamp}] {msg}\n")
    log_box.see(tk.END)

# ---------------- FILE ---------------- #

def choose_folder():
    folder = filedialog.askdirectory()
    if folder:
        output_dir.set(folder)

# ---------------- STOP ---------------- #

def stop_download():
    global process, current_file

    if process:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            log("⏹️ İndirme durduruldu")

            # yarım dosya sil
            if current_file and os.path.exists(current_file):
                try:
                    os.remove(current_file)
                    log("🧹 Yarım dosya silindi")
                except:
                    pass

        except Exception as e:
            log(f"❌ Durdurma hatası: {e}")
        finally:
            process = None
            current_file = None

# ---------------- DOWNLOAD ---------------- #
def get_playlist_count(url):
    try:
        result = subprocess.run(
            [
                YTDLP_PATH,
                "--flat-playlist",
                "--print", "id",
                "--no-warnings",
                "--ignore-errors",
                url
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        return len([l for l in result.stdout.splitlines() if l.strip()])
    except Exception as e:
        log(f"❌ Playlist sayısı alınamadı: {e}")
        return 0
def is_real_playlist(url):
    try:
        result = subprocess.run(
            [
                YTDLP_PATH,
                "--flat-playlist",
                "--print", "%(playlist_count)s",
                url
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        print("is playlist : ",result)
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        return len(lines) > 1
    except:
        return False

def clean_video_url(url, keep_playlist=True):
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    if keep_playlist:
        return url  # playlist'i bozma

    if "v" in qs:
        return f"https://www.youtube.com/watch?v={qs['v'][0]}"

    return url

def start_download():
    log("⏳ Video bilgileri alınıyor...")
    threading.Thread(target=download, daemon=True).start()

def download():
    global process, current_file
    global current_index, total_count
    global current_tree_item
    current_tree_item = None

    current_index = 0
    total_count = 0

    url = url_entry.get().strip()
    bitrate = bitrate_var.get()
    out_dir = output_dir.get()

    format_type = format_var.get()   # "mp3" veya "mp4"
    item_label = "Şarkı" if format_type == "mp3" else "Video"
    
    last_destination = None
    last_filename = None

    target_ext = ".mp3" if format_type == "mp3" else ".mp4"


    if not url:
        messagebox.showerror("Hata", "URL gir")
        return

    os.makedirs(out_dir, exist_ok=True)


    is_playlist_mode = playlist_mode_var.get()

    common_args = [
        "--cookies", os.path.join(BASE_PATH, "cookies.txt"),
        "-4",
        "--sleep-requests", "2",
        "--sleep-interval", "2",
    ]
    
    if format_type == "mp3":
        cmd = [
            YTDLP_PATH,
            *common_args,
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", bitrate,
            "--embed-thumbnail",
            "--add-metadata",
            "--no-overwrites",
            "--output", f"{out_dir}/%(title)s.%(ext)s"
        ]
    else:  # mp4
        cmd = [
            YTDLP_PATH,
            *common_args,
            "-f", "bv*+ba/b",
            "--merge-output-format", "mp4",
            "--no-overwrites",
            "--output", f"{out_dir}/%(playlist_index)s - %(title)s.%(ext)s",
            clean_video_url(url)
        ]

    # ▶ Playlist sayısını ÖNCEDEN al
    if is_playlist_mode:
        total_count = get_playlist_count(url)
        log(f"📃 Playlist bulundu: {total_count} adet")
        # playlist korunur
        clean_url = clean_video_url(url, keep_playlist=True)
        cmd.append(clean_url)
    else:
        total_count = 1
        log("🎯 Tek video modu")

        cmd.append("--no-playlist")

        # playlist temizlenir
        clean_url = clean_video_url(url, keep_playlist=False)
        cmd.append(clean_url)

    progress_var.set(0)
    log("▶️ İndirme başladı")

    process = subprocess.Popen(
        cmd,
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )


    for line in process.stdout:
        line = line.strip()
        print(line)
        if "Destination:" in line:
            filename = line.split("Destination:")[-1].strip()

            if filename == last_filename:
                continue  # aynı dosya, geç

            # ❗ hedef dosya değilse UI'yi IGNORE et
            if not filename.lower().endswith(target_ext):
                continue
                
            last_filename = filename
            current_file = filename
            current_index += 1

            stage_log(
                "count",
                f"🎵 {item_label} {current_index} / {total_count}"
            )

            stage_log("connect", "▶ Bağlantı kuruluyor")

            current_tree_item = tree.insert(
                "",
                "end",
                values=(os.path.basename(filename), "⬇ İndiriliyor", "0%"),
                tags=("downloading",)
            )
            continue


        # 🎵 Ses akışı
        if "Extracting audio" in line or "Downloading webpage" in line:
            stage_log("audio", "🎵 Ses akışı alınıyor")
            continue

        # 🔄 Dönüştürme
        if "ffmpeg" in line or "ExtractAudio" in line:
            stage_log("convert", "🔄 Dönüştürülüyor (ffmpeg)")
            continue

        # ⬇️ İndirme yüzdesi
        m = re.search(r"(\d+(?:\.\d+)?)%", line)
        if m and current_file:
            percent = min(100, int(float(m.group(1))))
            progress_var.set(percent)


            if current_tree_item:
                tree.item(
                    current_tree_item,
                    values=(
                        tree.item(current_tree_item)["values"][0],
                        "⬇ İndiriliyor",
                        f"{percent}%"
                    )
                )


            stage_log("download", f"⬇️ İndiriliyor: %{percent}")
            continue

        # ✅ GERÇEK TAMAMLANDI
        if "Deleting original file" in line or "Finished downloading" in line:
            last_filename = None
            if current_tree_item:
                tree.item(
                    current_tree_item,
                    values=(
                        tree.item(current_tree_item)["values"][0],
                        "✅ Tamamlandı",
                        "100%"
                    ),
                    tags=("done",)
                )
                current_tree_item = None

            stage_log("done", "✅ Tamamlandı")
            current_file = None

    progress_var.set(100)
    log("✅ İndirme süreci bitti")

# ---------------- Output folder---------------- #

def open_output_folder():
    path = output_dir.get()
    if os.path.exists(path):
        subprocess.Popen(f'explorer "{os.path.abspath(path)}"')
    else:
        messagebox.showerror("Hata", "Klasör bulunamadı")



# ---------------- GUI ---------------- #

root = tk.Tk()


root.title("Advanced MP3 Downloader")
root.geometry("1000x650")
root.minsize(900, 550)

output_dir = tk.StringVar(value="downloads")
bitrate_var = tk.StringVar(value="192")

# ---------------- TOP BAR ---------------- #

top_frame = ttk.Frame(root)
top_frame.pack(fill="x", padx=10, pady=5)
top_frame.columnconfigure(1, weight=1)  # URL ve path uzayabilsin
top_frame.columnconfigure(2, weight=3)  # path en uzun alan


ttk.Label(top_frame, text="URL").grid(row=0, column=0, sticky="w")
url_entry = ttk.Entry(top_frame)
url_entry.grid(row=0, column=1, columnspan=7, sticky="ew", padx=5)




ttk.Label(top_frame, text="Çıkış Klasörü").grid(row=1, column=0, sticky="w")
ttk.Entry(top_frame, textvariable=output_dir).grid(row=1, column=1,columnspan=3, sticky="ew", padx=5)
ttk.Button(top_frame, text="📁", command=choose_folder).grid(row=1, column=4)

ttk.Button(top_frame, text="📂 Klasörü Aç", command=open_output_folder).grid(row=1, column=5, padx=5)
ttk.Button(top_frame, text="▶️ İNDİR", command=start_download).grid(row=1, column=6, padx=5)
ttk.Button(top_frame, text="⏹️ DURDUR", command=stop_download).grid(row=1, column=7, padx=5)
options_frame = ttk.Frame(top_frame)
options_frame.grid(row=2, column=1, columnspan=4, sticky="w", pady=5)


ttk.Label(options_frame, text="Bitrate").pack(side="left", padx=(0, 5))

bitrate_menu = ttk.OptionMenu(
    options_frame,
    bitrate_var,
    "192",
    "128",
    "192",
    "320"
)
bitrate_menu.pack(side="left", padx=(0, 15))



## playlist mode ##
playlist_mode_var = tk.BooleanVar(value=False)  # default: tek video

playlist_checkbox = tk.Checkbutton(
    root,
    text="Playlist indir",
    variable=playlist_mode_var
)
playlist_checkbox.pack(anchor="w", padx=10, pady=5)
def on_playlist_toggle():
    if playlist_mode_var.get():
        log("⚠️ Playlist modu açık: Tüm liste indirilecek")

playlist_checkbox.config(command=on_playlist_toggle)


#####
format_var = tk.StringVar(value="mp3")

def on_format_change(*args):
    if format_var.get() == "mp4":
        bitrate_menu.configure(state="disabled")
    else:
        bitrate_menu.configure(state="normal")

format_var.trace_add("write", on_format_change)
#####
ttk.Radiobutton(
    options_frame,
    text="MP3",
    variable=format_var,
    value="mp3"
).pack(side="left", padx=2)

ttk.Radiobutton(
    options_frame,
    text="MP4",
    variable=format_var,
    value="mp4"
).pack(side="left", padx=2)

top_frame.columnconfigure(1, weight=1)
top_frame.columnconfigure(3, weight=2)


progress_frame = ttk.Frame(root)
progress_frame.pack(fill="x", padx=10, pady=(0,5))

progress_var = tk.IntVar(value=0)
progress_bar = ttk.Progressbar(
    progress_frame,
    variable=progress_var,
    maximum=100
)
progress_bar.pack(fill="x", expand=True)

def paste_from_clipboard(event=None):
    try:
        text = root.clipboard_get()
        url_entry.delete(0, tk.END)
        url_entry.insert(0, text)
    except:
        pass


url_menu = tk.Menu(root, tearoff=0)
url_menu.add_command(label="Yapıştır", command=paste_from_clipboard)
url_menu.add_command(label="Temizle", command=lambda: url_entry.delete(0, tk.END))
def show_url_menu(event):
    url_menu.tk_popup(event.x_root, event.y_root)
url_entry.bind("<Button-3>", show_url_menu)   # Windows

# ---------------- SPLIT AREA ---------------- #

main_pane = ttk.PanedWindow(root, orient=tk.VERTICAL)
main_pane.pack(fill="both", expand=True, padx=10, pady=10)

# ----------- LIST AREA ----------- #

list_frame = ttk.Frame(main_pane)
main_pane.add(list_frame, weight=3)

columns = ("Şarkı", "Durum", "Yüzde")
tree = ttk.Treeview(list_frame, columns=columns, show="headings")
tree.tag_configure("done", background="#d4f8d4")      # yeşil
tree.tag_configure("downloading", background="#fff3cd")  # sarı

for col in columns:
    tree.heading(col, text=col)
    tree.column(col, anchor="w" if col == "Şarkı" else "center")

tree.pack(side="left", fill="both", expand=True)

list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=list_scroll.set)
list_scroll.pack(side="right", fill="y")

# ----------- LOG AREA ----------- #

log_frame = ttk.Frame(main_pane)
main_pane.add(log_frame, weight=1)

log_box = tk.Text(log_frame, height=6)
log_box.pack(side="left", fill="both", expand=True)

log_scroll = ttk.Scrollbar(log_frame, command=log_box.yview)
log_box.configure(yscrollcommand=log_scroll.set)
log_scroll.pack(side="right", fill="y")


root.mainloop()
