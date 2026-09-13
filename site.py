from flask import Flask, request, redirect, render_template_string, session, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
import webbrowser
import threading
import os
import time
import datetime
import json

app = Flask(__name__)
app.secret_key = "artline_secret_key_2026_xK9mP"

ADMIN_IP = "5.137.202.41"
ADMIN_PASSWORD = "ArtLine2026Admin!"
REVIEWS_FILE = "reviews.txt"
PENDING_FILE = "pending_reviews.txt"
SETTINGS_FILE = "settings.json"
UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per day", "100 per hour"],
    storage_uri="memory://"
)

BLOCKED_IPS = set()
REQUEST_LOG = {}
BAD_WORDS = ["хуй", "пизд", "бляд", "ебан", "долбо", "мудак", "говно", "сука"]

def check_ddos(ip):
    now = time.time()
    if ip not in REQUEST_LOG:
        REQUEST_LOG[ip] = []
    REQUEST_LOG[ip] = [t for t in REQUEST_LOG[ip] if now - t < 10]
    REQUEST_LOG[ip].append(now)
    if len(REQUEST_LOG[ip]) > 50:
        BLOCKED_IPS.add(ip)
        return False
    return True

@app.before_request
def protect():
    ip = request.remote_addr
    if ip in BLOCKED_IPS:
        return "Доступ запрещён", 403
    if not check_ddos(ip):
        return "Слишком много запросов", 429

def load_settings():
    default = {
        "work_start": 9,
        "work_end": 18,
        "maintenance_until": None,
        "maintenance_message": "Идут технические работы на сайте"
    }
    if not os.path.exists(SETTINGS_FILE):
        return default
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in default.items():
            if k not in data:
                data[k] = v
        return data
    except:
        return default

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def load_reviews():
    if not os.path.exists(REVIEWS_FILE):
        return []
    with open(REVIEWS_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    result = []
    for line in lines:
        parts = line.split("|")
        if len(parts) >= 4:
            result.append({
                "id": parts[0],
                "name": parts[1],
                "text": parts[2],
                "stars": parts[3],
                "photo": parts[4] if len(parts) > 4 else "",
                "answer": parts[5] if len(parts) > 5 else ""
            })
    return result

def save_review(review):
    with open(REVIEWS_FILE, "a", encoding="utf-8") as f:
        line = f"{review['id']}|{review['name']}|{review['text']}|{review['stars']}|{review.get('photo','')}|{review.get('answer','')}\n"
        f.write(line)

def rewrite_reviews(reviews):
    with open(REVIEWS_FILE, "w", encoding="utf-8") as f:
        for r in reviews:
            line = f"{r['id']}|{r['name']}|{r['text']}|{r['stars']}|{r.get('photo','')}|{r.get('answer','')}\n"
            f.write(line)

def load_pending():
    if not os.path.exists(PENDING_FILE):
        return []
    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    now = time.time()
    result = []
    for line in lines:
        parts = line.split("|")
        if len(parts) >= 6:
            rid, name, text, stars, photo, ts = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
            if now - float(ts) >= 60:
                save_review({"id": rid, "name": name, "text": text, "stars": stars, "photo": photo, "answer": ""})
            else:
                result.append({"id": rid, "name": name, "text": text, "stars": stars, "photo": photo, "ts": float(ts)})
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        for r in result:
            f.write(f"{r['id']}|{r['name']}|{r['text']}|{r['stars']}|{r['photo']}|{r['ts']}\n")
    return result

def save_pending(review):
    with open(PENDING_FILE, "a", encoding="utf-8") as f:
        f.write(f"{review['id']}|{review['name']}|{review['text']}|{review['stars']}|{review['photo']}|{time.time()}\n")

def check_review(text):
    text_lower = text.lower()
    for word in BAD_WORDS:
        if word in text_lower:
            return False, "Отзыв содержит недопустимые слова"
    if len(text) < 5:
        return False, "Отзыв слишком короткий"
    if len(text) > 1000:
        return False, "Отзыв слишком длинный"
    return True, "OK"

def is_admin():
    ip = request.remote_addr
    return ip == ADMIN_IP or session.get("admin") == True

@app.route("/")
def home():
    settings = load_settings()
    
    if settings.get("maintenance_until"):
        try:
            until = datetime.datetime.strptime(settings["maintenance_until"], "%Y-%m-%d %H:%M")
            now = datetime.datetime.now()
            if now < until:
                diff = until - now
                minutes = int(diff.total_seconds() // 60)
                return render_template_string("""
                <html><head><meta charset="UTF-8"><title>Тех.работы</title>
                <style>
                body { background: #1a1a1a; color: white; font-family: Arial;
                       display: flex; justify-content: center; align-items: center;
                       height: 100vh; text-align: center; flex-direction: column; }
                h1 { color: #ff4500; font-size: 60px; margin-bottom: 30px; }
                p { font-size: 26px; margin: 10px 0; }
                .time { color: #ff8c00; font-size: 80px; font-weight: bold; margin: 30px 0; }
                </style></head>
                <body>
                <h1>🔧 Идут технические работы</h1>
                <p>{{ message }}</p>
                <p>Сайт откроется через:</p>
                <div class="time">{{ minutes }} мин</div>
                <p>До: {{ until }}</p>
                </body></html>
                """, message=settings["maintenance_message"], minutes=minutes, until=settings["maintenance_until"])
            else:
                settings["maintenance_until"] = None
                save_settings(settings)
        except:
            settings["maintenance_until"] = None
            save_settings(settings)
    
    load_pending()
    reviews = load_reviews()
    
    reviews_html = ""
    for r in reviews:
        stars_display = "⭐" * int(r["stars"]) + "☆" * (5 - int(r["stars"]))
        photo_html = f'<img src="/uploads/{r["photo"]}" class="review-photo">' if r.get("photo") else ""
        answer_html = f'<div class="admin-answer"><b>💬 Ответ администратора:</b><br>{r["answer"]}</div>' if r.get("answer") else ""
        admin_actions = ""
        if is_admin():
            admin_actions = f'''
            <a href="/admin/delete/{r["id"]}" class="delete-btn" onclick="return confirm('Удалить отзыв?')">🗑 Удалить</a>
            <form method="POST" action="/admin/answer/{r["id"]}" style="margin-top:10px;">
                <input type="text" name="answer" placeholder="Ответ на отзыв..." style="padding:10px;background:#1a1a1a;border:2px solid #ff8c00;border-radius:8px;color:white;width:100%;margin-bottom:8px;">
                <button type="submit" style="background:#ff8c00;color:white;padding:8px 20px;border:none;border-radius:8px;cursor:pointer;">Ответить</button>
            </form>
            '''
        
        reviews_html += f'''
        <div class="review">
            <h4>👤 {r["name"]}</h4>
            <p class="stars">{stars_display}</p>
            {photo_html}
            <p>{r["text"]}</p>
            {answer_html}
            {admin_actions}
        </div>
        '''
    
    admin_panel = ""
    if is_admin():
        admin_panel = render_template_string("""
        <div class="admin-panel">
            <h2>🔐 Админ-панель</h2>
            <p>Ты вошёл как администратор</p>
            <div class="admin-controls">
                <div class="admin-block">
                    <h3>⏰ Время работы</h3>
                    <form method="POST" action="/admin/set_time">
                        <label>Начало (час):</label>
                        <input type="number" name="start" min="0" max="23" value="{{ start }}" required>
                        <label>Конец (час):</label>
                        <input type="number" name="end" min="0" max="23" value="{{ end }}" required>
                        <button type="submit">Сохранить</button>
                    </form>
                </div>
                <div class="admin-block">
                    <h3>🔧 Тех.работы</h3>
                    <form method="POST" action="/admin/maintenance">
                        <label>До какого времени (НСК):</label>
                        <input type="datetime-local" name="until" required>
                        <button type="submit" class="danger">Включить</button>
                    </form>
                    <form method="POST" action="/admin/stop_maintenance" style="margin-top:10px;">
                        <button type="submit" class="ok">Остановить</button>
                    </form>
                </div>
            </div>
            <p style="margin-top:20px;"><a href="/admin/logout" style="color:#ff8c00;">Выйти из админки</a></p>
        </div>
        """, start=settings["work_start"], end=settings["work_end"])
    
    return render_template_string("""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>ArtLine - Автосервис Новосибирск</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; }

#splash {
    position: fixed; top: 0; left: 0;
    width: 100%; height: 100%;
    background: #000;
    display: flex; justify-content: center; align-items: center;
    z-index: 9999;
    animation: blink 1.5s infinite;
    overflow: hidden;
}
#splash img { width: 100%; height: 100%; object-fit: contain; }
@keyframes blink {
    0% { opacity: 1; }
    50% { opacity: 0.7; }
    100% { opacity: 1; }
}
#main { display: none; }

header {
    background: linear-gradient(135deg, #ff4500, #ff8c00);
    padding: 80px 20px; text-align: center;
    min-height: 100vh;
    display: flex; flex-direction: column;
    justify-content: center; align-items: center;
}
header h1 { font-size: 80px; margin-bottom: 20px; letter-spacing: 3px; }
header p { font-size: 26px; opacity: 0.95; }

.float-btn {
    position: fixed; right: 30px; top: 50%;
    transform: translateY(-50%);
    width: 70px; height: 70px;
    background: #ff4500; color: white;
    border-radius: 50%;
    display: flex; justify-content: center; align-items: center;
    font-size: 35px; cursor: pointer;
    box-shadow: 0 5px 25px rgba(255, 69, 0, 0.6);
    z-index: 1000; text-decoration: none;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { transform: translateY(-50%) scale(1); }
    50% { transform: translateY(-50%) scale(1.1); }
}
.float-btn:hover { background: #ff8c00; }

.services { padding: 80px 20px; max-width: 1200px; margin: 0 auto; }
.services h2 { text-align: center; font-size: 50px; margin-bottom: 60px; color: #ff8c00; }

.service-block {
    display: flex; align-items: center; gap: 40px;
    margin-bottom: 80px;
    opacity: 0; transform: translateY(50px);
    transition: all 1s ease;
}
.service-block.show { opacity: 1; transform: translateY(0); }
.service-block:nth-child(even) { flex-direction: row-reverse; }
.service-block img {
    width: 400px; height: 300px; object-fit: cover;
    border-radius: 20px; border: 4px solid #ff4500;
}
.service-block .text { flex: 1; }
.service-block h3 { font-size: 36px; color: #ff8c00; margin-bottom: 15px; }
.service-block p { font-size: 20px; color: #ccc; line-height: 1.6; margin-bottom: 15px; }

.price-note {
    display: inline-block;
    background: rgba(255, 69, 0, 0.15);
    color: #ff8c00;
    padding: 10px 20px;
    border-radius: 10px;
    border-left: 4px solid #ff4500;
    font-size: 18px;
    font-weight: bold;
}

.admin-panel {
    background: #1a0000;
    border: 3px solid #ff4500;
    padding: 30px;
    border-radius: 20px;
    margin: 40px auto;
    max-width: 900px;
}
.admin-panel h2 { color: #ff4500; font-size: 32px; margin-bottom: 15px; }
.admin-panel > p { color: #ffcc80; margin-bottom: 25px; }
.admin-controls { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.admin-block {
    background: #2a2a2a;
    padding: 20px;
    border-radius: 15px;
    border-left: 5px solid #ff4500;
}
.admin-block h3 { color: #ff8c00; margin-bottom: 15px; font-size: 20px; }
.admin-block label { display: block; color: #ccc; margin: 8px 0 5px; }
.admin-block input {
    width: 100%; padding: 10px; margin-bottom: 10px;
    background: #1a1a1a; border: 2px solid #ff4500;
    border-radius: 8px; color: white; font-size: 16px;
}
.admin-block button {
    background: #ff4500; color: white;
    padding: 10px 20px; border: none;
    border-radius: 8px; font-size: 16px; cursor: pointer;
    width: 100%;
}
.admin-block button:hover { background: #ff8c00; }
.admin-block button.danger { background: #d32f2f; }
.admin-block button.danger:hover { background: #b71c1c; }
.admin-block button.ok { background: #2e7d32; }
.admin-block button.ok:hover { background: #1b5e20; }

.reviews { padding: 80px 20px; max-width: 900px; margin: 0 auto; }
.reviews h2 { text-align: center; font-size: 50px; margin-bottom: 40px; color: #ff8c00; }
.review {
    background: #2a2a2a; padding: 25px;
    border-radius: 15px; border-left: 5px solid #ff8c00;
    margin-bottom: 20px;
}
.review h4 { color: #ff8c00; margin-bottom: 10px; font-size: 20px; }
.review .stars { color: #ffcc00; font-size: 22px; margin-bottom: 10px; letter-spacing: 3px; }
.review p { color: #ccc; font-size: 18px; line-height: 1.5; }
.review-photo { max-width: 100%; border-radius: 10px; margin: 10px 0; display: block; }
.admin-answer {
    background: rgba(255, 140, 0, 0.15);
    border-left: 4px solid #ff8c00;
    padding: 12px 18px;
    border-radius: 8px;
    margin-top: 15px;
    color: #ffcc80;
    font-size: 17px;
}
.delete-btn {
    display: inline-block;
    background: #d32f2f; color: white;
    padding: 8px 18px; border-radius: 8px;
    text-decoration: none; font-size: 15px;
    margin-top: 12px;
}
.delete-btn:hover { background: #b71c1c; }

.review-form {
    background: #2a2a2a; padding: 30px;
    border-radius: 15px; margin-top: 30px;
}
.review-form h3 { color: #ff8c00; margin-bottom: 20px; font-size: 26px; }
.review-form input, .review-form textarea, .review-form select {
    width: 100%; padding: 15px; margin-bottom: 15px;
    background: #1a1a1a; border: 2px solid #ff4500;
    border-radius: 10px; color: white;
    font-size: 18px; font-family: Arial;
}
.review-form textarea { min-height: 120px; resize: vertical; }
.review-form button {
    background: #ff4500; color: white;
    padding: 15px 40px; border: none;
    border-radius: 10px; font-size: 20px; cursor: pointer;
}
.review-form button:hover { background: #ff8c00; }

#pending-message {
    display: none;
    position: fixed; top: 0; left: 0;
    width: 100%; height: 100%;
    background: rgba(0,0,0,0.95);
    z-index: 99999;
    justify-content: center; align-items: center;
    flex-direction: column;
    text-align: center;
    padding: 30px;
}
#pending-message.active { display: flex; }
#pending-message h2 { color: #ff8c00; font-size: 40px; margin-bottom: 20px; }
#pending-message p { color: white; font-size: 22px; margin-bottom: 20px; }
#timer { font-size: 80px; color: #ff8c00; font-weight: bold; margin: 20px 0; }
#pending-message .ok-btn {
    background: #ff4500; color: white;
    padding: 15px 50px; border: none;
    border-radius: 10px; font-size: 22px;
    cursor: pointer; margin-top: 20px;
}

.contact { background: #0f0f0f; padding: 80px 20px; text-align: center; }
.contact h2 { font-size: 50px; color: #ff8c00; margin-bottom: 40px; }
.contact p { font-size: 24px; margin: 15px 0; }
.contact a { color: #ff8c00; text-decoration: none; }
.contact a:hover { text-decoration: underline; }

footer { background: #000; padding: 30px; text-align: center; color: #666; }
</style>
</head>
<body>

<div id="splash">
    <img src="https://i.oneme.ru/i?r=BUE2sh_eZW7g8kugOdIm2NotAs_zH4XqNLo8l9T4E_hYvYGUEHSPLPI4UBRX30jt4Ki-lVzsyQysV3DaVqjHCp2E&expires=1789382268534" alt="ArtLine">
</div>

<div id="main">
<a href="#contact" class="float-btn">↓</a>

<header>
    <h1>ARTLINE</h1>
    <p>Станция обслуживания и тюнинга автомобилей</p>
</header>

<section class="services">
    <h2>Наши услуги</h2>

    <div class="service-block">
        <img src="https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=600" alt="Ремонт ДВС">
        <div class="text">
            <h3>Капитальный ремонт ДВС, ГБЦ</h3>
            <p>Полная разборка, дефектовка и восстановление двигателя и головки блока цилиндров.</p>
            <div class="price-note">💰 Цены уточнять по телефону</div>
        </div>
    </div>

    <div class="service-block">
        <img src="https://images.unsplash.com/photo-1625047509248-ec889cbff17f?w=600" alt="Замена ДВС и КПП">
        <div class="text">
            <h3>Замена ДВС и КПП</h3>
            <p>Замена двигателя и коробки передач любой сложности. Подбор и установка.</p>
            <div class="price-note">💰 Цены уточнять по телефону</div>
        </div>
    </div>

    <div class="service-block">
        <img src="https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=600" alt="Ремонт коленвалов">
        <div class="text">
            <h3>Ремонт коленвалов, распредвалов</h3>
            <p>Шлифовка и восстановление коленчатых и распределительных валов.</p>
            <div class="price-note">💰 Цены уточнять по телефону</div>
        </div>
    </div>

    <div class="service-block">
        <img src="https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600" alt="Сварочные работы">
        <div class="text">
            <h3>Сварочные работы</h3>
            <p>Аргонная и полуавтоматическая сварка. Ремонт кузова, глушителей, деталей.</p>
            <div class="price-note">💰 Цены уточнять по телефону</div>
        </div>
    </div>

    <div class="service-block">
        <img src="https://images.unsplash.com/photo-1632823469850-1b7b1e8b7e1e?w=600" alt="Ходовая">
        <div class="text">
            <h3>Диагностика и ремонт ходовой</h3>
            <p>Полная диагностика подвески, замена амортизаторов, рычагов, сайлентблоков.</p>
            <div class="price-note">💰 Цены уточнять по телефону</div>
        </div>
    </div>

    <div class="service-block">
        <img src="https://images.unsplash.com/photo-1580273916550-e323be2ae537?w=600" alt="Замена жидкостей">
        <div class="text">
            <h3>Замена тех. жидкостей</h3>
            <p>Замена масла, антифриза, тормозной жидкости, жидкости ГУР и других.</p>
            <div class="price-note">💰 Цены уточнять по телефону</div>
        </div>
    </div>

    <div class="service-block">
        <img src="https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=600" alt="Тюнинг">
        <div class="text">
            <h3>Установка доп. оборудования</h3>
            <p>Установка аксессуаров, дополнительного оборудования, тюнинг автомобилей.</p>
            <div class="price-note">💰 Цены уточнять по телефону</div>
        </div>
    </div>
</section>

{{ admin_panel|safe }}

<section class="reviews">
    <h2>Отзывы клиентов</h2>
    {{ reviews_html|safe if reviews_html else '<p style="text-align:center;color:#888;">Пока нет отзывов. Будь первым!</p>' }}
    
    <div class="review-form">
        <h3>Оставить отзыв</h3>
        <form method="POST" action="/add" enctype="multipart/form-data" id="review-form">
            <input type="text" name="name" placeholder="Твоё имя" required>
            <select name="stars" required>
                <option value="5">⭐⭐⭐⭐⭐ Отлично</option>
                <option value="4">⭐⭐⭐⭐ Хорошо</option>
                <option value="3">⭐⭐⭐ Нормально</option>
                <option value="2">⭐⭐ Плохо</option>
                <option value="1">⭐ Ужасно</option>
            </select>
            <textarea name="text" placeholder="Твой отзыв..." required></textarea>
            <label style="color:#ccc;display:block;margin-bottom:8px;">📷 Фото (необязательно)</label>
            <input type="file" name="photo" accept="image/*">
            <button type="submit">Отправить</button>
        </form>
    </div>
</section>

<section class="contact" id="contact">
    <h2>Контакты</h2>
    <p>📞 Телефон: <a href="tel:+79039396662">8-903-939-666-2</a></p>
    <p>✉️ Email: <a href="mailto:Eclipse1993@mail.ru">Eclipse1993@mail.ru</a></p>
    <p>🌐 ВКонтакте: <a href="https://vk.ru/artlinenovosibirsk" target="_blank">vk.ru/artlinenovosibirsk</a></p>
    <p>📍 Адрес: г. Новосибирск, ул. Якушева 53</p>
    <p>🕐 Работаем: Пн-Сб с {{ start }}:00 до {{ end }}:00 <span id="status"></span></p>
</section>

<footer>
    <p>© 2026 ArtLine. Все права защищены.</p>
</footer>
</div>

<div id="pending-message">
    <h2>✅ Спасибо за отзыв!</h2>
    <p>Сейчас мы его проверим.<br>Если всё в порядке — он появится на сайте.</p>
    <div id="timer">60</div>
    <p>секунд до окончания проверки</p>
    <button class="ok-btn" onclick="closePending()">ОК</button>
</div>

<script>
setTimeout(function() {
    document.getElementById("splash").style.display = "none";
    document.getElementById("main").style.display = "block";
    checkStatus();
}, 3000);

window.addEventListener("scroll", function() {
    var blocks = document.querySelectorAll(".service-block");
    blocks.forEach(function(block) {
        var position = block.getBoundingClientRect().top;
        if (position < window.innerHeight - 100) {
            block.classList.add("show");
        }
    });
});

function checkStatus() {
    var now = new Date();
    var day = now.getDay();
    var hour = now.getHours();
    var status = document.getElementById("status");
    var startHour = {{ start }};
    var endHour = {{ end }};
    
    if (day >= 1 && day <= 6 && hour >= startHour && hour < endHour) {
        status.innerHTML = "(Открыто)";
        status.style.color = "lime";
        status.style.fontWeight = "bold";
    } else {
        status.innerHTML = "(Закрыто)";
        status.style.color = "red";
        status.style.fontWeight = "bold";
    }
}

document.getElementById("review-form").addEventListener("submit", function(e) {
    document.getElementById("pending-message").classList.add("active");
    var seconds = 60;
    var timerEl = document.getElementById("timer");
    timerEl.innerText = seconds;
    var interval = setInterval(function() {
        seconds--;
        timerEl.innerText = seconds;
        if (seconds <= 0) clearInterval(interval);
    }, 1000);
});

function closePending() {
    document.getElementById("pending-message").classList.remove("active");
    location.reload();
}
</script>

</body>
</html>""", reviews_html=reviews_html, admin_panel=admin_panel,
   start=settings["work_start"], end=settings["work_end"])

@app.route("/add", methods=["POST"])
@limiter.limit("5 per minute")
def add():
    name = request.form.get("name", "Аноним")
    text = request.form.get("text", "")
    stars = request.form.get("stars", "5")
    
    ok, reason = check_review(text)
    if not ok:
        return f"""
        <html><head><meta charset="UTF-8"></head>
        <body style="background:#1a1a1a;color:white;font-family:Arial;text-align:center;padding:50px;">
        <h1 style="color:#ff4500;">❌ Отзыв отклонён</h1>
        <p style="font-size:22px;margin:20px 0;">{reason}</p>
        <a href="/" style="color:#ff8c00;font-size:20px;">← Вернуться на сайт</a>
        </body></html>
        """, 400
    
    photo_name = ""
    if "photo" in request.files:
        file = request.files["photo"]
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext in ["jpg", "jpeg", "png", "gif", "webp"]:
                photo_name = f"{int(time.time())}_{secure_filename(file.filename)}"
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], photo_name))
    
    review_id = str(int(time.time() * 1000))
    save_pending({"id": review_id, "name": name, "text": text, "stars": stars, "photo": photo_name})
    
    return redirect("/")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/")
        else:
            return "Неверный пароль. <a href='/admin/login'>Назад</a>", 403
    
    return """
    <html><head><meta charset="UTF-8"><title>Вход</title>
    <style>
    body { background: #1a1a1a; color: white; font-family: Arial;
           display: flex; justify-content: center; align-items: center;
           height: 100vh; }
    .form { background: #2a2a2a; padding: 40px; border-radius: 20px;
            border: 3px solid #ff4500; text-align: center; }
    h1 { color: #ff4500; margin-bottom: 20px; }
    input { padding: 15px; width: 300px; background: #1a1a1a;
            border: 2px solid #ff4500; border-radius: 10px;
            color: white; font-size: 18px; margin-bottom: 15px; }
    button { background: #ff4500; color: white; padding: 15px 40px;
             border: none; border-radius: 10px; font-size: 18px;
             cursor: pointer; }
    button:hover { background: #ff8c00; }
    </style></head>
    <body>
    <div class="form">
    <h1>🔐 Вход для админа</h1>
    <form method="POST">
    <input type="password" name="password" placeholder="Пароль" required><br>
    <button type="submit">Войти</button>
    </form>
    </div>
    </body></html>
    """

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/")

@app.route("/admin/delete/<rid>")
def admin_delete(rid):
    if not is_admin():
        return "Доступ запрещён", 403
    reviews = load_reviews()
    reviews = [r for r in reviews if r["id"] != rid]
    rewrite_reviews(reviews)
    return redirect("/")

@app.route("/admin/answer/<rid>", methods=["POST"])
def admin_answer(rid):
    if not is_admin():
        return "Доступ запрещён", 403
    answer = request.form.get("answer", "")
    reviews = load_reviews()
    for r in reviews:
        if r["id"] == rid:
            r["answer"] = answer
    rewrite_reviews(reviews)
    return redirect("/")

@app.route("/admin/set_time", methods=["POST"])
def admin_set_time():
    if not is_admin():
        return "Доступ запрещён", 403
    settings = load_settings()
    settings["work_start"] = int(request.form.get("start", 9))
    settings["work_end"] = int(request.form.get("end", 18))
    save_settings(settings)
    return redirect("/")

@app.route("/admin/maintenance", methods=["POST"])
def admin_maintenance():
    if not is_admin():
        return "Доступ запрещён", 403
    settings = load_settings()
    until = request.form.get("until", "")
    if until:
        until = until.replace("T", " ")
        settings["maintenance_until"] = until
        save_settings(settings)
    return redirect("/")

@app.route("/admin/stop_maintenance", methods=["POST"])
def admin_stop_maintenance():
    if not is_admin():
        return "Доступ запрещён", 403
    settings = load_settings()
    settings["maintenance_until"] = None
    save_settings(settings)
    return redirect("/")

if __name__ == "__main__":
    threading.Timer(1, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False, port=5000)
