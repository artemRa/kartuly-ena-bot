import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown
import os
import json
import math
import string
import random
import re
import pandas as pd


# Загрузка конфигурации из JSON-файла
TOKEN = os.getenv('TELEGRAM_TOKEN')
DB_PATH = "data/kartuly-ena.db"

# Стикеры
with open('stickers.json', 'r', encoding='utf-8') as f:
    happy_sticker_list = json.load(f)
    

# Транслитерация на грузинский
def transliterate_to_georgian(text):
    # Словарь для сопоставления латинских букв с грузинскими
    transliteration_map = {
        'a': 'ა', 'b': 'ბ', 'g': 'გ', 'd': 'დ', 'e': 'ე', 
        'v': 'ვ', 'z': 'ზ', 't': 'თ', 'i': 'ი', 'k': 'კ', 
        'l': 'ლ', 'm': 'მ', 'n': 'ნ', 'o': 'ო', 'p': 'პ',
        'zh': 'ჟ', 'r': 'რ', 's': 'ს', 't': 'ტ', 'u': 'უ', 
        'f': 'ფ', 'q': 'ქ', 'gh': 'ღ', 'sh': 'შ', 'ch': 'ჩ', 
        'ts': 'ც', 'dz': 'ძ', 'ts': 'წ', 'ch': 'ჭ', 'kh': 'ხ',
        'j': 'ჯ', 'h': 'ჰ', 
    }

    # Начальное значение для результата
    result = ""
    text = text.lower()
    
    # Текущий индекс в строке
    i = 0

    while i < len(text):
        # Проверяем двухбуквенные соответствия
        if i+1 < len(text) and text[i:i+2] in transliteration_map:
            result += transliteration_map[text[i:i+2]]
            i += 2
        # Проверяем однобуквенные соответствия
        elif text[i] in transliteration_map:
            result += transliteration_map[text[i]]
            i += 1
        else:
            # Если символ не найден в словаре, добавляем его как есть
            result += text[i]
            i += 1

    return result


# Очистка текста
def clean_text(text):
    # Убираем пунктуацию с помощью регулярного выражения
    text = re.sub(r'[^\w\s]|[\d]', ' ', text)
    # Удаляем лишние пробелы и приводим текст к нижнему регистру
    text = " ".join(text.lower().split())
    return text

# Функция для удаления всех символов 'ა' с конца слова
def preprocess_word(word):
    # Удаляем первую 'ჰ', если она есть
    if word.startswith('ჰ'):
        word = word[1:]
    # Удаляем все 'ა', 'თ' с конца слова
    word = word.rstrip('ა')
    word = word.rstrip('თ')
    return word

# Сравнение одинаковости текстов
def comparison_of_texts(txt1, txt2):
    txt1 = clean_text(txt1)
    txt2 = clean_text(txt2)
    
    # Преобразуем предложения в списки слов
    words1 = txt1.lower().split()
    words2 = txt2.lower().split()
    
    # Создаём наборы исходных слов для уникальных слов
    original_words1 = set(words1)
    
    # Обрабатываем слова, удаляя все 'ა' с конца
    processed_words1 = set(preprocess_word(word) for word in words1)
    processed_words2 = set(preprocess_word(word) for word in words2)

    # Не написанные в ответе слова
    unique_words = set()
    for word in words1:
        processed_word = preprocess_word(word)
        if processed_word not in processed_words2:
            unique_words.add(word)
            
    # Лишние
    extra_words = set()
    for word in words2:
        processed_word = preprocess_word(word)
        if processed_word not in processed_words1:
            extra_words.add(word)
            
    # Находим пересечение и объединение множеств обработанных слов
    intersection = processed_words1.intersection(processed_words2)
    union = processed_words1.union(processed_words2)
    
    # Псевдо коэффициент Жаккара
    if len(union) == 0:
        jaccard = 1.0  # Если оба текста пустые
    else:
        jaccard = len(intersection) / len(processed_words1)
    
    # Преобразуем коэффициент в балл от 0 до 10
    score = round(jaccard * 10)
    
    # Смягчение логики
    if len(processed_words1) > 5:
        score = max(score, 10 - len(unique_words))
    
    return score, unique_words, extra_words



# Подчёркивание слов
def underline_words_in_text(text, words_to_underline):

    # Преобразуем список слов для подчёркивания в нижний регистр для нечувствительности к регистру
    words_to_underline = set(word.lower() for word in words_to_underline)
    
    # Функция для замены
    def replacer(match):
        word = match.group()
        word_clean = re.sub(r'^\W+|\W+$', '', word)  # Удаляем пунктуацию с начала и конца
        if word_clean.lower() in words_to_underline:
            return f'*{word}*'
        else:
            return word
    
    # Используем регулярное выражение для поиска слов и пунктуации
    result_text = re.sub(r'\w+[\w\'-]*|\s+|[^\w\s]+', replacer, text)
    return result_text


# FUN: Получение случайного предложения
def get_random_sentence(level, complexity):
    low = 0 if complexity == 100 else complexity * 0.8
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Выполняем запрос для извлечения случайной строки
        query = '''
        SELECT x.*
        FROM examples x
        JOIN meta_info y on x.id = y.id
        JOIN complexity_dict d
        WHERE 1=1
            AND y.delete_it <> 1
            AND y.complexity between ? and ?
            AND d.worst_verb >= y.worst_verb
            AND d.simple = y.simple
            AND d.level = ?
        ORDER BY RANDOM() LIMIT 1
        '''
        cursor.execute(query, (low, complexity, level,))
        result = cursor.fetchone()

    # Возвращаем случайную строку или None, если таблица пуста
    return result


# FUN: Получение случайного предложения
def get_help(id):
    # Используем контекстный менеджер для подключения к базе данных
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        query = '''
        SELECT x.id, x.origin, coalesce(y.rus, 'Нет информации') as verb_form
        FROM meta_info x
        LEFT JOIN verb_tense_dict y on x.worst_verb = y.num
        WHERE id = ?
        '''

        cursor.execute(query, (id,))
        result = cursor.fetchone()

    # Возвращаем результат запроса или None, если данных нет
    return result


# FUN: Получить текущий скор по пользователю
def get_user_total_score(user_id):
    # Используем контекстный менеджер для подключения к базе данных
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Выполнение SQL-запроса для суммирования баллов
        cursor.execute('''
        SELECT SUM(score), AVG(score), COUNT(*)
        FROM user_scores 
        WHERE DATE('now', '-7 days') <= DATE(timestamp)
        AND user_id=?
        ''', (user_id,))
        result = cursor.fetchone()

    # Возвращаем результат запроса
    return result

# Добавление баллов пользователю
def add_user_total_score(user_id, gain):
    # Используем контекстный менеджер для подключения к базе данных
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Вставляем новые данные в таблицу user_scores
        cursor.execute("INSERT INTO user_scores (user_id, score) VALUES (?, ?)", (user_id, gain))
        # Фиксируем изменения в базе данных
        conn.commit()

# Корректировка уровня       
def update_user_complexity(user_id, level=None, complexity=None):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Проверяем, существует ли пользователь в таблице
        cursor.execute("SELECT user_id FROM user_complexity WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        # Пользователя нет в таблице, создаём новую запись
        if result is None:
            complexity = complexity or 100
            level = level or 'easy'
            
            # Записываем данные о новом пользователе
            cursor.execute("""
                INSERT INTO user_complexity (user_id, level, complexity)
                VALUES (?, ?, ?)
            """, (user_id, level, complexity))
                
        else:
            # Пользователь существует, обновляем переданный параметр
            if level is not None:
                cursor.execute("""
                    UPDATE user_complexity
                    SET level = ?, timestamp = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (level, user_id))
            else:
                cursor.execute("""
                    UPDATE user_complexity
                    SET complexity = ?, timestamp = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (complexity, user_id))

        # Фиксируем изменения в базе данных
        conn.commit()

# Сохранённые параметры сложности
def get_user_complexity(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT level, complexity FROM user_complexity WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return result

        
# Корректировка примера
def make_examples_changing(text_id, new_text_rus):
    # Используем контекстный менеджер для подключения к базе данных
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE examples SET rus = ? WHERE id = ?", (new_text_rus, text_id))
        conn.commit()
        
        
# Корректировка словаря
def make_dict_changing(rus, desc, wid):
    # Используем контекстный менеджер для подключения к базе данных
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE word_meaning_dict SET rus = ?, desc = ? WHERE wid = ?", (rus, desc, wid))
        conn.commit()
        

# Корректировка cluster_name
def make_verb_dict_changing(wid, cluster_id, verb, cluster_name):
    # Используем контекстный менеджер для подключения к базе данных
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM verb_forms_clusters WHERE wid = ? and cluster_id = ? and tense = ? LIMIT 1"
        
        cursor.execute(query, (wid, cluster_id, verb))
        check = cursor.fetchone()
        
        if check:

            result = cursor.fetchone()
            cursor.execute(
                "UPDATE verb_forms_clusters SET cluster_name = ? WHERE wid = ? AND cluster_id = ? AND tense = ?", 
                (cluster_name, wid, cluster_id, verb)
            )
            conn.commit()
        

def get_development_emoji(complexity):
    thresholds = [200, 500, 1000, 1500, 3000]
    emojis = ['🥚', '🐣', '🐥', '🦅', '🐉', '🧙🏼']
    
    for threshold, emoji in zip(thresholds, emojis):
        if complexity < threshold:
            return emoji
    return emojis[-1]

# СЦЕНАРИИ ЧАТ-БОТА
ASK_QUESTION, PROCESS_ANSWER, FIX_TRANSLATION, SELECT_DIFFICULTY = range(4)

# Новый обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user = update.effective_user
    nickname = transliterate_to_georgian(user.first_name).strip() or "ბიჭო"
    
    welcome_text = (
        f"გამარჯობა, {escape_markdown(nickname, version=2)}\\! 👋\n"
        "როგორ ხარ\\?\n\n"
        "Добро пожаловать в бот\\! Выполняй задания и улучшай свой уровень грузинского\\.\n\n"
        "\\/setting настройка сложности\n"
        "\\/fix корректировка перевода\n"
        "\\/task следующее задание\n"
    )
    keyboard = [
        [InlineKeyboardButton("⏩ შემდეგი", callback_data='next')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=chat_id,
        text=welcome_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )
    return ASK_QUESTION



# Обработки команды /task
async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id

    # Отказаустойчивый алгоритм получения данных об уровне пользователя
    if context.user_data.get('level') is None or context.user_data.get('complexity') is None:
        user = update.effective_user
        user_id = user.id
        complexity_from_bd = get_user_complexity(user_id)
        if complexity_from_bd:
            level = complexity_from_bd[0] or 'easy'
            complexity = complexity_from_bd[1] or 100
        else:
            level = 'easy'
            complexity = 100
    else:
        level = context.user_data.get('level', 'easy')
        complexity = context.user_data.get('complexity', 100)
        
    example = get_random_sentence(level, complexity)
    
    if not example:
        while complexity >= 100:
            example = get_random_sentence(level, complexity)
            if example:
                break
            complexity -= 10

    if not example:
        await context.bot.send_message(chat_id=chat_id, text="Упс... Что-то сломалось")
        return ConversationHandler.END
    
    # Сбор информации о предложении
    txt_geo = example[1]
    txt_rus = example[2]
    txt_id = example[0]

    context.user_data.update({
        'txt_geo': txt_geo,
        'txt_rus': txt_rus,
        'txt_id': txt_id,
        'gain': 0
    })

    # Дополнительные кнопки
    keyboard = []

    # Проверяем, содержит ли level слово 'simple'
    if 'simple' not in level:
        keyboard.append([InlineKeyboardButton("🙏 დახმარება", callback_data='help')])

    
    # Добавляем вторую кнопку, которая всегда должна быть
    keyboard.append([InlineKeyboardButton("⏩ შემდეგი", callback_data='next')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    emoji_level = get_development_emoji(complexity)
    message = (
        f"თარგმნე ქართულად\n"        
        f">`{escape_markdown(txt_rus, version=2)}`\n"
        f"⚙️ _{level}_\n"
        f"{emoji_level} {complexity}"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )
    return ASK_QUESTION


# Обработки нажатия на кнопку /help
async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    txt_rus = context.user_data.get('txt_rus', 'Упс... что-то сломалось')
    txt_id = context.user_data.get('txt_id')

    if txt_id is None:
        await query.message.reply_text("Не удалось получить информацию о тексте.")
        return ASK_QUESTION

    # Списание баллов за помощь
    hp_cost = 1
    context.user_data['gain'] -= hp_cost

    help_info = get_help(txt_id)
    if not help_info:
        await query.message.reply_text("Упс... что-то пошло не так, не удалось получить помощь.")
        return ASK_QUESTION

    help_words, help_verb_info = help_info[1], help_info[2]
    
    help_text = (
        f"თარგმნე ქართულად\n" 
        f">`{escape_markdown(txt_rus, version=2)}`\n•••\n"
        f"📦 {escape_markdown(help_words, version=2)}\n"
        f"🔑 {help_verb_info}\n❗️*\\-{hp_cost}* წერტილი"
    )
    
    # Создание кнопок "Конец" и "Ещё"
    keyboard = [
        [InlineKeyboardButton("🤷 არ ვიცი", callback_data='dont_know')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    
    await query.edit_message_text(text=help_text, reply_markup=reply_markup, parse_mode="MarkdownV2")
    return ASK_QUESTION

def get_random_oldstylesmile():
    oldstylesmile_list = [
        "( ͡° ͜ʖ ͡°)",
        "(▀̿Ĺ̯▀̿ ̿)",
        "ლ(ಠ益ಠლ)",
        "(◕‿◕)",
        "(‾ʖ̫‾)",
        "(ʘ‿ʘ)╯",
        "(ಠ_ಠ)",
        "(=◕ᆽ◕=)",
        "(ᵔᴥᵔ)",
        "(⊙ω⊙)",
        "( ͡❛ ͜ʖ ͡❛)",
        "(V●ᴥ●V)",
        "ʕ⁠ಠ⁠_⁠ಠ⁠ʔ"
        "(ಥ﹏ಥ)",
        "(◕︵◕)",
        "(ಥ_ʖಥ)",
        "(｡ŏ﹏ŏ)",
        "(⊙﹏⊙)",
        "(ᵕ≀ ̠ᵕ )",
        "༼ つ ಥ_ಥ ༽つ",
        "◉_◉",
        "༼ʘ̚ل͜ʘ̚༽",
        "ᕦ(ò_óˇ)ᕤ",
        "⚆ _ ⚆"
    ]
    
    return escape_markdown(random.choice(oldstylesmile_list), version=2) 


def get_random_motivation():
    motivation_list = [
        "ყოჩაღ!",
        "ძალიან კარგი!",
        "მაგარი ხარ!",
        "ვამაყობ შენით!",
        "რა მაგარია!",
        "ჯიგარი ხარ!",
        "კარგად იმუშავე!",
        "ბრავო!",
        "საუკეთესო ხარ!",
        "ოქრო ხარ!"
        ]
    
    return escape_markdown(random.choice(motivation_list), version=2) 


# Обработка ответа пользователя на /task
async def process_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    
    if update.message:
        # Пользователь отправил текстовый ответ
        user_response = update.message.text
        if not user_response:
            await update.message.reply_text("Не удалось прочитать ваш ответ, попробуйте еще раз.")
            return ASK_QUESTION
        compare_answers = True
        message = update.message
    elif update.callback_query:
        # Пользователь нажал на кнопку "Не знаю"
        query = update.callback_query
        await query.answer()
        user_response = ''  # Пользователь не предоставил ответ
        compare_answers = False
        message = query.message
    else:
        await update.message.reply_text("Произошла ошибка, попробуйте еще раз.")
        return ASK_QUESTION

    txt_geo = context.user_data.get('txt_geo', 'N/A')
    gain0 = context.user_data.get('gain', 0)
    user = update.effective_user
    user_id = user.id
    start_txt = ""
    
    if compare_answers:
        # Выполняем сравнение ответов
        gain, missing_words, extra_words = comparison_of_texts(txt_geo, user_response)
        gain = max(0, gain + gain0)
        add_user_total_score(user_id, gain)
        txt_geo2 = underline_words_in_text(escape_markdown(txt_geo, version=2), missing_words)
        
        smile_type = '🔥' if gain > 5 else '💔'
        gain_txt = f"{smile_type} *\\{gain}*\\/10"
        start_txt = f"{get_random_motivation()} " if gain > 5 else ""
        
        mult = -50 if gain <= 3 else gain * 5 if gain > 7 else 0
        
    else:
        # Пропускаем сравнение ответов
#         gain = gain0  # Без дополнительного заработка
        txt_geo2 = escape_markdown(txt_geo, version=2)
        gain = gain0
        gain_txt = get_random_oldstylesmile()
        mult = -25
    
    complexity0 = context.user_data.get('complexity')
    
    # Заплатка на случай обнуления памяти
    if complexity0 is None:
        complexity_from_bd = get_user_complexity(user_id)
        if complexity_from_bd:
            complexity0 = complexity_from_bd[1]
        else:
            complexity0 = 100
            
    complexity1 = min(max(complexity0 + mult, 100), 1000)
    
    if complexity1 != complexity0:
        context.user_data['complexity'] = complexity1
        update_user_complexity(user_id, complexity = complexity1)
    
    keyboard = [
#         [InlineKeyboardButton("❌ საკმარისია", callback_data='stop')],
        [InlineKeyboardButton("📖 ლექსიკონი", callback_data='dictionary')],
        [InlineKeyboardButton("⏩ შემდეგი", callback_data='next')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    
    result = f"{start_txt}აი სწორი პასუხი\n>{txt_geo2}\n{gain_txt}"

    
    await message.reply_text(result, reply_markup=reply_markup, parse_mode="MarkdownV2")

    # Поощрение для удачного результата
    if gain >= 8:
        await update.message.reply_sticker(sticker=random.choice(happy_sticker_list))

    return PROCESS_ANSWER


# Вызов блока /fix
async def ask_extra_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    txt_rus = context.user_data.get('txt_rus', 'Упс... что-то сломалось')
    txt_geo = context.user_data.get('txt_geo', 'N/A')
    message = (
        "📚 Перевод неточный\\? Напишите правильный\\*\n"
        f">`{escape_markdown(txt_geo, version=2)}`\n"
        f">`{escape_markdown(txt_rus, version=2)}`"
    )
    
    # Отправляем сообщение с текстом на русском и грузинском
    keyboard = [
        [InlineKeyboardButton("⏮️ უკან", callback_data='next')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode="MarkdownV2")

    return FIX_TRANSLATION


# Обработка исправления
async def handle_extra_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    extra_response = update.message.text
    user = update.effective_user
    user_id = user.id
    nickname = transliterate_to_georgian(user.first_name).strip() or "ბიჭო"
    gain = 10
    
    if not extra_response:
        await update.message.reply_text("არ მესმის, ისევ სცადე")
        return FIX_TRANSLATION

    # Получаем текст на грузинском из контекста
    txt_geo = context.user_data.get('txt_geo', 'N/A')
    txt_id = context.user_data.get('txt_id', 0)
    
    # Внесение изменения в БД
    make_examples_changing(txt_id, extra_response)
    # Награда за исправление
#     add_user_total_score(user_id, gain)
    
    # Отправляем сообщение с грузинским текстом и ответом пользователя
    message = (
        f"✅ დიდი მადლობა, {escape_markdown(nickname, version=2)}\\! გავასწორე\\!\n"
        f">`{escape_markdown(txt_geo, version=2)}`\n"
        f">`{escape_markdown(extra_response, version=2)}`"
    )
    
    # Создаем кнопку "Следующий"
    keyboard = [
        [InlineKeyboardButton("⏩ შემდეგი", callback_data='next')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

    return FIX_TRANSLATION


# Установка уровня сложности
async def set_difficulty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [
            InlineKeyboardButton("1️⃣ easy", callback_data='difficulty_easy'),
            InlineKeyboardButton("2️⃣ medium", callback_data='difficulty_medium'),
            InlineKeyboardButton("3️⃣ hard", callback_data='difficulty_hard')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🕹️ აირჩიე რამდენი რთული გსურს\n\n"
        "Самое сложное в грузинском \\- это глаголы\\. Выбери\\, что уже знаешь\\.\n\n"
        "*1\\.* только настоящее время\n"
        "*2\\.* все основные времена\n"
        "*3\\.* вообще всё\n\n"   
    )
    
    await update.message.reply_text(
        text, 
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

    # Сохраняем предыдущее состояние, чтобы вернуться к нему позже
    return SELECT_DIFFICULTY

async def difficulty_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    # Данные о пользователе
    user = update.effective_user
    user_id = user.id
    # Получаем выбранный уровень сложности из callback_data
    difficulty = query.data.split('_')[1]
    context.user_data['level'] = difficulty
    update_user_complexity(user_id, level = difficulty)
    
    keyboard = [
        [InlineKeyboardButton("⏩ შემდეგი", callback_data='next')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"✅ Уровень сложности успешно установлен на\\: *{difficulty}*\n"
    )

    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )
    
    # Возвращаемся в предыдущее состояние
    # previous_state = context.user_data.get('previous_state', ASK_QUESTION)
    # context.user_data['current_state'] = previous_state
    return ASK_QUESTION


# Статистика за последнюю неделю
async def end_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_id = user.id
    nickname = transliterate_to_georgian(user.first_name).strip() or "ბიჭო"

    gain, avg, count = get_user_total_score(user_id) or (0, 0, 0)
    avg = round(avg, 2)

    message = (
        f"🥹 ძალიან კარგი, {escape_markdown(nickname, version=2)}\\!\n"
        f"💰 ერთ კვირაში მოიგე \\{gain} HP\n\n"
        f"რეიტინგი {escape_markdown(str(avg), version=2)}\nრაოდენობა \\{count}"
    )
    
    # Создаем кнопку "Следующий"
    keyboard = [
        [InlineKeyboardButton("⏩ შემდეგი", callback_data='next')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

    return PROCESS_ANSWER

# Словарь
def get_words_for_dict_set(text_id):
    # Подключаемся к базе данных
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        query = '''
        SELECT z.word
        FROM examples x
        JOIN examples_words y on x.id = y.id
        JOIN word_meaning_dict z on y.wid = z.wid
        WHERE x.id = ? AND y.hide = 0
        '''
        cursor.execute(query, (text_id,))
        results = cursor.fetchall()
        # Извлекаем слова из результатов
        words_in_db = [row[0] for row in results]
    return set(words_in_db)  # Возвращаем как множество для удобства

def get_one_words_from_dict(text_id, word):
    # Подключаемся к базе данных
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        query = '''
        SELECT z.wid, z.word, z.rus, z.desc, z.pos, z.forms, z.alt, z.likes
        , y.verb, d.rus as verb_rus, d.geo as rus_geo
        FROM examples x
        JOIN examples_words y on x.id = y.id
        JOIN word_meaning_dict z on y.wid = z.wid
        LEFT JOIN verb_tense_dict d on y.verb = d.num
        WHERE x.id = ? AND z.word = ?
        '''
        cursor.execute(query, (text_id, word, ))
        results = cursor.fetchone()
    return results


def format_variable(var, template):
    if var:
        escaped_var = escape_markdown(str(var), version=2)
        return template.format(var=escaped_var)
    else:
        return ''

async def show_dictionary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # Получаем текст на грузинском из контекста
    txt_id = context.user_data.get('txt_id', 0)

    # Разбиваем текст на уникальные слова
    words = list(get_words_for_dict_set(txt_id))
    
    # Указываем количество кнопок в строке
    buttons_per_row = 4
    word_len_line_max = 0
    word_len_line = 0

    # Создаем кнопки для каждого слова
    keyboard = []
    row = []
    for word in words:
        word_len_line_max = max(len(word), word_len_line_max)
        word_len_line = word_len_line_max * (len(row)+1)
        if len(row) > 0 and (len(row) == buttons_per_row or word_len_line > 18):
            word_len_line_max = len(word)
            keyboard.append(row)
            row = []
        row.append(InlineKeyboardButton(word, callback_data=f'word_{word}'))
        
    # После цикла добавляем оставшиеся кнопки, если они есть
    if row:
        keyboard.append(row)
    
    # Добавляем кнопку "назад"
    keyboard.append([InlineKeyboardButton("⏩ შემდეგი", callback_data='next')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    

    txt_rus = context.user_data.get('txt_rus', 'Упс... что-то сломалось')
    txt_geo = context.user_data.get('txt_geo', 'N/A')
      
    text = (
        "📖 Выберете слово или фразу, чтобы получить перевод\n"
        f">`{escape_markdown(txt_geo, version=2)}`\n"
        f">`{escape_markdown(txt_rus, version=2)}`\n"
#         f"{escape_markdown(get_random_large_emoticon('thinking'), version=2)}"
    )

    if query.data == 'dictionary':
        # Если вызвана через кнопку "словарь", отправляем новое сообщение
        await query.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
    else:
        # Иначе редактируем существующее сообщение
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
        
    return PROCESS_ANSWER

def generate_verb_text(wid, tense):
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT x.*, y.cluster_name
    FROM verb_forms_dict x
    LEFT JOIN verb_forms_clusters y
        ON x.wid = y.wid 
        AND x.tense = y.tense 
        AND x.cluster_id = y.cluster_id
    WHERE x.wid = ? AND x.tense = ?
    """
    df = pd.read_sql_query(query, conn, params=(wid, tense))
    conn.close()

    person_order = [1, 2, 3, 13, 23, 4, 5, 6, 16, 26]
    pronouns = {
        1: "მე",
        2: "შენ",
        3: "ის",
        13: "მას",
        23: "მან",
        4: "ჩვენ",
        5: "თქვენ",
        6: "ისინი",
        16: "მათ",
        26: "იმათმა"
    }
    
    cluster_emojis = {
        1: '1️⃣',
        2: '2️⃣',
        3: '3️⃣',
        4: '4️⃣',
        5: '5️⃣'
    }

    clusters = df[['cluster_id', 'cluster_name']].drop_duplicates().sort_values('cluster_id')
    text_sections = []
    
    for idx, row in clusters.iterrows():
        cluster_id = row['cluster_id']
        cluster_name = row['cluster_name']
        
        # Добавляем заголовок кластера с эмоджи и именем
        if cluster_id:
            emoji = cluster_emojis.get(cluster_id, '#️⃣') 
            header = f"{emoji} *{cluster_name}*\n"
            text_sections.append(header)
        
        # Отбираем глаголы, принадлежащие текущему кластеру
        cluster_verbs = df[(df['cluster_id'] == cluster_id) | (df['cluster_id'].isna())]
    
        for person in person_order:
            num0 = (person % 10)
            num = num0 - 3 if num0 > 3 else num0
            words = cluster_verbs[cluster_verbs['person'] == person]['word'].tolist()
            if words:
                pronoun = pronouns[person]
                words_str = " • ".join(words)
                line = f"{num} *{pronoun}* {words_str}"
                text_sections.append(line)
                if num == 3:
                    text_sections.append('')
                
#         text_sections.append('')
    
    # Объединяем все секции в один текст
    text = '\n'.join(text_sections)
    return text

def wrap_in_quote(text):
    quoted_text = "\n".join(f">{line}" for line in text.splitlines())
    return quoted_text


async def show_word_meaning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # Извлекаем слово из callback_data
    txt_id = context.user_data.get('txt_id', 0)
    word = query.data[len('word_'):]
    
    result = get_one_words_from_dict(txt_id, word)
    if result:
        wid, word, rus, desc, pos, forms, alt, likes, verb, verb_rus, verb_geo = result
        
        context.user_data['wid'] = wid
        context.user_data['rus'] = rus
        context.user_data['desc'] = desc
        context.user_data['verb'] = verb
        
        link1 = f"ganmarteba.ge/search/{word}"
        link2 = f"def.ge/{word}"
        
        rus = rus.replace("/", " • ")
        rus = " ".join(rus.split())
        
        if alt:
            alt = alt.replace("/", " • ")
            alt = " ".join(alt.split())
            word = word + " • " + alt
            
        verb_forms_full = ""
        if "V" in verb:
            verb_forms = generate_verb_text(wid, verb)
            verb_forms_full = f"*{verb_rus}*\n🇬🇪 {verb_geo}\n\n{verb_forms}"
            verb_forms_full = f"\n{wrap_in_quote(verb_forms_full)}"
        
        text = (
            f"*💬 {escape_markdown(word, version=2)} • {escape_markdown(rus, version=2)}*\n"
            + format_variable(desc, "{var}\n")
            + "\n"
            + format_variable(pos, "ℹ️ {var}\n")
            + format_variable(forms, "♻️ {var}\n")
            + "\n"
            + format_variable(link1, "🔗 {var}\n")
            + format_variable(link2, "🔗 {var}\n")
            + verb_forms_full
        )
        
    else:
        text = "Упс... Что-то сломалось"
    
    # Создаем кнопку "дальше"
    keyboard = [
        [
#             InlineKeyboardButton("👍 Нравится", callback_data='like_word'),
            InlineKeyboardButton("✏️ ახალი", callback_data='edit_word')
        ],
        [InlineKeyboardButton("📖 ლექსიკონი", callback_data='back_to_dictionary')],
        [InlineKeyboardButton("⏩ შემდეგი", callback_data='next')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
   
    # Отправляем сообщение со значением слова
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )
    return PROCESS_ANSWER

async def back_to_dictionary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # Просто вызываем функцию show_dictionary для отображения списка слов
    return await show_dictionary(update, context)

EDIT_RUS_DESC = 100

async def edit_word_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    rus = context.user_data.get('rus')
    desc = context.user_data.get('desc')
    text = (
        "📚 Перевод недостаточно точный\\? Напишите правильный в формате:\n"
        f">`{escape_markdown(rus, version=2)}`\n"
        f">`\\[{escape_markdown(desc, version=2)}\\]`\n"
        ">`\\{\\# перевод\\}`"
    )
    
    await query.message.reply_text(
        text=text,
        parse_mode='MarkdownV2'
    )

    # Устанавливаем состояние ожидания нового ввода
    return EDIT_RUS_DESC

# Сборщик текста из фигурных скобок 
def process_user_input(user_input):
    pattern = r'\{([^{}]*)\}'
    extracted_text = re.findall(pattern, user_input)
    cleaned_input = re.sub(pattern, '', user_input)
    cleaned_input = ' '.join(cleaned_input.split())
    
    return extracted_text, cleaned_input

async def receive_new_rus_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    user = update.effective_user
    user_id = user.id
    nickname = transliterate_to_georgian(user.first_name).strip() or "ბიჭო"
    
    # Инициализируем rus и desc как None
    rus = None
    desc = None

    wid = context.user_data.get('wid')
    rus0 = context.user_data.get('rus')
    desc0 = context.user_data.get('desc')
    
    extract, user_input = process_user_input(user_input)
    
    if len(extract) > 0:
        verb = context.user_data.get('verb')
        for index, item in enumerate(extract):
            first_char = item[0]  # Берём первый символ
            if first_char.isdigit():  # Проверяем, является ли он цифрой
                cluster_id = int(first_char)  # Преобразуем в число
                cluster_name = item[1:].strip().lower()
                make_verb_dict_changing(wid, cluster_id, verb, cluster_name)
                

    # Проверяем, есть ли описание в квадратных скобках
    if '[' in user_input or ']' in user_input:

        start = user_input.find('[')
        end = user_input.find(']', start)
        
        # Проверяем корректность скобок
        if end == -1 or start == -1:
            rus = None
            desc = None
        
        else:

            desc = user_input[start + 1:end].strip()
                
            if desc[:1] == "+":
                desc = desc[1:2].upper() + desc[2:]
                if not desc0.endswith("."):
                    desc0 += "."
                desc = desc0 + " " + desc
            else:
                desc = desc[:1].upper() + desc[1:]
                
            rus_part = user_input[:start] + user_input[end + 1:]
            rus = rus_part.strip().lower()
    else:
            rus = user_input.strip().lower()

    rus = None if rus is None or len(rus) == 0 else rus
    desc = None if desc is None or len(desc) == 0 else desc
    
    rus = rus or rus0
    desc = desc or desc0
    
    if not desc.endswith("."):
        desc += "."
    
    # Обновляем запись в базе данных
    make_dict_changing(rus, desc, wid)
    
    keyboard = [
        [InlineKeyboardButton("📖 ლექსიკონი", callback_data='dictionary')],
        [InlineKeyboardButton("⏩ შემდეგი", callback_data='next')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text=f"✅ დიდი მადლობა, {escape_markdown(nickname, version=2)}\\! გავასწორე\\!\n",
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )
    
    # Возвращаемся к основному состоянию
    return PROCESS_ANSWER



# Функция для обработки нажатия кнопки "Ещё"
async def retry_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    # Перезапуск процесса, вызвав команду /task заново
    return await task_start(update, context)


# Функция для обработки команды /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Вопрос отменён")
    return ConversationHandler.END

# Обновляем функцию invalid_command
async def invalid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.strip() == '/setting':
        # Если введена команда /setting, переходим к настройке сложности
        return await set_difficulty(update, context)
    else:
        await update.message.reply_text("❌ Ответьте на вопрос")
        return context.user_data.get('current_state', ASK_QUESTION)


    
async def send_reminders(context: ContextTypes.DEFAULT_TYPE):

    # Список возможных мотивирующих сообщений
    motivational_texts = [
        "ასე ვერ გახდები ჯედაი 🌌",
        "ჰოგვარტსში მარტო ჯადოსნური ცოდნით მიდიან 🧙🏼",
        "ასე ვერ გახდები სუპერგმირი 💥",
        "ბეტმენი ვერაფერს გიშველის, თუ თავად არ იმუშავებ 🦇",
        "ასე ვერ გახდები დრაკონების დედა 🐉",
        "ეს არ არის იბიცა, აქ ხაჭაპური სჯობია პიცას 🕺🏼",
        "ასე ვერ გახდები ვეფხისტყაოსანი 🐯"
    ]
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        query = '''
        SELECT user_id
        , CAST(min(julianday('now') - julianday(timestamp)) as INTEGER) as days
        FROM user_scores
        --WHERE user_id = 156855338
        GROUP BY user_id
        '''
        cursor.execute(query) 
        rows = cursor.fetchall()

    for (user_id, days) in rows:

        if days > 0:
            
            text = (
                "*⏱️ Время учить грузинский*\n\n"
                f"უკვე *{days}* დღე ვარჯიშის გარეშეა\\!\n"
                f"{escape_markdown(random.choice(motivational_texts), version=2)}"
            )

            keyboard = [
                [InlineKeyboardButton("⏩ შემდეგი", callback_data='next')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2"
            )
#         return ASK_QUESTION
        
        
# Создание бота
app = ApplicationBuilder().token(TOKEN).build()


# Пример настройки внутри main или после app.run_polling():
app.job_queue.run_repeating(send_reminders, interval=24*60*60, first=60*60)
    
# Настройка ConversationHandler
conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("start", start),  # Добавляем обработчик /start
        CommandHandler("task", task_start), 
        CallbackQueryHandler(task_start, pattern='next')
    ],
    states={
        ASK_QUESTION: [
            CommandHandler("setting", set_difficulty),
            CommandHandler("task", task_start),
            CallbackQueryHandler(difficulty_callback, pattern='^difficulty_'),
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_answer),  # Обрабатываем только текст
            MessageHandler(filters.COMMAND, invalid_command),  # Запрещаем команды
            CallbackQueryHandler(show_help, pattern='help'),
            CallbackQueryHandler(process_answer, pattern='^dont_know$'),  # Обработка кнопки "Не знаю"
            CallbackQueryHandler(retry_task, pattern='next')  # Повторный запуск
        ],
        PROCESS_ANSWER: [
            CommandHandler("fix", ask_extra_question),  # Обработчик команды /fix
            CommandHandler("setting", set_difficulty),
            CallbackQueryHandler(show_dictionary, pattern='^dictionary$'),
            CallbackQueryHandler(show_word_meaning, pattern='^word_'),
            CallbackQueryHandler(show_dictionary, pattern='^back_to_dictionary$'),
#             CallbackQueryHandler(like_word_handler, pattern='^like_word$'),
            CallbackQueryHandler(edit_word_handler, pattern='^edit_word$'),
            CallbackQueryHandler(difficulty_callback, pattern='^difficulty_'),
            CallbackQueryHandler(end_conversation, pattern='stop'),
            CallbackQueryHandler(retry_task, pattern='next')
        ],
        EDIT_RUS_DESC: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_rus_desc),
        ],
        FIX_TRANSLATION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_extra_answer),
            CallbackQueryHandler(retry_task, pattern='next') # Обработка кнопки "Продолжить"
        ],
        SELECT_DIFFICULTY: [
            CallbackQueryHandler(difficulty_callback, pattern='^difficulty_'),
            # Обрабатываем команду /cancel
            CommandHandler("cancel", cancel),
            # Если пользователь вводит текст или команду, предупреждаем
            MessageHandler(filters.ALL, invalid_command),
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False  # Разрешаем обработку других сообщений
)

# Добавление ConversationHandler в приложение
app.add_handler(conv_handler, group=1)

# Регистрация глобального обработчика для кнопки "Next"
# app.add_handler(CallbackQueryHandler(retry_task, pattern='next'))

# Запуск бота
app.run_polling()