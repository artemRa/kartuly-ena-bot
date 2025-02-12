import sqlite3
from config import DB_PATH

# Добавление баллов пользователю
def add_user_total_score(user_id, gain):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO user_scores (user_id, score) VALUES (?, ?)", (user_id, gain))
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
            # Пользователь существует, обновляем параметр
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

     
# Корректировка предложения
def make_examples_changing(text_id, new_text_rus):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE examples SET rus = ? WHERE id = ?", (new_text_rus, text_id))
        conn.commit()
        
        
# Корректировка словаря
def make_dict_changing(rus, desc, wid):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE word_meaning_dict SET rus = ?, desc = ? WHERE wid = ?", (rus, desc, wid))
        conn.commit()
        

# Корректировка cluster_name в таблице verb_forms_clusters
def make_verb_dict_changing(wid, cluster_id, verb, cluster_name):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM verb_forms_clusters WHERE wid = ? and cluster_id = ? and tense = ? LIMIT 1"  
        cursor.execute(query, (wid, cluster_id, verb))
        check = cursor.fetchone()
        
        # корректируем, если глоагол есть в таблице
        if check:
            cursor.execute(
                "UPDATE verb_forms_clusters SET cluster_name = ? WHERE wid = ? AND cluster_id = ? AND tense = ?", 
                (cluster_name, wid, cluster_id, verb)
            )
            conn.commit()
        