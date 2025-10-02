#!/usr/bin/env python3
import os
import requests
import hashlib
import json
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo

# === CONFIGURA QUI LE PAGINE DA MONITORARE ===
URLS = [
    "https://www.dipsum.unisa.it/home/news",
    "https://corsi.unisa.it/linguistica-e-didattica-dell-italiano/comunicazioni-docenti",
    "https://corsi.unisa.it/filologia-letterature-e-storia-dell-antichita/comunicazioni-docenti",
    "https://corsi.unisa.it/filologia-moderna/comunicazioni-docenti",
    "https://search.app/FDANfFo57SDp2Pz99"
]
# ==============================================

HASH_FILE = "hashes.json"
TIMEOUT = 20  # secondi per le richieste
USER_AGENT = "Mozilla/5.0 (compatible; UNISA-monitor/1.0; +https://github.com/)"

def now_rome_hour():
    """Ritorna l'ora corrente in Europa/Rome (0-23)."""
    return datetime.now(ZoneInfo("Europe/Rome")).hour

def should_run_now():
    """Esegue solo se l'ora locale è tra 05:00 e 02:00 (inclusi)."""
    h = now_rome_hour()
    # se h >=5 (5..23) oppure h <=2 (0..2)
    return (h >= 5) or (h <= 2)

def fetch_text(url):
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, timeout=TIMEOUT, headers=headers)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    # Primo tentativo: elemento con id 'comunicazioni-docenti' o elementi tipici
    for selector in ["#comunicazioni-docenti", "article", "main", "section", ".news", ".content"]:
        node = soup.select_one(selector)
        if node and len(node.get_text(strip=True)) > 50:
            return node.get_text(separator="\n", strip=True)
    # fallback: tutto il testo della pagina
    return soup.get_text(separator="\n", strip=True)

def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def send_telegram(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ERRORE: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID mancanti.")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        print("Errore invio Telegram:", e)
        return False

def load_hashes():
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_hashes(hashes):
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, ensure_ascii=False)

def main():
    print("Ora locale (Europe/Rome):", now_rome_hour())
    if not should_run_now():
        print("Fuori dall'intervallo 05:00-02:00. Terminazione veloce.")
        return

    prev = load_hashes()
    new = {}
    changes = []

    for url in URLS:
        print("Controllo:", url)
        try:
            content = fetch_text(url)
        except Exception as e:
            print(f"Errore fetch {url}: {e}")
            continue
        h = sha256(content)
        new[url] = h
        if url in prev:
            if prev[url] != h:
                print("-> Cambiamento rilevato:", url)
                snippet = content.strip().replace("\n", " ")[:700]
                changes.append((url, snippet))
        else:
            # prima esecuzione: popoliamo lo stato ma non inviamo notifiche
            print("-> Prima esecuzione per questa pagina:", url)

    if changes:
        message = "⬆️ <b>Aggiornamenti rilevati</b>:\n\n"
        for (u, s) in changes:
            message += f"{u}\n{s[:400]}...\n\n"
        ok = send_telegram(message)
        print("Invio Telegram:", ok)
    else:
        print("Nessun cambiamento rilevato.")

    save_hashes(new)
    print("Fine esecuzione.")

if __name__ == "__main__":
    main()
