import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import os

# --- Попытка импорта из локального файла с более широкой обработкой ошибок ---
try:
    # Импортируем необходимые компоненты из image_parser
    from image_parser import run_parser, DEFAULT_CSV_FILE_PATH, DEFAULT_DOWNLOAD_FOLDER, MAX_WORKERS
    # Убедимся, что импорт прошел успешно
    _parser_module_loaded = True
except Exception as e:
    # Если произошла ЛЮБАЯ ошибка при импорте image_parser (синтаксическая, NameError и т.д.)
    _parser_module_loaded = False
    _import_error_message = f"Не удалось загрузить модуль парсера image_parser.py:\n{e}\nУбедитесь, что файл существует, не содержит синтаксических ошибок и все необходимые библиотеки (requests, beautifulsoup4, selenium) установлены."
    print(_import_error_message) # Также выведем в консоль

    # Определяем заглушки, чтобы GUI мог запуститься, но парсинг не будет работать
    DEFAULT_CSV_FILE_PATH = ""
    DEFAULT_DOWNLOAD_FOLDER = ""
    MAX_WORKERS = 1 # Заглушка для настройки

    # Определяем заглушку для функции run_parser
    def run_parser(*args, **kwargs):
        print("Функция run_parser не загружена из-за ошибки импорта!")
        if 'status_callback' in kwargs and callable(kwargs['status_callback']):
            kwargs['status_callback']("КРИТИЧЕСКАЯ ОШИБКА: Модуль парсера не загружен. См. сообщение выше.")
        return 0, 0, 0


class ImageParserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Парсер изображений")
        self.root.geometry("600x600") # Увеличим немного размер окна

        # Переменные для хранения путей и настроек
        self.csv_file_path = tk.StringVar(value=DEFAULT_CSV_FILE_PATH)
        self.download_dir_path = tk.StringVar(value=DEFAULT_DOWNLOAD_FOLDER)
        self.headless_mode = tk.BooleanVar(value=True) # Переменная для состояния чекбокса, по умолчанию True (фоновый режим)
        self.max_workers = tk.IntVar(value=MAX_WORKERS) # Переменная для количества потоков

        # --- Фрейм для выбора файлов ---
        file_frame = ttk.LabelFrame(root, text="Настройки путей", padding="10")
        file_frame.pack(padx=10, pady=10, fill="x")

        # CSV файл
        ttk.Label(file_frame, text="CSV файл:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.csv_entry = ttk.Entry(file_frame, textvariable=self.csv_file_path, width=50)
        self.csv_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.csv_button = ttk.Button(file_frame, text="Обзор...", command=self.browse_csv)
        self.csv_button.grid(row=0, column=2, padx=5, pady=5)

        # Папка для загрузки
        ttk.Label(file_frame, text="Папка загрузки:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.dir_entry = ttk.Entry(file_frame, textvariable=self.download_dir_path, width=50)
        self.dir_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.dir_button = ttk.Button(file_frame, text="Обзор...", command=self.browse_dir)
        self.dir_button.grid(row=1, column=2, padx=5, pady=5)

        file_frame.columnconfigure(1, weight=1) # Позволяет полю ввода растягиваться

        # --- Фрейм для настроек парсинга ---
        settings_frame = ttk.LabelFrame(root, text="Настройки парсинга", padding="10")
        settings_frame.pack(padx=10, pady=5, fill="x")

        # Переключатель фонового режима
        self.headless_checkbox = ttk.Checkbutton(settings_frame,
                                                 text="Запускать браузер в фоновом режиме (без окна)",
                                                 variable=self.headless_mode)
        self.headless_checkbox.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # Настройка количества потоков
        ttk.Label(settings_frame, text="Количество потоков:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.workers_spinbox = ttk.Spinbox(settings_frame, from_=1, to=16, textvariable=self.max_workers, width=5) # Ограничим до 16
        self.workers_spinbox.grid(row=1, column=1, padx=5, pady=5, sticky="w")


        # --- Кнопка запуска ---
        self.start_button = ttk.Button(root, text="Начать парсинг", command=self.start_parsing)
        self.start_button.pack(pady=10)

        # --- Фрейм для вывода логов ---
        log_frame = ttk.LabelFrame(root, text="Лог выполнения", padding="10")
        log_frame.pack(padx=10, pady=5, fill="both", expand=True)

        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, state='disabled')
        self.log_area.pack(fill="both", expand=True)

        # --- Прогресс бар и статистика ---
        status_frame = ttk.Frame(root, padding="5")
        status_frame.pack(fill="x", padx=10, pady=5)

        self.progress_bar = ttk.Progressbar(status_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.stats_label = ttk.Label(status_frame, text="Готово к запуску")
        self.stats_label.pack(side="left", padx=(10, 0)) # Изменим side и добавим отступ

        # --- Кнопка копирования логов ---
        self.copy_log_button = ttk.Button(status_frame, text="Копировать лог", command=self.copy_logs_to_clipboard, state='disabled')
        self.copy_log_button.pack(side="right")
        # --- Конец кнопки копирования ---

        # Показать сообщение об ошибке импорта, если оно есть
        if not _parser_module_loaded:
            messagebox.showerror("Ошибка запуска", _import_error_message)
            # Отключить кнопку старта, если модуль парсера не загружен
            self.start_button.config(state="disabled")


    def browse_csv(self):
        """Открывает диалог выбора CSV файла."""
        initial_dir = os.path.dirname(self.csv_file_path.get()) if self.csv_file_path.get() else os.path.expanduser("~")
        file_path = filedialog.askopenfilename(
            title="Выберите CSV файл",
            filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")],
            initialdir=initial_dir
        )
        if file_path:
            self.csv_file_path.set(file_path)

    def browse_dir(self):
        """Открывает диалог выбора папки для загрузки."""
        initial_dir = self.download_dir_path.get() if self.download_dir_path.get() else os.path.expanduser("~")
        dir_path = filedialog.askdirectory(
            title="Выберите папку для сохранения изображений",
            initialdir=initial_dir
        )
        if dir_path:
            self.download_dir_path.set(dir_path)

    def update_status(self, message):
        """Обновляет текстовое поле лога (безопасно для потоков)."""
        def _update():
            if not self.root.winfo_exists(): return # Проверяем, существует ли еще окно
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, message + "\n")
            self.log_area.see(tk.END) # Автопрокрутка вниз
            self.log_area.config(state='disabled')
        if self.root.winfo_exists():
            self.root.after(0, _update)

    def update_progress(self, current, total):
        """Обновляет прогресс-бар (безопасно для потоков)."""
        def _update():
            if not self.root.winfo_exists(): return
            if total > 0:
                percentage = int((current / total) * 100)
                self.progress_bar['value'] = percentage
                self.stats_label.config(text=f"{current}/{total} ({percentage}%)")
            else:
                self.progress_bar['value'] = 0
                self.stats_label.config(text="Нет данных для обработки")
        if self.root.winfo_exists():
            self.root.after(0, _update)

    def on_parsing_complete(self, result):
        """Вызывается после завершения парсинга."""
        if not self.root.winfo_exists(): return

        processed, success, errors = result
        self.update_status("\n===================================")
        self.update_status(f"Завершено. Обработано: {processed}, Успешно: {success}, Ошибки: {errors}")
        self.stats_label.config(text=f"Завершено! Успешно: {success}, Ошибки: {errors}")
        self.start_button.config(state="normal") # Включаем кнопку обратно
        self.copy_log_button.config(state="normal") # Включаем кнопку копирования логов

    def copy_logs_to_clipboard(self):
        """Копирует содержимое лога в буфер обмена."""
        try:
            log_content = self.log_area.get(1.0, tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(log_content)
            self.update_status("Лог скопирован в буфер обмена.") # Сообщение в лог
            # Можно добавить временное сообщение рядом с кнопкой, если нужно
            # self.stats_label.config(text="Лог скопирован!")
            # self.root.after(2000, lambda: self.stats_label.config(text=f"Завершено! ...")) # Восстановить старый текст
        except Exception as e:
            messagebox.showerror("Ошибка копирования", f"Не удалось скопировать лог:\n{e}")

    def start_parsing(self):
        """Запускает процесс парсинга в отдельном потоке."""
        # Проверяем, загружен ли модуль парсера
        if not _parser_module_loaded:
             messagebox.showerror("Ошибка запуска", "Модуль парсера не загружен. Исправьте ошибки и перезапустите программу.")
             return

        csv_path = self.csv_file_path.get()
        download_dir = self.download_dir_path.get()
        headless = self.headless_mode.get() # Получаем состояние чекбокса
        max_workers = self.max_workers.get() # Получаем количество потоков

        if not csv_path or not os.path.isfile(csv_path):
            messagebox.showerror("Ошибка", f"CSV файл не найден или путь не указан:\n{csv_path}")
            return
        if not download_dir:
            messagebox.showerror("Ошибка", "Папка для загрузки не указана.")
            return
        if max_workers < 1:
             messagebox.showerror("Ошибка", "Количество потоков должно быть не менее 1.")
             return


        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')
        self.progress_bar['value'] = 0
        self.stats_label.config(text="Запуск...")
        self.start_button.config(state="disabled")
        self.copy_log_button.config(state="disabled") # Отключаем кнопку копирования при старте

        # Создаем и запускаем поток
        thread_csv_path = str(csv_path)
        thread_download_dir = str(download_dir)
        thread_headless = bool(headless)
        thread_max_workers = int(max_workers)


        self.parser_thread = threading.Thread(
            target=self.run_parser_thread,
            args=(thread_csv_path, thread_download_dir, thread_headless, thread_max_workers),
            daemon=True
        )
        self.parser_thread.start()

    def run_parser_thread(self, csv_path, download_dir, headless, max_workers):
        """Функция, выполняемая в отдельном потоке."""
        result = (0, 0, 0)
        try:
            if not os.path.exists(download_dir):
                try:
                    os.makedirs(download_dir)
                    self.update_status(f"Создана папка: {download_dir}")
                except OSError as e:
                    self.update_status(f"Ошибка создания папки {download_dir}: {e}")
                    self.root.after(0, self.on_parsing_complete, result)
                    return

            # Передаем настройки в run_parser
            result = run_parser(csv_path, download_dir, self.update_status, self.update_progress, headless=headless, max_workers=max_workers)

        except Exception as e:
            # Ловим любые ошибки, которые могли возникнуть в run_parser
            self.update_status(f"\nКРИТИЧЕСКАЯ ОШИБКА В ПОТОКЕ ПАРСЕРА: {e}")
            import traceback
            self.update_status(traceback.format_exc())
        finally:
            if hasattr(self, 'root') and self.root.winfo_exists():
                 self.root.after(0, self.on_parsing_complete, result)


if __name__ == "__main__":
    # Проверка существования файла image_parser.py перед запуском GUI
    # Если файл не найден или есть ошибка импорта, _parser_module_loaded будет False
    # и сообщение об ошибке будет показано в messagebox после инициализации GUI.
    root = tk.Tk()
    app = ImageParserApp(root)
    root.mainloop()