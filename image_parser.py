# -*- coding: utf-8 -*-
import csv
import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urlparse, urljoin
import time
import threading
import json
import sys
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import re
import subprocess
import shutil

# Try loading environment variables from a .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Импорт Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException as SeleniumNoSuchElementException
    _selenium_available = True
except ImportError:
    _selenium_available = False
    print("ПРЕДУПРЕЖДЕНИЕ: Библиотека Selenium не найдена. Парсинг с использованием Selenium будет недоступен.")
    # Определяем заглушки, чтобы код не падал при вызове
    class WebDriverException(Exception): pass
    class TimeoutException(Exception): pass
    class SeleniumNoSuchElementException(Exception): pass


# --- Настройки ---
DEFAULT_CSV_FILE_PATH = 'SuperGraContent Sheet1.csv' # Путь по умолчанию к вашему CSV
DEFAULT_DOWNLOAD_FOLDER = 'downloaded_images' # Папка по умолчанию для сохранения

# Укажите путь к вашему chromedriver, если он не в PATH, иначе оставьте None
# Пример: WEBDRIVER_PATH = '/path/to/your/chromedriver'
WEBDRIVER_PATH = os.environ.get('WEBDRIVER_PATH') or None
# Необязательная настройка пути к бинарнику Chrome/Chromium (например, для Heroku или Docker)
CHROME_BINARY = os.environ.get('CHROME_BINARY') or os.environ.get('GOOGLE_CHROME_BIN')
# Дополнительные аргументы для Chrome через переменную окружения, например: "--remote-debugging-port=9222 --lang=ru"
CHROME_ARGS = os.environ.get('CHROME_ARGS', '')

MAX_WORKERS = 4 # Количество потоков по умолчанию

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Windows NT 10.0; rv:115.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6312.58 Safari/537.36',
    'Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Mobile Safari/537.36',
]

BASE_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7,ru;q=0.6',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0',
    'Referer': 'https://www.google.com/', # Общий реферер
}

# --- Обновленный словарь селекторов ---
DOMAIN_SELECTORS = {
    'rozetka.com.ua': [
        'rz-gallery-main-content-image img[loading="eager"]', # <-- Новый приоритет: ищем img с loading="eager"
        'ul.simple-slider__list > li.simple-slider__item:not([data-place="mock"]):first-of-type rz-gallery-main-content-image img', # Селектор для первого элемента слайдера
        'rz-gallery-main-content-image img', # Старый приоритетный селектор
        '.main-slider__item img',           # Альтернатива внутри слайдера
        'img.picture-container__img',       # Старый селектор (на всякий случай)
        'img[alt*="Фото"]',                # Старый селектор
        '.main-slider__image img'          # Старый селектор
    ],
    'bt.rozetka.com.ua': [ # Добавлено для поддомена bt
        'rz-gallery-main-content-image img[loading="eager"]', # <-- Новый приоритет
        'ul.simple-slider__list > li.simple-slider__item:not([data-place="mock"]):first-of-type rz-gallery-main-content-image img',
        'rz-gallery-main-content-image img',
        '.main-slider__item img',
        'img.picture-container__img',
        'img[alt*="Фото"]',
        '.main-slider__image img'
    ],
    'hard.rozetka.com.ua': [ # Добавлено для поддомена hard
        'rz-gallery-main-content-image img[loading="eager"]', # <-- Новый приоритет
        'ul.simple-slider__list > li.simple-slider__item:not([data-place="mock"]):first-of-type rz-gallery-main-content-image img',
        'rz-gallery-main-content-image img',
        '.main-slider__item img',
        'img.picture-container__img',
        'img[alt*="Фото"]',
        '.main-slider__image img'
    ],
    'prom.ua': [
        'div[data-qaid="image_block"] img',
        'img[data-qaid="image_preview"]',
        '.product-gallery__image img'
    ],
    'allo.ua': [
        'div.p-gallery__main-pic .swiper-slide-active img',
        '#product-media-gallery img',
        '.swiper-slide-active img'
    ],
    'moyo.ua': [
        '.product-img-main img',
        '.gallery-main-img-block img',
        'img.gallery-image',
        '.fotorama__active img'
    ],
    'stylus.ua': [
        '.main-image-block img',
        '.product-images__main img',
        'img.main-image',
        '.active .main-image-block img',
        '.fotorama__active img',
        '.product-photo-main img'
    ],
    'www.ctrs.com.ua': [
        '.product-images .swiper-slide-active img',
        '.product-gallery__picture img',
        '.main-image img',
        'img.main-photo__pic',
        '.swiper-slide-active img',
        '.product-slider-block .swiper-slide-active img'
    ],
    'ktc.ua': [
        '.product__imagemain img',
        '.product__imagemain a img',
        '.product__imagemain a', # Иногда ссылка содержит URL
        '.photos-full a[data-fancybox-group="button"] img', # Для галереи
        '.fotorama__img', # Для Fotorama галереи
        '.product-images__main img',
        '.fotorama__active img',
        '.product__slider-main .swiper-slide-active img',
    ],
    'ti.ua': [
        '.product-item-detail-image.swiper-slide.active-prod-img img',
        '.product-item-detail-image.swiper-slide.swiper-slide-active img',
        '.product-pictures-swiper .swiper-slide-active img',
        '.product-image-gallery__image img',
        '.product-gallery__image img',
        '.detail-slider-holder .img-control-preview.active-preview img'
    ],
    'storeinua.com': [
        '.product-gallery--loaded .product__media img',
        '.product__main-photos img',
        '.gallery-top .swiper-slide-active img',
        '.product-page-gallery__main-image img',
        '.product-gallery__slide.is-active img'
    ]
    # Добавьте другие домены и их селекторы по необходимости
}

# --- Функции ---

def _log_status(message, status_callback=None):
    """Логирует сообщение через callback (для GUI) или print (для консоли)."""
    if status_callback:
        status_callback(message)
    else:
        # В консольной версии избегаем перезаписи прогресс-бара
        sys.stdout.write('\r' + ' ' * 80 + '\r') # Очищаем строку
        print(message)
        sys.stdout.flush()


def get_domain(url):
    """Извлекает основной домен (и поддомены для известных случаев) из URL."""
    try:
        parsed_url = urlparse(url)
        netloc = parsed_url.netloc
        if netloc in DOMAIN_SELECTORS: return netloc
        netloc_parts = netloc.split('.')
        if len(netloc_parts) >= 2:
            if netloc_parts[-2] in ('com', 'net', 'org', 'edu', 'gov') and len(netloc_parts) > 2: return '.'.join(netloc_parts[-3:])
            else: return '.'.join(netloc_parts[-2:])
        else: return netloc
    except Exception: return None

# --- Новая функция для парсинга srcset ---
def parse_srcset(srcset_string, base_url):
    """Парсит атрибут srcset и возвращает URL для наибольшей ширины."""
    if not srcset_string: return None
    candidates = [s.strip() for s in srcset_string.split(',')]; largest_width = 0; largest_url = None; fallback_url = None
    for candidate in candidates:
        parts = candidate.split(); url_part = parts[0] if parts else None; width = 0
        if not url_part: continue
        if len(parts) > 1 and parts[-1].endswith('w'):
            try: width_str = parts[-1][:-1]; width = int(width_str)
            except ValueError: width = 0; fallback_url = fallback_url or url_part
        elif len(parts) > 1 and parts[-1].endswith('x'): fallback_url = fallback_url or url_part
        elif len(parts) == 1: fallback_url = fallback_url or url_part
        if width > largest_width: largest_width = width; largest_url = url_part
    if largest_url: return urljoin(base_url, largest_url)
    elif fallback_url: return urljoin(base_url, fallback_url)
    return None


def find_image_url_from_schema(html_content, base_url):
    """Находит URL изображения в Schema.org (ld+json)."""
    soup = BeautifulSoup(html_content, 'html.parser')
    try:
        schema_tags = soup.find_all('script', type='application/ld+json')
        for tag in schema_tags:
            try:
                if tag.string:
                    json_string = tag.string.replace('\\"', '"').replace('\\/', '/')
                    json_string = json_string.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
                    json_string = json_string.strip()
                    if json_string.startswith('<!--'): json_string = json_string.split('-->')[0].split('<!--')[1]
                    json_string = json_string.strip(); schema_data = json.loads(json_string)
                else: continue
                if isinstance(schema_data, dict):
                    product_img_url = find_image_url_from_product_schema(schema_data, base_url)
                    if product_img_url: return product_img_url
                elif isinstance(schema_data, list):
                     for item in schema_data:
                          if isinstance(item, dict):
                                nested_img_url = find_image_url_from_product_schema(item, base_url)
                                if nested_img_url: return nested_img_url
            except (json.JSONDecodeError, TypeError, AttributeError): continue
            except Exception: continue
    except Exception: pass
    return None

def find_image_url_from_product_schema(schema_data, base_url):
    """Вспомогательная функция для поиска image внутри структуры Product Schema."""
    if not isinstance(schema_data, dict): return None
    queue = [schema_data]; visited = set()
    while queue:
        current_item = queue.pop(0); item_id = id(current_item)
        if item_id in visited: continue
        visited.add(item_id)
        if isinstance(current_item, dict):
            if current_item.get('@type') == 'Product' and 'image' in current_item:
                image_data = current_item.get('image')
                if isinstance(image_data, str):
                    img_url_candidate = image_data.strip()
                    if img_url_candidate: return urljoin(base_url, img_url_candidate)
                elif isinstance(image_data, dict):
                    img_url_candidate = image_data.get('contentUrl') or image_data.get('url')
                    if img_url_candidate: return urljoin(base_url, img_url_candidate.strip())
                elif isinstance(image_data, list) and image_data:
                    for img_item in image_data:
                        img_url_candidate = None
                        if isinstance(img_item, str): img_url_candidate = img_item.strip()
                        elif isinstance(img_item, dict):
                            if img_item.get('@type') == 'ImageObject': img_url_candidate = img_item.get('contentUrl') or img_item.get('url')
                            else: img_url_candidate = img_item.get('url') or img_item.get('contentUrl')
                        if img_url_candidate: return urljoin(base_url, img_url_candidate.strip())
            for value in current_item.values():
                if isinstance(value, (dict, list)): queue.append(value)
        elif isinstance(current_item, list):
            for element in current_item:
                if isinstance(element, (dict, list)): queue.append(element)
    return None


def find_image_url_from_og_image(html_content, base_url):
    """Находит URL изображения в Open Graph meta tag."""
    soup = BeautifulSoup(html_content, 'html.parser')
    try:
        og_image_tag = soup.find('meta', property='og:image')
        if og_image_tag and og_image_tag.get('content'):
            img_url_candidate = og_image_tag['content'].strip()
            if img_url_candidate:
                potential_og_image = urljoin(base_url, img_url_candidate)
                if 'logo' in potential_og_image.lower() or 'icon' in potential_og_image.lower() or 'sprite' in potential_og_image.lower(): return None
                else: return potential_og_image
    except Exception: pass
    return None


# --- Функция для улучшения URL-адресов изображений ---
def improve_image_url(url, status_callback=None):
    """
    Улучшает URL-адреса изображений, заменяя маленькие размеры на большие.
    В частности, для домена citrus.world заменяет size_150 на size_800.
    """
    if not url or not isinstance(url, str):
        return url
    
    try:
        # Проверяем, содержит ли URL домен citrus.world и размер вида size_XXX
        if 'citrus.world' in url.lower() and re.search(r'size_\d+', url):
            # Используем re.sub для замены size_XXX на size_800
            improved_url = re.sub(r'size_\d+', 'size_800', url)
            if improved_url != url: # Логируем только если замена произошла
                _log_status(f"URL_IMPROVE: Заменен размер в URL: {url} -> {improved_url}", status_callback)
            return improved_url
        
        # Здесь можно добавить другие правила улучшения URL для других доменов
        
        return url
    except Exception as e:
        _log_status(f"URL_IMPROVE: Ошибка при улучшении URL {url}: {e}", status_callback)
        return url  # В случае ошибки возвращаем исходный URL

# --- Новая функция для выбора лучшего URL из кандидатов ---
def select_best_image_url(candidates, base_url, status_callback=None):
    """Фильтрует и выбирает лучший URL изображения из списка кандидатов, отдавая приоритет высокому разрешению."""
    if not candidates:
        _log_status("BEST_URL: Нет кандидатов для выбора.", status_callback)
        return None

    valid_urls = []
    _log_status(f"BEST_URL: Получены кандидаты: {candidates}", status_callback)
    for url in candidates:
        if not url or not isinstance(url, str):
            continue
        try:
            full_url = urljoin(base_url, url.strip())
            # Базовая валидация и фильтрация
            parsed_url = urlparse(full_url)
            if not parsed_url.scheme or not parsed_url.netloc:
                 _log_status(f"BEST_URL: Пропуск невалидной структуры URL: {full_url}", status_callback)
                 continue
            if 'data:image' in full_url.lower():
                 _log_status(f"BEST_URL: Пропуск data URI: {full_url[:100]}...", status_callback)
                 continue
            lower_url = full_url.lower()
            # Исключаем заведомо неподходящие URL
            skip_keywords = ['placeholder', 'stub', 'sprite', 'logo', 'icon', 'loader', 'spinner', 'avatar', 'dummy', 'blank', 'banner', 'ads', 'pixel', 'track', 'default', '/svg/']
            if any(kw in lower_url for kw in skip_keywords):
                 _log_status(f"BEST_URL: Пропуск URL, похожего на плейсхолдер/иконку/трекер: {full_url}", status_callback)
                 continue
            # Проверка на распространенные расширения изображений (в конце или как часть пути)
            image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff']
            has_image_extension = any(lower_url.endswith(ext) for ext in image_extensions)
            if not has_image_extension:
                 # Дополнительная проверка, если расширения нет в конце
                 path_part = parsed_url.path.lower()
                 query_part = parsed_url.query.lower()
                 if not any(ext in path_part or ext in query_part for ext in image_extensions):
                      # Попытка угадать по Content-Type (если бы мы делали HEAD запрос, но это медленно)
                      # Пока будем строже: если нет расширения, пропускаем, кроме известных CDN паттернов (сложно)
                      _log_status(f"BEST_URL: Пропуск URL без явного расширения изображения: {full_url}", status_callback)
                      continue

            # Улучшаем URL перед добавлением в список валидных
            improved_url = improve_image_url(full_url, status_callback)
            valid_urls.append(improved_url)
        except Exception as e:
             _log_status(f"BEST_URL: Ошибка обработки кандидата '{url}': {e}", status_callback)
             continue


    if not valid_urls:
        _log_status(f"BEST_URL: Не найдено валидных URL изображений после фильтрации.", status_callback)
        return None

    # Удаление дубликатов с сохранением порядка (примерно)
    unique_urls = sorted(list(set(valid_urls)), key=valid_urls.index)
    _log_status(f"BEST_URL: Уникальные валидные кандидаты: {unique_urls}", status_callback)

    # Приоритезация на основе ключевых слов и разрешения в URL
    prioritized = []
    for url in unique_urls:
        lower_url = url.lower()
        priority = 0 # Базовый приоритет

        # Ключевые слова высокого разрешения
        high_res_keywords = ['/original/', '/source/', '/big/', '/large/', '_xl.', '_large.', 'zoom', 'full', 'master', 'hires', 'maxres']
        if any(kw in lower_url for kw in high_res_keywords):
            priority += 100 # Увеличен приоритет

        # Ключевые слова среднего разрешения
        medium_res_keywords = ['/medium/', '/med/', '_medium.', '_m.', '/product/', '/catalog/']
        if any(kw in lower_url for kw in medium_res_keywords):
            priority += 10 # Оставляем низким

        # Ключевые слова низкого разрешения (штраф)
        low_res_keywords = ['/small/', '/thumb', '_small.', '_s.', '_thumb.', 'preview', 'mini', 'icon', 'logo', '/100x', '/200x', '/300x', 'tile'] # Добавлен 'tile'
        if any(kw in lower_url for kw in low_res_keywords):
            priority -= 50 # Увеличен штраф

        # Приоритет для определенных атрибутов (если бы передавали тип источника)
        # Например, data-zoom-image мог бы дать +60

        # Проверка разрешения в URL (например, 1200x1200)
        resolution_match = re.search(r'(\d{3,})[xX](\d{3,})', url)
        if resolution_match:
             try:
                 w, h = int(resolution_match.group(1)), int(resolution_match.group(2))
                 # Даем больше очков за большие размеры
                 area_bonus = min(40, (w * h) // 50000) # Бонус до 40 очков за площадь
                 priority += area_bonus
                 _log_status(f"BEST_URL: Найдены размеры {w}x{h} в URL '{url}', бонус {area_bonus}", status_callback)
             except ValueError:
                 pass # Не удалось преобразовать в числа

        # Предпочтение JPG/PNG перед WEBP/GIF, если приоритет одинаковый
        if lower_url.endswith('.jpg') or lower_url.endswith('.jpeg') or lower_url.endswith('.png'):
             priority += 1

        prioritized.append((priority, url))

    # Сортировка по приоритету (убывание), затем по длине URL (убывание, как доп. эвристика)
    prioritized.sort(key=lambda x: (-x[0], -len(x[1])))

    _log_status(f"BEST_URL: Отсортированный список: {prioritized}", status_callback)

    if not prioritized:
         _log_status("BEST_URL: Список приоритетов пуст.", status_callback)
         return None

    best_url = prioritized[0][1]
    # Финальное улучшение URL перед возвратом
    final_url = improve_image_url(best_url, status_callback)
    if final_url != best_url:
        _log_status(f"BEST_URL: Улучшен финальный URL: {best_url} -> {final_url}", status_callback)
    else:
        _log_status(f"BEST_URL: Выбран лучший URL: {final_url} (Приоритет: {prioritized[0][0]})", status_callback)
    return final_url


# --- Обновленная функция find_image_url_from_css_selectors ---
def find_image_url_from_css_selectors(html_content, domain, base_url, status_callback=None):
    """Находит URL изображения с использованием CSS селекторов, собирает кандидатов и выбирает лучший."""
    _log_status(f"CSS_SELECTORS: Поиск для домена '{domain}' (URL: {base_url})", status_callback)
    soup = BeautifulSoup(html_content, 'html.parser')
    current_domain = get_domain(base_url); selectors = DOMAIN_SELECTORS.get(current_domain)
    if not selectors:
        _log_status(f"CSS_SELECTORS: Селекторы для домена '{current_domain}' не найдены.", status_callback)
        return None
    _log_status(f"CSS_SELECTORS: Используются селекторы: {selectors}", status_callback)

    candidates = [] # Список для сбора URL-кандидатов

    for selector in selectors:
        _log_status(f"CSS_SELECTORS: Проверка селектора: '{selector}'", status_callback)
        try:
            img_tags = soup.select(selector) # Используем select для поиска всех совпадений
            if not img_tags:
                 _log_status(f"CSS_SELECTORS: Теги по селектору '{selector}' не найдены.", status_callback)
                 continue

            for img_tag in img_tags:
                _log_status(f"CSS_SELECTORS: Найден тег по селектору '{selector}'. Сбор кандидатов...", status_callback)
                # 1. Атрибуты с высоким приоритетом
                high_priority_attrs = ['data-zoom-image', 'data-large-image', 'data-original']
                for attr in high_priority_attrs:
                    attr_value = img_tag.get(attr)
                    if attr_value: candidates.append(attr_value)

                # 2. srcset
                srcset_value = img_tag.get('srcset')
                if srcset_value:
                    srcset_candidate = parse_srcset(srcset_value, base_url) # parse_srcset уже ищет лучший URL в srcset
                    if srcset_candidate: candidates.append(srcset_candidate)

                # 3. Parent href (если ведет на изображение)
                if img_tag.parent and img_tag.parent.name == 'a':
                     parent_href = img_tag.parent.get('href')
                     if parent_href:
                          # Простая проверка, что href похож на URL изображения
                          lower_href = parent_href.lower()
                          if any(ext in lower_href for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']):
                              candidates.append(parent_href)

                # 4. data-src (средний приоритет)
                data_src_value = img_tag.get('data-src')
                if data_src_value: candidates.append(data_src_value)

                # 5. src (низкий приоритет)
                src_value = img_tag.get('src')
                if src_value: candidates.append(src_value)

                # Можно добавить поиск ссылок внутри родительских элементов, если нужно

        except Exception as e:
            _log_status(f"CSS_SELECTORS: Ошибка при обработке селектора '{selector}': {e}", status_callback)
            continue

    _log_status(f"CSS_SELECTORS: Сбор кандидатов завершен для {base_url}.", status_callback)
    return select_best_image_url(candidates, base_url, status_callback) # Выбираем лучший URL

# --- Обновленная функция find_image_url_from_selenium_element ---
def find_image_url_from_selenium_element(driver, domain, status_callback=None): # <-- Добавлен status_callback=None
    """
    Находит главный элемент изображения с помощью Selenium, собирает кандидатов URL и выбирает лучший.
    """
    if not _selenium_available: return None
    current_domain = get_domain(driver.current_url); selectors = DOMAIN_SELECTORS.get(current_domain)
    if not selectors:
        _log_status(f"SELENIUM: Селекторы для домена '{current_domain}' не найдены.", status_callback)
        return None
    _log_status(f"SELENIUM: Используются селекторы: {selectors}", status_callback)

    base_url = driver.current_url # Определяем base_url один раз

    # --- ИЗМЕНЕНО: Последовательная проверка селекторов с приоритетом первого ---
    for i, selector in enumerate(selectors): # Итерация с индексом
        _log_status(f"SELENIUM: Проверка селектора #{i+1}: '{selector}'", status_callback)
        candidates = [] # Кандидаты для текущего шага
        try:
            img_element = None
            if i == 0: # --- Для ПЕРВОГО селектора ищем только ПЕРВЫЙ элемент ---
                try:
                    _log_status(f"SELENIUM: Поиск ПЕРВОГО элемента по приоритетному селектору '{selector}'", status_callback)
                    img_element = WebDriverWait(driver, 7).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector))) # Увеличено ожидание
                except (TimeoutException, SeleniumNoSuchElementException):
                    _log_status(f"SELENIUM: ПЕРВЫЙ элемент по приоритетному селектору '{selector}' не найден.", status_callback)
                    continue # Переходим к следующему селектору в списке
            else: # --- Для ПОСЛЕДУЮЩИХ селекторов ищем первый из найденных ---
                 try:
                    _log_status(f"SELENIUM: Поиск ЛЮБОГО элемента по запасному селектору '{selector}'", status_callback)
                    # Ищем все, но возьмем первый видимый/подходящий? Или просто первый? Возьмем просто первый.
                    img_elements = WebDriverWait(driver, 3).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))) # Меньшее ожидание
                    if img_elements:
                        img_element = img_elements[0] # Берем первый из найденных
                    else:
                         _log_status(f"SELENIUM: Элементы по запасному селектору '{selector}' не найдены.", status_callback)
                         continue
                 except (TimeoutException, SeleniumNoSuchElementException):
                     _log_status(f"SELENIUM: Элементы по запасному селектору '{selector}' не найдены.", status_callback)
                     continue

            # --- Если элемент найден (либо первый по первому селектору, либо первый по запасному) ---
            if img_element:
                _log_status(f"SELENIUM: Найден элемент по селектору '{selector}'. Сбор кандидатов...", status_callback)
                attrs_dict = driver.execute_script("""
                    var img = arguments[0]; var result = {};
                    var attrs = ['srcset', 'src', 'currentSrc', 'data-zoom-image', 'data-large-image', 'data-original', 'data-src'];
                    attrs.forEach(attr => { if (img.hasAttribute(attr)) result[attr.replace(/-/g, '_')] = img.getAttribute(attr); });
                    if (img.parentElement && img.parentElement.tagName === 'A' && img.parentElement.href) {
                        let href = img.parentElement.href;
                        // ИСПРАВЛЕНО: Экранируем \ в регулярном выражении
                        if (href && /\\.(jpg|jpeg|png|webp|gif|bmp)$/i.test(href.split('?')[0])) {
                             result.parent_href = href;
                        }
                    }
                    return result;
                """, img_element)

                if attrs_dict:
                    # Собираем кандидатов из атрибутов найденного элемента
                    if 'srcset' in attrs_dict and attrs_dict['srcset']:
                        srcset_candidate = parse_srcset(attrs_dict['srcset'], base_url)
                        if srcset_candidate: candidates.append(srcset_candidate)

                    high_priority_keys = ['data_zoom_image', 'data_large_image', 'data_original', 'parent_href']
                    for key in high_priority_keys:
                        if key in attrs_dict and attrs_dict[key]: candidates.append(attrs_dict[key])

                    medium_priority_keys = ['data_src']
                    for key in medium_priority_keys:
                         if key in attrs_dict and attrs_dict[key]: candidates.append(attrs_dict[key])

                    low_priority_keys = ['currentSrc', 'src']
                    for key in low_priority_keys:
                         if key in attrs_dict and attrs_dict[key]: candidates.append(attrs_dict[key])

            # --- Выбираем лучший URL из кандидатов, собранных для ЭТОГО селектора ---
            if candidates:
                _log_status(f"SELENIUM: Выбор лучшего URL из кандидатов для селектора '{selector}': {candidates}", status_callback)
                best_url = select_best_image_url(candidates, base_url, status_callback)
                if best_url:
                    _log_status(f"SELENIUM: Лучший URL найден по селектору '{selector}': {best_url}", status_callback)
                    return best_url # Возвращаем первый найденный лучший URL
                else:
                     _log_status(f"SELENIUM: Не удалось выбрать лучший URL из кандидатов для селектора '{selector}'.", status_callback)
            # Если кандидатов нет или лучший не выбран, цикл продолжается к следующему селектору

        except Exception as e: # Ловим другие ошибки на всякий случай
             _log_status(f"SELENIUM: Непредвиденная ошибка при обработке селектора '{selector}': {e}", status_callback)
             continue # Переходим к следующему селектору

    # Если ни один селектор не дал результата
    _log_status(f"SELENIUM: URL не найден ни по одному селектору для {base_url}", status_callback)
    return None


def download_image(session, image_url, save_path_base, status_callback=None):
    """
    Скачивает изображение, определяет его РЕАЛЬНЫЙ формат (приоритет Content-Type),
    сохраняет во временный файл, при необходимости конвертирует в стандартный формат (PNG)
    с помощью ImageMagick и возвращает путь к финальному файлу.
    """
    temp_save_path = None # Путь к временному файлу
    final_save_path = None # Путь к финальному файлу
    try:
        response = session.get(image_url, stream=True, timeout=20)
        response.raise_for_status()
        if response.headers.get('content-length') == '0':
            return False, f"Ошибка скачивания: Файл пустой для URL: {image_url}"

        # --- Определение исходного расширения (Приоритет Content-Type) ---
        content_type = response.headers.get('content-type', '').lower()
        initial_extension = None
        known_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.avif', '.tif', '.tiff']
        _log_status(f"DOWNLOAD: URL={image_url}, Content-Type='{content_type}'", status_callback)

        if 'jpeg' in content_type or 'jpg' in content_type: initial_extension = '.jpg'
        elif 'png' in content_type: initial_extension = '.png'
        elif 'gif' in content_type: initial_extension = '.gif'
        elif 'webp' in content_type: initial_extension = '.webp'
        elif 'bmp' in content_type: initial_extension = '.bmp'
        elif 'avif' in content_type: initial_extension = '.avif'
        elif 'tiff' in content_type: initial_extension = '.tiff'
        elif content_type.startswith('image/'):
             ext_part = content_type.split('/')[-1].split(';')[0]
             if ext_part and len(ext_part) <= 4 and ext_part.isalnum() and ('.' + ext_part) in known_extensions:
                  initial_extension = '.' + ext_part
             else: _log_status(f"DOWNLOAD: Content-Type '{content_type}' дал неизвестное/неподдерживаемое расширение '{ext_part}'.", status_callback)
        else: _log_status(f"DOWNLOAD: Не удалось определить тип по Content-Type '{content_type}'.", status_callback)

        # Если Content-Type не помог, пробуем URL
        if not initial_extension:
            _log_status(f"DOWNLOAD: Попытка определить расширение по URL...", status_callback)
            try:
                path_part = urlparse(image_url).path
                _, parsed_ext = os.path.splitext(os.path.basename(path_part))
                parsed_ext = parsed_ext.lower()
                if parsed_ext in known_extensions:
                    initial_extension = parsed_ext
                    _log_status(f"DOWNLOAD: Расширение взято из URL: {initial_extension}", status_callback)
            except Exception: pass # Игнорируем ошибки парсинга URL

        # Если совсем не удалось, fallback
        if not initial_extension:
            _log_status(f"DOWNLOAD: Не удалось определить исходное расширение. Используется fallback .jpg", status_callback)
            initial_extension = '.jpg'
        _log_status(f"DOWNLOAD: Исходное расширение определено как: {initial_extension}", status_callback)

        # --- Определение целевого формата и путей ---
        standard_formats = ['.jpg', '.jpeg', '.png']
        needs_conversion = initial_extension not in standard_formats
        target_extension = '.png' if needs_conversion else initial_extension # Конвертируем в PNG для сохранения качества
        _log_status(f"DOWNLOAD: Целевое расширение: {target_extension} (Конвертация: {'Да' if needs_conversion else 'Нет'})", status_callback)

        # Определяем финальный путь (с обработкой коллизий)
        save_dir = os.path.dirname(save_path_base); os.makedirs(save_dir, exist_ok=True)
        final_save_path_base = save_path_base # Используем исходную базу имени
        final_save_path = final_save_path_base + target_extension
        counter = 1
        original_final_path = final_save_path
        while os.path.exists(final_save_path):
            final_save_path = f"{final_save_path_base}_{counter}{target_extension}"; counter += 1
            if counter > 1000: return False, f"Слишком много файлов с похожим именем для {target_extension}. Пропуск: {original_final_path}"
        _log_status(f"DOWNLOAD: Финальный путь: {final_save_path}", status_callback)

        # Определяем временный путь
        temp_save_path = final_save_path_base + "_temp" + initial_extension
        _log_status(f"DOWNLOAD: Временный путь: {temp_save_path}", status_callback)

        # --- Скачивание во временный файл ---
        downloaded_size = 0
        try:
            with open(temp_save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk); downloaded_size += len(chunk)
            if downloaded_size == 0:
                 raise ValueError("Скачанный файл пустой")
            _log_status(f"DOWNLOAD: Временный файл сохранен: {temp_save_path} ({downloaded_size} байт)", status_callback)
        except Exception as write_err:
             if os.path.exists(temp_save_path): os.remove(temp_save_path)
             return False, f"Ошибка записи временного файла {temp_save_path}: {write_err}"

        # --- Конвертация (если нужна) ---
        if needs_conversion:
            magick_path = shutil.which('magick') # Проверяем наличие ImageMagick
            if not magick_path:
                _log_status(f"DOWNLOAD: ImageMagick ('magick') не найден в PATH. Невозможно конвертировать {initial_extension} в {target_extension}.", status_callback)
                if os.path.exists(temp_save_path): os.remove(temp_save_path)
                return False, f"Ошибка: ImageMagick не найден для конвертации {initial_extension}"

            _log_status(f"DOWNLOAD: Запуск конвертации ImageMagick: {temp_save_path} -> {final_save_path}", status_callback)
            command = [magick_path, temp_save_path, final_save_path]
            try:
                result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60) # Таймаут 60 сек
                _log_status(f"DOWNLOAD: Конвертация успешна. stdout:\n{result.stdout}\nstderr:\n{result.stderr}", status_callback)
                if os.path.exists(temp_save_path): os.remove(temp_save_path) # Удаляем временный файл
                return True, f"Изображение успешно скачано и конвертировано в {os.path.basename(final_save_path)}"
            except FileNotFoundError: # На случай, если shutil.which обманул
                 _log_status(f"DOWNLOAD: Ошибка конвертации - команда 'magick' не найдена (FileNotFoundError).", status_callback)
                 if os.path.exists(temp_save_path): os.remove(temp_save_path)
                 return False, "Ошибка конвертации: команда magick не найдена"
            except subprocess.CalledProcessError as conv_err:
                 _log_status(f"DOWNLOAD: Ошибка конвертации ImageMagick (код {conv_err.returncode}). Команда: {' '.join(command)}\nstdout:\n{conv_err.stdout}\nstderr:\n{conv_err.stderr}", status_callback)
                 if os.path.exists(temp_save_path): os.remove(temp_save_path)
                 if os.path.exists(final_save_path): os.remove(final_save_path) # Удаляем возможно частично созданный файл
                 return False, f"Ошибка конвертации ImageMagick: {conv_err.stderr[:200]}"
            except subprocess.TimeoutExpired:
                 _log_status(f"DOWNLOAD: Ошибка конвертации ImageMagick - превышен таймаут.", status_callback)
                 if os.path.exists(temp_save_path): os.remove(temp_save_path)
                 if os.path.exists(final_save_path): os.remove(final_save_path)
                 return False, "Ошибка конвертации: превышен таймаут ImageMagick"
            except Exception as conv_exc: # Другие возможные ошибки
                 _log_status(f"DOWNLOAD: Непредвиденная ошибка при конвертации: {conv_exc}", status_callback)
                 if os.path.exists(temp_save_path): os.remove(temp_save_path)
                 if os.path.exists(final_save_path): os.remove(final_save_path)
                 return False, f"Непредвиденная ошибка при конвертации: {conv_exc}"

        # --- Если конвертация не нужна ---
        else:
            _log_status(f"DOWNLOAD: Конвертация не требуется. Переименование {temp_save_path} -> {final_save_path}", status_callback)
            try:
                os.rename(temp_save_path, final_save_path)
                return True, f"Изображение успешно сохранено как: {os.path.basename(final_save_path)}"
            except OSError as rename_err:
                 _log_status(f"DOWNLOAD: Ошибка переименования временного файла: {rename_err}", status_callback)
                 if os.path.exists(temp_save_path): os.remove(temp_save_path) # Пытаемся удалить временный
                 if os.path.exists(final_save_path): os.remove(final_save_path) # И финальный, если вдруг создался
                 return False, f"Ошибка переименования файла: {rename_err}"

    # --- Обработка общих ошибок ---
    except requests.exceptions.Timeout:
        if temp_save_path and os.path.exists(temp_save_path): os.remove(temp_save_path)
        return False, f"Ошибка скачивания: Превышен таймаут для {image_url}"
    except requests.exceptions.RequestException as e:
        if temp_save_path and os.path.exists(temp_save_path): os.remove(temp_save_path)
        return False, f"Ошибка скачивания изображения {image_url}: {e}"
    except OSError as e:
        if temp_save_path and os.path.exists(temp_save_path): os.remove(temp_save_path)
        return False, f"Ошибка файловой системы при сохранении {save_path_base}: {e}"
    except Exception as e:
        if temp_save_path and os.path.exists(temp_save_path): os.remove(temp_save_path)
        import traceback; return False, f"Непредвиденная ошибка при скачивании/обработке {image_url}: {e}\n{traceback.format_exc()}"


# --- Обновленная функция process_single_row ---
def process_single_row(row_data, download_dir, headless, status_callback=None): # Добавлен status_callback
    """
    Обрабатывает одну строку CSV: сначала пытается быстрый парсинг (requests+BS),
    при неудаче переключается на медленный (Selenium).
    """
    if not row_data or len(row_data) < 2: return False, "Пропущено: Некорректные данные строки"
    product_url = row_data[0].strip(); desired_filename_base = row_data[1].strip()
    _log_status(f"PROCESS_ROW: Начало обработки URL: {product_url}, Имя файла: {desired_filename_base}", status_callback) # <-- ЛОГ
    safe_filename = desired_filename_base
    max_filename_length = 100
    safe_filename = safe_filename[:max_filename_length] if len(safe_filename) > max_filename_length else safe_filename
    if not safe_filename:
        _log_status(f"PROCESS_ROW: Пропущено (пустое имя файла после очистки) для URL: {product_url}", status_callback)
        return False, f"Пропущено: Пустое имя файла после очистки для URL: {product_url}"
    if not (product_url.lower().startswith('http://') or product_url.lower().startswith('https://')):
        _log_status(f"PROCESS_ROW: Пропущено (невалидный URL протокол) для URL: {product_url}", status_callback)
        return False, f"Пропущено: Невалидный URL протокол '{product_url}'"

    domain_for_check = get_domain(product_url)
    force_selenium_domains = ['rozetka.com.ua', 'bt.rozetka.com.ua', 'hard.rozetka.com.ua']
    image_url = None; session = None; fast_parse_failed = False # Инициализация по умолчанию

    # --- ПРОВЕРКА: Принудительный Selenium для Rozetka ---
    if domain_for_check in force_selenium_domains:
        _log_status(f"PROCESS_ROW: Принудительное использование Selenium для домена {domain_for_check}", status_callback)
        fast_parse_failed = True # Устанавливаем флаг, чтобы пропустить быстрый парсинг и перейти к Selenium
    # --- Конец проверки ---
    else: # <-- Только если это НЕ Rozetka, пытаемся быстрый парсинг
        # --- Попытка 1: Быстрый парсинг ---
        try: # <-- Начало блока try с правильным отступом
            session = requests.Session(); session.headers.update(BASE_HEADERS); session.headers['User-Agent'] = random.choice(USER_AGENTS)
            response = session.get(product_url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            response.encoding = response.apparent_encoding if response.apparent_encoding else 'utf-8'
            html_content = response.text; base_url = response.url
            domain = get_domain(base_url)

            image_url = find_image_url_from_schema(html_content, base_url)
            if image_url is None: image_url = find_image_url_from_og_image(html_content, base_url)
            if image_url is None: image_url = find_image_url_from_css_selectors(html_content, domain, base_url, status_callback) # Передаем callback

            if image_url:
                 _log_status(f"PROCESS_ROW: Выбран URL для скачивания (быстрый парсинг): {image_url}", status_callback)
                 # Улучшаем URL перед скачиванием
                 image_url = improve_image_url(image_url, status_callback)
                 _log_status(f"PROCESS_ROW: Улучшенный URL для скачивания: {image_url}", status_callback)
                 save_path_base = os.path.join(download_dir, safe_filename)
                 # Передаем status_callback в download_image
                 download_success, message = download_image(session, image_url, save_path_base, status_callback)
                 if download_success: return True, f"Быстрый парсинг успешен: {product_url} -> {message}"
                 else: image_url = None; fast_parse_failed = True # Переходим к Selenium
        except (requests.exceptions.Timeout, requests.exceptions.RequestException): # <-- Блок except с правильным отступом
             image_url = None; fast_parse_failed = True
        except Exception as e: # Ловим другие возможные ошибки BS/парсинга
            _log_status(f"PROCESS_ROW: Ошибка при быстром парсинге {product_url}: {e}", status_callback)
            image_url = None; fast_parse_failed = True # Отмечаем, что была ошибка
        finally: # <-- Блок finally с правильным отступом
            if session: session.close() # Закрываем сессию в любом случае после попытки requests

    # --- Попытка 2: Медленный парсинг (Selenium) ---
    # --- ИЗМЕНЕНО УСЛОВИЕ: Переходим к Selenium, если URL НЕ НАЙДЕН после быстрой попытки ---
    if image_url is None:
        if fast_parse_failed:
             _log_status(f"PROCESS_ROW: Быстрый парсинг не удался (ошибка) для {product_url}. Попытка Selenium...", status_callback)
        else:
             _log_status(f"PROCESS_ROW: URL не найден быстрым парсингом для {product_url}. Попытка Selenium...", status_callback) # <-- ЛОГ для случая, когда ошибок не было, но URL не найден

        if not _selenium_available:
            _log_status(f"PROCESS_ROW: Selenium недоступен для {product_url}", status_callback)
            return False, f"Не удалось получить изображение быстрым методом, а Selenium недоступен для {product_url}"
        driver = None; selenium_session = None
        try:
            options = Options();
            if headless: options.add_argument('--headless')
            options.add_argument('--no-sandbox'); options.add_argument('--disable-dev-shm-usage'); options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080'); options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
            options.add_experimental_option("excludeSwitches", ["enable-automation"]); options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-blink-features=AutomationControlled'); options.add_argument('--disable-infobars')
            options.add_argument('--disable-popup-blocking'); options.add_argument('--ignore-certificate-errors')
            options.add_argument('--disable-extensions'); options.add_argument('--profile-directory=Default'); options.add_argument("--incognito")
            options.add_argument("--disable-plugins-discovery")
            # Применяем путь к бинарнику Chrome при наличии
            if CHROME_BINARY:
                options.binary_location = CHROME_BINARY
            # Применяем дополнительные аргументы из переменной окружения
            if CHROME_ARGS:
                for arg in CHROME_ARGS.split():
                    a = arg.strip()
                    if a:
                        options.add_argument(a)

            if WEBDRIVER_PATH: service = Service(WEBDRIVER_PATH); driver = webdriver.Chrome(service=service, options=options)
            else:
                try:
                    from webdriver_manager.chrome import ChromeDriverManager
                    service = Service(ChromeDriverManager().install()); driver = webdriver.Chrome(service=service, options=options)
                except ImportError: driver = webdriver.Chrome(options=options) # Полагаемся на PATH
                except Exception as driver_init_err: return False, f"Ошибка инициализации ChromeDriver: {driver_init_err}."

            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"})
            driver.get(product_url)
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body"))); time.sleep(random.uniform(1, 3))
            base_url = driver.current_url; domain = get_domain(base_url)

            image_url = find_image_url_from_selenium_element(driver, domain, status_callback) # Передаем callback
            if image_url is None: # Fallback на парсинг source после Selenium
                 _log_status(f"SELENIUM: Не удалось найти URL через элементы Selenium для {product_url}. Попытка парсинга page_source...", status_callback)
                 html_content = driver.page_source
                 image_url = find_image_url_from_schema(html_content, base_url)
                 if image_url is None: image_url = find_image_url_from_og_image(html_content, base_url)
                 if image_url is None: image_url = find_image_url_from_css_selectors(html_content, domain, base_url, status_callback) # Передаем callback

            if image_url:
                _log_status(f"PROCESS_ROW: Выбран URL для скачивания (Selenium/page_source): {image_url}", status_callback)
                # Улучшаем URL перед скачиванием
                image_url = improve_image_url(image_url, status_callback)
                _log_status(f"PROCESS_ROW: Улучшенный URL для скачивания: {image_url}", status_callback)
                save_path_base = os.path.join(download_dir, safe_filename)
                selenium_session = requests.Session(); selenium_session.headers.update(BASE_HEADERS); selenium_session.headers['User-Agent'] = random.choice(USER_AGENTS)
                # Передаем status_callback в download_image
                download_success, message = download_image(selenium_session, image_url, save_path_base, status_callback)
                if download_success: return True, f"Selenium парсинг успешен: {product_url} -> {message}"
                else: return False, f"Selenium парсинг (найден URL, но ошибка скачивания): {product_url} -> {message}"
            else: return False, f"Не удалось найти URL главного изображения для {product_url} после всех попыток (включая Selenium)."
        except TimeoutException: return False, f"Ошибка загрузки страницы Selenium (таймаут) для {product_url}"
        except WebDriverException as e: err_msg = str(e); return False, f"Ошибка WebDriver при обработке {product_url}: {err_msg[:200]}"
        except requests.exceptions.RequestException as e: return False, f"Ошибка запроса при скачивании после Selenium для {product_url}: {e}"
        except Exception as e: import traceback; return False, f"Непредвиденная ошибка при обработке {product_url} (Selenium): {e}\n{traceback.format_exc()}"
        finally:
            if driver:
                try: driver.quit()
                except Exception: pass
            if selenium_session: selenium_session.close()

    if image_url is None and not fast_parse_failed: return False, f"Не удалось найти URL главного изображения для {product_url} (быстрый парсинг)."
    return False, f"Неизвестный результат обработки для {product_url}."


# --- Обновленная функция run_parser с детальным логированием пропущенных строк и принудительным стандартным диалектом ---
def run_parser(csv_path, download_dir, status_callback, progress_callback, headless=True, max_workers=MAX_WORKERS):
    """
    Запускает процесс парсинга изображений из CSV с использованием гибридного подхода (requests + Selenium).
    (Полная функция с исправленными отступами, детальным логированием и принудительным диалектом)
    """
    processed_count = 0; success_count = 0; error_count = 0
    data_rows = []; total_rows = 0

    # --- Предварительная проверка CSV файла и чтение данных ---
    try:
        # --- Блок определения кодировки (ЗАКОММЕНТИРОВАН - ПРИНУДИТЕЛЬНО UTF-8-SIG) ---
        file_encoding = 'utf-8-sig' # <-- ПРИНУДИТЕЛЬНО UTF-8 с обработкой BOM
        _log_status(f"Принудительно используется кодировка: {file_encoding}", status_callback)
        # try:
        #     import chardet
        #     with open(csv_path, 'rb') as f_detect:
        #         sample = f_detect.read(2048)
        #         result = chardet.detect(sample)
        #         detected_encoding = result['encoding'] if result else None
        #         confidence = result['confidence'] if result else 0
        #         if detected_encoding and confidence > 0.6:
        #             if detected_encoding.lower() == 'windows-1252':
        #                 _log_status(f"Chardet определил {detected_encoding} (уверенность: {confidence:.2f}), но используем CP1251 для кириллицы.", status_callback)
        #                 file_encoding = 'cp1251'
        #             elif detected_encoding.lower() == 'ascii':
        #                  file_encoding = 'utf-8'
        #                  _log_status(f"Определена кодировка CSV: {file_encoding} (ASCII)", status_callback)
        #             elif detected_encoding.lower() == 'windows-1251':
        #                  file_encoding = 'cp1251'
        #                  _log_status(f"Определена кодировка CSV: {file_encoding} (уверенность: {confidence:.2f})", status_callback)
        #             else:
        #                 file_encoding = detected_encoding
        #                 _log_status(f"Определена кодировка CSV: {file_encoding} (уверенность: {confidence:.2f})", status_callback)
        #         else:
        #             _log_status(f"Не удалось уверенно определить кодировку (определено: {detected_encoding}, уверенность: {confidence:.2f}). Используется UTF-8.", status_callback)
        #             file_encoding = 'utf-8'
        # except ImportError: _log_status("Предупреждение: chardet не установлен. Используется UTF-8 для чтения CSV.", status_callback); file_encoding = 'utf-8'
        # except Exception as e: _log_status(f"Ошибка определения кодировки: {e}. Используется UTF-8.", status_callback); file_encoding = 'utf-8'
        # --- Конец блока определения кодировки ---

        # --- Блок чтения CSV файла ---
        with open(csv_path, 'r', encoding=file_encoding, errors='replace', newline='') as csvfile: # Используем utf-8-sig
            # --- ИСПОЛЬЗУЕМ СТАНДАРТНЫЙ ДИАЛЕКТ (запятая, двойные кавычки) ---
            reader = csv.reader(csvfile)
            _log_status("Используется стандартный диалект CSV (разделитель - запятая, кавычки - двойные).", status_callback)
            # --- Конец принудительного диалекта ---

            # --- УДАЛЕНО: Пропуск заголовка, т.к. его нет в файлах ---
            # header = next(reader, None)
            # if header:
            #      try: _log_status(f"Пропущен заголовок: {header}", status_callback)
            #      except Exception as log_e: _log_status(f"Не удалось отобразить заголовок: {log_e}", status_callback)
            # --- Конец удаления ---

            # --- Цикл чтения и валидации строк с детальным логированием ---
            line_number = 1 # Начинаем нумерацию с 1, т.к. заголовок не пропускаем
            for row in reader:
                 # --- Отладочный вывод КАЖДОЙ строки, которую вернул reader ---
                 _log_status(f"DEBUG [Строка {line_number}]: Прочитано: {row}", status_callback)
                 # --- Конец отладочного вывода ---

                 if row and len(row) >= 2:
                      first_col = row[0].strip() if row[0] else ""
                      second_col = row[1].strip() if row[1] else ""
                      is_valid_url = first_col and (first_col.lower().startswith('http://') or first_col.lower().startswith('https://'))
                      is_valid_filename = bool(second_col)

                      if is_valid_url and is_valid_filename:
                           _log_status(f"RUN_PARSER [Строка {line_number} ВАЛИДНА]: URL='{row[0]}', Filename='{row[1]}'", status_callback) # <-- ЛОГ
                           data_rows.append(row[:2])
                      else: # <-- Исправлен отступ здесь
                           reason = []
                           if not row: reason.append("Строка пустая (после reader)")
                           elif len(row) < 2: reason.append(f"Меньше 2 столбцов ({len(row)})")
                           else:
                               if not first_col: reason.append("URL пустой")
                               elif not is_valid_url: reason.append("URL не начинается с http/https")
                               if not second_col: reason.append("Имя файла пустое")
                           log_row_data = str(row)[:150] + ('...' if len(str(row)) > 150 else '')
                           _log_status(f"[Строка {line_number} ПРОПУЩЕНА] Причина: {', '.join(reason)}. Данные: {log_row_data}", status_callback)
                 elif row: # Если строка есть, но в ней меньше 2 элементов
                      log_row_data = str(row)[:150] + ('...' if len(str(row)) > 150 else '')
                      _log_status(f"[Строка {line_number} ПРОПУЩЕНА] Причина: Меньше 2 столбцов ({len(row)}). Данные: {log_row_data}", status_callback)
                 # else: # Пустые строки можно не логировать
                 #      _log_status(f"[Строка {line_number} ПРОПУЩЕНА] Причина: Пустая строка (после reader).", status_callback)
                 line_number += 1
            # --- Конец цикла чтения и валидации ---

        total_rows = len(data_rows)
        _log_status(f"Предварительный подсчет: найдено {total_rows} валидных строк для обработки.", status_callback)
        # --- Конец блока чтения CSV файла ---

    # --- Обработка ошибок чтения файла ---
    except FileNotFoundError: _log_status(f"Ошибка: CSV файл не найден: {csv_path}", status_callback); progress_callback(0, 0); return 0, 0, 0
    except UnicodeDecodeError as e: _log_status(f"Критическая ошибка: Не удалось декодировать CSV файл с кодировкой '{file_encoding}'. Ошибка: {e}", status_callback); progress_callback(0, 0); return 0, 0, 0
    except Exception as e: _log_status(f"Критическая ошибка при чтении CSV: {e}", status_callback); import traceback; _log_status(traceback.format_exc(), status_callback); progress_callback(0, 0); return 0, 0, 0
    # --- Конец обработки ошибок чтения файла ---

    if total_rows == 0: _log_status("В CSV файле не найдено валидных строк.", status_callback); progress_callback(0, 0); return 0, 0, 0

    if not os.path.exists(download_dir):
        try: os.makedirs(download_dir); _log_status(f"Создана папка: {download_dir}", status_callback)
        except OSError as e: _log_status(f"Ошибка создания папки {download_dir}: {e}", status_callback); progress_callback(0, total_rows); return 0, 0, 0

    _log_status(f"Начинается обработка {total_rows} строк ({max_workers} потоков)...", status_callback)
    if _selenium_available: _log_status(f"Режим браузера (fallback): {'фоновый' if headless else 'с окном'}", status_callback)
    else: _log_status("Запасной метод (Selenium) недоступен.", status_callback)
    if progress_callback:
        progress_callback(0, total_rows)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Передаем status_callback в process_single_row
        futures = {executor.submit(process_single_row, row, download_dir, headless, status_callback): row for row in data_rows}
        completed_tasks = 0
        for future in as_completed(futures):
            row_data = futures[future]; completed_tasks += 1
            try:
                success, message = future.result()
                if not success or "успешно сохранено" in message: _log_status(message, status_callback)
                if success: success_count += 1
                else: error_count += 1
            except Exception as exc:
                error_msg = f"Поток для URL '{row_data[0] if row_data else '???'}' вызвал исключение: {exc}"
                _log_status(error_msg, status_callback); error_count += 1
            if progress_callback:
                progress_callback(completed_tasks, total_rows)

    _log_status(f"\n--- Обработка завершена ---", status_callback)
    _log_status(f"Всего обработано строк: {completed_tasks}", status_callback)
    _log_status(f"Успешно скачано изображений: {success_count}", status_callback)
    _log_status(f"Ошибок: {error_count}", status_callback)
    return completed_tasks, success_count, error_count


# --- Консольный запуск ---
if __name__ == "__main__":
    print("Запуск парсера из командной строки...")
    csv_file = DEFAULT_CSV_FILE_PATH
    download_folder = DEFAULT_DOWNLOAD_FOLDER

    if _selenium_available:
        headless_input = input("Запускать браузер в фоновом режиме (headless)? (y/n, по умолчанию y): ").lower().strip()
        run_headless = headless_input != 'n'
    else:
        print("Selenium недоступен, запуск возможен только с быстрым парсингом.")
        run_headless = True

    workers_input = input(f"Введите количество потоков (по умолчанию {MAX_WORKERS}): ").strip()
    try:
        num_workers = int(workers_input) if workers_input else MAX_WORKERS
        if num_workers < 1: num_workers = 1; print("Количество потоков не может быть меньше 1. Установлено 1.")
    except ValueError: num_workers = MAX_WORKERS; print(f"Некорректный ввод. Используется {MAX_WORKERS}")

    def console_progress(current, total):
        if total > 0:
            percent = int(100 * current / total); bar_length = 40
            filled_length = int(bar_length * current // total)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            progress_text = f"Прогресс: |{bar}| {current}/{total} ({percent}%)"
            sys.stdout.write('\r' + progress_text + ' ' * (80 - len(progress_text)))
            sys.stdout.flush()
            if current == total: print()
        elif current == 0 and total == 0: print("Прогресс: 0/0 (0%)")

    processed, success, errors = run_parser(csv_file, download_folder, _log_status, console_progress, headless=run_headless, max_workers=num_workers)

    print(f"\n--- Сводка ---")
    print(f"Обработано строк: {processed}")
    print(f"Успешно скачано: {success}")
    print(f"Ошибок: {errors}")