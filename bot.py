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
MIN_MAG = 3.0  # minimum büyüklük

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
        url = 'https://api.orhanaydogdu.com.tr/deprem/kandilli/live?limit=100&_=' + str(int(time.time()))
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
                key = '{:.3f}_{:.3f}_{}_{}'.format(lat, lon, mag, dep)
                if key in seen:
                    continue
                seen.add(key)

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
                print('Kayıt parse hatası: {}'.format(e))
                continue

        return quakes
    except Exception as e:
        print('Fetch hatası: {}'.format(e))
        return []

# ================================================================
# MESAJ FORMATI
# ================================================================
def mag_emoji(mag):
    if mag >= 5.0:
        return '🔴'
    if mag >= 4.0:
        return '🟠'
    if mag >= 3.0:
        return '🟡'
    return '🟢'

def format_message(q):
    emoji = mag_emoji(q['mag'])
    mag = q['mag']

    if mag >= 5.0:
        title = '⚠️ BÜYÜK DEPREM ⚠️'
    elif mag >= 4.0:
        title = '❗ ÖNEMLİ DEPREM'
    else:
        title = 'DEPREM'

    try:
        hashtag = q['loc'].split('(')[-1].replace(')', '').strip().lower().replace(' ', '')
    except Exception:
        hashtag = 'turkiye'

    msg = (
        '{} {}\n\n'
        '📍 {}\n'
        '📏 Büyüklük: *{:.1f}*\n'
        '⬇️ Derinlik: {} km\n'
        '🕐 {}\n\n'
        '🗺️ [Haritada Gör](https://depremradar.net/?lat={}&lon={})\n\n'
        '#deprem #kandilli #{}'
    ).format(
        emoji, title,
        q['loc'],
        mag,
        q['dep'],
        q['time'],
        q['lat'], q['lon'],
        hashtag
    )
    return msg

# ================================================================
# TELEGRAM'A GÖNDER
# ================================================================
def send_message(text):
    try:
        url = 'https://api.telegram.org/bot{}/sendMessage'.format(BOT_TOKEN)
        res = requests.post(url, json={
            'chat_id': CHANNEL_ID,
            'text': text,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': False
        }, timeout=10)
        result = res.json()
        if not result.get('ok'):
            print('Telegram hatası: {}'.format(result))
        return result.get('ok', False)
    except Exception as e:
        print('Gönderme hatası: {}'.format(e))
        return False

# ================================================================
# ANA DÖNGÜ
# ================================================================
def main():
    print('🚀 Deprem Radar Bot başladı — Kanal: {} — Min Mag: {}'.format(CHANNEL_ID, MIN_MAG))
    sent_ids = load_sent_ids()

    while True:
        try:
            quakes = fetch_quakes()
            new_count = 0

            for q in sorted(quakes, key=lambda x: x['time']):
                # Minimum büyüklük filtresi
                if q['mag'] < MIN_MAG:
                    sent_ids.add(q['id'])
                    continue

                if q['id'] not in sent_ids:
                    msg = format_message(q)
                    ok = send_message(msg)
                    if ok:
                        sent_ids.add(q['id'])
                        new_count += 1
                        print('✅ Gönderildi: M{} - {}'.format(q['mag'], q['loc']))
                        time.sleep(4)
                    else:
                        print('❌ Gönderilemedi: M{} - {}'.format(q['mag'], q['loc']))

            if new_count > 0:
                save_sent_ids(sent_ids)
                print('💾 {} yeni deprem gönderildi'.format(new_count))

            now = datetime.now().strftime('%H:%M:%S')
            print('[{}] Kontrol edildi. Sonraki: {}s sonra'.format(now, CHECK_INTERVAL))

        except Exception as e:
            print('Ana döngü hatası: {}'.format(e))

        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
