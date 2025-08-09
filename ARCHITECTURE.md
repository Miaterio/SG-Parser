# Архитектура SuperGra Parser

## Общий обзор

SuperGra Parser - это гибридный парсер изображений, разработанный для автоматического скачивания изображений товаров с украинских интернет-магазинов. Проект использует двухуровневый подход: быстрый парсинг через HTTP-запросы и резервный метод через автоматизацию браузера.

## Архитектурные компоненты

### 1. Core Engine (`image_parser.py`)
**Назначение**: Основная логика парсинга и скачивания
**Ключевые функции**:
- `run_parser()` - главная функция оркестрации
- `process_single_row()` - обработка отдельного URL
- `parse_with_requests()` - быстрый парсинг
- `parse_with_selenium()` - резервный метод

### 2. Web Interface (`web-parser/`)
**Назначение**: Веб-интерфейс для загрузки CSV и запуска парсинга
**Компоненты**:
- `app.py` - Flask приложение
- `templates/index.html` - пользовательский интерфейс
- `Procfile` - конфигурация для деплоя

### 3. Configuration System
**Конфигурационные файлы**:
- `requirements.txt` - зависимости Python
- `DOMAIN_SELECTORS` - CSS селекторы для каждого сайта
- Environment variables (в будущем)

## Поток данных

```
CSV File → Upload → Parse Rows → Process URLs → Download Images
    ↓           ↓         ↓            ↓              ↓
[Manual]   [Web UI]  [Validation]  [Multi-method]  [Local Storage]
```

### Детальный поток:

1. **Входные данные**: CSV файл с URL и именами файлов
2. **Валидация**: Проверка формата CSV и URL
3. **Распределение задач**: ThreadPoolExecutor для параллельной обработки
4. **Парсинг изображений**:
   - Попытка 1: requests + BeautifulSoup (быстро)
   - Попытка 2: Selenium WebDriver (для JS-сайтов)
5. **Скачивание**: HTTP скачивание с retry логикой
6. **Сохранение**: Локальное сохранение с обработкой ошибок

## Формат CSV

```csv
URL,Filename
https://example.com/product/123,image1.jpg
https://example.com/product/456,image2.png
```

- **Колонка 1**: URL товара
- **Колонка 2**: Имя файла для сохранения
- **Формат**: UTF-8 с запятыми как разделители

## Технические решения

### Стратегии парсинга (по приоритету):
1. **Schema.org** - структурированные данные продуктов
2. **OpenGraph** - og:image мета-теги  
3. **CSS селекторы** - специфичные для каждого домена
4. **Fallback Selenium** - для JS-зависимых сайтов

### Оптимизация изображений:
- Выбор наибольшего разрешения из srcset
- Улучшение URL (замена размеров на максимальные)
- Фильтрация недействительных форматов

### Многопоточность:
- ThreadPoolExecutor с настраиваемым количеством потоков
- Безопасный доступ к общим ресурсам
- Callback система для прогресса

## Взаимодействие модулей

```
image_parser.py (Core)
├── Domain Selectors (Configuration)
├── Multi-threading (ThreadPoolExecutor)  
├── HTTP Client (requests/urllib3)
├── HTML Parser (BeautifulSoup)
├── Browser Automation (Selenium)
└── File I/O (os/shutil)

web-parser/ (Interface)
├── Flask App (app.py)
├── File Upload (werkzeug)
├── Template Engine (Jinja2)
└── Background Tasks (threading)
```

## Точки расширения

### 1. Новые домены
- Добавление в `DOMAIN_SELECTORS`
- Тестирование селекторов
- Документирование специфики

### 2. Дополнительные форматы
- Расширение валидации CSV
- Поддержка Excel/JSON
- Batch processing

### 3. API интеграция
- REST API endpoints
- Аутентификация
- Rate limiting

## Потенциальные проблемы продакшена

### 1. Selenium в контейнерах
- **Проблема**: Chrome/Chromium зависимости
- **Решение**: Docker с pre-installed Chrome

### 2. Масштабирование
- **Проблема**: Memory/CPU ограничения
- **Решение**: Queue systems (Celery/RQ)

### 3. Rate limiting
- **Проблема**: Блокировка IP сайтами
- **Решение**: Proxy ротация, задержки

### 4. Storage
- **Проблема**: Локальное сохранение файлов
- **Решение**: Cloud storage (S3/GCS)

## Рекомендации

### Для разработки:
1. Использовать виртуальное окружение
2. Тестировать на ограниченной выборке
3. Мониторить использование ресурсов

### Для продакшена:
1. Docker контейнеризация
2. Environment-based configuration
3. Централизованное логирование
4. Health checks и мониторинг

## Будущие изменения

### Краткосрочные (1-2 месяца):
- ZIP архивация результатов
- Job ID система для отслеживания
- Улучшенный веб-интерфейс
- Docker образ

### Долгосрочные (6+ месяцев):
- Microservices архитектура
- API-first подход  
- Database integration
- Analytics dashboard