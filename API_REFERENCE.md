# API Reference

Этот документ описывает ключевые функции и их интерфейсы для разработчиков.

## image_parser.py

### run_parser()

Основная функция для запуска парсинга CSV-файла и загрузки изображений.

```python
def run_parser(csv_path, download_dir, status_callback, progress_callback, headless=True, max_workers=MAX_WORKERS):
```

**Параметры:**
- `csv_path` (str): Путь к CSV-файлу с данными
- `download_dir` (str): Директория для сохранения загруженных изображений
- `status_callback` (callable): Колбек для обновления статуса (принимает str)
- `progress_callback` (callable): Колбек для обновления прогресса (принимает int)
- `headless` (bool, default=True): Режим headless для Selenium
- `max_workers` (int, default=MAX_WORKERS): Количество рабочих потоков

**Возвращает:** None

**Исключения:**
- FileNotFoundError: если CSV-файл не найден
- Другие: в зависимости от ошибок загрузки

### process_single_row()

Обрабатывает одну строку CSV-файла.

```python
def process_single_row(row_index, row, download_dir, status_callback, progress_callback, headless=True):
```

**Параметры:**
- `row_index` (int): Индекс строки (для логирования)
- `row` (list): Данные строки [product_url, desired_filename]
- `download_dir` (str): Директория для загрузки
- `status_callback` (callable): Колбек статуса
- `progress_callback` (callable): Колбек прогресса
- `headless` (bool): Режим headless

**Возвращает:** None

### parse_with_requests()

Быстрый парсинг через requests + BeautifulSoup.

```python
def parse_with_requests(url):
```

**Параметры:**
- `url` (str): URL страницы для парсинга

**Возвращает:** str или None - URL изображения

### parse_with_selenium()

Парсинг через Selenium (fallback для сложных сайтов).

```python
def parse_with_selenium(url, headless=True):
```

**Параметры:**
- `url` (str): URL страницы
- `headless` (bool): Headless режим

**Возвращает:** str или None - URL изображения

## web-parser/app.py

### Flask Routes

#### GET /
Возвращает главную страницу с формой загрузки.

**Возвращает:** HTML template (index.html)

#### POST /upload
Обрабатывает загруженный CSV-файл и запускает парсинг.

**Параметры:**
- `file` (FormData): CSV-файл через multipart/form-data

**Возвращает:** 
- Успех: JSON с сообщением об успехе
- Ошибка: JSON с описанием ошибки (статус 400)

## Константы и настройки

### DOMAIN_SELECTORS
```python
DOMAIN_SELECTORS = {
    'domain.com': [
        {'selector': 'img.product-image', 'attr': 'src'},
        # ...
    ]
}
```

Словарь селекторов для каждого домена.

### MAX_WORKERS
```python
MAX_WORKERS = 5
```

Максимальное количество рабочих потоков по умолчанию.

## Колбеки

### Status Callback
```python
def status_callback(message: str) -> None:
    """Обновление статуса выполнения"""
    pass
```

### Progress Callback
```python
def progress_callback(completed_count: int) -> None:
    """Обновление количества завершенных задач"""
    pass
```

## Формат CSV

```
https://example.com/product1,image1.jpg
https://example.com/product2,image2.png
```

- Без заголовка
- 2 колонки: URL товара, желаемое имя файла
- Кодировка: UTF-8 (BOM)

## Ошибки и обработка

- Сетевые ошибки: повторные попытки через requests
- Selenium ошибки: логирование и пропуск
- Файловые ошибки: создание директорий при необходимости
- CSV ошибки: валидация строк, пропуск невалидных

## Логирование

Система использует стандартный Python logging. Логи включают:
- Информацию о загруженных изображениях
- Ошибки парсинга и загрузки
- Статистику выполнения

## Использование в коде

```python
# Основное использование
from image_parser import run_parser

def status_cb(msg):
    print(f"Status: {msg}")

def progress_cb(count):
    print(f"Completed: {count}")

run_parser(
    csv_path="data.csv",
    download_dir="./images",
    status_callback=status_cb,
    progress_callback=progress_cb,
    headless=True,
    max_workers=3
)
```