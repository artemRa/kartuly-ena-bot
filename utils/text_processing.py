import re
from telegram.helpers import escape_markdown

# Очистка текста от пунктуации и цифр
def clean_text(text):
    text = re.sub(r'[^\w\s]|[\d]', ' ', text)
    text = " ".join(text.lower().split())
    return text

# Предобработка спорных слов
def preprocess_word(word):
    # в начале слова
    if word.startswith('ჰ'):
        word = word[1:]
    # в конце слова
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
            
    # Лишние слова в ответе
    extra_words = set()
    for word in words2:
        processed_word = preprocess_word(word)
        if processed_word not in processed_words1:
            extra_words.add(word)
            
    # Пересечение и объединение множеств обработанных слов
    intersection = processed_words1.intersection(processed_words2)
    union = processed_words1.union(processed_words2)
    
    # Псевдо-коэффициент Жаккара
    if len(union) == 0:
        jaccard = 1.0  # Если оба текста пустые
    else:
        jaccard = len(intersection) / len(processed_words1)
    
    # Преобразуем коэффициент в балл от 0 до 10
    score = round(jaccard * 10)
    
    # Смягчение логики
    if len(processed_words1) > 5 and len(intersection) > 0:
        score = max(score, 10 - len(unique_words))
    
    return score, unique_words, extra_words


# Форматирование слов жирным шрифтом
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

# Форматирование текста в формате Markdown
def format_variable(var, template):
    if var:
        escaped_var = escape_markdown(str(var), version=2)
        return template.format(var=escaped_var)
    else:
        return ''
    
# Обёртка текста в цитату
def wrap_in_quote(text):
    quoted_text = "\n".join(f">{line}" for line in text.splitlines())
    return quoted_text