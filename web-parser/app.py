from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
import os
import sys
import threading
import uuid
import zipfile
import shutil
from datetime import datetime
import logging
import io

# Добавляем родительскую директорию в путь, чтобы импортировать image_parser
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from image_parser import run_parser

app = Flask(__name__)

# Конфигурация из переменных окружения
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 50 * 1024 * 1024))  # 50MB
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', 4))
SELENIUM_HEADLESS = os.environ.get('SELENIUM_HEADLESS', 'true').lower() == 'true'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание необходимых директорий
for folder in [UPLOAD_FOLDER, 'downloads', 'temp']:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Глобальное хранилище статусов задач (в продакшене лучше использовать Redis)
jobs = {}

class JobStatus:
    def __init__(self, job_id, filename):
        self.job_id = job_id
        self.filename = filename
        self.status = 'starting'  # starting, running, completed, failed
        self.progress = {'completed': 0, 'total': 0}
        self.messages = []
        self.created_at = datetime.now()
        self.download_path = None
        self.zip_path = None

def create_job(filename):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = JobStatus(job_id, filename)
    logger.info(f"Создана задача {job_id} для файла {filename}")
    return job_id

def status_callback(job_id):
    def callback(message):
        if job_id in jobs:
            jobs[job_id].messages.append(f"{datetime.now().strftime('%H:%M:%S')}: {message}")
            logger.info(f"[{job_id}] {message}")
    return callback

def progress_callback(job_id):
    def callback(*args):
        # Поддержка вызовов progress_callback(completed) и progress_callback(completed, total)
        if len(args) == 1:
            completed, total = args[0], jobs.get(job_id, JobStatus(job_id, '')).progress.get('total', 0)
        elif len(args) >= 2:
            completed, total = args[0], args[1]
        else:
            completed, total = 0, 0
        if job_id in jobs:
            jobs[job_id].progress = {'completed': int(completed), 'total': int(total)}
            if completed > 0 and jobs[job_id].status == 'starting':
                jobs[job_id].status = 'running'
    return callback

def create_zip_archive(job_id, download_dir):
    """Создает ZIP архив со скачанными изображениями"""
    try:
        zip_filename = f"images_{job_id}.zip"
        zip_path = os.path.join('downloads', zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(download_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, download_dir)
                    zipf.write(file_path, arcname)
        
        if job_id in jobs:
            jobs[job_id].zip_path = zip_path
        
        logger.info(f"Создан ZIP архив: {zip_path}")
        return zip_path
    except Exception as e:
        logger.error(f"Ошибка создания ZIP архива: {e}")
        return None

def cleanup_job_files(job_id):
    """Очистка временных файлов задачи"""
    try:
        if job_id in jobs:
            job = jobs[job_id]
            # Удаляем папку скачанных изображений
            if job.download_path and os.path.exists(job.download_path):
                shutil.rmtree(job.download_path)
    except Exception as e:
        logger.error(f"Ошибка очистки файлов для задачи {job_id}: {e}")

def run_parser_async(job_id, csv_path, download_dir):
    """Асинхронный запуск парсера с обновлением статуса"""
    try:
        jobs[job_id].status = 'running'
        jobs[job_id].download_path = download_dir
        
        # Запуск парсера
        completed, success, errors = run_parser(
            csv_path=csv_path,
            download_dir=download_dir,
            status_callback=status_callback(job_id),
            progress_callback=progress_callback(job_id),
            headless=SELENIUM_HEADLESS,
            max_workers=MAX_WORKERS
        )
        
        # Создание ZIP архива
        if success > 0:
            zip_path = create_zip_archive(job_id, download_dir)
            if zip_path:
                jobs[job_id].status = 'completed'
                jobs[job_id].messages.append(f"Завершено: {success} успешно, {errors} ошибок")
            else:
                jobs[job_id].status = 'failed'
                jobs[job_id].messages.append("Ошибка создания ZIP архива")
        else:
            jobs[job_id].status = 'failed'
            jobs[job_id].messages.append("Не удалось скачать ни одного изображения")
            
    except Exception as e:
        jobs[job_id].status = 'failed'
        jobs[job_id].messages.append(f"Критическая ошибка: {str(e)}")
        logger.error(f"Ошибка в задаче {job_id}: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('Файл не выбран')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран')
        return redirect(request.url)
        
    if not file.filename.endswith('.csv'):
        flash('Разрешены только CSV файлы')
        return redirect(request.url)
    
    try:
        # Создание задачи
        job_id = create_job(file.filename)
        
        # Сохранение файла
        filename = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{file.filename}")
        file.save(filename)
        
        # Создание директории для скачивания
        download_dir = os.path.join('temp', f'job_{job_id}')
        os.makedirs(download_dir, exist_ok=True)
        
        # Запуск парсера в отдельном потоке
        parser_thread = threading.Thread(
            target=run_parser_async,
            args=(job_id, filename, download_dir)
        )
        parser_thread.daemon = True
        parser_thread.start()
        
        flash(f'Файл загружен! ID задачи: {job_id}')
        return redirect(url_for('job_status', job_id=job_id))
        
    except Exception as e:
        flash(f'Ошибка загрузки файла: {str(e)}')
        return redirect(request.url)

@app.route('/status/<job_id>')
def job_status(job_id):
    if job_id not in jobs:
        flash('Задача не найдена')
        return redirect(url_for('index'))
    
    job = jobs[job_id]
    return render_template('status.html', job=job)

@app.route('/api/status/<job_id>')
def api_job_status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = jobs[job_id]
    return jsonify({
        'job_id': job.job_id,
        'status': job.status,
        'progress': job.progress,
        'messages': job.messages[-10:],  # Последние 10 сообщений
        'download_ready': job.zip_path is not None and os.path.exists(job.zip_path)
    })

@app.route('/download/<job_id>')
def download_result(job_id):
    if job_id not in jobs:
        flash('Задача не найдена')
        return redirect(url_for('index'))
    
    job = jobs[job_id]
    if job.status != 'completed' or not job.zip_path or not os.path.exists(job.zip_path):
        flash('Файл для скачивания не готов')
        return redirect(url_for('job_status', job_id=job_id))
    
    try:
        return send_file(
            job.zip_path,
            as_attachment=True,
            download_name=f"images_{job.filename}_{job_id}.zip",
            mimetype='application/zip'
        )
    except Exception as e:
        flash(f'Ошибка скачивания: {str(e)}')
        return redirect(url_for('job_status', job_id=job_id))

@app.route('/cleanup/<job_id>', methods=['POST'])
def cleanup_job(job_id):
    if job_id in jobs:
        cleanup_job_files(job_id)
        del jobs[job_id]
        flash('Задача удалена')
    return redirect(url_for('index'))

@app.route('/logs/<job_id>')
def download_logs(job_id):
    """Скачать логи задачи в txt формате с фильтрацией:
    1) Если сохранение успешно — только строка с URL и названием из CSV
    2) Если ошибка — полный блок логов для соответствующей строки + URL и название из CSV
    """
    if job_id not in jobs:
        flash('Задача не найдена')
        return redirect(url_for('index'))

    job = jobs[job_id]

    # Группируем сообщения по блокам обработки строк, начиная с "PROCESS_ROW: Начало обработки URL: ..."
    sections = []
    current = { 'header': None, 'url': None, 'filename': None, 'lines': [] }

    for entry in job.messages:
        # entry вида: "HH:MM:SS: message"
        ts, sep, text = entry.partition(': ')
        msg_text = text if sep else entry

        if "PROCESS_ROW: Начало обработки URL:" in msg_text:
            # Сохраняем предыдущий блок, если был
            if current['header'] is not None or current['lines']:
                sections.append(current)
            # Начинаем новый блок
            current = { 'header': entry, 'url': None, 'filename': None, 'lines': [entry] }
            # Парсим URL и имя файла из стартовой строки
            try:
                url_marker = "URL: "
                name_marker = ", Имя файла: "
                ustart = msg_text.find(url_marker)
                nstart = msg_text.find(name_marker)
                if ustart != -1 and nstart != -1:
                    url = msg_text[ustart + len(url_marker): nstart]
                    filename = msg_text[nstart + len(name_marker):]
                    current['url'] = url.strip()
                    current['filename'] = filename.strip()
            except Exception:
                pass
        else:
            # Обычная строка лога текущего блока
            current['lines'].append(entry)

    # Добавляем финальный блок
    if current['header'] is not None or current['lines']:
        sections.append(current)

    # Формируем отфильтрованный вывод
    out_lines = [
        f"Job ID: {job.job_id}",
        f"Filename: {job.filename}",
        f"Created at: {job.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "Messages:",
    ]

    for sec in sections:
        # Определяем успешность: ищем в блоке строку с "успешен:" и "Изображение успешно сохранено как:"
        success = False
        for entry in sec['lines']:
            _ts, _sep, t = entry.partition(': ')
            t = t if _sep else entry
            if ("успешен:" in t) and ("Изображение успешно сохранено как:" in t):
                success = True
                break

        url = sec.get('url') or ''
        filename = sec.get('filename') or ''

        if success:
            # Только одна строка-резюме с оригинальным URL и названием из CSV
            out_lines.append(f"УСПЕХ: {url} -> {filename}")
        else:
            # Ошибка/неуспех: добавляем заголовок и полный блок логов
            if url or filename:
                out_lines.append(f"ОШИБКА: {url} -> {filename}")
            out_lines.extend(sec['lines'])
        out_lines.append("")  # пустая строка между блоками

    content = "\n".join(out_lines) + "\n"
    buf = io.BytesIO(content.encode('utf-8'))
    return send_file(buf, as_attachment=True, download_name=f"logs_{job.job_id}.txt", mimetype='text/plain')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)