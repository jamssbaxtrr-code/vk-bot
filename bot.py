from flask import Flask, request, json
import sqlite3
import vk_api

app = Flask(__name__)

# Твои данные
TOKEN = "vk1.a.BVFM-nypRNiDpNCZX3_WoOh5kBohFidE0CEkOm3zFv33wF1Zle-F5GiJla1-p1s5J3v9I6la1-pl5sJ3v9I6"
GROUP_ID = 198743474
CONFIRMATION_CODE = "a7d82bb2"

# Инициализация VK API
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()

# Настройка базы данных
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Таблица пользователей и их очков
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            score INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица истории лайков (защита от накрутки)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS liked_posts (
            user_id INTEGER,
            object_id INTEGER,
            PRIMARY KEY (user_id, object_id)
        )
    ''')
    
    # Таблица истории комментариев (проверка на первый комментарий и защиту от накрутки)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS post_comments (
            post_id INTEGER PRIMARY KEY,
            first_commenter_id INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Функция изменения очков пользователя
def update_score(user_id, points):
    if not user_id:
        return
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT score FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        new_score = max(0, row[0] + points) # Очки не могут уходить в минус
        cursor.execute('UPDATE users SET score = ? WHERE user_id = ?', (new_score, user_id))
    else:
        if points > 0:
            cursor.execute('INSERT INTO users (user_id, score) VALUES (?, ?)', (user_id, points))
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def processing():
    if request.method == 'GET':
        return "Bot is running!", 200

    # Защита от пустых запросов (например, от пингов UptimeRobot)
    if not request.data:
        return "OK", 200

    try:
        data = json.loads(request.data.decode('utf-8'))
    except Exception:
        return "OK", 200
    
    if 'type' in data:
        # 1. Подтверждение сервера
        if data['type'] == 'confirmation':
            return CONFIRMATION_CODE
            
        # 2. Сообщения и админ-команды
        elif data['type'] == 'message_new':
            message = data['object']['message']
            user_id = message['from_id']
            text = message.get('text', '').strip()
            text_lower = text.lower()
            
            # Команда ТОП-5
            if text_lower in ['/топ', '!топ', 'топ']:
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                cursor.execute('SELECT user_id, score FROM users ORDER BY score DESC LIMIT 5')
                top_users = cursor.fetchall()
                conn.close()
                
                if not top_users:
                    reply_text = "Рейтинг пока пуст! Ставьте лайки и пишите комментарии, чтобы заработать очки."
                else:
                    reply_text = "🏆 Топ-5 активных участников:\n"
                    for index, (uid, score) in enumerate(top_users, start=1):
                        try:
                            user_info = vk.users.get(user_ids=uid)[0]
                            name = f"{user_info['first_name']} {user_info['last_name']}"
                        except:
                            name = f"ID{uid}"
                        reply_text += f"{index}. @id{uid} ({name}) — {score} очков\n"
                
                vk.messages.send(peer_id=message['peer_id'], message=reply_text, random_id=0)
            
            # Команда ЛИЧНОЙ статистики
            elif text_lower in ['/статистика', 'мои очки', 'статистика', '/мои очки']:
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                cursor.execute('SELECT score FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                conn.close()
                
                user_score = row[0] if row else 0
                reply_text = f"📊 Ваша активность:\nУ вас набрано: {user_score} очков."
                vk.messages.send(peer_id=message['peer_id'], message=reply_text, random_id=0)

            # Команда СБРОСА всей статистики
            elif text_lower in ['/сброс', 'сбросить топ']:
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                cursor.execute('DELETE FROM users')
                cursor.execute('DELETE FROM liked_posts')
                cursor.execute('DELETE FROM post_comments')
                conn.commit()
                conn.close()
                vk.messages.send(peer_id=message['peer_id'], message="🔄 Вся статистика успешно сброшена!", random_id=0)

            # Команда ВЫДАЧИ баллов (например: /дать @musk_2000 10 или /выдать @id 10)
            elif text_lower.startswith(('/дать', '/плюс', 'выдать', '/выдать')):
                parts = text.split()
                if len(parts) >= 3:
                    target_id_str = parts[1]
                    try:
                        points = int(parts[2])
                        
                        clean_target = target_id_str.replace('@', '').replace('vk.com/', '').strip('/')
                        
                        if clean_target.startswith('id') and clean_target[2:].isdigit():
                            target_id = int(clean_target[2:])
                        elif clean_target.isdigit():
                            target_id = int(clean_target)
                        else:
                            user_info = vk.users.get(user_ids=clean_target)[0]
                            target_id = user_info['id']

                        update_score(target_id, points)
                        vk.messages.send(peer_id=message['peer_id'], message=f"✅ Успешно начислено {points} очков пользователю.", random_id=0)
                    except Exception as e:
                        vk.messages.send(peer_id=message['peer_id'], message="❌ Ошибка: пользователь не найден или неверный формат.", random_id=0)

            # Команда УДАЛЕНИЯ/УМЕНЬШЕНИЯ баллов (например: /забрать @musk_2000 5)
            elif text_lower.startswith(('/забрать', '/минус', '/удалить')):
                parts = text.split()
                if len(parts) >= 3:
                    target_id_str = parts[1]
                    try:
                        points = int(parts[2])
                        
                        clean_target = target_id_str.replace('@', '').replace('vk.com/', '').strip('/')
                        
                        if clean_target.startswith('id') and clean_target[2:].isdigit():
                            target_id = int(clean_target[2:])
                        elif clean_target.isdigit():
                            target_id = int(clean_target)
                        else:
                            user_info = vk.users.get(user_ids=clean_target)[0]
                            target_id = user_info['id']

                        update_score(target_id, -points)
                        vk.messages.send(peer_id=message['peer_id'], message=f"✅ Успешно списано {points} очков у пользователя.", random_id=0)
                    except Exception as e:
                        vk.messages.send(peer_id=message['peer_id'], message="❌ Ошибка: пользователь не найден или неверный формат.", random_id=0)
                
            return 'ok'

        # 3. Добавление лайка (с защитой от накрутки)
        elif data['type'] == 'like_add':
            obj = data['object']
            user_id = obj.get('liker_id') or obj.get('user_id')
            object_id = obj.get('object_id')
            
            if user_id and object_id:
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM liked_posts WHERE user_id = ? AND object_id = ?', (user_id, object_id))
                if not cursor.fetchone():
                    cursor.execute('INSERT INTO liked_posts (user_id, object_id) VALUES (?, ?)', (user_id, object_id))
                    conn.commit()
                    update_score(user_id, 1)
                conn.close()
            return 'ok'

        # 4. Удаление лайка (чтобы забрать балл назад)
        elif data['type'] == 'like_remove':
            obj = data['object']
            user_id = obj.get('liker_id') or obj.get('user_id')
            object_id = obj.get('object_id')
            
            if user_id and object_id:
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM liked_posts WHERE user_id = ? AND object_id = ?', (user_id, object_id))
                if cursor.fetchone():
                    cursor.execute('DELETE FROM liked_posts WHERE user_id = ? AND object_id = ?', (user_id, object_id))
                    conn.commit()
                    update_score(user_id, -1)
                conn.close()
            return 'ok'

        # 5. Комментарий (с бонусом первому комментатору)
        elif data['type'] == 'wall_reply_new':
            obj = data['object']
            user_id = obj.get('from_id')
            post_id = obj.get('post_id')
            
            if user_id and post_id:
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                
                cursor.execute('SELECT first_commenter_id FROM post_comments WHERE post_id = ?', (post_id,))
                row = cursor.fetchone()
                
                if not row:
                    # Первый комментарий — 2 балла
                    cursor.execute('INSERT INTO post_comments (post_id, first_commenter_id) VALUES (?, ?)', (post_id, user_id))
                    conn.commit()
                    conn.close()
                    update_score(user_id, 2)
                else:
                    conn.close()
                
            return 'ok'
            
    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
