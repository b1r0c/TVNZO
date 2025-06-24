import requests
import os
import re
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ... (tutto il resto del tuo codice iniziale rimane invariato fino a qui) ...
# load_dotenv(), DADDY_CACHE_FILE, load_daddy_cache(), save_daddy_cache(),
# headers_to_extvlcopt(), search_m3u8_in_sites() non necessitano modifiche.

load_dotenv()

DADDY_CACHE_FILE = "daddy_cache.json"
daddy_cache = {}

def load_daddy_cache():
    canali_daddy_flag = os.getenv("CANALI_DADDY", "no").strip().lower()
    if canali_daddy_flag != "si":
        print("[INFO] Skipping loading daddy_cache as CANALI_DADDY is not 'si'.")
        return
    """Carica la cache dei link di daddy da un file JSON."""
    global daddy_cache
    if os.path.exists(DADDY_CACHE_FILE):
        try:
            with open(DADDY_CACHE_FILE, 'r', encoding='utf-8') as f:
                daddy_cache = json.load(f)
            print(f"[i] Cache dei link daddy caricata da {DADDY_CACHE_FILE}")
        except (json.JSONDecodeError, IOError) as e:
            print(f"[!] Errore nel caricare la cache dei link daddy: {e}")
            daddy_cache = {}

def save_daddy_cache():
    canali_daddy_flag = os.getenv("CANALI_DADDY", "no").strip().lower()
    if canali_daddy_flag != "si":
        print("[INFO] Skipping saving daddy_cache as CANALI_DADDY is not 'si'.")
        return
    """Salva la cache dei link di daddy su un file JSON."""
    global daddy_cache
    try:
        with open(DADDY_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(daddy_cache, f, indent=4)
        print(f"[i] Cache dei link daddy salvata in {DADDY_CACHE_FILE}")
    except IOError as e:
        print(f"[!] Errore nel salvare la cache dei link daddy: {e}")

# ... (le altre tue funzioni come headers_to_extvlcopt, search_m3u8_in_sites, etc. rimangono qui) ...

# ========= NUOVA FUNZIONE PER I CANALI MPD =========
def format_mpd_channels():
    """
    Legge il file mpd.m3u, estrae i canali, li formatta e restituisce
    una stringa pronta per essere aggiunta alla playlist principale.
    """
    try:
        with open('mpd.m3u', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("[INFO] Il file mpd.m3u non è stato trovato. Salto l'aggiunta di questi canali.")
        return "" # Ritorna una stringa vuota se il file non esiste

    # Espressione regolare per catturare i blocchi di canali MPD
    pattern = re.compile(
        r'#EXTINF:-1,(.*?)\n'
        r'#KODIPROP:inputstream\.adaptive\.license_type=(.*?)\n'
        r'#KODIPROP:inputstream\.adaptive\.license_key=(.*?)\n'
        r'(https://.*\.mpd)'
    )

    matches = pattern.finditer(content)
    formatted_channels = []

    # Template per la formattazione di ogni canale
    channel_template = (
        '#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" tvg-logo="URL_LOGO_QUI" group-title="CANALI MPD",{name}\n'
        '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36\n'
        '#EXTVLCOPT:inputstream.adaptive.license_type={license_type}\n'
        '#EXTVLCOPT:inputstream.adaptive.license_key={license_key}\n'
        '{stream_url}'
    )

    for match in matches:
        channel_name = match.group(1).strip()
        license_type = match.group(2).strip()
        license_key = match.group(3).strip()
        stream_url = match.group(4).strip()
        
        formatted_channel = channel_template.format(
            name=channel_name,
            license_type=license_type,
            license_key=license_key,
            stream_url=stream_url
        )
        formatted_channels.append(formatted_channel)

    if not formatted_channels:
        return ""

    print(f"[i] Formattati {len(formatted_channels)} canali dal file mpd.m3u.")
    # Unisce tutti i canali formattati in una singola stringa, separati da una riga vuota
    return "\n\n" + "\n\n".join(formatted_channels)
# ======================================================


def merger_playlist():
    # ... (il codice esistente di questa funzione rimane uguale fino all'unione) ...
    print("Eseguendo il merger_playlist...")
    
    load_dotenv()
    NOMEREPO = os.getenv("NOMEREPO", "").strip()
    NOMEGITHUB = os.getenv("NOMEGITHUB", "").strip()
    
    url1 = "channels_italy.m3u8"
    url2 = "eventi.m3u8"
    url6 = "https://raw.githubusercontent.com/Brenders/Pluto-TV-Italia-M3U/main/PlutoItaly.m3u"
    
    def download_playlist(source, append_params=False, exclude_group_title=None):
        if source.startswith("http"):
            response = requests.get(source)
            response.raise_for_status()
            playlist = response.text
        else:
            with open(source, 'r', encoding='utf-8') as f:
                playlist = f.read()
        
        playlist = '\n'.join(line for line in playlist.split('\n') if not line.startswith('#EXTM3U'))
        if exclude_group_title:
            playlist = '\n'.join(line for line in playlist.split('\n') if exclude_group_title not in line)
        return playlist
    
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    playlist1 = download_playlist(url1)
    
    canali_daddy_flag = os.getenv("CANALI_DADDY", "no").strip().lower()
    if canali_daddy_flag == "si":
        playlist2 = download_playlist(url2, append_params=True)
    else:
        print("[INFO] Skipping eventi.m3u8 in merger_playlist as CANALI_DADDY is not 'si'.")
        playlist2 = ""

    playlist6 = download_playlist(url6)
    
    # Unisci le playlist esistenti
    lista = playlist1 + "\n" + playlist2 + "\n" + playlist6
    
    # ========= MODIFICA: AGGIUNTA CANALI MPD =========
    mpd_content = format_mpd_channels()
    lista += mpd_content
    # ===============================================
    
    # Aggiungi intestazione EPG
    lista = f'#EXTM3U url-tvg="https://raw.githubusercontent.com/{NOMEGITHUB}/{NOMEREPO}/refs/heads/main/epg.xml"\n' + lista
    
    # Salva la playlist
    output_filename = os.path.join(script_directory, "lista.m3u")
    with open(output_filename, 'w', encoding='utf-8') as file:
        file.write(lista)
    
    print(f"Playlist combinata salvata in: {output_filename}")


def merger_playlistworld():
    # ... (il codice esistente di questa funzione rimane uguale fino all'unione) ...
    print("Eseguendo il merger_playlistworld...")
    
    load_dotenv()
    NOMEREPO = os.getenv("NOMEREPO", "").strip()
    NOMEGITHUB = os.getenv("NOMEGITHUB", "").strip()
    
    url1 = "channels_italy.m3u8"
    url2 = "eventi.m3u8"
    url5 = "https://raw.githubusercontent.com/Brenders/Pluto-TV-Italia-M3U/main/PlutoItaly.m3u"
    url6 = "world.m3u8"
    
    def download_playlist(source, append_params=False, exclude_group_title=None):
        if source.startswith("http"):
            response = requests.get(source)
            response.raise_for_status()
            playlist = response.text
        else:
            with open(source, 'r', encoding='utf-8') as f:
                playlist = f.read()
        
        playlist = '\n'.join(line for line in playlist.split('\n') if not line.startswith('#EXTM3U'))
        if exclude_group_title:
            playlist = '\n'.join(line for line in playlist.split('\n') if exclude_group_title not in line)
        return playlist
    
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    playlist1 = download_playlist(url1)
    
    canali_daddy_flag = os.getenv("CANALI_DADDY", "no").strip().lower()
    if canali_daddy_flag == "si":
        playlist2 = download_playlist(url2, append_params=True)
    else:
        print("[INFO] Skipping eventi.m3u8 in merger_playlistworld as CANALI_DADDY is not 'si'.")
        playlist2 = ""

    playlist5 = download_playlist(url5)
    playlist6 = download_playlist(url6, exclude_group_title="Italy")
    
    # Unisci le playlist esistenti
    lista = playlist1 + "\n" + playlist2 + "\n" + playlist5 + "\n" + playlist6
    
    # ========= MODIFICA: AGGIUNTA CANALI MPD =========
    mpd_content = format_mpd_channels()
    lista += mpd_content
    # ===============================================
    
    # Aggiungi intestazione EPG
    lista = f'#EXTM3U url-tvg="https://raw.githubusercontent.com/{NOMEGITHUB}/{NOMEREPO}/refs/heads/main/epg.xml"\n' + lista
    
    # Salva la playlist
    output_filename = os.path.join(script_directory, "lista.m3u")
    with open(output_filename, 'w', encoding='utf-8') as file:
        file.write(lista)
    
    print(f"Playlist combinata salvata in: {output_filename}")


# ... (Tutto il resto del tuo script da 'epg_merger' in poi rimane invariato) ...
# Aggiungi qui le funzioni epg_merger, eventi_m3u8_generator_world e il blocco if __name__ == "__main__":
# esattamente come erano nel tuo file originale.
