from flask import Flask, request, json

app = Flask(__name__)

# Твои актуальные данные
TOKEN = "vk1.a.BVFM-nypRNiDpNCZX3_WoOh5kBohFidE0CEkOm3zFv33wF1Zle-F5GiJla1-p1s5J3v9I6la1-pl5sJ3v9I6"
GROUP_ID = 198743474
CONFIRMATION_CODE = "a7d82bb2"

@app.route('/', methods=['POST'])
def processing():
    # Распаковываем JSON-запрос от ВКонтакте
    data = json.loads(request.data.decode('utf-8'))
    
    # Проверяем тип события
    if 'type' in data:
        if data['type'] == 'confirmation':
            # Возвращаем строку подтверждения, которую требует ВК
            return CONFIRMATION_CODE
            
        elif data['type'] == 'message_new':
            # Сюда можно будет добавить логику бота
            return 'ok'
            
    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
