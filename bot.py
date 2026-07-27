from flask import Flask, request, json
import sqlite3
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

app = Flask(__name__)

# Твои данные
TOKEN = "vk1.a.BVFM-nypRNiDpNCZX3_WoOh5kBohFidE0CEkOm3zFv33wF1Zle-F5GiJla1-p1s5J3v9I6la1-pl5sJ3v9I6"
GROUP_ID = 198743474
CONFIRMATION_CODE = "a7d82bb2"

# Инициализация VK API для отправки ответов
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()

# Настройка базы данных SQLite для очков
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            score INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Функция добавления очков пользователю
def add_score(user_id, points=1):
    if not user_id:
        return
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT score FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute('UPDATE users SET score = score + ? WHERE user_id = ?', (points, user_id))
    else:
        cursor.execute('INSERT INTO users (user_id, score) VALUES (?, ?)', (user_id, points))
    conn.commit()
    conn.close()

@app.route('/', methods=['POST'])
def processing():
    data = json.loads(request.data.decode('utf-8'))
    
    if 'type' in data:
        # 1. Подтверждение сервера для ВКонтакте
        if data['type'] == 'confirmation':
            return CONFIRMATION_CODE
            
        # 2. Новое сообщение (команда /топ)
        elif data['type'] == 'message_new':
            message = data['object']['message']
            user_id = message['from_id']
            text = message.get('text', '').lower()
            
            if text in ['/топ', '!топ', 'топ']:
                # Получаем топ-5 пользователей из базы
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                cursor.execute('SELECT user_id, score FROM users ORDER BY score DESC LIMIT 5')
                top_users = cursor.fetchall()
                conn.close()
                
                if not top_users:
                    reply_text = "Рейтинг пока пуст! Будьте первым, кто поставит лайк или напишет комментарий."
                else:
                    reply_text = "🏆 Топ-5 активных участников:\n"
                    for index, (uid, score) in enumerate(top_users, start=1):
                        # Получаем имя пользователя через VK API
                        try:
                            user_info = vk.users.get(user_ids=uid)[0]
                            name = f"{user_info['first_name']} {user_info['last_name']}"
                        except:
                            name = f"ID{uid}"
                        reply_text += f"{index}. {name} — {score} очков\n"
                
                # Отправляем сообщение в чат/личку
                vk.messages.send(
                    peer_id=message['peer_id'],
                    message=reply_text,
                    random_id=0
                )
            return 'ok'

        # 3. Лайк на запись (начисление очка)
        elif data['type'] == 'like_add':
            obj = data['object']
            # Проверяем, что лайк поставлен на запись на стене (object_type == 'wall')
            if obj.get('object_type') == 'wall':
                user_id = obj.get('liker_id')
                add_score(user_id, 1)
            return 'ok'

        # 4. Комментарий на стене (начисление очка)
        elif data['type'] == 'wall_reply_new':
            user_id = data['object'].get('from_id')
            add_score(user_id, 1)
            return 'ok'
            
    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
