from flask import Flask, render_template, request, redirect, url_for, flash
import os
import sys
import threading

# Добавляем родительскую директорию в путь, чтобы импортировать image_parser
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from image_parser import run_parser

app = Flask(__name__)
app.secret_key = 'supersecretkey'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and file.filename.endswith('.csv'):
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)
        
        download_dir = os.path.join(os.path.dirname(__file__), '..', 'downloaded_images')
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        try:
            # Запускаем парсер в отдельном потоке, чтобы не блокировать веб-сервер
            # В будущем здесь можно будет реализовать более сложную систему статусов (например, с Celery)
            parser_thread = threading.Thread(
                target=run_parser, 
                args=(filename, download_dir, None, None, True, 4)
            )
            parser_thread.start()

            flash(f'Файл {file.filename} успешно загружен. Парсинг запущен в фоновом режиме. Изображения будут сохранены в папку downloaded_images.')
        except Exception as e:
            flash(f'Произошла ошибка при запуске парсера: {e}')
        
        return redirect(url_for('index'))
    else:
        flash('Only .csv files are allowed')
        return redirect(request.url)

if __name__ == '__main__':
    app.run(debug=True)