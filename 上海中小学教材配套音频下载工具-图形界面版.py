import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import threading
import queue
import requests
import os
import re
import locale
import sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote

# --- Platform-specific command key for shortcuts ---
cmd_key = "Command" if sys.platform == "darwin" else "Control"

# ==============================================================================
#  LANGUAGE TRANSLATIONS & FOLDER FORMATS
# ==============================================================================
LANG = {
    'en': {
        'title': "SHEDU Audio Downloader", 'inputs_frame': "Inputs", 'codes_label': "Codes:",
        'options_frame': "Options", 'target_dir_label': "Target Dir:", 'browse_button': "Browse...",
        'folder_format_label': "Sort into folders:", 'silent_check': "Hide download progress",
        'log_frame': "Log", 'get_urls_button': "Get URLs", 'download_button': "Get & Download",
        'msg_enter_code': "Please enter at least one code.",
        'msg_invalid_code': "Warning: '{code}' is not a valid 8-digit number. Skipping.",
        'msg_no_links': "No .shtml links found for this code.", 'msg_no_title': "No title found",
        'msg_download_failed': "  -> Download failed: {e}", 'msg_file_error': "  -> File error: {e}",
        'msg_request_error': "An error occurred for code {code}: {e}",
        'progress_label': "Downloading: {filename}", 'download_complete': " ✔️ Download complete: {filename}",
        'folder_formats': {
            'No sub-folder (default)': 'n', '{code}-{title}': 'ct', '{code}': 'c',
            '{title}': 't', '{title}-{code}': 'tc'
        },
        'menu_cut': "Cut", 'menu_copy': "Copy", 'menu_paste': "Paste", 'menu_delete': "Delete"
    },
    'zh': {
        'title': "上海中小学教材配套音频下载工具", 'inputs_frame': "输入", 'codes_label': "提取码:",
        'options_frame': "选项", 'target_dir_label': "目标文件夹:", 'browse_button': "浏览...",
        'folder_format_label': "按照文件夹分类:", 'silent_check': "隐藏下载进度",
        'log_frame': "日志", 'get_urls_button': "获取网址", 'download_button': "获取并下载",
        'msg_enter_code': "请输入至少一个提取码。",
        'msg_invalid_code': "警告: '{code}' 不是一个有效的8位数字。已跳过。",
        'msg_no_links': "未能为此提取码找到 .shtml 链接。", 'msg_no_title': "未找到标题",
        'msg_download_failed': "  -> 下载失败: {e}", 'msg_file_error': "  -> 文件错误: {e}",
        'msg_request_error': "处理提取码 {code} 时发生错误: {e}",
        'progress_label': "正在下载: {filename}", 'download_complete': " ✔️ 下载完成: {filename}",
        'folder_formats': {
            '不进行分类 (默认)': 'n', '{提取码}-{标题}': 'ct', '{提取码}': 'c',
            '{标题}': 't', '{标题}-{提取码}': 'tc'
        },
        'menu_cut': "剪切", 'menu_copy': "复制", 'menu_paste': "粘贴", 'menu_delete': "删除"
    }
}

# ==============================================================================
#  CORE LOGIC
# ==============================================================================

def sanitize_filename(name):
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    sanitized = re.sub(r'__+', '_', sanitized)
    return sanitized.strip(' _')

def download_file(url, base_dir, folder_format, code, title, silent, output_queue, lang):
    sub_folder = ""
    if folder_format == 'ct': sub_folder = f"{code}-{title}"
    elif folder_format == 'c': sub_folder = code
    elif folder_format == 't': sub_folder = title
    elif folder_format == 'tc': sub_folder = f"{title}-{code}"
    safe_sub_folder = sanitize_filename(sub_folder)
    download_path = os.path.join(base_dir, safe_sub_folder)
    os.makedirs(download_path, exist_ok=True)
    try:
        with requests.get(url, stream=True, timeout=20) as r:
            r.raise_for_status()
            filename = unquote(r.url.split('/')[-1])
            if "content-disposition" in r.headers:
                match = re.search(r'filename="?([^"]+)"?', r.headers['content-disposition'])
                if match: filename = unquote(match.group(1))
            file_path = os.path.join(download_path, sanitize_filename(filename))
            total_size = int(r.headers.get('content-length', 0))
            
            downloaded_bytes = 0
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        # Send progress data to the queue instead of using tqdm
                        if not silent:
                            progress_data = {'downloaded': downloaded_bytes, 'total': total_size, 'filename': filename}
                            output_queue.put(('progress', progress_data))
        
        output_queue.put(('log', LANG[lang]['download_complete'].format(filename=filename)))

    except Exception as e:
        output_queue.put(('error', LANG[lang]['msg_download_failed'].format(e=e)))

def fetch_and_parse_logic(code, should_download, options, output_queue):
    lang = options['lang']
    base_url = "https://mp3.bookmall.com.cn"
    target_url = f"{base_url}/book/access.action"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko"}
    payload = {"code": code}
    try:
        response = requests.post(target_url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.select_one('dl.EnglishBox dd h5').get_text(strip=True) if soup.select_one('dl.EnglishBox dd h5') else LANG[lang]['msg_no_title']
        output_queue.put(('title', code)); output_queue.put(('title', title))
        shtml_links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.shtml')]
        if not shtml_links: output_queue.put(('warning', LANG[lang]['msg_no_links'])); return
        for link in shtml_links:
            full_url = urljoin(base_url, link)
            output_queue.put(('url', full_url))
            if should_download:
                download_file(full_url, options['target_dir'], options['folder_format'], code, title, options['silent'], output_queue, lang)
    except Exception as e:
        output_queue.put(('error', LANG[lang]['msg_request_error'].format(code=code, e=e)))

# ==============================================================================
#  GUI APPLICATION CLASS
# ==============================================================================

class App:
    def __init__(self, root, initial_lang):
        self.root = root
        self.queue = queue.Queue()
        self.lang_var = tk.StringVar(value=initial_lang)
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        lang_frame = ttk.Frame(main_frame)
        lang_frame.pack(fill=tk.X, expand=False, pady=(0, 10))
        ttk.Radiobutton(lang_frame, text="English", variable=self.lang_var, value='en', command=self.update_language).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(lang_frame, text="简体中文", variable=self.lang_var, value='zh', command=self.update_language).pack(side=tk.LEFT, padx=5)
        self.input_frame = ttk.LabelFrame(main_frame, padding="10")
        self.input_frame.pack(fill=tk.X, expand=False)
        self.input_frame.columnconfigure(1, weight=1)
        self.codes_label = ttk.Label(self.input_frame)
        self.codes_label.grid(row=0, column=0, sticky="nw", padx=5, pady=5)
        self.codes_text = scrolledtext.ScrolledText(self.input_frame, height=8, width=40)
        self.codes_text.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        self.options_frame = ttk.LabelFrame(main_frame, padding="10")
        self.options_frame.pack(fill=tk.X, expand=False, pady=10)
        self.options_frame.columnconfigure(1, weight=1)
        self.target_dir_label = ttk.Label(self.options_frame)
        self.target_dir_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.target_dir_var = tk.StringVar(value=os.getcwd())
        self.target_dir_entry = ttk.Entry(self.options_frame, textvariable=self.target_dir_var)
        self.target_dir_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.browse_button = ttk.Button(self.options_frame, command=self.browse_directory)
        self.browse_button.grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.folder_format_label = ttk.Label(self.options_frame)
        self.folder_format_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.folder_format_var = tk.StringVar()
        self.folder_format_combo = ttk.Combobox(self.options_frame, textvariable=self.folder_format_var, state="readonly")
        self.folder_format_combo.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.silent_var = tk.BooleanVar(value=False)
        self.silent_check = ttk.Checkbutton(self.options_frame, variable=self.silent_var)
        self.silent_check.grid(row=1, column=2, sticky="w", padx=10, pady=5)
        
        # --- NEW: Progress Bar ---
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_label = ttk.Label(self.progress_frame, text="", anchor="w")
        self.progress_label.pack(fill=tk.X, expand=True, pady=(0,2))
        self.progress_bar = ttk.Progressbar(self.progress_frame, orient='horizontal', mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True)

        self.button_frame = ttk.Frame(main_frame)
        self.button_frame.pack(fill=tk.X, expand=False, pady=5)
        self.get_urls_button = ttk.Button(self.button_frame, command=lambda: self.start_task(download=False))
        self.get_urls_button.pack(side=tk.RIGHT, padx=5)
        self.download_button = ttk.Button(self.button_frame, command=lambda: self.start_task(download=True))
        self.download_button.pack(side=tk.RIGHT, padx=5)
        self.log_frame = ttk.LabelFrame(main_frame, padding="10")
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(self.log_frame, state='disabled', wrap=tk.WORD, bg="black")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_config('title', foreground='lightgreen'); self.log_text.tag_config('url', foreground='cyan')
        self.log_text.tag_config('warning', foreground='yellow'); self.log_text.tag_config('error', foreground='red')
        self.log_text.tag_config('separator', foreground='lightcoral'); self.log_text.tag_config('log', foreground='white')
        
        self.create_context_menus()
        self.update_language()
        self.process_queue()

    def create_context_menus(self):
        self.code_menu = tk.Menu(self.root, tearoff=0)
        self.log_menu = tk.Menu(self.root, tearoff=0)
        self.codes_text.bind("<Button-2>" if sys.platform == "darwin" else "<Button-3>", self.show_code_menu)
        self.log_text.bind("<Button-2>" if sys.platform == "darwin" else "<Button-3>", self.show_log_menu)

    def show_code_menu(self, event):
        has_selection = bool(self.codes_text.tag_ranges("sel"))
        lang, d = self.lang_var.get(), LANG[self.lang_var.get()]
        self.code_menu.entryconfig(d['menu_cut'], state=tk.NORMAL if has_selection else tk.DISABLED)
        self.code_menu.entryconfig(d['menu_copy'], state=tk.NORMAL if has_selection else tk.DISABLED)
        self.code_menu.entryconfig(d['menu_delete'], state=tk.NORMAL if has_selection else tk.DISABLED)
        try: self.code_menu.entryconfig(d['menu_paste'], state=tk.NORMAL if self.root.clipboard_get() else tk.DISABLED)
        except tk.TclError: self.code_menu.entryconfig(d['menu_paste'], state=tk.DISABLED)
        self.code_menu.post(event.x_root, event.y_root)

    def show_log_menu(self, event):
        has_selection = bool(self.log_text.tag_ranges("sel"))
        self.log_menu.entryconfig(LANG[self.lang_var.get()]['menu_copy'], state=tk.NORMAL if has_selection else tk.DISABLED)
        self.log_menu.post(event.x_root, event.y_root)
        
    def delete_selection(self, widget):
        if widget.tag_ranges("sel"): widget.delete("sel.first", "sel.last")

    def update_language(self):
        lang = self.lang_var.get()
        d = LANG[lang]
        self.root.title(d['title'])
        self.input_frame.config(text=d['inputs_frame']); self.codes_label.config(text=d['codes_label'])
        self.options_frame.config(text=d['options_frame']); self.target_dir_label.config(text=d['target_dir_label'])
        self.browse_button.config(text=d['browse_button']); self.folder_format_label.config(text=d['folder_format_label'])
        self.silent_check.config(text=d['silent_check']); self.log_frame.config(text=d['log_frame'])
        self.get_urls_button.config(text=d['get_urls_button']); self.download_button.config(text=d['download_button'])
        self.code_menu.delete(0, tk.END)
        self.code_menu.add_command(label=d['menu_cut'], accelerator=f"{cmd_key}+X", command=lambda: self.codes_text.event_generate("<<Cut>>"))
        self.code_menu.add_command(label=d['menu_copy'], accelerator=f"{cmd_key}+C", command=lambda: self.codes_text.event_generate("<<Copy>>"))
        self.code_menu.add_command(label=d['menu_paste'], accelerator=f"{cmd_key}+V", command=lambda: self.codes_text.event_generate("<<Paste>>"))
        self.code_menu.add_separator()
        self.code_menu.add_command(label=d['menu_delete'], command=lambda: self.delete_selection(self.codes_text))
        self.log_menu.delete(0, tk.END)
        self.log_menu.add_command(label=d['menu_copy'], accelerator=f"{cmd_key}+C", command=lambda: self.log_text.event_generate("<<Copy>>"))
        folder_formats = d['folder_formats']
        self.folder_format_combo['values'] = list(folder_formats.keys())
        self.folder_format_var.set(list(folder_formats.keys())[0])

    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory: self.target_dir_var.set(directory)

    def log_message(self, message, tag=None):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message + '\n', tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')
        
    def start_task(self, download=False):
        raw_codes = self.codes_text.get("1.0", tk.END).strip()
        lang = self.lang_var.get()
        if not raw_codes: self.log_message(LANG[lang]['msg_enter_code'], "error"); return
        codes = re.split(r'[,\s\n]+', raw_codes)
        unique_codes = sorted(list(set(filter(None, codes))))
        descriptive_selection = self.folder_format_var.get()
        folder_format_code = LANG[lang]['folder_formats'][descriptive_selection]
        options = {'target_dir': self.target_dir_var.get(), 'folder_format': folder_format_code, 'silent': self.silent_var.get(), 'lang': lang}
        self.log_text.configure(state='normal'); self.log_text.delete('1.0', tk.END); self.log_text.configure(state='disabled')
        self.get_urls_button.config(state='disabled'); self.download_button.config(state='disabled')
        
        if download and not options['silent']:
            self.progress_frame.pack(fill=tk.X, expand=False, pady=(0,5))
        
        threading.Thread(target=self.worker_thread, args=(unique_codes, download, options), daemon=True).start()

    def worker_thread(self, codes, download, options):
        lang = options['lang']
        for i, code in enumerate(codes):
            if not (code.isdigit() and len(code) == 8):
                self.queue.put(('warning', LANG[lang]['msg_invalid_code'].format(code=code))); continue
            fetch_and_parse_logic(code, download, options, self.queue)
            if i < len(codes) - 1: self.queue.put(('separator', '--------'))
        self.queue.put(('finish', None))

    def process_queue(self):
        try:
            msg_type, msg_content = self.queue.get_nowait()
            if msg_type == 'progress':
                data = msg_content
                if data['total'] > 0:
                    percentage = (data['downloaded'] / data['total']) * 100
                    self.progress_bar['value'] = percentage
                    self.progress_label['text'] = LANG[self.lang_var.get()]['progress_label'].format(filename=data['filename'])
                else: # Handle cases where total size is unknown
                    self.progress_bar.config(mode='indeterminate')
                    self.progress_bar.start()
            elif msg_type == 'finish':
                self.get_urls_button.config(state='normal'); self.download_button.config(state='normal')
                self.progress_frame.pack_forget() # Hide progress bar when all tasks are done
                self.progress_bar.config(mode='determinate'); self.progress_bar['value'] = 0
            else:
                self.log_message(msg_content, msg_type)
        except queue.Empty: pass
        finally:
            self.root.after(100, self.process_queue)

if __name__ == "__main__":
    initial_lang = 'en'
    try:
        default_locale, _ = locale.getdefaultlocale()
        if default_locale and default_locale.lower().startswith(('zh_cn', 'zh_sg')): initial_lang = 'zh'
    except Exception: pass
    root = tk.Tk()
    app = App(root, initial_lang)
    root.mainloop()