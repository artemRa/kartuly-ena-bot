import sqlite3
import pandas as pd
from config import DB_PATH

# Получение случайного предложения /task
def get_random_sentence(level, complexity):
    # границы по сложности
    low = 0 if complexity == 100 else complexity * 0.8
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
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

    return result


# Получение подсказки /taks-help
def get_help(id):
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

    return result


# Получить текущий скор по пользователю - НЕ ИСПОЛЬЗУЕТСЯ
def get_user_total_score(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT SUM(score), AVG(score), COUNT(*)
        FROM user_scores 
        WHERE DATE('now', '-7 days') <= DATE(timestamp)
        AND user_id=?
        ''', (user_id,))
        result = cursor.fetchone()

    return result


# Сохранённые параметры сложности по пользователю
def get_user_complexity(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT level, complexity FROM user_complexity WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return result


# Множество слов для словаря по выбраному предложению 
def get_words_for_dict_set(text_id):
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
        words_in_db = [row[0] for row in results]
    return set(words_in_db)


# Информация по выбранному слову из словаря
def get_one_words_from_dict(text_id, word):
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