import requests
import time
import json
import os
from datetime import datetime

# ================================================================
# AYARLAR
# ================================================================
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'BURAYA_TOKEN_YAZ')
CHANNEL_ID = '@depremradar'
CHECK_INTERVAL = 60  # saniye
SENT_IDS_FILE = 'sent_ids.json'

# ================================================================
# GÖNDERILEN DEPREMLERİ TAKIP ET
# ================================================================
def load_sent_ids():
    if os.path.exists(SENT_IDS_FILE):
        with open(SENT_IDS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_sent_ids(ids):
    ids_list = list(ids)[-500:]
    with open(SENT_IDS_FILE, 'w') as f:
        json.dump(ids_list, f)

# ================================================================
# DEPREMLERİ ÇEK
# ================================================================
def fetch_quakes():
    try:
        url = f'https://api.orhanaydogdu.com.tr/deprem/kandilli/live?limit=100&_={int(time.time())}'
        res = requests.get(url, timeout=10)
        data = res.json()
        if not data.get('status') or not data.get('result'):
            return []

        quakes = []
        seen = set()
        for q in data['result']:
            try:
                lat = q['geojson']['coordinates'][1]
                lon = q['geojson']['coordinates'][0]
                mag = float(q.get('mag', 0))
                dep = q.get('depth', 0)
                key = f"{lat:.3f}_{lon:.3f}_{mag}_{dep}"
                if key in seen:
                    continue
                seen.add(key)

                # Zaman alanını güvenli şekilde al
                time_str = (
                    q.get('date') or
                    q.get('date_time') or
                    q.get('datetime') or
                    q.get('created_at') or
                    'Bilinmiyor'
                )

                quakes.append({
                    'id': q.get('earthquake_id') or key,
                    'lat': lat,
                    'lon': lon,
                    'mag': mag,
                    'dep': dep,
                    'loc': q.get('title', 'Bilinmiyor'),
                    'time': time_str
                })
            except Exception as e:
                print(f'Kayıt parse hatası: {e}')
                continue

        return quakes
    except Exception as e:
        print(f'Fetch hatası: {e}')
        return []

# ================================================================
# MESAJ FORMATI
# ================================================================
def mag_emoji(mag):
    if mag >= 5.0: return '🔴'
    if mag >= 4.0: return '🟠'
    if mag >= 3.0: return '🟡'
    return '🟢'

def format_message(q):
    emoji = mag_emoji(q['mag'])
    mag = q['mag']

    if mag >= 5.0:
        title = '⚠️ BÜYÜK DEPREM ⚠️'
    elif mag >= 4.0:
        title = '❗ ÖNEMLİ DEPREM'
    elif mag >= 3.0:
        title = 'DEPREM'
    else:
        title = 'Küçük Deprem'

    try:
        hashtag = q['loc'].split('(')[-1].replace(')', '').strip().lower().replace(' ', '')
    except:
        hashtag = 'turkiye'

    msg = (
        f"{emoji} {title}\n\n"
        f"📍 {q['loc']}\n"
        f"📏 Büyüklük: *{mag:.1f}*\n"
        f"⬇️ Derinlik: {q['dep']} km\n"
        f"🕐 {q['time']}\n\n"
        f"🗺️ [Haritada Gör](https://depremradar.net/?lat={q['lat']}&lon={q['lon']})\n\n"
        f"#deprem #kandilli #{hashtag}"
    )
    return msg

# ================================================================
# TELEGRAM'A GÖNDER
# ================================================================
def send_message(text):
    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        res = requests.post(url, json={
            'chat_id': CHANNEL_ID,
            'text': text,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': False
        }, timeout=10)
        result = res.json()
        if not result.get('ok'):
            print(f'Telegram hatası: {result}')
        return result.get('ok', False)
    except Exception as e:
        print(f'Gönderme hatası: {e}')
        return False

# ================================================================
# ANA DÖNGÜ
# ================================================================
def main():
    print(f'🚀 Deprem Radar Bot başladı — Kanal: {CHANNEL_ID}')
    sent_ids = load_sent_ids()

    while True:
        try:
            quakes = fetch_quakes()
            new_count = 0

            for q in sorted(quakes, key=lambda x: x['time']):
                if q['id'] not in sent_ids:
                    msg = format_message(q)
                    ok = send_message(msg)
                    if ok:
                        sent_ids.add(q['id'])
                        new_count += 1
                        print(f"✅ Gönderildi: M{q['mag']} - {q['loc']}")
                        time.sleep(2)
                    else:
                        print(f"❌ Gönderilemedi: M{q['mag']} - {q['loc']}")

            if new_count > 0:
                save_sent_ids(sent_ids)
                print(f'💾 {new_count} yeni deprem gönderildi')

            now = datetime.now().strftime('%H:%M:%S')
            print(f'[{now}] Kontrol edildi. Sonraki: {CHECK_INTERVAL}s sonra')

        except Exception as e:
            print(f'Ana döngü hatası: {e}')

        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
