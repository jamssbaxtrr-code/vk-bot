import os
import sqlite3
import vk_api
from flask import Flask, request, json

app = Flask(__name__)

# Инициализация данных
TOKEN = "vk1.a.BVFM-nypRNWDpdNCZXJ_wVoDh9kBohFkREJ0cEkOWh3zFv33wf1Zrie2zfFqSw1k0IE_WF2GOIbDxfiz6w_1OmTAlgKUoILqnRGgXR9dRuyqcO2oIi-WyaLg5b3Ei00XoLFjoqtlCJLVREvNP5POquMyW55HqACgXmLNmtbu-cvLil63lZ3F7BTC65MxKuzBj4c6RH9F3UXkDwlIzL3XDA"
GROUP_ID = 198743474
CONFIRMATION_CODE = "твой_код_подтверждения_из_вк" # Появится в настройках группы ВК

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()

# Подключение к базе данных и создание таблицы
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            points INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Функция для добавления очков пользователю
def add_points(user_id, amount):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row:
        new_points = row[0] + amount
        cursor.execute("UPDATE users SET points = ? WHERE user_id = ?", (new_points, user_id))
    else:
        cursor.execute("INSERT INTO users (user_id, points) VALUES (?, ?)", (user_id, amount))
        
    conn.commit()
    conn.close()

@app.route("/", methods=["POST"])
def processing():
    data = json.loads(request.data.decode('utf-8'))
    
    # Проверка типа события для подтверждения сервера в ВК
    if data.get('type') == 'confirmation':
        return CONFIRMATION_CODE
        
    if data.get('group_id') != GROUP_ID:
        return "invalid group id"
        
    event_type = data.get('type')
    
    # Обработка нового комментария на стене
    if event_type == 'wall_reply_new':
        event_obj = data.get('object', {})
        user_id = event_obj.get('from_id')
        if user_id and user_id > 0:
            add_points(user_id, 5)
            print(f"Пользователь {user_id} получил 5 очков за комментарий.")
            
    # Обработка нового сообщения в ЛС
    elif event_type == 'message_new':
        message_data = data.get('object', {}).get('message', {})
        user_id = message_data.get('from_id')
        text = message_data.get('text', '').lower()
        
        if text in ['очки', 'рейтинг', 'баланс']:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            points = row[0] if row else 0
            conn.close()
            
            vk.messages.send(
                user_id=user_id,
                message=f"Твой текущий баланс активности: {points} очков.",
                random_id=0
            )
            
        elif text in ["топ", "рейтинг топ", "топ игроков"]:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, points FROM users ORDER BY points DESC LIMIT 10")
            top_users = cursor.fetchall()
            conn.close()
            
            if not top_users:
                top_text = "Пока нет активных игроков в рейтинге."
            else:
                top_text = "🏆 Топ-10 активных игроков:\n\n"
                for index, (uid, pts) in enumerate(top_users, start=1):
                    top_text += f"{index}. [id{uid}|Игрок] — {pts} очков\n"
                    
            vk.messages.send(
                user_id=user_id,
                message=top_text,
                random_id=0
            )
            
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
