from flask import Flask, request, json
import sqlite3
import vk_api

app = Flask(__name__)

TOKEN = "vk1.a.BVFM-nypRNWDpdNCZXJ_wVoDh9kBohFkREJ0cEkOWh3zFv33wf1Zrie2zfFqSw1k0IE_WF2GOIbDxfiz6w_1OmTAlgKUoILqnRGgXR9dRuyqcO2oIi-WyaLg5b3Ei00XoLFjoqtlCJLVREvNP5POquMyW55HqACgXmLNmtbu-cvLil63lZ3F7BTC65MxKuzBj4c6RH9F3UXkDwlIzL3XDA"
GROUP_ID = 198743474
CONFIRMATION_CODE = "a7d82bb2"

# Твой ID администратора
ADMIN_ID = 474329598

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()

def init_db():
    conn = sqlite3.connect('database.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, score INTEGER DEFAULT 0)')
    cursor.execute('CREATE TABLE IF NOT EXISTS liked_posts (user_id INTEGER, object_id INTEGER, PRIMARY KEY (user_id, object_id))')
    cursor.execute('CREATE TABLE IF NOT EXISTS post_comments (post_id INTEGER PRIMARY KEY, first_commenter_id INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS post_commenters (post_id INTEGER, user_id INTEGER, PRIMARY KEY (post_id, user_id))')
    conn.commit()
    conn.close()

init_db()

def update_score(user_id, points):
    if not user_id:
        return
    conn = sqlite3.connect('database.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT score FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        new_score = max(0, row[0] + points)
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

    if not request.data:
        return "OK", 200

    try:
        data = json.loads(request.data.decode('utf-8'))
    except Exception:
        return "OK", 200
    
    if 'type' in data:
        if data['type'] == 'confirmation':
            return CONFIRMATION_CODE
            
        elif data['type'] == 'message_new':
            try:
                message = data['object']['message']
                user_id = int(message['from_id'])
                text = message.get('text', '').strip()
                text_lower = text.lower()
                
                # Публичные команды
                if text_lower in ['/топ', '!топ', 'топ']:
                    conn = sqlite3.connect('database.db')
                    cursor = conn.cursor()
                    cursor.execute('SELECT user_id, score FROM users ORDER BY score DESC LIMIT 5')
                    top_users = cursor.fetchall()
                    conn.close()
                    
                    if not top_users:
                        reply_text = "Рейтинг пока пуст!"
                    else:
                        user_ids = [uid for uid, score in top_users]
                        try:
                            user_infos = vk.users.get(user_ids=user_ids)
                            names_dict = {user['id']: f"{user['first_name']} {user['last_name']}" for user in user_infos}
                        except Exception:
                            names_dict = {}

                        reply_text = "🏆 Топ-5 участников:\n"
                        for index, (uid, score) in enumerate(top_users, start=1):
                            name = names_dict.get(uid, f"id{uid}")
                            reply_text += f"{index}. {name} — {score} очков\n"
                            
                    vk.messages.send(peer_id=message['peer_id'], message=reply_text, random_id=0)
                
                elif text_lower in ['/статистика', 'мои очки', 'статистика']:
                    conn = sqlite3.connect('database.db')
                    cursor = conn.cursor()
                    cursor.execute('SELECT score FROM users WHERE user_id = ?', (user_id,))
                    row = cursor.fetchone()
                    conn.close()
                    user_score = row[0] if row else 0
                    vk.messages.send(peer_id=message['peer_id'], message=f"📊 У вас набрано: {user_score} очков.", random_id=0)

                # Админские команды
                elif text_lower.startswith('/доксброс'):
                    if user_id != ADMIN_ID:
                        return 'ok'
                    conn = sqlite3.connect('database.db')
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM users')
                    cursor.execute('DELETE FROM liked_posts')
                    cursor.execute('DELETE FROM post_comments')
                    cursor.execute('DELETE FROM post_commenters')
                    conn.commit()
                    conn.close()
                    vk.messages.send(peer_id=message['peer_id'], message="🔄 Статистика успешно сброшена!", random_id=0)

                elif text_lower.startswith('/докбаллы'):
                    if user_id != ADMIN_ID:
                        return 'ok'
                    parts = text.split()
                    if len(parts) >= 3:
                        try:
                            target_id_str = parts[1]
                            points = int(parts[2])
                            clean_target = target_id_str.replace('@', '').replace('vk.com/', '').strip('/')
                            
                            if clean_target.startswith('id') and clean_target[2:].isdigit():
                                target_id = int(clean_target[2:])
                            elif clean_target.isdigit():
                                target_id = int(clean_target)
                            else:
                                resolved = vk.utils.resolveScreenName(screen_name=clean_target)
                                if resolved and resolved.get('type') == 'user':
                                    target_id = resolved['object_id']
                                else:
                                    raise Exception("User not found")
                                    
                            update_score(target_id, points)
                            vk.messages.send(peer_id=message['peer_id'], message=f"✅ Успешно начислено {points} очков.", random_id=0)
                        except Exception:
                            vk.messages.send(peer_id=message['peer_id'], message="❌ Ошибка в формате ID или баллов.", random_id=0)

                elif text_lower.startswith('/докбаллыснять'):
                    if user_id != ADMIN_ID:
                        return 'ok'
                    parts = text.split()
                    if len(parts) >= 3:
                        try:
                            target_id_str = parts[1]
                            points = int(parts[2])
                            clean_target = target_id_str.replace('@', '').replace('vk.com/', '').strip('/')
                            
                            if clean_target.startswith('id') and clean_target[2:].isdigit():
                                target_id = int(clean_target[2:])
                            elif clean_target.isdigit():
                                target_id = int(clean_target)
                            else:
                                resolved = vk.utils.resolveScreenName(screen_name=clean_target)
                                if resolved and resolved.get('type') == 'user':
                                    target_id = resolved['object_id']
                                else:
                                    raise Exception("User not found")
                                    
                            update_score(target_id, -points)
                            vk.messages.send(peer_id=message['peer_id'], message=f"✅ Успешно снято {points} очков.", random_id=0)
                        except Exception:
                            vk.messages.send(peer_id=message['peer_id'], message="❌ Ошибка в формате ID или баллов.", random_id=0)

            except Exception:
                pass
                
            return 'ok'

        elif data['type'] == 'like_add':
            try:
                obj = data['object']
                user_id = int(obj.get('liker_id') or obj.get('user_id', 0))
                object_id = obj.get('object_id')
                if user_id and object_id:
                    conn = sqlite3.connect('database.db')
                    cursor = conn.cursor()
                    cursor.execute('SELECT 1 FROM liked_posts WHERE user_id = ? AND object_id = ?', (user_id, object_id))
                    if not cursor.fetchone():
                        cursor.execute('INSERT OR IGNORE INTO liked_posts (user_id, object_id) VALUES (?, ?)', (user_id, object_id))
                        conn.commit()
                        update_score(user_id, 1)
                    conn.close()
            except Exception:
                pass
            return 'ok'

        elif data['type'] == 'like_remove':
            try:
                obj = data['object']
                user_id = int(obj.get('liker_id') or obj.get('user_id', 0))
                object_id = obj.get('object_id')
                if user_id and object_id:
                    conn = sqlite3.connect('database.db')
                    cursor = conn.cursor()
                    cursor.execute('SELECT 1 FROM liked_posts WHERE user_id = ? AND object_id = ?', (user_id, object_id))
                    if cursor.fetchone():
                        cursor.execute('DELETE FROM liked_posts WHERE user_id = ? AND object_id = ?', (user_id, object_id))
                        conn.commit()
                        update_score(user_id, -1)
                    conn.close()
            except Exception:
                pass
            return 'ok'

        elif data['type'] == 'wall_reply_new':
            try:
                obj = data['object']
                user_id = int(obj.get('from_id') or obj.get('user_id', 0))
                post_id = obj.get('post_id') or obj.get('object_id')
                
                if user_id > 0 and post_id:
                    conn = sqlite3.connect('database.db')
                    cursor = conn.cursor()
                    
                    cursor.execute('SELECT 1 FROM post_commenters WHERE post_id = ? AND user_id = ?', (post_id, user_id))
                    already_rewarded = cursor.fetchone()
                    
                    if not already_rewarded:
                        cursor.execute('INSERT OR IGNORE INTO post_commenters (post_id, user_id) VALUES (?, ?)', (post_id, user_id))
                        
                        cursor.execute('SELECT first_commenter_id FROM post_comments WHERE post_id = ?', (post_id,))
                        row = cursor.fetchone()
                        
                        if not row:
                            cursor.execute('INSERT OR IGNORE INTO post_comments (post_id, first_commenter_id) VALUES (?, ?)', (post_id, user_id))
                            conn.commit()
                            conn.close()
                            update_score(user_id, 2)
                        else:
                            conn.commit()
                            conn.close()
                            update_score(user_id, 1)
                    else:
                        conn.close()
            except Exception:
                pass
                
            return 'ok'
            
    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
