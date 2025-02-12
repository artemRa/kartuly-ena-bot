import re

# Функция для транслитерации текста на грузинский язык
def transliterate_to_georgian(text) -> str:
 
    transliteration_map = {
        'a': 'ა', 'b': 'ბ', 'g': 'გ', 'd': 'დ', 'e': 'ე', 
        'v': 'ვ', 'z': 'ზ', 't': 'თ', 'i': 'ი', 'k': 'კ', 
        'l': 'ლ', 'm': 'მ', 'n': 'ნ', 'o': 'ო', 'p': 'პ',
        'zh': 'ჟ', 'r': 'რ', 's': 'ს', 't': 'ტ', 'u': 'უ', 
        'f': 'ფ', 'q': 'ქ', 'gh': 'ღ', 'sh': 'შ', 'ch': 'ჩ', 
        'ts': 'ც', 'dz': 'ძ', 'ts': 'წ', 'ch': 'ჭ', 'kh': 'ხ',
        'j': 'ჯ', 'h': 'ჰ', 
    }

    result = ""
    text = text.lower()
    i = 0

    while i < len(text):
        # двухбуквенные соответствия
        if i+1 < len(text) and text[i:i+2] in transliteration_map:
            result += transliteration_map[text[i:i+2]]
            i += 2
        # однобуквенные соответствия
        elif text[i] in transliteration_map:
            result += transliteration_map[text[i]]
            i += 1
        else:
            # символ не найден в словаре
            result += text[i]
            i += 1
        
        # удаляем повторяющиеся символы
        result = re.sub(r'([ა-ჰ])\1+', r'\1', result)
        
    return result