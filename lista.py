import requests
import os
import re
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DADDY_CACHE_FILE = "daddy_cache.json"
daddy_cache = {}

def aggiungi_mpd_in_lista(lista_path, mpd_path, output_path):
    with open(lista_path, 'r', encoding='utf-8') as f:
        lista_lines = f.readlines()
    with open(mpd_path, 'r', encoding='utf-8') as f:
        mpd_lines = f.readlines()
    # Opzioni VLC comuni (modifica se vuoi)
    vlc_opts = [
        '#EXTVLCOPT:http-user-agent="VAVOO/2.6"\n',
        '#EXTVLCOPT:http-referer="https://vavoo.to/"\n',
        '#EXTVLCOPT:http-header="Origin: https://vavoo.to"\n'
    ]
    merged_lines = lista_lines
    merged_lines.append('\n# ---- INIZIO STREAM MPD ----\n')
    i = 0
    while i < len(mpd_lines):
        line = mpd_lines[i]
        if line.startswith('#EXTINF'):
            merged_lines.append(line)
            merged_lines += vlc_opts
            i += 1
            if i < len(mpd_lines):
                merged_lines.append(mpd_lines[i])
        i += 1
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(merged_lines)

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

def headers_to_extvlcopt(headers_dict):
    """Converts a dictionary of headers to a full #EXTVLCOPT line."""
    if not headers_dict:
        return []
    
    vlc_opt_lines = []
    for key, value in headers_dict.items():
        lower_key = key.lower()
        if lower_key == 'user-agent':
            vlc_opt_lines.append(f'#EXTVLCOPT:http-user-agent="{value}"')
        elif lower_key == 'referer':
            vlc_opt_lines.append(f'#EXTVLCOPT:http-referer="{value}"')
        elif lower_key == 'cookie':
            vlc_opt_lines.append(f'#EXTVLCOPT:http-cookie="{value}"')
        else:
            # Generic header format, ensuring value is a string
            vlc_opt_lines.append(f'#EXTVLCOPT:http-header="{key}: {str(value)}"')
            
    return vlc_opt_lines

def search_m3u8_in_sites(channel_id, is_tennis=False):
    """
    Cerca i file .m3u8 nei siti specificati per i canali daddy e tennis
    """
    # Controlla la cache prima per i canali daddy
    if not is_tennis and str(channel_id) in daddy_cache:
        cached_url = daddy_cache[str(channel_id)]
        print(f"[✓] Stream daddy trovato nella cache per channel_id {channel_id}: {cached_url}")
        return cached_url

    PROXY_URL = os.getenv("HTTP_PROXY")
    PROXIES = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
    
    if PROXY_URL:
        print(f"[i] Tentativo di utilizzo del proxy per le richieste a new.newkso.ru.")

    if is_tennis:
        # Per i canali tennis, cerca in wikihz
        # Esempio: se id è 1507 cerca wikiten7, se è 1517 cerca wikiten17
        if len(str(channel_id)) == 4 and str(channel_id).startswith('15'):
            tennis_suffix = str(channel_id)[2:]  # Prende le ultime due cifre
            folder_name = f"wikiten{tennis_suffix}"
            base_url = "https://new.newkso.ru/wikihz/"
            test_url = f"{base_url}{folder_name}/mono.m3u8"
            
            try:
                response = requests.head(test_url, timeout=15, proxies=PROXIES)
                if response.status_code == 200:
                    print(f"[✓] Stream tennis trovato: {test_url}")
                    return test_url
                else:
                    print(f"[-] Tentativo su {test_url} fallito con status code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"[!] Errore di rete cercando {test_url}: {e}")
            except Exception as e:
                print(f"[!] Errore imprevisto cercando {test_url}: {e}")

    else:
        # Per i canali daddy, cerca nei siti specificati
        daddy_sites = [
            "https://new.newkso.ru/wind/",
            "https://new.newkso.ru/ddy6/", 
            "https://new.newkso.ru/zeko/",
            "https://new.newkso.ru/nfs/",
            "https://new.newkso.ru/dokko1/"
        ]
        
        folder_name = f"premium{channel_id}"
        
        for site in daddy_sites:
            test_url = f"{site}{folder_name}/mono.m3u8"
            try:
                response = requests.head(test_url, timeout=15, proxies=PROXIES)
                if response.status_code == 200:
                    print(f"[✓] Stream daddy trovato: {test_url}")
                    # Salva nella cache in memoria
                    daddy_cache[str(channel_id)] = test_url
                    return test_url
                else:
                    # Logga lo status code per il debug
                    print(f"[-] Tentativo su {test_url} fallito con status code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"[!] Errore di rete cercando {test_url}: {e}")
                continue # Continua con il prossimo sito
            except Exception as e:
                print(f"[!] Errore imprevisto cercando {test_url}: {e}")
    
    print(f"[!] Nessun stream .m3u8 trovato per channel_id {channel_id}")
    return None

def merger_playlist():
    # Codice del primo script qui
    # Aggiungi il codice del tuo script "merger_playlist.py" in questa funzione.
    # Ad esempio:
    print("Eseguendo il merger_playlist.py...")
    # Il codice che avevi nello script "merger_playlist.py" va qui, senza modifiche.
    import requests
    import os
    from dotenv import load_dotenv

    # Carica le variabili d'ambiente dal file .env
    load_dotenv()

    NOMEREPO = os.getenv("NOMEREPO", "").strip()
    NOMEGITHUB = os.getenv("NOMEGITHUB", "").strip()
    
    # Percorsi o URL delle playlist M3U8
    url1 = "channels_italy.m3u8"  # File locale
    url2 = "eventi.m3u8"   
    url6 = "https://raw.githubusercontent.com/Brenders/Pluto-TV-Italia-M3U/main/PlutoItaly.m3u"
    
    # Funzione per scaricare o leggere una playlist
    def download_playlist(source, append_params=False, exclude_group_title=None):
        if source.startswith("http"):
            response = requests.get(source)
            response.raise_for_status()
            playlist = response.text
        else:
            with open(source, 'r', encoding='utf-8') as f:
                playlist = f.read()
        
        # Rimuovi intestazione iniziale
        playlist = '\n'.join(line for line in playlist.split('\n') if not line.startswith('#EXTM3U'))
    
        if exclude_group_title:
            playlist = '\n'.join(line for line in playlist.split('\n') if exclude_group_title not in line)
    
        return playlist
    
    # Ottieni la directory dove si trova lo script
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    # Scarica/leggi le playlist
    playlist1 = download_playlist(url1) # channels_italy.m3u8
    
    canali_daddy_flag = os.getenv("CANALI_DADDY", "no").strip().lower()
    if canali_daddy_flag == "si":
        playlist2 = download_playlist(url2, append_params=True) # eventi.m3u8
    else:
        print("[INFO] Skipping eventi.m3u8 in merger_playlist as CANALI_DADDY is not 'si'.")
        playlist2 = "" # Empty playlist if not enabled

    playlist6 = download_playlist(url6)
    
    # Unisci le playlist
    lista = playlist1 + "\n" + playlist2 + "\n" + playlist6
    
    # Aggiungi intestazione EPG
    lista = f'#EXTM3U url-tvg="https://raw.githubusercontent.com/{NOMEGITHUB}/{NOMEREPO}/refs/heads/main/epg.xml"\n' + lista
    
    # Salva la playlist
    output_filename = os.path.join(script_directory, "lista.m3u")
    with open(output_filename, 'w', encoding='utf-8') as file:
        file.write(lista)
    
    print(f"Playlist combinata salvata in: {output_filename}")
    
# Funzione per il primo script (merger_playlist.py)
def merger_playlistworld():
    # Codice del primo script qui
    # Aggiungi il codice del tuo script "merger_playlist.py" in questa funzione.
    # Ad esempio:
    print("Eseguendo il merger_playlist.py...")
    # Il codice che avevi nello script "merger_playlist.py" va qui, senza modifiche.
    import requests
    import os
    from dotenv import load_dotenv

    # Carica le variabili d'ambiente dal file .env
    load_dotenv()

    NOMEREPO = os.getenv("NOMEREPO", "").strip()
    NOMEGITHUB = os.getenv("NOMEGITHUB", "").strip()
    
    # Percorsi o URL delle playlist M3U8
    url1 = "channels_italy.m3u8"  
    url2 = "eventi.m3u8"   
    url5 = "https://raw.githubusercontent.com/Brenders/Pluto-TV-Italia-M3U/main/PlutoItaly.m3u"      
    url6 = "world.m3u8"
    
    # Funzione per scaricare o leggere una playlist
    def download_playlist(source, append_params=False, exclude_group_title=None):
        if source.startswith("http"):
            response = requests.get(source)
            response.raise_for_status()
            playlist = response.text
        else:
            with open(source, 'r', encoding='utf-8') as f:
                playlist = f.read()
        
        # Rimuovi intestazione iniziale
        playlist = '\n'.join(line for line in playlist.split('\n') if not line.startswith('#EXTM3U'))
    
        if exclude_group_title:
            playlist = '\n'.join(line for line in playlist.split('\n') if exclude_group_title not in line)
    
        return playlist
    
    # Ottieni la directory dove si trova lo script
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    # Scarica/leggi le playlist
    playlist1 = download_playlist(url1) # channels_italy.m3u8
    
    canali_daddy_flag = os.getenv("CANALI_DADDY", "no").strip().lower()
    if canali_daddy_flag == "si":
        playlist2 = download_playlist(url2, append_params=True) # eventi.m3u8
    else:
        print("[INFO] Skipping eventi.m3u8 in merger_playlistworld as CANALI_DADDY is not 'si'.")
        playlist2 = "" # Empty playlist if not enabled

    playlist5 = download_playlist(url5)
    playlist6 = download_playlist(url6, exclude_group_title="Italy")
    # Unisci le playlist
    lista = playlist1 + "\n" + playlist2 + "\n" + playlist5 + "\n" + playlist6
    
    # Aggiungi intestazione EPG
    lista = f'#EXTM3U url-tvg="https://raw.githubusercontent.com/{NOMEGITHUB}/{NOMEREPO}/refs/heads/main/epg.xml"\n' + lista
    
    # Salva la playlist
    output_filename = os.path.join(script_directory, "lista.m3u")
    with open(output_filename, 'w', encoding='utf-8') as file:
        file.write(lista)
    
    print(f"Playlist combinata salvata in: {output_filename}")

# Funzione per il secondo script (epg_merger.py)
def epg_merger():
    # Codice del secondo script qui
    # Aggiungi il codice del tuo script "epg_merger.py" in questa funzione.
    # Ad esempio:
    print("Eseguendo l'epg_merger.py...")
    # Il codice che avevi nello script "epg_merger.py" va qui, senza modifiche.
    import requests
    import gzip
    import os
    import xml.etree.ElementTree as ET
    import io

    # URL dei file GZIP o XML da elaborare
    urls_gzip = [
        'https://www.open-epg.com/files/italy1.xml',
        'https://www.open-epg.com/files/italy2.xml',
        'https://www.open-epg.com/files/italy3.xml',
        'https://www.open-epg.com/files/italy4.xml',
        'https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz'
    ]

    # File di output
    output_xml = 'epg.xml'    # Nome del file XML finale

    # URL remoto di it.xml
    url_it = 'https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/it.xml'

    # File eventi locale
    path_eventi = 'eventi.xml'

    def download_and_parse_xml(url):
        """Scarica un file .xml o .gzip e restituisce l'ElementTree."""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Prova a decomprimere come GZIP
            try:
                with gzip.open(io.BytesIO(response.content), 'rb') as f_in:
                    xml_content = f_in.read()
            except (gzip.BadGzipFile, OSError):
                # Non Ã¨ un file gzip, usa direttamente il contenuto
                xml_content = response.content

            return ET.ElementTree(ET.fromstring(xml_content))
        except requests.exceptions.RequestException as e:
            print(f"Errore durante il download da {url}: {e}")
        except ET.ParseError as e:
            print(f"Errore nel parsing del file XML da {url}: {e}")
        return None

    # Creare un unico XML vuoto
    root_finale = ET.Element('tv')
    tree_finale = ET.ElementTree(root_finale)

    # Processare ogni URL
    for url in urls_gzip:
        tree = download_and_parse_xml(url)
        if tree is not None:
            root = tree.getroot()
            for element in root:
                root_finale.append(element)

    # Check CANALI_DADDY flag before processing eventi.xml
    canali_daddy_flag = os.getenv("CANALI_DADDY", "no").strip().lower()
    if canali_daddy_flag == "si":
        # Aggiungere eventi.xml da file locale
        if os.path.exists(path_eventi):
            try:
                tree_eventi = ET.parse(path_eventi)
                root_eventi = tree_eventi.getroot()
                for programme in root_eventi.findall(".//programme"):
                    root_finale.append(programme)
            except ET.ParseError as e:
                print(f"Errore nel parsing del file eventi.xml: {e}")
        else:
            print(f"File non trovato: {path_eventi}")
    else:
        print("[INFO] Skipping eventi.xml in epg_merger as CANALI_DADDY is not 'si'.")

    # Aggiungere it.xml da URL remoto
    tree_it = download_and_parse_xml(url_it)
    if tree_it is not None:
        root_it = tree_it.getroot()
        for programme in root_it.findall(".//programme"):
            root_finale.append(programme)
    else:
        print(f"Impossibile scaricare o analizzare il file it.xml da {url_it}")

    # Funzione per pulire attributi
    def clean_attribute(element, attr_name):
        if attr_name in element.attrib:
            old_value = element.attrib[attr_name]
            new_value = old_value.replace(" ", "").lower()
            element.attrib[attr_name] = new_value

    # Pulire gli ID dei canali
    for channel in root_finale.findall(".//channel"):
        clean_attribute(channel, 'id')

    # Pulire gli attributi 'channel' nei programmi
    for programme in root_finale.findall(".//programme"):
        clean_attribute(programme, 'channel')

    # Salvare il file XML finale
    with open(output_xml, 'wb') as f_out:
        tree_finale.write(f_out, encoding='utf-8', xml_declaration=True)
    print(f"File XML salvato: {output_xml}")
             
# Funzione per il terzo script (eventi_m3u8_generator.py)
def eventi_m3u8_generator_world():
    # Codice del terzo script qui
    # Aggiungi il codice del tuo script "eventi_m3u8_generator.py" in questa funzione.
    print("Eseguendo l'eventi_m3u8_generator.py...")
    # Il codice che avevi nello script "eventi_m3u8_generator.py" va qui, senza modifiche.
    import json
    import re
    import requests
    import urllib.parse # Consolidato
    from datetime import datetime, timedelta
    from dateutil import parser
    import os
    from dotenv import load_dotenv
    from PIL import Image, ImageDraw, ImageFont
    import io # Aggiunto per encoding URL
    import time
    
    # Carica le variabili d'ambiente dal file .env
    load_dotenv()

    LINK_DADDY = os.getenv("LINK_DADDY", "https://daddylive.dad").strip() 
    JSON_FILE = "daddyliveSchedule.json" 
    OUTPUT_FILE = "eventi.m3u8" 
    HEADERS = { 
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36" 
    } 
     
    HTTP_TIMEOUT = 10 
    session = requests.Session() 
    session.headers.update(HEADERS) 
    # Definisci current_time e three_hours_in_seconds per la logica di caching
    current_time = time.time()
    three_hours_in_seconds = 3 * 60 * 60
    
    def clean_category_name(name): 
        # Rimuove tag html come </span> o simili 
        return re.sub(r'<[^>]+>', '', name).strip()
        
    def clean_tvg_id(tvg_id):
        """
        Pulisce il tvg-id rimuovendo caratteri speciali, spazi e convertendo tutto in minuscolo
        """
        # import re # 're' Ã¨ giÃ  importato a livello di funzione
        # Rimuove caratteri speciali comuni mantenendo solo lettere e numeri
        cleaned = re.sub(r'[^a-zA-Z0-9À-ÿ]', '', tvg_id)
        return cleaned.lower()
     
    def search_logo_for_event(event_name): 
        """ 
        Cerca un logo per l'evento specificato utilizzando un motore di ricerca 
        Restituisce l'URL dell'immagine trovata o None se non trovata 
        """ 
        try: 
            # Rimuovi eventuali riferimenti all'orario dal nome dell'evento
            # Cerca pattern come "Team A vs Team B (20:00)" e rimuovi la parte dell'orario
            clean_event_name = re.sub(r'\s*\(\d{1,2}:\d{2}\)\s*$', '', event_name)
            # Se c'ÃÂ¨ un ':', prendi solo la parte dopo
            if ':' in clean_event_name:
                clean_event_name = clean_event_name.split(':', 1)[1].strip()
            
            # Verifica se l'evento contiene "vs" o "-" per identificare le due squadre
            teams = None
            if " vs " in clean_event_name:
                teams = clean_event_name.split(" vs ")
            elif " VS " in clean_event_name:
                teams = clean_event_name.split(" VS ")
            elif " VS. " in clean_event_name:
                teams = clean_event_name.split(" VS. ")
            elif " vs. " in clean_event_name:
                teams = clean_event_name.split(" vs. ")
            
            # Se abbiamo identificato due squadre, cerchiamo i loghi separatamente
            if teams and len(teams) == 2:
                team1 = teams[0].strip()
                team2 = teams[1].strip()
                
                print(f"[🔍] Ricerca logo per Team 1: {team1}")
                logo1_url = search_team_logo(team1)
                
                print(f"[🔍] Ricerca logo per Team 2: {team2}")
                logo2_url = search_team_logo(team2)
                
                # Se abbiamo trovato entrambi i loghi, creiamo un'immagine combinata
                if logo1_url and logo2_url:
                    # Scarica i loghi e l'immagine VS
                    try:
                        from os.path import exists, getmtime
                        
                        # Crea la cartella logos se non esiste
                        logos_dir = "logos"
                        os.makedirs(logos_dir, exist_ok=True)
                        
                        # Verifica se l'immagine combinata esiste giÃÂ  e non ÃÂ¨ obsoleta
                        output_filename = f"logos/{team1}_vs_{team2}.png"
                        if exists(output_filename):
                            file_age = current_time - os.path.getmtime(output_filename)
                            if file_age <= three_hours_in_seconds:
                                print(f"[✓] Utilizzo immagine combinata esistente: {output_filename}")
                                
                                # Carica le variabili d'ambiente per GitHub
                                NOMEREPO = os.getenv("NOMEREPO", "").strip()
                                NOMEGITHUB = os.getenv("NOMEGITHUB", "").strip()
                                
                                # Se le variabili GitHub sono disponibili, restituisci l'URL raw di GitHub
                                if NOMEGITHUB and NOMEREPO:
                                    github_raw_url = f"https://raw.githubusercontent.com/{NOMEGITHUB}/{NOMEREPO}/main/{output_filename}"
                                    print(f"[✓] URL GitHub generato per logo esistente: {github_raw_url}")
                                    return github_raw_url
                                else:
                                    # Altrimenti restituisci il percorso locale
                                    return output_filename
                        
                        # Scarica i loghi
                        img1, img2 = None, None
                        
                        if logo1_url:
                            try:
                                # Aggiungi un User-Agent simile a un browser
                                logo_headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                                }
                                response1 = requests.get(logo1_url, headers=logo_headers, timeout=10)
                                response1.raise_for_status() # Controlla errori HTTP
                                if 'image' in response1.headers.get('Content-Type', '').lower():
                                    img1 = Image.open(io.BytesIO(response1.content))
                                    print(f"[✓] Logo1 scaricato con successo da: {logo1_url}")
                                else:
                                    print(f"[!] URL logo1 ({logo1_url}) non è un'immagine (Content-Type: {response1.headers.get('Content-Type')}).")
                                    logo1_url = None # Invalida URL se non è un'immagine
                            except requests.exceptions.RequestException as e_req:
                                print(f"[!] Errore scaricando logo1 ({logo1_url}): {e_req}")
                                logo1_url = None
                            except Exception as e_pil: # Errore specifico da PIL durante Image.open
                                print(f"[!] Errore PIL aprendo logo1 ({logo1_url}): {e_pil}")
                                logo1_url = None
                        
                        if logo2_url:
                            try:
                                # Aggiungi un User-Agent simile a un browser
                                logo_headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                                }
                                response2 = requests.get(logo2_url, headers=logo_headers, timeout=10)
                                response2.raise_for_status() # Controlla errori HTTP
                                if 'image' in response2.headers.get('Content-Type', '').lower():
                                    img2 = Image.open(io.BytesIO(response2.content))
                                    print(f"[✓] Logo2 scaricato con successo da: {logo2_url}")
                                else:
                                    print(f"[!] URL logo2 ({logo2_url}) non è un'immagine (Content-Type: {response2.headers.get('Content-Type')}).")
                                    logo2_url = None # Invalida URL se non è un'immagine
                            except requests.exceptions.RequestException as e_req:
                                print(f"[!] Errore scaricando logo2 ({logo2_url}): {e_req}")
                                logo2_url = None
                            except Exception as e_pil: # Errore specifico da PIL durante Image.open
                                print(f"[!] Errore PIL aprendo logo2 ({logo2_url}): {e_pil}")
                                logo2_url = None
                        
                        # Carica l'immagine VS (assicurati che esista nella directory corrente)
                        vs_path = "vs.png"
                        if exists(vs_path):
                            img_vs = Image.open(vs_path)
                            # Converti l'immagine VS in modalitÃÂ  RGBA se non lo ÃÂ¨ giÃÂ 
                            if img_vs.mode != 'RGBA':
                                img_vs = img_vs.convert('RGBA')
                        else:
                            # Crea un'immagine di testo "VS" se il file non esiste
                            img_vs = Image.new('RGBA', (100, 100), (255, 255, 255, 0))
                            from PIL import ImageDraw, ImageFont
                            draw = ImageDraw.Draw(img_vs)
                            try:
                                font = ImageFont.truetype("arial.ttf", 40)
                            except:
                                font = ImageFont.load_default()
                            draw.text((30, 30), "VS", fill=(255, 0, 0), font=font)
                        
                        # Procedi con la combinazione solo se entrambi i loghi sono stati caricati con successo
                        if not (img1 and img2):
                            print(f"[!] Impossibile caricare entrambi i loghi come immagini valide per la combinazione. Logo1 caricato: {bool(img1)}, Logo2 caricato: {bool(img2)}.")
                            raise ValueError("Uno o entrambi i loghi non sono stati caricati correttamente.") # Questo forzerÃ  l'except sottostante
                        
                        # Ridimensiona le immagini a dimensioni uniformi
                        size = (150, 150)
                        img1 = img1.resize(size)
                        img2 = img2.resize(size)
                        img_vs = img_vs.resize((100, 100))
                        
                        # Assicurati che tutte le immagini siano in modalitÃÂ  RGBA per supportare la trasparenza
                        if img1.mode != 'RGBA':
                            img1 = img1.convert('RGBA')
                        if img2.mode != 'RGBA':
                            img2 = img2.convert('RGBA')
                        
                        # Crea una nuova immagine con spazio per entrambi i loghi e il VS
                        combined_width = 300
                        combined = Image.new('RGBA', (combined_width, 150), (255, 255, 255, 0))
                        
                        # Posiziona le immagini con il VS sovrapposto al centro
                        # Posiziona il primo logo a sinistra
                        combined.paste(img1, (0, 0), img1)
                        # Posiziona il secondo logo a destra
                        combined.paste(img2, (combined_width - 150, 0), img2)
                        
                        # Posiziona il VS al centro, sovrapposto ai due loghi
                        vs_x = (combined_width - 100) // 2
                        
                        # Crea una copia dell'immagine combinata prima di sovrapporre il VS
                        # Questo passaggio ÃÂ¨ importante per preservare i dettagli dei loghi sottostanti
                        combined_with_vs = combined.copy()
                        combined_with_vs.paste(img_vs, (vs_x, 25), img_vs)
                        
                        # Usa l'immagine con VS sovrapposto
                        combined = combined_with_vs
                        
                        # Salva l'immagine combinata
                        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
                        combined.save(output_filename)
                        
                        print(f"[✓] Immagine combinata creata: {output_filename}")
                        
                        # Carica le variabili d'ambiente per GitHub
                        NOMEREPO = os.getenv("NOMEREPO", "").strip()
                        NOMEGITHUB = os.getenv("NOMEGITHUB", "").strip()
                        
                        # Se le variabili GitHub sono disponibili, restituisci l'URL raw di GitHub
                        if NOMEGITHUB and NOMEREPO:
                            github_raw_url = f"https://raw.githubusercontent.com/{NOMEGITHUB}/{NOMEREPO}/main/{output_filename}"
                            print(f"[✓] URL GitHub generato: {github_raw_url}")
                            return github_raw_url
                        else:
                            # Altrimenti restituisci il percorso locale
                            return output_filename
                        
                    except Exception as e:
                        print(f"[!] Errore nella creazione dell'immagine combinata: {e}")
                        # Se fallisce, restituisci solo il primo logo trovato
                        return logo1_url or logo2_url
                
                # Se non abbiamo trovato entrambi i loghi, restituisci quello che abbiamo
                return logo1_url or logo2_url
            if ':' in event_name:
                # Usa la parte prima dei ":" per la ricerca
                prefix_name = event_name.split(':', 1)[0].strip()
                print(f"[🔍] Tentativo ricerca logo con prefisso: {prefix_name}")
                
                # Prepara la query di ricerca con il prefisso
                search_query = urllib.parse.quote(f"{prefix_name} logo")
                
                # Utilizziamo l'API di Bing Image Search con parametri migliorati
                search_url = f"https://www.bing.com/images/search?q={search_query}&qft=+filterui:photo-transparent+filterui:aspect-square&form=IRFLTR"
                
                headers = { 
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Cache-Control": "max-age=0",
                    "Connection": "keep-alive"
                } 
                
                response = requests.get(search_url, headers=headers, timeout=10)
                
                if response.status_code == 200: 
                    # Metodo 1: Cerca pattern per murl (URL dell'immagine media)
                    patterns = [
                        r'murl&quot;:&quot;(https?://[^&]+)&quot;',
                        r'"murl":"(https?://[^"]+)"',
                        r'"contentUrl":"(https?://[^"]+\.(?:png|jpg|jpeg|svg))"',
                        r'<img[^>]+src="(https?://[^"]+\.(?:png|jpg|jpeg|svg))[^>]+class="mimg"',
                        r'<a[^>]+class="iusc"[^>]+m=\'{"[^"]*":"[^"]*","[^"]*":"(https?://[^"]+)"'
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, response.text)
                        if matches and len(matches) > 0:
                            # Prendi il primo risultato che sembra un logo (preferibilmente PNG o SVG)
                            for match in matches:
                                if '.png' in match.lower() or '.svg' in match.lower():
                                    print(f"[✓] Logo trovato con prefisso: {match}")
                                    return match
                            # Se non troviamo PNG o SVG, prendi il primo risultato
                            print(f"[✓] Logo trovato con prefisso: {matches[0]}")
                            return matches[0]
            
            # Se non riusciamo a identificare le squadre e il prefisso non ha dato risultati, procedi con la ricerca normale
            print(f"[🔍] Ricerca standard per: {clean_event_name}")
            
            
            # Se non riusciamo a identificare le squadre, procedi con la ricerca normale
            # Prepara la query di ricerca piÃÂ¹ specifica
            search_query = urllib.parse.quote(f"{clean_event_name} logo")
            
            # Utilizziamo l'API di Bing Image Search con parametri migliorati
            search_url = f"https://www.bing.com/images/search?q={search_query}&qft=+filterui:photo-transparent+filterui:aspect-square&form=IRFLTR"
            
            headers = { 
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "max-age=0",
                "Connection": "keep-alive"
            } 
            
            response = requests.get(search_url, headers=headers, timeout=10)
            
            if response.status_code == 200: 
                # Metodo 1: Cerca pattern per murl (URL dell'immagine media)
                patterns = [
                    r'murl&quot;:&quot;(https?://[^&]+)&quot;',
                    r'"murl":"(https?://[^"]+)"',
                    r'"contentUrl":"(https?://[^"]+\.(?:png|jpg|jpeg|svg))"',
                    r'<img[^>]+src="(https?://[^"]+\.(?:png|jpg|jpeg|svg))[^>]+class="mimg"',
                    r'<a[^>]+class="iusc"[^>]+m=\'{"[^"]*":"[^"]*","[^"]*":"(https?://[^"]+)"'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, response.text)
                    if matches and len(matches) > 0:
                        # Prendi il primo risultato che sembra un logo (preferibilmente PNG o SVG)
                        for match in matches:
                            if '.png' in match.lower() or '.svg' in match.lower():
                                return match
                        # Se non troviamo PNG o SVG, prendi il primo risultato
                        return matches[0]
                
                # Metodo alternativo: cerca JSON incorporato nella pagina
                json_match = re.search(r'var\s+IG\s*=\s*(\{.+?\});\s*', response.text)
                if json_match:
                    try:
                        # Estrai e analizza il JSON
                        json_str = json_match.group(1)
                        # Pulisci il JSON se necessario
                        json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+):', r'\1"\2":', json_str)
                        data = json.loads(json_str)
                        
                        # Cerca URL di immagini nel JSON
                        if 'images' in data and len(data['images']) > 0:
                            for img in data['images']:
                                if 'murl' in img:
                                    return img['murl']
                    except Exception as e:
                        print(f"[!] Errore nell'analisi JSON: {e}")
                
                print(f"[!] Nessun logo trovato per '{clean_event_name}' con i pattern standard")
                
                # Ultimo tentativo: cerca qualsiasi URL di immagine nella pagina
                any_img = re.search(r'(https?://[^"\']+\.(?:png|jpg|jpeg|svg|webp))', response.text)
                if any_img:
                    return any_img.group(1)
                    
        except Exception as e: 
            print(f"[!] Errore nella ricerca del logo per '{event_name}': {e}") 
        
        # Se non troviamo nulla, restituiamo None 
        return None

    def search_team_logo(team_name):
        """
        Funzione dedicata alla ricerca del logo di una singola squadra
        """
        try:
            # Prepara la query di ricerca specifica per la squadra
            search_query = urllib.parse.quote(f"{team_name} logo")
            
            # Utilizziamo l'API di Bing Image Search con parametri migliorati
            search_url = f"https://www.bing.com/images/search?q={search_query}&qft=+filterui:photo-transparent+filterui:aspect-square&form=IRFLTR"
            
            headers = { 
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "max-age=0",
                "Connection": "keep-alive"
            } 
            
            response = requests.get(search_url, headers=headers, timeout=10)
            
            if response.status_code == 200: 
                # Metodo 1: Cerca pattern per murl (URL dell'immagine media)
                patterns = [
                    r'murl&quot;:&quot;(https?://[^&]+)&quot;',
                    r'"murl":"(https?://[^"]+)"',
                    r'"contentUrl":"(https?://[^"]+\.(?:png|jpg|jpeg|svg))"',
                    r'<img[^>]+src="(https?://[^"]+\.(?:png|jpg|jpeg|svg))[^>]+class="mimg"',
                    r'<a[^>]+class="iusc"[^>]+m=\'{"[^"]*":"[^"]*","[^"]*":"(https?://[^"]+)"'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, response.text)
                    if matches and len(matches) > 0:
                        # Prendi il primo risultato che sembra un logo (preferibilmente PNG o SVG)
                        for match in matches:
                            if '.png' in match.lower() or '.svg' in match.lower():
                                return match
                        # Se non troviamo PNG o SVG, prendi il primo risultato
                        return matches[0]
                
                # Metodo alternativo: cerca JSON incorporato nella pagina
                json_match = re.search(r'var\s+IG\s*=\s*(\{.+?\});\s*', response.text)
                if json_match:
                    try:
                        # Estrai e analizza il JSON
                        json_str = json_match.group(1)
                        # Pulisci il JSON se necessario
                        json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+):', r'\1"\2":', json_str)
                        data = json.loads(json_str)
                        
                        # Cerca URL di immagini nel JSON
                        if 'images' in data and len(data['images']) > 0:
                            for img in data['images']:
                                if 'murl' in img:
                                    return img['murl']
                    except Exception as e:
                        print(f"[!] Errore nell'analisi JSON: {e}")
                
                print(f"[!] Nessun logo trovato per '{team_name}' con i pattern standard")
                
                # Ultimo tentativo: cerca qualsiasi URL di immagine nella pagina
                any_img = re.search(r'(https?://[^"\']+\.(?:png|jpg|jpeg|svg|webp))', response.text)
                if any_img:
                    return any_img.group(1)
                    
        except Exception as e: 
            print(f"[!] Errore nella ricerca del logo per '{team_name}': {e}") 
        
        # Se non troviamo nulla, restituiamo None 
        return None
     
    def get_stream_from_channel_id(channel_id): 
        # Prima cerca nei nuovi siti .m3u8
        m3u8_url = search_m3u8_in_sites(channel_id, is_tennis=False)
        if m3u8_url:
            return m3u8_url
        
        # Fallback al vecchio metodo .php se non trovato
        embed_url = f"{LINK_DADDY}/stream/stream-{channel_id}.php" 
        print(f"Fallback URL .php per il canale Daddylive {channel_id}.")
        return embed_url
     
    # def clean_category_name(name): # Rimossa definizione duplicata
    #     # Rimuove tag html come </span> o simili
    #     return re.sub(r'<[^>]+>', '', name).strip()
     
    def extract_channels_from_json(path): 
        keywords = {"italy", "rai", "italia", "it", "uk", "tnt", "usa", "tennis channel", "tennis stream", "la"} 
        now = datetime.now()  # ora attuale completa (data+ora) 
        yesterday_date = (now - timedelta(days=1)).date() # Data di ieri
     
        with open(path, "r", encoding="utf-8") as f: 
            data = json.load(f) 
     
        categorized_channels = {} 
     
        for date_key, sections in data.items(): 
            date_part = date_key.split(" - ")[0] 
            try: 
                date_obj = parser.parse(date_part, fuzzy=True).date() 
            except Exception as e: 
                print(f"[!] Errore parsing data '{date_part}': {e}") 
                continue 
            
            # Determina se processare questa data
            process_this_date = False
            is_yesterday_early_morning_event_check = False

            if date_obj == now.date():
                process_this_date = True
            elif date_obj == yesterday_date:
                process_this_date = True
                is_yesterday_early_morning_event_check = True # Flag per eventi di ieri mattina presto
            else:
                # Salta date che non sono nÃ© oggi nÃ© ieri
                continue

            if not process_this_date:
                continue
     
            for category_raw, event_items in sections.items(): 
                category = clean_category_name(category_raw)
                # Salta la categoria TV Shows
                if category.lower() == "tv shows":
                    continue
                if category not in categorized_channels: 
                    categorized_channels[category] = [] 
     
                for item in event_items: 
                    time_str = item.get("time", "00:00") # Orario originale dal JSON
                    event_title = item.get("event", "Evento") 
     
                    try: 
                        # Parse orario evento originale (dal JSON)
                        original_event_time_obj = datetime.strptime(time_str, "%H:%M").time()

                        # Costruisci datetime completo dell'evento con la sua data originale
                        # e l'orario originale, poi applica il timedelta(hours=2) (per "correzione timezone?")
                        # Questo event_datetime_adjusted Ã¨ quello che viene usato per il filtro "meno di 2 ore fa" per oggi
                        # e per il nome del canale.
                        event_datetime_adjusted_for_display_and_filter = datetime.combine(date_obj, original_event_time_obj) + timedelta(hours=2)

                        if is_yesterday_early_morning_event_check:
                            # Filtro per eventi di ieri mattina presto (00:00 - 04:00, ora JSON)
                            start_filter_time = datetime.strptime("00:00", "%H:%M").time()
                            end_filter_time = datetime.strptime("04:00", "%H:%M").time()
                            # Confronta l'orario originale dell'evento
                            if not (start_filter_time <= original_event_time_obj <= end_filter_time):
                                # Evento di ieri, ma non nell'intervallo 00:00-04:00 -> salto
                                continue
                        else: # Eventi di oggi
                            # Controllo: includi solo se l'evento Ã¨ iniziato da meno di 2 ore
                            # Usa event_datetime_adjusted_for_display_and_filter che ha giÃ  il +2h
                            if now - event_datetime_adjusted_for_display_and_filter > timedelta(hours=2):
                                # Evento di oggi iniziato da piÃ¹ di 2 ore -> salto
                                continue
                        
                        time_formatted = event_datetime_adjusted_for_display_and_filter.strftime("%H:%M")
                    except Exception as e_time:
                        print(f"[!] Errore parsing orario '{time_str}' per evento '{event_title}' in data '{date_key}': {e_time}")
                        time_formatted = time_str # Fallback
     
                    for ch in item.get("channels", []): 
                        channel_name = ch.get("channel_name", "") 
                        channel_id = ch.get("channel_id", "") 
     
                        words = set(re.findall(r'\b\w+\b', channel_name.lower())) 
                        if keywords.intersection(words): 
                            tvg_name = f"{event_title} ({time_formatted})" 
                            categorized_channels[category].append({ 
                                "tvg_name": tvg_name, 
                                "channel_name": channel_name, 
                                "channel_id": channel_id,
                                "event_title": event_title  # Aggiungiamo il titolo dell'evento per la ricerca del logo
                            }) 
     
        return categorized_channels 
     
    def generate_m3u_from_schedule(json_file, output_file): 
        categorized_channels = extract_channels_from_json(json_file) 

        with open(output_file, "w", encoding="utf-8") as f: 
            f.write("#EXTM3U\n") 

            # Controlla se ci sono eventi prima di aggiungere il canale DADDYLIVE
            has_events = any(channels for channels in categorized_channels.values())
            
            if has_events:
                # Aggiungi il canale iniziale/informativo solo se ci sono eventi
                f.write(f'#EXTINF:-1 tvg-name="DADDYLIVE" group-title="Eventi Live",DADDYLIVE\n')
                f.write("https://example.com.m3u8\n\n")
            else:
                print("[ℹ️] Nessun evento trovato, canale DADDYLIVE non aggiunto.")

            for category, channels in categorized_channels.items(): 
                if not channels: 
                    continue 
          
                for ch in channels: 
                    tvg_name = ch["tvg_name"] 
                    channel_id = ch["channel_id"] 
                    event_title = ch["event_title"]  # Otteniamo il titolo dell'evento
                    channel_name = ch["channel_name"]
                    
                    # Cerca un logo per questo evento
                    # Rimuovi l'orario dal titolo dell'evento prima di cercare il logo
                    clean_event_title = re.sub(r'\s*\(\d{1,2}:\d{2}\)\s*$', '', event_title)
                    print(f"[🔍] Ricerca logo per: {clean_event_title}") 
                    logo_url = search_logo_for_event(clean_event_title)
                    logo_attribute = f' tvg-logo="{logo_url}"' if logo_url else ''
     
                    try: 
                        # Controlla se è un canale tennis
                        if "tennis channel" in channel_name.lower() or "tennis stream" in channel_name.lower():
                            # Usa la nuova funzione per i canali tennis
                            stream = search_m3u8_in_sites(channel_id, is_tennis=True)
                            if not stream:
                                # Fallback al metodo originale se non trovato
                                stream = get_stream_from_channel_id(channel_id)
                        else:
                            stream = get_stream_from_channel_id(channel_id)
                            
                        if stream: 
                            cleaned_event_id = clean_tvg_id(event_title) # Usa event_title per tvg-id
                            f.write(f'#EXTINF:-1 tvg-id="{cleaned_event_id}" tvg-name="{category} | {tvg_name}"{logo_attribute} group-title="Eventi Live",{category} | {tvg_name}\n')
                            # Aggiungi EXTHTTP headers per canali daddy (esclusi .php)
                            if ("newkso.ru" in stream or "premium" in stream) and not stream.endswith('.php'):
                                daddy_headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Referer": "https://forcedtoplay.xyz/", "Origin": "https://forcedtoplay.xyz"}
                                vlc_opt_lines = headers_to_extvlcopt(daddy_headers)
                                for line in vlc_opt_lines:
                                    f.write(f'{line}\n')
                            f.write(f'{stream}\n\n')
                            print(f"[✓] {tvg_name}" + (f" (logo trovato)" if logo_url else " (nessun logo trovato)")) 
                        else: 
                            print(f"[✗] {tvg_name} - Nessuno stream trovato") 
                    except Exception as e: 
                        print(f"[!] Errore su {tvg_name}: {e}") 
     
    # Esegui la generazione quando la funzione viene chiamata
    generate_m3u_from_schedule(JSON_FILE, OUTPUT_FILE)

# Funzione per il terzo script (eventi_m3u8_generator.py)
def eventi_m3u8_generator():
    # Codice del terzo script qui
    # Aggiungi il codice del tuo script "eventi_m3u8_generator.py" in questa funzione.
    print("Eseguendo l'eventi_m3u8_generator.py...")
    # Il codice che avevi nello script "eventi_m3u8_generator.py" va qui, senza modifiche.
    import json 
    import re 
    import requests 
    from urllib.parse import quote 
    from datetime import datetime, timedelta 
    from dateutil import parser 
    import urllib.parse
    import os
    from dotenv import load_dotenv
    from PIL import Image, ImageDraw, ImageFont
    import io
    import urllib.parse # Aggiunto per encoding URL
    import time

    # Carica le variabili d'ambiente dal file .env
    load_dotenv()
    LINK_DADDY = os.getenv("LINK_DADDY", "https://daddylive.dad").strip()
    JSON_FILE = "daddyliveSchedule.json" 
    OUTPUT_FILE = "eventi.m3u8" 
     
    HEADERS = { 
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36" 
    } 
     
    HTTP_TIMEOUT = 10 
    session = requests.Session() 
    session.headers.update(HEADERS) 
    # Definisci current_time e three_hours_in_seconds per la logica di caching
    current_time = time.time()
    three_hours_in_seconds = 3 * 60 * 60
    
    def clean_category_name(name): 
        # Rimuove tag html come </span> o simili 
        return re.sub(r'<[^>]+>', '', name).strip()
        
    def clean_tvg_id(tvg_id):
        """
        Pulisce il tvg-id rimuovendo caratteri speciali, spazi e convertendo tutto in minuscolo.
        """
        import re
        # Rimuove caratteri speciali comuni mantenendo solo lettere e numeri
        cleaned = re.sub(r'[^a-zA-Z0-9À-ÿ]', '', tvg_id)
        return cleaned.lower()
     
    def search_logo_for_event(event_name): 
        """ 
        Cerca un logo per l'evento specificato utilizzando un motore di ricerca 
        Restituisce l'URL dell'immagine trovata o None se non trovata 
        """ 
        try: 
            # Rimuovi eventuali riferimenti all'orario dal nome dell'evento
            # Cerca pattern come "Team A vs Team B (20:00)" e rimuovi la parte dell'orario
            clean_event_name = re.sub(r'\s*\(\d{1,2}:\d{2}\)\s*$', '', event_name)
            # Se c'è un ':', prendi solo la parte dopo
            if ':' in clean_event_name:
                clean_event_name = clean_event_name.split(':', 1)[1].strip()
            
            # Verifica se l'evento contiene "vs" o "-" per identificare le due squadre
            teams = None
            if " vs " in clean_event_name:
                teams = clean_event_name.split(" vs ")
            elif " VS " in clean_event_name:
                teams = clean_event_name.split(" VS ")
            elif " VS. " in clean_event_name:
                teams = clean_event_name.split(" VS. ")
            elif " vs. " in clean_event_name:
                teams = clean_event_name.split(" vs. ")
            
            # Se abbiamo identificato due squadre, cerchiamo i loghi separatamente
            if teams and len(teams) == 2:
                team1 = teams[0].strip()
                team2 = teams[1].strip()
                
                print(f"[🔍] Ricerca logo per Team 1: {team1}")
                logo1_url = search_team_logo(team1)
                
                print(f"[🔍] Ricerca logo per Team 2: {team2}")
                logo2_url = search_team_logo(team2)
                
                # Se abbiamo trovato entrambi i loghi, creiamo un'immagine combinata
                if logo1_url and logo2_url:
                    # Scarica i loghi e l'immagine VS
                    try:
                        from os.path import exists, getmtime
                        
                        # Crea la cartella logos se non esiste
                        logos_dir = "logos"
                        os.makedirs(logos_dir, exist_ok=True)
                        
                        # Verifica se l'immagine combinata esiste giÃÂ  e non ÃÂ¨ obsoleta
                        output_filename = f"logos/{team1}_vs_{team2}.png"
                        if exists(output_filename):
                            file_age = current_time - os.path.getmtime(output_filename)
                            if file_age <= three_hours_in_seconds:
                                print(f"[✓] Utilizzo immagine combinata esistente: {output_filename}")
                                
                                # Carica le variabili d'ambiente per GitHub
                                NOMEREPO = os.getenv("NOMEREPO", "").strip()
                                NOMEGITHUB = os.getenv("NOMEGITHUB", "").strip()
                                
                                # Se le variabili GitHub sono disponibili, restituisci l'URL raw di GitHub
                                if NOMEGITHUB and NOMEREPO:
                                    github_raw_url = f"https://raw.githubusercontent.com/{NOMEGITHUB}/{NOMEREPO}/main/{output_filename}"
                                    print(f"[✓] URL GitHub generato per logo esistente: {github_raw_url}")
                                    return github_raw_url
                                else:
                                    # Altrimenti restituisci il percorso locale
                                    return output_filename
                        
                        # Scarica i loghi
                        img1, img2 = None, None
                        
                        if logo1_url:
                            try:
                                # Aggiungi un User-Agent simile a un browser
                                logo_headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                                }
                                response1 = requests.get(logo1_url, headers=logo_headers, timeout=10)
                                response1.raise_for_status() # Controlla errori HTTP
                                if 'image' in response1.headers.get('Content-Type', '').lower():
                                    img1 = Image.open(io.BytesIO(response1.content))
                                    print(f"[✓] Logo1 scaricato con successo da: {logo1_url}")
                                else:
                                    print(f"[!] URL logo1 ({logo1_url}) non è un'immagine (Content-Type: {response1.headers.get('Content-Type')}).")
                                    logo1_url = None # Invalida URL se non è un'immagine
                            except requests.exceptions.RequestException as e_req:
                                print(f"[!] Errore scaricando logo1 ({logo1_url}): {e_req}")
                                logo1_url = None
                            except Exception as e_pil: # Errore specifico da PIL durante Image.open
                                print(f"[!] Errore PIL aprendo logo1 ({logo1_url}): {e_pil}")
                                logo1_url = None
                        
                        if logo2_url:
                            try:
                                # Aggiungi un User-Agent simile a un browser
                                logo_headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                                }
                                response2 = requests.get(logo2_url, headers=logo_headers, timeout=10)
                                response2.raise_for_status() # Controlla errori HTTP
                                if 'image' in response2.headers.get('Content-Type', '').lower():
                                    img2 = Image.open(io.BytesIO(response2.content))
                                    print(f"[✓] Logo2 scaricato con successo da: {logo2_url}")
                                else:
                                    print(f"[!] URL logo2 ({logo2_url}) non è un'immagine (Content-Type: {response2.headers.get('Content-Type')}).")
                                    logo2_url = None # Invalida URL se non è un'immagine
                            except requests.exceptions.RequestException as e_req:
                                print(f"[!] Errore scaricando logo2 ({logo2_url}): {e_req}")
                                logo2_url = None
                            except Exception as e_pil: # Errore specifico da PIL durante Image.open
                                print(f"[!] Errore PIL aprendo logo2 ({logo2_url}): {e_pil}")
                                logo2_url = None
                        
                        # Carica l'immagine VS (assicurati che esista nella directory corrente)
                        vs_path = "vs.png"
                        if exists(vs_path):
                            img_vs = Image.open(vs_path)
                            # Converti l'immagine VS in modalitÃÂ  RGBA se non lo ÃÂ¨ giÃÂ 
                            if img_vs.mode != 'RGBA':
                                img_vs = img_vs.convert('RGBA')
                        else:
                            # Crea un'immagine di testo "VS" se il file non esiste
                            img_vs = Image.new('RGBA', (100, 100), (255, 255, 255, 0))
                            from PIL import ImageDraw, ImageFont
                            draw = ImageDraw.Draw(img_vs)
                            try:
                                font = ImageFont.truetype("arial.ttf", 40)
                            except:
                                font = ImageFont.load_default()
                            draw.text((30, 30), "VS", fill=(255, 0, 0), font=font)
                        
                        # Procedi con la combinazione solo se entrambi i loghi sono stati caricati con successo
                        if not (img1 and img2):
                            print(f"[!] Impossibile caricare entrambi i loghi come immagini valide per la combinazione. Logo1 caricato: {bool(img1)}, Logo2 caricato: {bool(img2)}.")
                            raise ValueError("Uno o entrambi i loghi non sono stati caricati correttamente.") # Questo forzerÃ  l'except sottostante
                        
                        # Ridimensiona le immagini a dimensioni uniformi
                        size = (150, 150)
                        img1 = img1.resize(size)
                        img2 = img2.resize(size)
                        img_vs = img_vs.resize((100, 100))
                        
                        # Assicurati che tutte le immagini siano in modalitÃÂ  RGBA per supportare la trasparenza
                        if img1.mode != 'RGBA':
                            img1 = img1.convert('RGBA')
                        if img2.mode != 'RGBA':
                            img2 = img2.convert('RGBA')
                        
                        # Crea una nuova immagine con spazio per entrambi i loghi e il VS
                        combined_width = 300
                        combined = Image.new('RGBA', (combined_width, 150), (255, 255, 255, 0))
                        
                        # Posiziona le immagini con il VS sovrapposto al centro
                        # Posiziona il primo logo a sinistra
                        combined.paste(img1, (0, 0), img1)
                        # Posiziona il secondo logo a destra
                        combined.paste(img2, (combined_width - 150, 0), img2)
                        
                        # Posiziona il VS al centro, sovrapposto ai due loghi
                        vs_x = (combined_width - 100) // 2
                        
                        # Crea una copia dell'immagine combinata prima di sovrapporre il VS
                        # Questo passaggio ÃÂ¨ importante per preservare i dettagli dei loghi sottostanti
                        combined_with_vs = combined.copy()
                        combined_with_vs.paste(img_vs, (vs_x, 25), img_vs)
                        
                        # Usa l'immagine con VS sovrapposto
                        combined = combined_with_vs
                        
                        # Salva l'immagine combinata
                        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
                        combined.save(output_filename)
                        
                        print(f"[✓] Immagine combinata creata: {output_filename}")
                        
                        # Carica le variabili d'ambiente per GitHub
                        NOMEREPO = os.getenv("NOMEREPO", "").strip()
                        NOMEGITHUB = os.getenv("NOMEGITHUB", "").strip()
                        
                        # Se le variabili GitHub sono disponibili, restituisci l'URL raw di GitHub
                        if NOMEGITHUB and NOMEREPO:
                            github_raw_url = f"https://raw.githubusercontent.com/{NOMEGITHUB}/{NOMEREPO}/main/{output_filename}"
                            print(f"[✓] URL GitHub generato: {github_raw_url}")
                            return github_raw_url
                        else:
                            # Altrimenti restituisci il percorso locale
                            return output_filename
                        
                    except Exception as e:
                        print(f"[!] Errore nella creazione dell'immagine combinata: {e}")
                        # Se fallisce, restituisci solo il primo logo trovato
                        return logo1_url or logo2_url
                
                # Se non abbiamo trovato entrambi i loghi, restituisci quello che abbiamo
                return logo1_url or logo2_url
            if ':' in event_name:
                # Usa la parte prima dei ":" per la ricerca
                prefix_name = event_name.split(':', 1)[0].strip()
                print(f"[🔍] Tentativo ricerca logo con prefisso: {prefix_name}")
                
                # Prepara la query di ricerca con il prefisso
                search_query = urllib.parse.quote(f"{prefix_name} logo")
                
                # Utilizziamo l'API di Bing Image Search con parametri migliorati
                search_url = f"https://www.bing.com/images/search?q={search_query}&qft=+filterui:photo-transparent+filterui:aspect-square&form=IRFLTR"
                
                headers = { 
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Cache-Control": "max-age=0",
                    "Connection": "keep-alive"
                } 
                
                response = requests.get(search_url, headers=headers, timeout=10)
                
                if response.status_code == 200: 
                    # Metodo 1: Cerca pattern per murl (URL dell'immagine media)
                    patterns = [
                        r'murl&quot;:&quot;(https?://[^&]+)&quot;',
                        r'"murl":"(https?://[^"]+)"',
                        r'"contentUrl":"(https?://[^"]+\.(?:png|jpg|jpeg|svg))"',
                        r'<img[^>]+src="(https?://[^"]+\.(?:png|jpg|jpeg|svg))[^>]+class="mimg"',
                        r'<a[^>]+class="iusc"[^>]+m=\'{"[^"]*":"[^"]*","[^"]*":"(https?://[^"]+)"'
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, response.text)
                        if matches and len(matches) > 0:
                            # Prendi il primo risultato che sembra un logo (preferibilmente PNG o SVG)
                            for match in matches:
                                if '.png' in match.lower() or '.svg' in match.lower():
                                    print(f"[✓] Logo trovato con prefisso: {match}")
                                    return match
                            # Se non troviamo PNG o SVG, prendi il primo risultato
                            print(f"[✓] Logo trovato con prefisso: {matches[0]}")
                            return matches[0]
            
            # Se non riusciamo a identificare le squadre e il prefisso non ha dato risultati, procedi con la ricerca normale
            print(f"[🔍] Ricerca standard per: {clean_event_name}")
            
            
            # Se non riusciamo a identificare le squadre, procedi con la ricerca normale
            # Prepara la query di ricerca piÃÂ¹ specifica
            search_query = urllib.parse.quote(f"{clean_event_name} logo")
            
            # Utilizziamo l'API di Bing Image Search con parametri migliorati
            search_url = f"https://www.bing.com/images/search?q={search_query}&qft=+filterui:photo-transparent+filterui:aspect-square&form=IRFLTR"
            
            headers = { 
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "max-age=0",
                "Connection": "keep-alive"
            } 
            
            response = requests.get(search_url, headers=headers, timeout=10)
            
            if response.status_code == 200: 
                # Metodo 1: Cerca pattern per murl (URL dell'immagine media)
                patterns = [
                    r'murl&quot;:&quot;(https?://[^&]+)&quot;',
                    r'"murl":"(https?://[^"]+)"',
                    r'"contentUrl":"(https?://[^"]+\.(?:png|jpg|jpeg|svg))"',
                    r'<img[^>]+src="(https?://[^"]+\.(?:png|jpg|jpeg|svg))[^>]+class="mimg"',
                    r'<a[^>]+class="iusc"[^>]+m=\'{"[^"]*":"[^"]*","[^"]*":"(https?://[^"]+)"'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, response.text)
                    if matches and len(matches) > 0:
                        # Prendi il primo risultato che sembra un logo (preferibilmente PNG o SVG)
                        for match in matches:
                            if '.png' in match.lower() or '.svg' in match.lower():
                                return match
                        # Se non troviamo PNG o SVG, prendi il primo risultato
                        return matches[0]
                
                # Metodo alternativo: cerca JSON incorporato nella pagina
                json_match = re.search(r'var\s+IG\s*=\s*(\{.+?\});\s*', response.text)
                if json_match:
                    try:
                        # Estrai e analizza il JSON
                        json_str = json_match.group(1)
                        # Pulisci il JSON se necessario
                        json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+):', r'\1"\2":', json_str)
                        data = json.loads(json_str)
                        
                        # Cerca URL di immagini nel JSON
                        if 'images' in data and len(data['images']) > 0:
                            for img in data['images']:
                                if 'murl' in img:
                                    return img['murl']
                    except Exception as e:
                        print(f"[!] Errore nell'analisi JSON: {e}")
                
                print(f"[!] Nessun logo trovato per '{clean_event_name}' con i pattern standard")
                
                # Ultimo tentativo: cerca qualsiasi URL di immagine nella pagina
                any_img = re.search(r'(https?://[^"\']+\.(?:png|jpg|jpeg|svg|webp))', response.text)
                if any_img:
                    return any_img.group(1)
                    
        except Exception as e: 
            print(f"[!] Errore nella ricerca del logo per '{event_name}': {e}") 
        
        # Se non troviamo nulla, restituiamo None 
        return None

    def search_team_logo(team_name):
        """
        Funzione dedicata alla ricerca del logo di una singola squadra
        """
        try:
            # Prepara la query di ricerca specifica per la squadra
            search_query = urllib.parse.quote(f"{team_name} logo")
            
            # Utilizziamo l'API di Bing Image Search con parametri migliorati
            search_url = f"https://www.bing.com/images/search?q={search_query}&qft=+filterui:photo-transparent+filterui:aspect-square&form=IRFLTR"
            
            headers = { 
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "max-age=0",
                "Connection": "keep-alive"
            } 
            
            response = requests.get(search_url, headers=headers, timeout=10)
            
            if response.status_code == 200: 
                # Metodo 1: Cerca pattern per murl (URL dell'immagine media)
                patterns = [
                    r'murl&quot;:&quot;(https?://[^&]+)&quot;',
                    r'"murl":"(https?://[^"]+)"',
                    r'"contentUrl":"(https?://[^"]+\.(?:png|jpg|jpeg|svg))"',
                    r'<img[^>]+src="(https?://[^"]+\.(?:png|jpg|jpeg|svg))[^>]+class="mimg"',
                    r'<a[^>]+class="iusc"[^>]+m=\'{"[^"]*":"[^"]*","[^"]*":"(https?://[^"]+)"'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, response.text)
                    if matches and len(matches) > 0:
                        # Prendi il primo risultato che sembra un logo (preferibilmente PNG o SVG)
                        for match in matches:
                            if '.png' in match.lower() or '.svg' in match.lower():
                                return match
                        # Se non troviamo PNG o SVG, prendi il primo risultato
                        return matches[0]
                
                # Metodo alternativo: cerca JSON incorporato nella pagina
                json_match = re.search(r'var\s+IG\s*=\s*(\{.+?\});\s*', response.text)
                if json_match:
                    try:
                        # Estrai e analizza il JSON
                        json_str = json_match.group(1)
                        # Pulisci il JSON se necessario
                        json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+):', r'\1"\2":', json_str)
                        data = json.loads(json_str)
                        
                        # Cerca URL di immagini nel JSON
                        if 'images' in data and len(data['images']) > 0:
                            for img in data['images']:
                                if 'murl' in img:
                                    return img['murl']
                    except Exception as e:
                        print(f"[!] Errore nell'analisi JSON: {e}")
                
                print(f"[!] Nessun logo trovato per '{team_name}' con i pattern standard")
                
                # Ultimo tentativo: cerca qualsiasi URL di immagine nella pagina
                any_img = re.search(r'(https?://[^"\']+\.(?:png|jpg|jpeg|svg|webp))', response.text)
                if any_img:
                    return any_img.group(1)
                    
        except Exception as e: 
            print(f"[!] Errore nella ricerca del logo per '{team_name}': {e}") 
        
        # Se non troviamo nulla, restituiamo None 
        return None
     
    def get_stream_from_channel_id(channel_id): 
        # Prima cerca nei nuovi siti .m3u8
        m3u8_url = search_m3u8_in_sites(channel_id, is_tennis=False)
        if m3u8_url:
            return m3u8_url
        
        # Fallback al vecchio metodo .php se non trovato
        embed_url = f"{LINK_DADDY}/stream/stream-{channel_id}.php" 
        print(f"Fallback URL .php per il canale Daddylive {channel_id}.")
        return embed_url
     
    def clean_category_name(name): 
        # Rimuove tag html come </span> o simili 
        return re.sub(r'<[^>]+>', '', name).strip() 
     
    def extract_channels_from_json(path): 
        keywords = {"italy", "rai", "italia", "it"} 
        now = datetime.now()  # ora attuale completa (data+ora) 
        yesterday_date = (now - timedelta(days=1)).date() # Data di ieri
     
        with open(path, "r", encoding="utf-8") as f: 
            data = json.load(f) 
     
        categorized_channels = {} 
     
        for date_key, sections in data.items(): 
            date_part = date_key.split(" - ")[0] 
            try: 
                date_obj = parser.parse(date_part, fuzzy=True).date() 
            except Exception as e: 
                print(f"[!] Errore parsing data '{date_part}': {e}") 
                continue 
     
            # filtro solo per eventi del giorno corrente 
            if date_obj != now.date(): 
                continue 
     
            date_str = date_obj.strftime("%Y-%m-%d") 
     
            for category_raw, event_items in sections.items(): 
                category = clean_category_name(category_raw)
                # Salta la categoria TV Shows
                if category.lower() == "tv shows":
                    continue
                if category not in categorized_channels: 
                    categorized_channels[category] = [] 
     
                for item in event_items: 
                    time_str = item.get("time", "00:00") 
                    try: 
                        # Parse orario evento 
                        time_obj = datetime.strptime(time_str, "%H:%M") + timedelta(hours=2)  # correzione timezone? 
     
                        # crea datetime completo con data evento e orario evento 
                        event_datetime = datetime.combine(date_obj, time_obj.time()) 
     
                        # Controllo: includi solo se l'evento Ã¨ iniziato da meno di 2 ore 
                        if now - event_datetime > timedelta(hours=2): 
                            # Evento iniziato da piÃ¹ di 2 ore -> salto 
                            continue 
     
                        time_formatted = time_obj.strftime("%H:%M") 
                    except Exception: 
                        time_formatted = time_str 
     
                    event_title = item.get("event", "Evento") 
     
                    for ch in item.get("channels", []): 
                        channel_name = ch.get("channel_name", "") 
                        channel_id = ch.get("channel_id", "") 
     
                        words = set(re.findall(r'\b\w+\b', channel_name.lower())) 
                        if keywords.intersection(words): 
                            tvg_name = f"{event_title} ({time_formatted})" 
                            categorized_channels[category].append({ 
                                "tvg_name": tvg_name, 
                                "channel_name": channel_name, 
                                "channel_id": channel_id,
                                "event_title": event_title  # Aggiungiamo il titolo dell'evento per la ricerca del logo
                            }) 
     
        return categorized_channels 
     
    def generate_m3u_from_schedule(json_file, output_file): 
        categorized_channels = extract_channels_from_json(json_file) 

        with open(output_file, "w", encoding="utf-8") as f: 
            f.write("#EXTM3U\n") 

            # Controlla se ci sono eventi prima di aggiungere il canale DADDYLIVE
            has_events = any(channels for channels in categorized_channels.values())
            
            if has_events:
                # Aggiungi il canale iniziale/informativo solo se ci sono eventi
                f.write(f'#EXTINF:-1 tvg-name="DADDYLIVE" group-title="Eventi Live",DADDYLIVE\n')
                f.write("https://example.com.m3u8\n\n")
            else:
                print("[ℹ️] Nessun evento trovato, canale DADDYLIVE non aggiunto.")

            for category, channels in categorized_channels.items(): 
                if not channels: 
                    continue 
          
                for ch in channels: 
                    tvg_name = ch["tvg_name"] 
                    channel_id = ch["channel_id"] 
                    event_title = ch["event_title"]  # Otteniamo il titolo dell'evento
                    
                    # Cerca un logo per questo evento
                    # Rimuovi l'orario dal titolo dell'evento prima di cercare il logo
                    clean_event_title = re.sub(r'\s*\(\d{1,2}:\d{2}\)\s*$', '', event_title)
                    print(f"[🔍] Ricerca logo per: {clean_event_title}") 
                    logo_url = search_logo_for_event(clean_event_title)
                    logo_attribute = f' tvg-logo="{logo_url}"' if logo_url else ''
     
                    try: 
                        stream = get_stream_from_channel_id(channel_id) 
                        if stream: 
                            cleaned_event_id = clean_tvg_id(event_title) # Usa event_title per tvg-id
                            f.write(f'#EXTINF:-1 tvg-id="{cleaned_event_id}" tvg-name="{category} | {tvg_name}"{logo_attribute} group-title="Eventi Live",{category} | {tvg_name}\n')
                            # Aggiungi EXTHTTP headers per canali daddy (esclusi .php)
                            if ("newkso.ru" in stream or "premium" in stream) and not stream.endswith('.php'):
                                daddy_headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Referer": "https://forcedtoplay.xyz/", "Origin": "https://forcedtoplay.xyz"}
                                vlc_opt_lines = headers_to_extvlcopt(daddy_headers)
                                for line in vlc_opt_lines:
                                    f.write(f'{line}\n')
                            f.write(f'{stream}\n\n')
                            print(f"[✓] {tvg_name}" + (f" (logo trovato)" if logo_url else " (nessun logo trovato)")) 
                        else: 
                            print(f"[✗] {tvg_name} - Nessuno stream trovato") 
                    except Exception as e: 
                        print(f"[!] Errore su {tvg_name}: {e}") 
     
    if __name__ == "__main__": 
        generate_m3u_from_schedule(JSON_FILE, OUTPUT_FILE)

# Funzione per il quarto script (schedule_extractor.py)
def schedule_extractor():
    # Codice del quarto script qui
    # Aggiungi il codice del tuo script "schedule_extractor.py" in questa funzione.
    print("Eseguendo lo schedule_extractor.py...")
    # Il codice che avevi nello script "schedule_extractor.py" va qui, senza modifiche.
    from playwright.sync_api import sync_playwright
    import os
    import json
    from datetime import datetime
    import re
    from bs4 import BeautifulSoup
    from dotenv import load_dotenv
    
    # Carica le variabili d'ambiente dal file .env
    load_dotenv()
    
    LINK_DADDY = os.getenv("LINK_DADDY", "https://daddylive.dad").strip()
    
    def html_to_json(html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        result = {}
        
        date_rows = soup.find_all('tr', class_='date-row')
        if not date_rows:
            print("AVVISO: Nessuna riga di data trovata nel contenuto HTML!")
            return {}
    
        current_date = None
        current_category = None
    
        for row in soup.find_all('tr'):
            if 'date-row' in row.get('class', []):
                current_date = row.find('strong').text.strip()
                result[current_date] = {}
                current_category = None
    
            elif 'category-row' in row.get('class', []) and current_date:
                current_category = row.find('strong').text.strip() + "</span>"
                result[current_date][current_category] = []
    
            elif 'event-row' in row.get('class', []) and current_date and current_category:
                time_div = row.find('div', class_='event-time')
                info_div = row.find('div', class_='event-info')
    
                if not time_div or not info_div:
                    continue
    
                time_strong = time_div.find('strong')
                event_time = time_strong.text.strip() if time_strong else ""
                event_info = info_div.text.strip()
    
                event_data = {
                    "time": event_time,
                    "event": event_info,
                    "channels": []
                }
    
                # Cerca la riga dei canali successiva
                next_row = row.find_next_sibling('tr')
                if next_row and 'channel-row' in next_row.get('class', []):
                    channel_links = next_row.find_all('a', class_='channel-button-small')
                    for link in channel_links:
                        href = link.get('href', '')
                        channel_id_match = re.search(r'stream-(\d+)\.php', href)
                        if channel_id_match:
                            channel_id = channel_id_match.group(1)
                            channel_name = link.text.strip()
                            channel_name = re.sub(r'\s*\(CH-\d+\)$', '', channel_name)
    
                            event_data["channels"].append({
                                "channel_name": channel_name,
                                "channel_id": channel_id
                            })
    
                result[current_date][current_category].append(event_data)
    
        return result
    
    def modify_json_file(json_file_path):
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        current_month = datetime.now().strftime("%B")
    
        for date in list(data.keys()):
            match = re.match(r"(\w+\s\d+)(st|nd|rd|th)\s(\d{4})", date)
            if match:
                day_part = match.group(1)
                suffix = match.group(2)
                year_part = match.group(3)
                new_date = f"{day_part}{suffix} {current_month} {year_part}"
                data[new_date] = data.pop(date)
    
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        
        print(f"File JSON modificato e salvato in {json_file_path}")
    
    def extract_schedule_container():
        url = f"{LINK_DADDY}/"
    
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_output = os.path.join(script_dir, "daddyliveSchedule.json")
    
        print(f"Accesso alla pagina {url} per estrarre il main-schedule-container...")
    
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
    
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    print(f"Tentativo {attempt} di {max_attempts}...")
                    page.goto(url)
                    print("Attesa per il caricamento completo...")
                    page.wait_for_timeout(10000)  # 10 secondi
    
                    schedule_content = page.evaluate("""() => {
                        const container = document.getElementById('main-schedule-container');
                        return container ? container.outerHTML : '';
                    }""")
    
                    if not schedule_content:
                        print("AVVISO: main-schedule-container non trovato o vuoto!")
                        if attempt == max_attempts:
                            browser.close()
                            return False
                        else:
                            continue
    
                    print("Conversione HTML in formato JSON...")
                    json_data = html_to_json(schedule_content)
    
                    with open(json_output, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, indent=4)
    
                    print(f"Dati JSON salvati in {json_output}")
    
                    modify_json_file(json_output)
                    browser.close()
                    return True
    
                except Exception as e:
                    print(f"ERRORE nel tentativo {attempt}: {str(e)}")
                    if attempt == max_attempts:
                        print("Tutti i tentativi falliti!")
                        browser.close()
                        return False
                    else:
                        print(f"Riprovando... (tentativo {attempt + 1} di {max_attempts})")
    
            browser.close()
            return False
    
    if __name__ == "__main__":
        success = extract_schedule_container()
        if not success:
            exit(1)

def epg_eventi_generator_world():
    # Codice del quinto script qui
    # Aggiungi il codice del tuo script "epg_eventi_generator.py" in questa funzione.
    print("Eseguendo l'epg_eventi_generator_world.py...")
    # Il codice che avevi nello script "epg_eventi_generator.py" va qui, senza modifiche.
    import os
    import re
    import json
    from datetime import datetime, timedelta
    
    # Funzione di utilitÃÂ  per pulire il testo (rimuovere tag HTML span)
    def clean_text(text):
        return re.sub(r'</?span.*?>', '', str(text))
    
    # Funzione di utilitÃÂ  per pulire il Channel ID (rimuovere spazi e caratteri speciali)
    def clean_channel_id(text):
        """Rimuove caratteri speciali e spazi dal channel ID lasciando tutto attaccato"""
        # Rimuovi prima i tag HTML
        text = clean_text(text)
        # Rimuovi tutti gli spazi
        text = re.sub(r'\s+', '', text)
        # Mantieni solo caratteri alfanumerici (rimuovi tutto il resto)
        text = re.sub(r'[^a-zA-Z0-9]', '', text)
        # Assicurati che non sia vuoto
        if not text:
            text = "unknownchannel"
        return text
    
    # --- SCRIPT 5: epg_eventi_xml_generator (genera eventi.xml) ---
    def load_json_for_epg(json_file_path):
        """Carica e filtra i dati JSON per la generazione EPG"""
        if not os.path.exists(json_file_path):
            print(f"[!] File JSON non trovato per EPG: {json_file_path}")
            return {}
        
        try:
            with open(json_file_path, "r", encoding="utf-8") as file:
                json_data = json.load(file)
        except json.JSONDecodeError as e:
            print(f"[!] Errore nel parsing del file JSON: {e}")
            return {}
        except Exception as e:
            print(f"[!] Errore nell'apertura del file JSON: {e}")
            return {}
            
        # Lista delle parole chiave per canali italiani
        keywords = ['italy', 'rai', 'italia', 'it', 'uk', 'tnt', 'usa', 'tennis channel', 'tennis stream', 'la']
        
        filtered_data = {}
        for date, categories in json_data.items():
            filtered_categories = {}
            for category, events in categories.items():
                filtered_events = []
                for event_info in events: # Original loop for events
                    # Filtra gli eventi in base all'orario specificato (00:00 - 04:00)
                    event_time_str = event_info.get("time", "00:00") # Prende l'orario dell'evento, default a "00:00" se mancante
                    try:
                        event_actual_time = datetime.strptime(event_time_str, "%H:%M").time()
                        
                        # Definisci gli orari limite per il filtro
                        filter_start_time = datetime.strptime("00:00", "%H:%M").time()
                        filter_end_time = datetime.strptime("04:00", "%H:%M").time()

                        # Escludi eventi se l'orario ÃÂ¨ compreso tra 00:00 e 04:00 inclusi
                        if filter_start_time <= event_actual_time <= filter_end_time:
                            continue # Salta questo evento e passa al successivo
                    except ValueError:
                        print(f"[!] Orario evento non valido '{event_time_str}' per l'evento '{event_info.get('event', 'Sconosciuto')}' durante il caricamento JSON. Evento saltato.")
                        continue

                    filtered_channels = []
                    # Utilizza .get("channels", []) per gestire casi in cui "channels" potrebbe mancare
                    for channel in event_info.get("channels", []): 
                        channel_name = clean_text(channel.get("channel_name", "")) # Usa .get per sicurezza
                        
                        # Filtra per canali italiani - solo parole intere
                        channel_words = channel_name.lower().split()
                        if any(word in keywords for word in channel_words):
                            filtered_channels.append(channel)
                    
                    if filtered_channels:
                        # Assicura che event_info sia un dizionario prima dello unpacking
                        if isinstance(event_info, dict):
                            filtered_events.append({**event_info, "channels": filtered_channels})
                        else:
                            # Logga un avviso se il formato dell'evento non ÃÂ¨ quello atteso
                            print(f"[!] Formato evento non valido durante il filtraggio per EPG: {event_info}")
                
                if filtered_events:
                    filtered_categories[category] = filtered_events
            
            if filtered_categories:
                filtered_data[date] = filtered_categories
        
        return filtered_data
    
    def generate_epg_xml(json_data):
        """Genera il contenuto XML EPG dai dati JSON filtrati"""
        epg_content = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
        
        italian_offset = timedelta(hours=2)
        italian_offset_str = "+0200" 
    
        current_datetime_utc = datetime.utcnow()
        current_datetime_local = current_datetime_utc + italian_offset
    
        # Tiene traccia degli ID dei canali per cui ÃÂ¨ giÃÂ  stato scritto il tag <channel>
        channel_ids_processed_for_channel_tag = set() 
    
        for date_key, categories in json_data.items():
            # Dizionario per memorizzare l'ora di fine dell'ultimo evento per ciascun canale IN QUESTA DATA SPECIFICA
            # Viene resettato per ogni nuova data.
            last_event_end_time_per_channel_on_date = {}
    
            try:
                date_str_from_key = date_key.split(' - ')[0]
                date_str_cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str_from_key)
                event_date_part = datetime.strptime(date_str_cleaned, "%A %d %B %Y").date()
            except ValueError as e:
                print(f"[!] Errore nel parsing della data EPG: '{date_str_from_key}'. Errore: {e}")
                continue
            except IndexError as e:
                print(f"[!] Formato data non valido: '{date_key}'. Errore: {e}")
                continue
    
            if event_date_part < current_datetime_local.date():
                continue
    
            for category_name, events_list in categories.items():
                # Ordina gli eventi per orario di inizio (UTC) per garantire la corretta logica "evento precedente"
                try:
                    sorted_events_list = sorted(
                        events_list,
                        key=lambda x: datetime.strptime(x.get("time", "00:00"), "%H:%M").time()
                    )
                except Exception as e_sort:
                    print(f"[!] Attenzione: Impossibile ordinare gli eventi per la categoria '{category_name}' nella data '{date_key}'. Si procede senza ordinamento. Errore: {e_sort}")
                    sorted_events_list = events_list
    
                for event_info in sorted_events_list:
                    time_str_utc = event_info.get("time", "00:00")
                    event_name_original = clean_text(event_info.get("event", "Evento Sconosciuto"))
                    event_name = event_name_original.replace('&', 'and')
                    event_desc = event_info.get("description", f"Trasmesso in diretta.")
    
                    # USA EVENT NAME COME CHANNEL ID - PULITO DA CARATTERI SPECIALI E SPAZI
                    channel_id = clean_channel_id(event_name)
    
                    try:
                        event_time_utc_obj = datetime.strptime(time_str_utc, "%H:%M").time()
                        event_datetime_utc = datetime.combine(event_date_part, event_time_utc_obj)
                        event_datetime_local = event_datetime_utc + italian_offset
                    except ValueError as e:
                        print(f"[!] Errore parsing orario UTC '{time_str_utc}' per EPG evento '{event_name}'. Errore: {e}")
                        continue
                    
                    if event_datetime_local < (current_datetime_local - timedelta(hours=2)):
                        continue
    
                    # Verifica che ci siano canali disponibili
                    channels_list = event_info.get("channels", [])
                    if not channels_list:
                        print(f"[!] Nessun canale disponibile per l'evento '{event_name}'")
                        continue
    
                    for channel_data in channels_list:
                        if not isinstance(channel_data, dict):
                            print(f"[!] Formato canale non valido per l'evento '{event_name}': {channel_data}")
                            continue
    
                        channel_name_cleaned = clean_text(channel_data.get("channel_name", "Canale Sconosciuto"))
    
                        # Crea tag <channel> se non giÃÂ  processato
                        if channel_id not in channel_ids_processed_for_channel_tag:
                            epg_content += f'  <channel id="{channel_id}">\n'
                            epg_content += f'    <display-name>{event_name}</display-name>\n'
                            epg_content += f'  </channel>\n'
                            channel_ids_processed_for_channel_tag.add(channel_id)
                        
                        # --- LOGICA ANNUNCIO MODIFICATA ---
                        announcement_stop_local = event_datetime_local # L'annuncio termina quando inizia l'evento corrente
    
                        # Determina l'inizio dell'annuncio
                        if channel_id in last_event_end_time_per_channel_on_date:
                            # C'ÃÂ¨ stato un evento precedente su questo canale in questa data
                            previous_event_end_time_local = last_event_end_time_per_channel_on_date[channel_id]
                            
                            # Assicurati che l'evento precedente termini prima che inizi quello corrente
                            if previous_event_end_time_local < event_datetime_local:
                                announcement_start_local = previous_event_end_time_local
                            else:
                                # Sovrapposizione o stesso orario di inizio, problematico.
                                # Fallback a 00:00 del giorno, o potresti saltare l'annuncio.
                                print(f"[!] Attenzione: L'evento '{event_name}' inizia prima o contemporaneamente alla fine dell'evento precedente su questo canale. Fallback per l'inizio dell'annuncio.")
                                announcement_start_local = datetime.combine(event_datetime_local.date(), datetime.min.time())
                        else:
                            # Primo evento per questo canale in questa data
                            announcement_start_local = datetime.combine(event_datetime_local.date(), datetime.min.time()) # 00:00 ora italiana
    
                        # Assicura che l'inizio dell'annuncio sia prima della fine
                        if announcement_start_local < announcement_stop_local:
                            announcement_title = f'Inizia alle {event_datetime_local.strftime("%H:%M")}.' # Orario italiano
                            
                            epg_content += f'  <programme start="{announcement_start_local.strftime("%Y%m%d%H%M%S")} {italian_offset_str}" stop="{announcement_stop_local.strftime("%Y%m%d%H%M%S")} {italian_offset_str}" channel="{channel_id}">\n'
                            epg_content += f'    <title lang="it">{announcement_title}</title>\n'
                            epg_content += f'    <desc lang="it">{event_name}.</desc>\n' 
                            epg_content += f'    <category lang="it">Annuncio</category>\n'
                            epg_content += f'  </programme>\n'
                        elif announcement_start_local == announcement_stop_local:
                            print(f"[INFO] Annuncio di durata zero saltato per l'evento '{event_name}' sul canale '{channel_id}'.")
                        else: # announcement_start_local > announcement_stop_local
                            print(f"[!] Attenzione: L'orario di inizio calcolato per l'annuncio è successivo all'orario di fine per l'evento '{event_name}' sul canale '{channel_id}'. Annuncio saltato.")
    
                        # --- EVENTO PRINCIPALE ---
                        main_event_start_local = event_datetime_local 
                        main_event_stop_local = event_datetime_local + timedelta(hours=2) # Durata fissa 2 ore
                        
                        epg_content += f'  <programme start="{main_event_start_local.strftime("%Y%m%d%H%M%S")} {italian_offset_str}" stop="{main_event_stop_local.strftime("%Y%m%d%H%M%S")} {italian_offset_str}" channel="{channel_id}">\n'
                        epg_content += f'    <title lang="it">{event_desc}</title>\n'
                        epg_content += f'    <desc lang="it">{event_name}</desc>\n'
                        epg_content += f'    <category lang="it">{clean_text(category_name)}</category>\n'
                        epg_content += f'  </programme>\n'
    
                        # Aggiorna l'orario di fine dell'ultimo evento per questo canale in questa data
                        last_event_end_time_per_channel_on_date[channel_id] = main_event_stop_local
        
        epg_content += "</tv>\n"
        return epg_content
    
    def save_epg_xml(epg_content, output_file_path):
        """Salva il contenuto EPG XML su file"""
        try:
            with open(output_file_path, "w", encoding="utf-8") as file:
                file.write(epg_content)
            print(f"[✓] File EPG XML salvato con successo: {output_file_path}")
            return True
        except Exception as e:
            print(f"[!] Errore nel salvataggio del file EPG XML: {e}")
            return False
    
    def main_epg_generator(json_file_path, output_file_path="eventi.xml"):
        """Funzione principale per generare l'EPG XML"""
        print(f"[INFO] Inizio generazione EPG XML da: {json_file_path}")
        
        # Carica e filtra i dati JSON
        json_data = load_json_for_epg(json_file_path)
        
        if not json_data:
            print("[!] Nessun dato valido trovato nel file JSON.")
            return False
        
        print(f"[INFO] Dati caricati per {len(json_data)} date")
        
        # Genera il contenuto XML EPG
        epg_content = generate_epg_xml(json_data)
        
        # Salva il file XML
        success = save_epg_xml(epg_content, output_file_path)
        
        if success:
            print(f"[✓] Generazione EPG XML completata con successo!")
            return True
        else:
            print(f"[!] Errore durante la generazione EPG XML.")
            return False
    
    # Esempio di utilizzo
    if __name__ == "__main__":
        # Percorso del file JSON di input
        input_json_path = "daddyliveSchedule.json"  # Modifica con il tuo percorso
        
        # Percorso del file XML di output
        output_xml_path = "eventi.xml"
        
        # Esegui la generazione EPG
        main_epg_generator(input_json_path, output_xml_path)

# Funzione per il quinto script (epg_eventi_generator.py)
def epg_eventi_generator():
    # Codice del quinto script qui
    # Aggiungi il codice del tuo script "epg_eventi_generator.py" in questa funzione.
    print("Eseguendo l'epg_eventi_generator.py...")
    # Il codice che avevi nello script "epg_eventi_generator.py" va qui, senza modifiche.
    import os
    import re
    import json
    from datetime import datetime, timedelta
    
    # Funzione di utilitÃÂ  per pulire il testo (rimuovere tag HTML span)
    def clean_text(text):
        return re.sub(r'</?span.*?>', '', str(text))
    
    # Funzione di utilitÃÂ  per pulire il Channel ID (rimuovere spazi e caratteri speciali)
    def clean_channel_id(text):
        """Rimuove caratteri speciali e spazi dal channel ID lasciando tutto attaccato"""
        # Rimuovi prima i tag HTML
        text = clean_text(text)
        # Rimuovi tutti gli spazi
        text = re.sub(r'\s+', '', text)
        # Mantieni solo caratteri alfanumerici (rimuovi tutto il resto)
        text = re.sub(r'[^a-zA-Z0-9]', '', text)
        # Assicurati che non sia vuoto
        if not text:
            text = "unknownchannel"
        return text
    
    # --- SCRIPT 5: epg_eventi_xml_generator (genera eventi.xml) ---
    def load_json_for_epg(json_file_path):
        """Carica e filtra i dati JSON per la generazione EPG"""
        if not os.path.exists(json_file_path):
            print(f"[!] File JSON non trovato per EPG: {json_file_path}")
            return {}
        
        try:
            with open(json_file_path, "r", encoding="utf-8") as file:
                json_data = json.load(file)
        except json.JSONDecodeError as e:
            print(f"[!] Errore nel parsing del file JSON: {e}")
            return {}
        except Exception as e:
            print(f"[!] Errore nell'apertura del file JSON: {e}")
            return {}
            
        # Lista delle parole chiave per canali italiani
        keywords = ['italy', 'rai', 'italia', 'it']
        
        filtered_data = {}
        for date, categories in json_data.items():
            filtered_categories = {}
            for category, events in categories.items():
                filtered_events = []
                for event_info in events:
                    filtered_channels = []
                    # Utilizza .get("channels", []) per gestire casi in cui "channels" potrebbe mancare
                    for channel in event_info.get("channels", []): 
                        channel_name = clean_text(channel.get("channel_name", "")) # Usa .get per sicurezza
                        
                        # Filtra per canali italiani - solo parole intere
                        channel_words = channel_name.lower().split()
                        if any(word in keywords for word in channel_words):
                            filtered_channels.append(channel)
                    
                    if filtered_channels:
                        # Assicura che event_info sia un dizionario prima dello unpacking
                        if isinstance(event_info, dict):
                            filtered_events.append({**event_info, "channels": filtered_channels})
                        else:
                            # Logga un avviso se il formato dell'evento non ÃÂ¨ quello atteso
                            print(f"[!] Formato evento non valido durante il filtraggio per EPG: {event_info}")
                
                if filtered_events:
                    filtered_categories[category] = filtered_events
            
            if filtered_categories:
                filtered_data[date] = filtered_categories
        
        return filtered_data
    
    def generate_epg_xml(json_data):
        """Genera il contenuto XML EPG dai dati JSON filtrati"""
        epg_content = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
        
        italian_offset = timedelta(hours=2)
        italian_offset_str = "+0200" 
    
        current_datetime_utc = datetime.utcnow()
        current_datetime_local = current_datetime_utc + italian_offset
    
        # Tiene traccia degli ID dei canali per cui ÃÂ¨ giÃÂ  stato scritto il tag <channel>
        channel_ids_processed_for_channel_tag = set() 
    
        for date_key, categories in json_data.items():
            # Dizionario per memorizzare l'ora di fine dell'ultimo evento per ciascun canale IN QUESTA DATA SPECIFICA
            # Viene resettato per ogni nuova data.
            last_event_end_time_per_channel_on_date = {}
    
            try:
                date_str_from_key = date_key.split(' - ')[0]
                date_str_cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str_from_key)
                event_date_part = datetime.strptime(date_str_cleaned, "%A %d %B %Y").date()
            except ValueError as e:
                print(f"[!] Errore nel parsing della data EPG: '{date_str_from_key}'. Errore: {e}")
                continue
            except IndexError as e:
                print(f"[!] Formato data non valido: '{date_key}'. Errore: {e}")
                continue
    
            if event_date_part < current_datetime_local.date():
                continue
    
            for category_name, events_list in categories.items():
                # Ordina gli eventi per orario di inizio (UTC) per garantire la corretta logica "evento precedente"
                try:
                    sorted_events_list = sorted(
                        events_list,
                        key=lambda x: datetime.strptime(x.get("time", "00:00"), "%H:%M").time()
                    )
                except Exception as e_sort:
                    print(f"[!] Attenzione: Impossibile ordinare gli eventi per la categoria '{category_name}' nella data '{date_key}'. Si procede senza ordinamento. Errore: {e_sort}")
                    sorted_events_list = events_list
    
                for event_info in sorted_events_list:
                    time_str_utc = event_info.get("time", "00:00")
                    event_name = clean_text(event_info.get("event", "Evento Sconosciuto"))
                    event_desc = event_info.get("description", f"Trasmesso in diretta.")
    
                    # USA EVENT NAME COME CHANNEL ID - PULITO DA CARATTERI SPECIALI E SPAZI
                    channel_id = clean_channel_id(event_name)
    
                    try:
                        event_time_utc_obj = datetime.strptime(time_str_utc, "%H:%M").time()
                        event_datetime_utc = datetime.combine(event_date_part, event_time_utc_obj)
                        event_datetime_local = event_datetime_utc + italian_offset
                    except ValueError as e:
                        print(f"[!] Errore parsing orario UTC '{time_str_utc}' per EPG evento '{event_name}'. Errore: {e}")
                        continue
                    
                    if event_datetime_local < (current_datetime_local - timedelta(hours=2)):
                        continue
    
                    # Verifica che ci siano canali disponibili
                    channels_list = event_info.get("channels", [])
                    if not channels_list:
                        print(f"[!] Nessun canale disponibile per l'evento '{event_name}'")
                        continue
    
                    for channel_data in channels_list:
                        if not isinstance(channel_data, dict):
                            print(f"[!] Formato canale non valido per l'evento '{event_name}': {channel_data}")
                            continue
    
                        channel_name_cleaned = clean_text(channel_data.get("channel_name", "Canale Sconosciuto"))
    
                        # Crea tag <channel> se non giÃÂ  processato
                        if channel_id not in channel_ids_processed_for_channel_tag:
                            epg_content += f'  <channel id="{channel_id}">\n'
                            epg_content += f'    <display-name>{event_name}</display-name>\n'
                            epg_content += f'  </channel>\n'
                            channel_ids_processed_for_channel_tag.add(channel_id)
                        
                        # --- LOGICA ANNUNCIO MODIFICATA ---
                        announcement_stop_local = event_datetime_local # L'annuncio termina quando inizia l'evento corrente
    
                        # Determina l'inizio dell'annuncio
                        if channel_id in last_event_end_time_per_channel_on_date:
                            # C'ÃÂ¨ stato un evento precedente su questo canale in questa data
                            previous_event_end_time_local = last_event_end_time_per_channel_on_date[channel_id]
                            
                            # Assicurati che l'evento precedente termini prima che inizi quello corrente
                            if previous_event_end_time_local < event_datetime_local:
                                announcement_start_local = previous_event_end_time_local
                            else:
                                # Sovrapposizione o stesso orario di inizio, problematico.
                                # Fallback a 00:00 del giorno, o potresti saltare l'annuncio.
                                print(f"[!] Attenzione: L'evento '{event_name}' inizia prima o contemporaneamente alla fine dell'evento precedente su questo canale. Fallback per l'inizio dell'annuncio.")
                                announcement_start_local = datetime.combine(event_datetime_local.date(), datetime.min.time())
                        else:
                            # Primo evento per questo canale in questa data
                            announcement_start_local = datetime.combine(event_datetime_local.date(), datetime.min.time()) # 00:00 ora italiana
    
                        # Assicura che l'inizio dell'annuncio sia prima della fine
                        if announcement_start_local < announcement_stop_local:
                            announcement_title = f'Inizia alle {event_datetime_local.strftime("%H:%M")}.' # Orario italiano
                            
                            epg_content += f'  <programme start="{announcement_start_local.strftime("%Y%m%d%H%M%S")} {italian_offset_str}" stop="{announcement_stop_local.strftime("%Y%m%d%H%M%S")} {italian_offset_str}" channel="{channel_id}">\n'
                            epg_content += f'    <title lang="it">{announcement_title}</title>\n'
                            epg_content += f'    <desc lang="it">{event_name}.</desc>\n' 
                            epg_content += f'    <category lang="it">Annuncio</category>\n'
                            epg_content += f'  </programme>\n'
                        elif announcement_start_local == announcement_stop_local:
                            print(f"[INFO] Annuncio di durata zero saltato per l'evento '{event_name}' sul canale '{channel_id}'.")
                        else: # announcement_start_local > announcement_stop_local
                            print(f"[!] Attenzione: L'orario di inizio calcolato per l'annuncio è successivo all'orario di fine per l'evento '{event_name}' sul canale '{channel_id}'. Annuncio saltato.")
    
                        # --- EVENTO PRINCIPALE ---
                        main_event_start_local = event_datetime_local 
                        main_event_stop_local = event_datetime_local + timedelta(hours=2) # Durata fissa 2 ore
                        
                        epg_content += f'  <programme start="{main_event_start_local.strftime("%Y%m%d%H%M%S")} {italian_offset_str}" stop="{main_event_stop_local.strftime("%Y%m%d%H%M%S")} {italian_offset_str}" channel="{channel_id}">\n'
                        epg_content += f'    <title lang="it">{event_desc}</title>\n'
                        epg_content += f'    <desc lang="it">{event_name}</desc>\n'
                        epg_content += f'    <category lang="it">{clean_text(category_name)}</category>\n'
                        epg_content += f'  </programme>\n'
    
                        # Aggiorna l'orario di fine dell'ultimo evento per questo canale in questa data
                        last_event_end_time_per_channel_on_date[channel_id] = main_event_stop_local
        
        epg_content += "</tv>\n"
        return epg_content
    
    def save_epg_xml(epg_content, output_file_path):
        """Salva il contenuto EPG XML su file"""
        try:
            with open(output_file_path, "w", encoding="utf-8") as file:
                file.write(epg_content)
            print(f"[✓] File EPG XML salvato con successo: {output_file_path}")
            return True
        except Exception as e:
            print(f"[!] Errore nel salvataggio del file EPG XML: {e}")
            return False
    
    def main_epg_generator(json_file_path, output_file_path="eventi.xml"):
        """Funzione principale per generare l'EPG XML"""
        print(f"[INFO] Inizio generazione EPG XML da: {json_file_path}")
        
        # Carica e filtra i dati JSON
        json_data = load_json_for_epg(json_file_path)
        
        if not json_data:
            print("[!] Nessun dato valido trovato nel file JSON.")
            return False
        
        print(f"[INFO] Dati caricati per {len(json_data)} date")
        
        # Genera il contenuto XML EPG
        epg_content = generate_epg_xml(json_data)
        
        # Salva il file XML
        success = save_epg_xml(epg_content, output_file_path)
        
        if success:
            print(f"[✓] Generazione EPG XML completata con successo!")
            return True
        else:
            print(f"[!] Errore durante la generazione EPG XML.")
            return False
    
    # Esempio di utilizzo
    if __name__ == "__main__":
        # Percorso del file JSON di input
        input_json_path = "daddyliveSchedule.json"  # Modifica con il tuo percorso
        
        # Percorso del file XML di output
        output_xml_path = "eventi.xml"
        
        # Esegui la generazione EPG
        main_epg_generator(input_json_path, output_xml_path)
        
# Funzione per il sesto script (italy_channels.py)
def italy_channels():
    print("Eseguendo il italy_channels.py...")

    import requests
    import re
    import os
    import xml.etree.ElementTree as ET
    from dotenv import load_dotenv
    import urllib.parse # Aggiunto per urlencode e quote
    import json         # Aggiunto per json.JSONDecodeError
    from bs4 import BeautifulSoup # Aggiunto per il parsing HTML

    # Carica le variabili d'ambiente dal file .env
    load_dotenv()

    LINK_SS = os.getenv("LINK_SKYSTREAMING", "https://skystreaming.yoga").strip()
    LINK_DADDY = os.getenv("LINK_DADDY", "https://daddylive.dad").strip()
    EPG_FILE = "epg.xml"
    OUTPUT_FILE = "channels_italy.m3u8"
    DEFAULT_TVG_ICON = ""
    HTTP_TIMEOUT = 20  # Timeout per le richieste HTTP in secondi

    # Crea una sessione requests per riutilizzare connessioni e gestire cookies
    session = requests.Session()

    BASE_URLS = [
        "https://vavoo.to"
    ]

    CATEGORY_KEYWORDS = {
        "Rai": ["rai"],
        "Mediaset": ["twenty seven", "twentyseven", "mediaset", "italia 1", "italia 2", "canale 5"],
        "Sport": ["inter", "milan", "lazio", "calcio", "tennis", "sport", "super tennis", "supertennis", "dazn", "eurosport", "sky sport", "rai sport"],
        "Film & Serie TV": ["crime", "primafila", "cinema", "movie", "film", "serie", "hbo", "fox", "rakuten", "atlantic"],
        "News": ["news", "tg", "rai news", "sky tg", "tgcom"],
        "Bambini": ["frisbee", "super!", "fresbee", "k2", "cartoon", "boing", "nick", "disney", "baby", "rai yoyo"],
        "Documentari": ["documentaries", "discovery", "geo", "history", "nat geo", "nature", "arte", "documentary"],
        "Musica": ["deejay", "rds", "hits", "rtl", "mtv", "vh1", "radio", "music", "kiss", "kisskiss", "m2o", "fm"],
        "Altro": ["focus", "real time"]
    }

    def fetch_epg(epg_file):
        try:
            tree = ET.parse(epg_file)
            return tree.getroot()
        except Exception as e:
            print(f"Errore durante la lettura del file EPG: {e}")
            return None

    def fetch_logos():
        # Contenuto di logos.txt integrato come dizionario Python
        logos_data = {
            "sky uno": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-uno-it.png",
            "rai 1": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-1-it.png",
            "rai 2": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-2-it.png",
            "rai 3": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-3-it.png",
            "eurosport 1": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/spain/eurosport-1-es.png",
            "eurosport 2": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/spain/eurosport-2-es.png",
            "italia 1": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/italia1-it.png",
            "la 7": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/la7-it.png",
            "la 7 d": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/la7d-it.png",
            "rai sport+": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-sport-it.png",
            "rai sport [live during events only]": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-sport-it.png",
            "rai premium": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-premium-it.png",
            "sky sport golf": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-golf-it.png",
            "sky sport moto gp": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-motogp-it.png",
            "sky sport tennis": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-tennis-it.png",
            "sky sport f1": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-f1-it.png",
            "sky sport football": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-football-it.png",
            "sky sport football [live during events only]": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-football-it.png",
            "sky sport uno": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-uno-it.png",
            "sky sport arena": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-arena-it.png",
            "sky cinema collection": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-collection-it.png",
            "sky cinema uno": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-uno-it.png",
            "sky cinema action": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-action-it.png",
            "sky cinema action (backup)": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-action-it.png",
            "sky cinema comedy": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-comedy-it.png",
            "sky cinema uno +24": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-uno-plus24-it.png",
            "sky cinema romance": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-romance-it.png",
            "sky cinema family": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-family-it.png",
            "sky cinema due +24": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-due-plus24-it.png",
            "sky cinema drama": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-drama-it.png",
            "sky cinema suspense": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-suspense-it.png",
            "sky sport 24": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-24-it.png",
            "sky sport 24 [live during events only]": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-24-it.png",
            "sky sport calcio": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-calcio-it.png",
            "sky calcio 1": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/germany/sky-select-1-alt-de.png",
            "sky calcio 2": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/germany/sky-select-2-alt-de.png",
            "sky calcio 3": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/germany/sky-select-3-alt-de.png",
            "sky calcio 4": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/germany/sky-select-4-alt-de.png",
            "sky calcio 5": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/germany/sky-select-5-alt-de.png",
            "sky calcio 6": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/germany/sky-select-6-alt-de.png",
            "sky calcio 7": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/germany/sky-select-7-alt-de.png",
            "sky serie": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-serie-it.png",
            "crime+investigation": "https://upload.wikimedia.org/wikipedia/commons/4/4d/Crime_%2B_Investigation_Logo_10.2019.svg",
            "20 mediaset": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/20-it.png",
            "mediaset 20": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/20-it.png",
            "27 twenty seven": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/Twentyseven_logo.svg/260px-Twentyseven_logo.svg.png",
            "27 twentyseven": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/Twentyseven_logo.svg/260px-Twentyseven_logo.svg.png",
            "canale 5": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/canale5-it.png",
            "cine 34 mediaset": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/cine34-it.png",
            "cine 34": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/cine34-it.png",
            "discovery focus": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/focus-it.png",
            "focus": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/focus-it.png",
            "italia 2": "https://upload.wikimedia.org/wikipedia/it/thumb/c/c5/Logo_Italia2.svg/520px-Logo_Italia2.svg.png",
            "mediaset italia 2": "https://upload.wikimedia.org/wikipedia/it/thumb/c/c5/Logo_Italia2.svg/520px-Logo_Italia2.svg.png",
            "mediaset italia": "https://www.italiasera.it/wp-content/uploads/2019/06/Mediaset-640x366.png",
            "mediaset extra": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/mediaset-extra-it.png",
            "mediaset 1": "https://play-lh.googleusercontent.com/2-Cl0plYUCxk8bnbeavm4ZOJ_S4Xuwmql_N3_E4OJyf7XK_YUvdNOWgzn8KD-Bur8w0",
            "mediaset infinity+ 1": "https://play-lh.googleusercontent.com/2-Cl0plYUCxk8bnbeavm4ZOJ_S4Xuwmql_N3_E4OJyf7XK_YUvdNOWgzn8KD-Bur8w0",
            "mediaset infinity+ 2": "https://play-lh.googleusercontent.com/2-Cl0plYUCxk8bnbeavm4ZOJ_S4Xuwmql_N3_E4OJyf7XK_YUvdNOWgzn8KD-Bur8w0",
            "mediaset infinity+ 5": "https://play-lh.googleusercontent.com/2-Cl0plYUCxk8bnbeavm4ZOJ_S4Xuwmql_N3_E4OJyf7XK_YUvdNOWgzn8KD-Bur8w0",
            "mediaset iris": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/iris-it.png",
            "iris": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/iris-it.png",
            "rete 4": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rete4-it.png",
            "sport italia (backup)": "https://play-lh.googleusercontent.com/0IcWROAOpuEcMf2qbOBNQYhrAPUuSmw-zv0f867kUxKSwSTD_chyCDuBP2PScIyWI9k",
            "sport italia": "https://play-lh.googleusercontent.com/0IcWROAOpuEcMf2qbOBNQYhrAPUuSmw-zv0f867kUxKSwSTD_chyCDuBP2PScIyWI9k",
            "sportitalia plus": "https://www.capitaladv.eu/wp-content/uploads/2020/07/LOGO-SPORTITALIA-PLUS-HD_2-1.png",
            "sport italia solo calcio [live during events only]": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/SI_Solo_Calcio_logo_%282019%29.svg/1200px-SI_Solo_Calcio_logo_%282019%29.svg.png",
            "sportitalia solocalcio": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/SI_Solo_Calcio_logo_%282019%29.svg/1200px-SI_Solo_Calcio_logo_%282019%29.svg.png",
            "dazn 1": "https://upload.wikimedia.org/wikipedia/commons/d/d6/Dazn-logo.png",
            "dazn2": "https://upload.wikimedia.org/wikipedia/commons/d/d6/Dazn-logo.png",
            "motortrend": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/Motor_Trend_logo.svg/2560px-Motor_Trend_logo.svg.png",
            "sky sport max": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-max-it.png",
            "sky sport nba": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-nba-it.png",
            "sky sport serie a": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-serie-a-it.png",
            "sky sports f1": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-f1-it.png",
            "sky super tennis": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-sport-tennis-it.png",
            "tennis channel": "https://images.tennis.com/image/upload/t_16-9_768/v1620828532/tenniscom-prd/assets/Fallback/Tennis_Fallback_v6_f5tjzv.jpg",
            "super tennis": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/super-tennis-it.png",
            "tv 8": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/tv8-it.png",
            "sky primafila 1": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 2": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 3": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 4": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 5": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 6": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 7": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 8": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 9": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 10": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 11": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 12": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 13": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 14": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 15": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 16": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 17": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky primafila 18": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-primafila-it.png",
            "sky cinema due": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-cinema-due-it.png",
            "sky atlantic": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-atlantic-it.png",
            "nat geo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/national-geographic-it.png",
            "discovery nove": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/nove-it.png",
            "discovery channel": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/discovery-channel-it.png",
            "real time": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/real-time-it.png",
            "rai 5": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-5-it.png",
            "rai gulp": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-gulp-it.png",
            "rai italia": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Rai_Italia_-_Logo_2017.svg/1024px-Rai_Italia_-_Logo_2017.svg.png",
            "rai movie": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-movie-it.png",
            "rai news 24": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-news-24-it.png",
            "rai scuola": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-scuola-it.png",
            "rai storia": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-storia-it.png",
            "rai yoyo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-yoyo-it.png",
            "rai 4": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/rai-4-it.png",
            "rai 4k": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/Rai_4K_-_Logo_2017.svg/1200px-Rai_4K_-_Logo_2017.svg.png",
            "hgtv": "https://d204lf4nuskf6u.cloudfront.net/italy-images/c2cbeaabb81be73e81c7f4291cf798e3.png?k=2nWZhtOSUQdq2s2ItEDH5%2BQEPdq1khUY8YJSK0%2BNV90dhkyaUQQ82V1zGPD7O5%2BS",
            "top crime": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/top-crime-it.png",
            "cielo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/cielo-it.png",
            "dmax": "https://cdn.cookielaw.org/logos/50417659-aa29-4f7f-b59d-f6e887deed53/a32be519-de41-40f4-abed-d2934ba6751b/9a44af24-5ca6-4098-aa95-594755bd7b2d/dmax_logo.png",
            "food network": "https://upload.wikimedia.org/wikipedia/commons/f/f4/Food_Network_-_Logo_2016.png",
            "giallo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/giallo-it.png",
            "history": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/history-channel-it.png",
            "la 5": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/la5-it.png",
            # "la 7 d" duplicato, mantenendo il primo. Se necessario, gestire diversamente.
            "sky arte": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-arte-it.png",
            "sky documentaries": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-documentaries-it.png",
            "sky nature": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/sky-nature-it.png",
            "warner tv": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Warner_TV_Italy.svg/1200px-Warner_TV_Italy.svg.png",
            "fox": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/fox-it.png",
            "nat geo wild": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/national-geographic-wild-it.png",
            "animal planet": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/2018_Animal_Planet_logo.svg/2560px-2018_Animal_Planet_logo.svg.png",
            "boing": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/boing-it.png",
            "k2": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/k2-it.png",
            "discovery k2": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/k2-it.png",
            "nick jr": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/nick-jr-it.png",
            "nickelodeon": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/nickelodeon-it.png",
            "premium crime": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/premium-crime-it.png",
            "rakuten action movies": "https://img.utdstc.com/icon/7f6/a4a/7f6a4a47aa35e90d889cb8e71ed9a6930fe5832219371761736e87e880f85a5f:200",
            "rakuten comedy movies": "https://img.utdstc.com/icon/7f6/a4a/7f6a4a47aa35e90d889cb8e71ed9a6930fe5832219371761736e87e880f85a5f:200",
            "rakuten drama": "https://img.utdstc.com/icon/7f6/a4a/7f6a4a47aa35e90d889cb8e71ed9a6930fe5832219371761736e87e880f85a5f:200",
            "rakuten family": "https://img.utdstc.com/icon/7f6/a4a/7f6a4a47aa35e90d889cb8e71ed9a6930fe5832219371761736e87e880f85a5f:200",
            "rakuten top free": "https://img.utdstc.com/icon/7f6/a4a/7f6a4a47aa35e90d889cb8e71ed9a6930fe5832219371761736e87e880f85a5f:200",
            "rakuten tv shows": "https://img.utdstc.com/icon/7f6/a4a/7f6a4a47aa35e90d889cb8e71ed9a6930fe5832219371761736e87e880f85a5f:200",
            "boing plus": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/79/Boing_Plus_logo_2020.svg/1200px-Boing_Plus_logo_2020.svg.png",
            "wwe channel": "https://upload.wikimedia.org/wikipedia/en/8/8c/WWE_Network_logo.jpeg",
            "rsi la 2": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f4/RSI_La_2_2012.svg/1200px-RSI_La_2_2012.svg.png",
            "rsi la 1": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/be/RSI_La_1_2012.svg/1200px-RSI_La_1_2012.svg.png",
            "cartoon network": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/cartoon-network-it.png",
            "sky tg 24": "https://play-lh.googleusercontent.com/0RJjBW8_r64dWLAbG7kUVrkESbBr9Ukx30pDI83e5_o1obv2MTC7KSpBAIhhXvJAkXE",
            "tg com 24": "https://yt3.hgoogleusercontent.com/ytc/AIdro_kVh4SupZFtHrALXp9dRWD9aahJOUfl8rhSF8VroefSLg=s900-c-k-c0x00ffffff-no-rj",
            "tgcom 24": "https://yt3.hgoogleusercontent.com/ytc/AIdro_kVh4SupZFtHrALXp9dRWD9aahJOUfl8rhSF8VroefSLg=s900-c-k-c0x00ffffff-no-rj",
            "cartoonito": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/cartoonito-it.png",
            "super!": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/Super%21_logo_2021.svg/1024px-Super%21_logo_2021.svg.png",
            "deejay tv": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/deejay-tv-it.png",
            "cartoonito (backup)": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/cartoonito-it.png",
            "frisbee": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/italy/frisbee-it.png",
            "catfish": "https://upload.wikimedia.org/wikipedia/commons/4/46/Catfish%2C_the_TV_Show_Logo.PNG", # "tv7 news" era attaccato qui, l'ho rimosso, sembrava un errore di battitura
            "disney+ film": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Disney%2B_logo.svg/2560px-Disney%2B_logo.svg.png",
            "comedy central": "https://yt3.googleusercontent.com/FPzu1EWCI54fIh2j9JEp0NOzwoeugjL4sZTQCdoxoQY1U4QHyKx2L3wPSw27IueuZGchIxtKfv8=s900-c-k-c0x00ffffff-no-rj",
            "arte network": "https://www.arte.tv/sites/corporate/wp-content/themes/arte-entreprise/img/arte_logo.png",
            "aurora arte": "https://www.auroraarte.it/wp-content/uploads/2023/11/AURORA-ARTE-brand.png",
            "telearte": "https://www.teleartetv.it/web/wp-content/uploads/2023/04/logo_TA.jpg",
            "sky sport motogp": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/italy/hd/sky-sport-motogp-hd-it.png",
            "sky sport": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/italy/sky-sport-it.png",
            "rai sport": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/italy/rai-sport-it.png",
            "rtv san marino sport": "https://static.wikia.nocookie.net/internationaltelevision/images/7/79/San_Marino_RTV_Sport_-_logo.png/revision/latest?cb=20221207153729",
            "rtv sport": "https://logowik.com/content/uploads/images/san-marino-rtv-sport-20211731580347.logowik.com.webp",
            "trsport": "https://teleromagna.it/Images/logo-tr-sport.jpg",
            "aci sport tv": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/italy/aci-sport-tv-it.png",
            "euronews": "https://play-lh.googleusercontent.com/Mi8GAQIp3x94VcvbxZNsK-CTNhHy1zmo51pmME5KkkK4WgN4aQhM1FlNgLZUMD4VAXhL",
            "tg norba 24": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/italy/tg-norba-24-it.png",
            "tv7 news": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcStj45lIWvQ0KFzv6jyIP9vOZgPnWQirEl6dw&s",
            "milan tv": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/italy/milan-tv-it.png",
            "rtl 102.5": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/italy/rtl-1025-it.png",
            "la c tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/lac-tv-it.png?raw=true",
            "italian fishing tv": "https://www.upmagazinearezzo.it/atladv/wp-content/uploads/2017/07/atlantide-adv-logo-italian-fishing-tv.jpg",
            "rtv san marino": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/italy/rtv-san-marino-it.png",
            "antenna sud": "https://www.antennasud.com/media/2022/08/cropped-LOGO_ANTENNA_SUD_ROSSO_FORATO.png",
            "senato tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/senato-tv-it.png?raw=true",
            "rete oro": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQkE5wuUMIVAtANMfpSL4T5bIO73owXBhpvEg&s",
            "caccia": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/caccia-it.png?raw=true",
            "111 tv": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSDr-HrHBtGsogIKps_qWVME_l5axKwINoq2Q&s",
            "lazio tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/lazio-style-channel-it.png?raw=true",
            "padre pio tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/padre-pio-tv-it.png?raw=true",
            "inter tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/inter-tv-it.png?raw=true",
            "kiss kiss italia": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/radio-kiss-kiss-italia-it.png?raw=true",
            "12 tv parma": "https://www.12tvparma.it/wp-content/uploads/2021/11/ogg-image.jpg",
            "canale 21 extra": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcROcfjFIqjwxnG9AbEhJ6gwKb6IprmlFnF9aQ&s",
            "videolina": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/videolina-it.png?raw=true",
            "tv 2000": "https://upload.wikimedia.org/wikipedia/it/0/0d/Logo_di_TV2000.png",
            "byoblu": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRaMdUB8WEdsRVi_WZLxoi79pqlRef4s9Zehg&s",
            "kiss kiss napoli": "https://kisskissnapoli.it/wp-content/uploads/2022/03/cropped-logo-kisskiss-napoli.png",
            "kiss kiss": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/radio-kiss-kiss-tv-it.png?raw=true",
            "caccia e pesca": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/caccia-pesca-it.png?raw=true",
            "pesca": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/pesca-it.png?raw=true",
            "canale 7": "https://upload.wikimedia.org/wikipedia/commons/2/24/Canale_7.png",
            "crime+inv": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/crime-and-investigation-it.png?raw=true",
            "cafe 24": "https://play-lh.googleusercontent.com/DW0Tvz72-8XZ7rEBVh1jBzwYE1fZhTaowuuxN75Jl8yBtnFkySH1z2T2b7OPlotmHeQ",
            "antenna 2": "https://www.omceo.bg.it/images/loghi/antenna-2.png",
            "avengers grimm channel": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQN8by3YXjCGJQaxT6b-cgZ872BjY_NLIrALA&s",
            "classica": "https://upload.wikimedia.org/wikipedia/commons/4/4e/CLA_HD_Logo-CENT-300ppi_CMYK.jpg",
            "70 80 hits": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS5WEMBuK9zFW2nr_clM7noNGaUwp5fxRrmJA&s",
            "cusano italia tv": "https://play-lh.googleusercontent.com/c2HegRLQmaQFJXROyFH-phglfaZzQ-vikbZ464ZVJGfW8kX9jQuLACb2TIlydv1apsg",
            "espansione tv": "https://massimoemanuelli.com/wp-content/uploads/2017/10/etv-logo-attuale.png?w=640",
            "tva vicenza": "https://massimoemanuelli.com/wp-content/uploads/2017/10/tva-vi-2.png",
            "m2o": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Radio_m2o_-_Logo_2019.svg/1200px-Radio_m2o_-_Logo_2019.svg.png",
            "televenezia": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ0xhoeVg7nRLPp8GnPkFzLUWvJ5WolvU-iYw&s",
            "a3": "https://yt3.googleusercontent.com/3zkPKViC7G2rHWbBpYzSL6dFM9OMFBqIC6JrT-mM73EQsERHMqx4sPzWpBD8nfEqgf_uSHi124Y=s900-c-k-c0x00ffffff-no-rj",
            "alto adige tv": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQSdt3E_MmezXRKr7QOUEr0leEcErbaNGqbog&s",
            "cremona 1": "https://www.arvedi.it/fileadmin/user_upload/istituzionale/gruppo-arvedi-e-informazione-logo-Cremona1.png",
            "gold tv": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSSjSJx2Wah0-hfWbBn4_C79K5I0600lcD8zw&s",
            "france 24": "https://github.com/tv-logo/tv-logos/blob/main/countries/france/france-24-fr.png?raw=true",
            "iunior tv": "https://upload.wikimedia.org/wikipedia/commons/9/94/Iunior_tv.png",
            "canale 2": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/canale-italia-2-it.png?raw=true",
            "pesca e caccia": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/caccia-pesca-it.png?raw=true",
            "qvc": "https://github.com/tv-logo/tv-logos/blob/main/countries/germany/qvc-de.png?raw=true",
            "tele chiara": "https://upload.wikimedia.org/wikipedia/commons/b/ba/Telechiara-logo.png",
            "bergamo tv": "https://www.opq.it/wp-content/uploads/BergamoTV.png",
            "italia 3": "https://static.wikia.nocookie.net/dreamlogos/images/4/4e/Italia_3_2013.png/revision/latest?cb=20200119124403",
            "primocanale": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/primocanale-it.png?raw=true",
            "rei tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/rei-tv-it.png?raw=true",
            "rete veneta": "https://upload.wikimedia.org/wikipedia/it/d/df/Logo_Rete_Veneta.png",
            "telearena": "https://upload.wikimedia.org/wikipedia/commons/6/60/TeleArena_logo.png",
            "reggio tv": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Reggio_TV_logo.png/640px-Reggio_TV_logo.png",
            "tv2000": "https://upload.wikimedia.org/wikipedia/it/0/0d/Logo_di_TV2000.png", # Duplicato di "tv 2000"
            "retebiella tv": "https://alpitv.com/wp-content/uploads/2022/01/logo.png",
            "videostar tv": "https://www.videostartv.eu/images/videostar.png",
            "canale 8": "https://upload.wikimedia.org/wikipedia/it/thumb/6/6d/TV8_Logo_2016.svg/1200px-TV8_Logo_2016.svg.png",
            "juwelo italia": "https://upload.wikimedia.org/wikipedia/commons/f/fd/Juwelo_TV.svg",
            "rtc telecalabria": "https://play-lh.googleusercontent.com/7PzluYVAEVOCNzGYGkewkKI3PA0PkCKAc9KUZGfYzAbZnQLnlPAE5iQBMZEUi7ZKwJc",
            "tele mia": "https://upload.wikimedia.org/wikipedia/commons/a/a6/Telemia.png",
            "bloomberg tv 4k": "https://github.com/tv-logo/tv-logos/blob/main/countries/united-states/bloomberg-television-us.png?raw=true",
            "tele abruzzo": "https://www.abruzzi.tv/logo-abruzzi.png",
            "fashiontv": "https://github.com/tv-logo/tv-logos/blob/main/countries/international/fashion-tv-int.png?raw=true",
            "quarta rete": "https://quartarete.tv/wp-content/uploads/2022/06/Logo-Quartarete-ok.png",
            "fashion tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/international/fashion-tv-int.png?raw=true", # Duplicato di "fashiontv"
            "love fm tv": "https://www.lovefm.it/themes/default/assets/img_c/logo-love-new.png",
            "telerama": "https://upload.wikimedia.org/wikipedia/commons/b/b1/T%C3%A9l%C3%A9rama_logo.png",
            "teletubbies": "https://banner2.cleanpng.com/20180606/qrg/aa9vorpin.webp",
            "primo canale": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/primocanale-it.png?raw=true", # Duplicato di "primocanale"
            "lira tv": "https://liratv.es/wp-content/uploads/2021/07/LIRA-TV-1.png",
            "la tr3": "https://www.tvdream.net/img/latr3.png",
            "tele liguria sud": "https://www.teleliguriasud.it/sito/wp-content/uploads/2024/10/LOGO-RETINA.png",
            "la nuova tv": "https://play-lh.googleusercontent.com/Ck_esrelbBPGT2rsTtvuvciOBHA0f5b-VExXvBf-NP9fegvHhEuN9MIx7pgdv1WlW8o",
            "top calcio 24": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRPHW5VLQDGnNMVZszgWZRqnBSjPUTgAcUltQ&s",
            "fm italia": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRtJ5HlBu4jXOrC4iA-giQNzXa9zm42bS-yrA&s",
            "supersix lombardia": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT_ebhZMV4eYibx6UpVDOt1KOlmhOPYBh0gKw&s",
            "prima tv": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Prima_TV_Logo_2022.svg/800px-Prima_TV_Logo_2022.svg.png",
            "camera dei deputati": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/camera-dei-deputati-it.png?raw=true",
            "tele venezia": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ0xhoeVg7nRLPp8GnPkFzLUWvJ5WolvU-iYw&s", # Duplicato di "televenezia"
            "telemolise": "https://m.media-amazon.com/images/I/61yiY3jR+kL.png",
            "esperia tv 18": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/ESPERIATV18_verde.png/260px-ESPERIATV18_verde.png",
            "onda novara tv": "https://gag-fondazionedeagostini.s3.amazonaws.com/wp-content/uploads/2023/03/logo-Onda-Novara-TV-Ufficiale-1.png",
            "carina tv": "https://radiocarina.it/wp-content/uploads/2024/01/RadioCarina-Vers.2.png",
            "teleromagna": "https://teleromagna.it/images/teleromagna-logo.png",
            "elive tv brescia": "https://upload.wikimedia.org/wikipedia/commons/e/ec/%C3%88_live_Brescia_logo.png",
            "bellla & monella tv": "https://upload.wikimedia.org/wikipedia/commons/0/0e/Logo_Ufficiale_Radio_Bellla_%26_Monella.png",
            "videotolentino": "https://yt3.googleusercontent.com/ytc/AIdro_kAZM1WRzE6qfQx90xPJ3v1Jz1gaJwn6BbrZcewu6eTcQ=s900-c-k-c0x00ffffff-no-rj",
            "super tv brescia": "https://bresciasat.it/assets/front/img/logo3.png",
            "umbria tv": "https://upload.wikimedia.org/wikipedia/commons/0/09/Umbria_TV_wordmark%2C_ca._2020.png",
            "qvc italia": "https://github.com/tv-logo/tv-logos/blob/main/countries/germany/qvc-de.png?raw=true", # Duplicato di "qvc"
            "rttr": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/rttr-it.png?raw=true",
            "onda tv": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT9Og_2yYQhg-ersjEG5xZ99bri_Di4l5dlyw&s",
            "rttr tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/rttr-it.png?raw=true", # Duplicato di "rttr"
            "teleboario": "https://i.ytimg.com/vi/vNB5TJBjA3U/sddefault.jpg",
            "video novara": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ1PvoHpnx0hNKtt435CUaJza2e_qsm5B87Cg&s",
            "fano tv": "https://prolocopesarourbino.it/wp-content/uploads/2019/07/FANO-TV.jpg",
            # "tva vicenza" duplicato
            "etv marche": "https://etvmarche.it/wp-content/uploads/2021/05/Logo-Marche-BLU.png",
            "granducato": "https://www.telegranducato.it/wp-content/uploads/img_struttura_sito/logo_granducato_ridotto.png",
            "maria+vision italia": "",
            "star comedy": "https://github.com/tv-logo/tv-logos/blob/main/countries/portugal/star-comedy-pt.png?raw=true",
            "telecolor": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/telecolore-it.png?raw=true",
            "telequattro": "https://telequattro.medianordest.it/wp-content/uploads/2020/10/T4Logo.png",
            "tele tusciasabina 2000": "https://yt3.googleusercontent.com/ytc/AIdro_lp10Brud3JZex6CgE4M9c-XcKFY4MrRhcFe9PUn-N4SD4=s900-c-k-c0x00ffffff-no-rj",
            "stereo 5 tv": "https://www.stereo5.it/2022/wp-content/uploads/2023/02/LOGO-NUOVO-2023-2.png",
            # "tele chiara" duplicato
            "televideo agrigento": "https://lh3.googleusercontent.com/proxy/UNXKnLrwdDNoio4peXah3Pz81kI5Cv2FzJo82TPzn4seN-JZ3tovuVe45XSRBkIyMOfrrZ3bnWaMsTi80Xj40Q",
            "vco azzurra tv": "https://upload.wikimedia.org/wikipedia/commons/9/91/Logo_VCO_Azzurra_TV.png",
            "company tv": "https://www.trendcomunicazione.com/wp-content/uploads/2018/11/20180416-logo-tv-bokka-300x155.png",
            "tele pavia": "https://www.milanopavia.tv/wp-content/uploads/2020/01/logoMilanoPaviaTV.png",
            "uninettuno": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSYRpKemP5FC0RLOQVhc9kPU71aJW9Tj9DU8g&s",
            "star life": "https://github.com/tv-logo/tv-logos/blob/main/countries/argentina/star-life-ar.png?raw=true",
            "vera tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/vera-tv-it.png?raw=true",
            "arancia tv": "",
            "entella tv": "https://m.media-amazon.com/images/I/81omr2rZ8+L.png",
            "euro tv": "https://upload.wikimedia.org/wikipedia/it/9/93/Eurotv.png",
            "peer tv alto adige": "https://www.cxtv.com.br/img/Tvs/Logo/webp-l/6e7dee025526c334b9280153c418e10e.webp",
            "esperia tv": "https://upload.wikimedia.org/wikipedia/commons/b/b3/Logo_ESPERIAtv.png",
            "tele friuli": "https://www.telefriuli.it/wp-content/uploads/2022/11/logo_telefriuli_positivo.png",
            "rtp": "https://upload.wikimedia.org/wikipedia/commons/7/7c/RTP.png",
            "icaro tv": "https://www.gruppoicaro.it/wp-content/uploads/2020/05/icarotv.png",
            "telea tv": "https://www.tvdream.net/img/telea-tv.png",
            "telemantova": "https://www.telemantova.it/gfx/lib/ath-v1/logos/tmn/plain.svg?20241007",
            "bloomberg tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/united-states/bloomberg-television-us.png?raw=true", # Duplicato di "bloomberg tv 4k" (URL identico)
            "super j": "https://e7.pngegg.com/pngimages/439/74/png-clipart-superman-superhero-drawing-super-man-font-superhero-heart.png",
            "uninettuno university tv": "https://www.laureaonlinegiurisprudenza.it/wp-content/uploads/2019/09/Logo-Uninettuno.png",
            "rds social tv": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/RDS-Logo.png/260px-RDS-Logo.png",
            "rete tv italia": "https://www.retetvitalia.it/news/wp-content/uploads/2019/07/cropped-RTI-L.png",
            "fm italia tv": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRtJ5HlBu4jXOrC4iA-giQNzXa9zm42bS-yrA&s", # Duplicato di "fm italia"
            "telenord": "https://upload.wikimedia.org/wikipedia/it/a/a8/Telenord.png",
            "equ tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/equ-tv-it.png?raw=true",
            "orler tv": "https://www.tvdream.net/img/orlertv.png",
            "rmc 101": "https://upload.wikimedia.org/wikipedia/commons/f/fc/LogoRMC101.png",
            "telebari": "https://www.aaroiemac.it/notizie/wp-content/uploads/2018/11/1524066248-telebari.png",
            "telepace trento": "https://www.tvdream.net/img/telepace-trento.png",
            "trentino tv": "https://www.trentinotv.it/images/resource/logo-trentino.png",
            "tv qui": "https://www.tvdream.net/img/tvqui-modena-cover.jpg",
            "tv 33": "https://d1yjjnpx0p53s8.cloudfront.net/styles/logo-thumbnail/s3/0013/3844/brand.gif?itok=54JkEUiu",
            "trm h24": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/trm-h24-it.png?raw=true",
            "tt teletutto": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSQpzqT0DLXv-md7VU-fTF5BeaEashocwHUdw&s",
            "teletricolore": "https://www.teletricolore.it/wp-content/uploads/2018/02/logo.png",
            "globus television": "https://ennapress.it/wp-content/uploads/2020/10/globus.png",
            "rtr 99 tv": "https://www.tvdream.net/img/rtr99-cover.jpg",
            "tele romagna": "https://teleromagna.it/images/teleromagna-logo.png", # Duplicato di "teleromagna"
            "telecitta": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Logo_Telecitt%C3%A0.svg/800px-Logo_Telecitt%C3%A0.svg.png",
            "rds social": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/RDS-Logo.png/260px-RDS-Logo.png", # Duplicato di "rds social tv"
            "super tv aristanis": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQFBXh88zZx4IvyQKyYd5Hu2yeytO42zNQ4zA&s",
            "tv yes": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/tv-yes-it.png?raw=true",
            "quadrifoglio tv": "https://i.imgur.com/GfzpwKD.png",
            "telemistretta": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQN6reG7R24hdOigLSXg2G5oKcPqKt8cBc0jQ&s",
            "tele sirio": "https://www.telesirio.it/images/logo.png",
            "tvrs": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/tvrs-it.png?raw=true",
            "tele tricolore": "https://www.teletricolore.it/wp-content/uploads/2018/02/logo.png", # Duplicato di "teletricolore"
            "telepace": "https://e7.pngegg.com/pngimages/408/890/png-clipart-telepace-high-definition-television-hot-bird-%C4%8Ct1-albero-della-vita-television-text.png",
            "baby tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/spain/baby-tv-es.png?raw=true",
            "mtv hits": "https://github.com/tv-logo/tv-logos/blob/main/countries/serbia/mtv-hits-rs.png?raw=true",
            "radio freccia": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/radio-freccia-it.png?raw=true",
            "bella radio tv": "https://i0.wp.com/bellaradio.it/wp-content/uploads/2020/01/Bella-2020-3.png?fit=3000%2C3000&ssl=1",
            "ol3 radio": "https://pbs.twimg.com/profile_images/570326948497195008/Wf6DPfFP_400x400.jpeg",
            "51 radio tv": "https://tvtvtv.ru/icons/51_tv.png",
            "radionorba tv": "https://github.com/tv-logo/tv-logos/blob/main/countries/italy/radio-norba-tv-it.png?raw=true",
            "euro indie music chart tv": "https://m.media-amazon.com/images/I/61Wa4RqJVJL.png",
            "tele radio sciacca": "https://pbs.twimg.com/profile_images/613988173203423232/rWCQ9j6h_400x400.png",
            "radio capital": "https://static.wikia.nocookie.net/logopedia/images/1/1e/Radio_Capital_-_Logo_2019.svg.png/revision/latest?cb=20190815181629",
            "radio 51": "https://tvtvtv.ru/icons/51_tv.png" # Duplicato di "51 radio tv"
        }
        # Converti tutte le chiavi in minuscolo per una corrispondenza case-insensitive
        return {k.lower(): v for k, v in logos_data.items()}

    def normalize_channel_name(name):
        name = re.sub(r"\s+", "", name.strip().lower())
        name = re.sub(r"\.it\b", "", name)
        name = re.sub(r"hd|fullhd", "", name)
        return name

    def create_channel_id_map(epg_root):
        channel_id_map = {}
        for channel in epg_root.findall('channel'):
            tvg_id = channel.get('id')
            display_name = channel.find('display-name').text
            if tvg_id and display_name:
                normalized_name = normalize_channel_name(display_name)
                channel_id_map[normalized_name] = tvg_id
        return channel_id_map

    def fetch_channels(base_url):
        try:
            response = session.get(f"{base_url}/channels", timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Errore durante il download da {base_url}: {e}")
            return []

    def clean_channel_name(name):
        name = re.sub(r"\s*(\|E|\|H|\(6\)|\(7\)|\.c|\.s)", "", name)
        name = re.sub(r"\s*\(.*?\)", "", name)
        if "zona dazn" in name.lower() or "dazn 1" in name.lower():
            return "DAZN2"
        if "mediaset 20" in name.lower():
            return "20 MEDIASET"
        if "mediaset italia 2" in name.lower():
            return "ITALIA 2"
        if "mediaset 1" in name.lower():
            return "ITALIA 1"
        return name.strip()

    def filter_italian_channels(channels, base_url):
        seen = {}
        results = []
        for ch in channels:
            if ch.get("country") == "Italy":
                clean_name = clean_channel_name(ch["name"])
                if clean_name.lower() in ["dazn", "dazn 2"]:
                    continue
                count = seen.get(clean_name, 0) + 1
                seen[clean_name] = count
                if count > 1:
                    clean_name = f"{clean_name} ({count})"
                results.append((clean_name, f"{base_url}/play/{ch['id']}/index.m3u8"))
        return results

    def classify_channel(name):
        for category, words in CATEGORY_KEYWORDS.items():
            if any(word in name.lower() for word in words):
                return category
        return "Altro"

    def get_manual_channels():
        # LINK_SS e LINK_DADDY sono disponibili qui se necessario per costruire URL o header specifici,
        # poichÃ© sono caricate nello scope della funzione italy_channels().

        # Esempio di header comuni per un gruppo di canali (es. kangal)
        custom_common_headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "referer": f"{LINK_SS}/", 
            "origin": LINK_SS        
        }

        return [
            # --- Canali CUSTOM (esempio con header comuni) ---
            #{"name": "XXXXX", "url": "XXXXXXXXX.m3u8", "tvg_id": "XXXXXXXX", "logo": "XXXXXXXX.png", "category": "XXXXXXXXXX", "http_headers": custom_common_headers}

            # --- ESEMPIO: Canale con header DIVERSI/UNICI ---
            #{
            #    "name": "Mio Canale Custom Alpha (X)",
            #    "url": "https://streaming.esempio.com/alpha/playlist.m3u8",
            #    "tvg_id": "custom.alpha.it", # ID per EPG
            #    "logo": "https://esempio.com/logo_alpha.png", # URL del logo
            #    "category": "Custom", # Categoria per raggruppamento
            #    "http_headers": {
            #        "user-agent": "MioPlayerCustom/1.0",
            #        "Referer": "https://sito-referer.esempio.com/"
            #        "origin": "https://sito-referer.esempio.com"
            #    }
            #}
            
        ]

    # --- Funzioni per risolvere gli stream Daddylive ---
    def get_stream_from_channel_id(channel_id):
        # Prima cerca nei nuovi siti .m3u8
        m3u8_url = search_m3u8_in_sites(channel_id, is_tennis=False)
        if m3u8_url:
            return m3u8_url
        
        # Fallback al vecchio metodo .php se non trovato
        raw_php_url = f"{LINK_DADDY.rstrip('/')}/stream/stream-{channel_id}.php"
        print(f"Fallback URL .php per il canale Daddylive {channel_id}.")
        return raw_php_url
    # --- Fine funzioni Daddylive ---

    def fetch_channels_from_daddylive_page(page_url, base_daddy_url):
        print(f"Tentativo di fetch dei canali da: {page_url}")
        channels = []
        seen_daddy_channel_ids = set() # Set per tracciare i channel_id giÃ  visti da Daddylive
        try:
            response = session.get(page_url, timeout=HTTP_TIMEOUT, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # --- INIZIO LOGICA DI PARSING E FILTRAGGIO SPECIFICA PER DADDYLIVE 24-7 CHANNELS ---

            # Marcatori che suggeriscono un canale NON italiano (per evitare falsi positivi)
            non_italian_markers = [
                " (de)", " (fr)", " (es)", " (uk)", " (us)", " (pt)", " (gr)", " (nl)", " (tr)", " (ru)",
                " deutsch", " france", " espaÃ±ol", " arabic", " greek", " turkish", " russian", " albania",
                " portugal" # Aggiunto basandomi sull'esempio fornito
            ]

            grid_items = soup.find_all('div', class_='grid-item')
            print(f"Trovati {len(grid_items)} elementi 'grid-item' nella pagina Daddylive.")

            for item in grid_items:
                link_tag = item.find('a', href=re.compile(r'/stream/stream-\d+\.php'))
                if not link_tag:
                    continue

                strong_tag = link_tag.find('strong')
                if not strong_tag:
                    continue

                channel_name_raw = strong_tag.text.strip()
                href = link_tag.get('href')
                
                # Estrai l'ID del canale dall'href, es. /stream/stream-717.php -> 717
                channel_id_match = re.search(r'/stream/stream-(\d+)\.php', href)

                if channel_id_match and channel_name_raw:
                    channel_id = channel_id_match.group(1)
                    lower_channel_name = channel_name_raw.lower()

                    if channel_id in seen_daddy_channel_ids:
                        print(f"Skipping Daddylive channel '{channel_name_raw}' (ID: {channel_id}) perché l'ID è già stato processato.")
                        continue # Passa al prossimo item

                    # Filtro primario: deve contenere "italy"
                    if "italy" in lower_channel_name:
                        is_confirmed_non_italian_by_marker = False
                        for marker in non_italian_markers:
                            if marker in lower_channel_name:
                                is_confirmed_non_italian_by_marker = True
                                print(f"Skipping Daddylive channel '{channel_name_raw}' (ID: {channel_id}) perché, pur contenendo 'italy', ha anche un marcatore non italiano: '{marker}'")
                                break
                        
                        if not is_confirmed_non_italian_by_marker:
                            seen_daddy_channel_ids.add(channel_id) # Aggiungi l'ID al set prima di tentare la risoluzione
                            print(f"Trovato canale potenzialmente ITALIANO (Daddylive HTML): {channel_name_raw}, ID: {channel_id}. Tentativo di risoluzione stream...")
                            stream_url = get_stream_from_channel_id(channel_id)
                            if stream_url:
                                channels.append((channel_name_raw, stream_url))
                                print(f"Risolto e aggiunto stream per {channel_name_raw}: {stream_url}")
                            else:
                                print(f"Impossibile risolvere lo stream per {channel_name_raw} (ID: {channel_id})")
                    # else:
                        # Questo blocco Ã¨ commentato per non intasare i log con canali non italiani
                        # Non stampiamo nulla per i canali che non contengono "italy" per non intasare il log
                        # print(f"Skipping Daddylive channel '{channel_name_raw}' (ID: {channel_id}) perchÃ© non contiene 'italy' nel nome.")
            # --- FINE LOGICA DI PARSING E FILTRAGGIO ---

            if not channels:
                print(f"Nessun canale estratto/risolto da {page_url}. Controlla la logica di parsing o la struttura della pagina.")

        except requests.RequestException as e:
            print(f"Errore durante il download da {page_url}: {e}")
        except Exception as e:
            print(f"Errore imprevisto durante il parsing di {page_url}: {e}")
        return channels

    def save_m3u8(organized_channels):
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write('#EXTM3U\n\n')
            for category, channels_list in organized_channels.items(): # Renamed 'channels' to 'channels_list'
                channels_list.sort(key=lambda x: x["name"].lower())
                for ch_data in channels_list: # Renamed 'ch' to 'ch_data' as it's a dict
                    raw_channel_url = ch_data['url']
                    channel_name = ch_data['name']
                    tvg_name_cleaned = re.sub(r"\s*\(.*?\)", "", ch_data["name"])
                    final_url_to_write = raw_channel_url

                    if final_url_to_write: # Scrivi solo se l'URL Ã¨ valido
                        f.write(f'#EXTINF:-1 tvg-id="{ch_data.get("tvg_id", "")}" tvg-name="{tvg_name_cleaned}" tvg-logo="{ch_data.get("logo", DEFAULT_TVG_ICON)}" group-title="{category}",{channel_name}\n')
                        
                        # 1. Controlla se ci sono header HTTP personalizzati (tipicamente per canali manuali)
                        if "http_headers" in ch_data and ch_data["http_headers"]:
                            headers_dict = ch_data["http_headers"]
                            vlc_opt_lines = headers_to_extvlcopt(headers_dict)
                            for line in vlc_opt_lines:
                                f.write(f"{line}\n")
                            f.write(f"{final_url_to_write}\n\n") # Write the base URL
                        # 2. Controlla se Ã¨ un canale Vavoo (basato sull'URL)
                        elif any(base_vavoo_url.rstrip('/') + "/play/" in final_url_to_write for base_vavoo_url in BASE_URLS): # VAVOO
                            vavoo_headers = {"User-Agent": "VAVOO/2.6", "Referer": "https://vavoo.to/", "Origin": "https://vavoo.to"}
                            vlc_opt_lines = headers_to_extvlcopt(vavoo_headers)
                            for line in vlc_opt_lines:
                                f.write(f'{line}\n')
                            f.write(f"{final_url_to_write}\n\n")
                        # 3. Controlla se è un file .php (tipicamente Daddylive)
                        elif final_url_to_write.endswith('.php'): 
                            # Per file .php (es. Daddylive), nessun header speciale aggiunto
                            f.write(f"{final_url_to_write}\n\n")
                        # 4. Controlla se è un canale daddy (newkso.ru o premium) ma non .php
                        elif ("newkso.ru" in final_url_to_write or "premium" in final_url_to_write) and not final_url_to_write.endswith('.php'):
                            daddy_headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Referer": "https://forcedtoplay.xyz/", "Origin": "https://forcedtoplay.xyz"}
                            vlc_opt_lines = headers_to_extvlcopt(daddy_headers)
                            for line in vlc_opt_lines:
                                f.write(f'{line}\n')
                            f.write(f"{final_url_to_write}\n\n")
                        # 5. Altri canali (es. link diretti manuali senza http_headers specifici)
                        else:
                            # Scrivi l'URL direttamente senza header aggiuntivi
                            f.write(f"{final_url_to_write}\n\n")
                    else:
                        print(f"Skipping channel {channel_name} due to missing stream URL after processing.")


    def main():
        epg_root = fetch_epg(EPG_FILE)
        if epg_root is None:
            print("Impossibile recuperare il file EPG, procedura interrotta.")
            return
        logos_dict = fetch_logos()
        channel_id_map = create_channel_id_map(epg_root)
        
        all_fetched_channels = [] # ConterrÃ  tuple (nome_canale, url_stream)

        # 1. Canali da sorgenti JSON (Vavoo)
        print("\n--- Fetching canali da sorgenti Vavoo (JSON) ---") # This line is always printed
        for base_vavoo_url in BASE_URLS:
            json_channels_data = fetch_channels(base_vavoo_url)
            all_fetched_channels.extend(filter_italian_channels(json_channels_data, base_vavoo_url))
        # Controlla se i canali Daddylive devono essere inclusi
        canali_daddy_enabled = os.getenv("CANALI_DADDY", "no").strip().lower() == "si"
        
        # 2. Canali dalla pagina HTML di Daddylive
        processed_scraped_channels = []
        if canali_daddy_enabled:
            print("\n--- Fetching canali da Daddylive (HTML) ---")
            daddylive_247_page_url = f"{LINK_DADDY.rstrip('/')}/24-7-channels.php"
            scraped_daddylive_channels = fetch_channels_from_daddylive_page(daddylive_247_page_url, LINK_DADDY)
            processed_scraped_channels = []
            seen_daddy_transformed_base_names = {}
            for raw_name, stream_url in scraped_daddylive_channels:
                # 1. Pulizia iniziale generica del nome grezzo
                name_after_initial_clean = clean_channel_name(raw_name)

                # 2. Trasformazioni specifiche per Daddylive:
                #    - Rimuovi "italy" (case insensitive)
                #    - Converti in maiuscolo
                # Questo sarÃ  il nome base per la gestione dei duplicati Daddylive
                base_daddy_name = re.sub(r'italy', '', name_after_initial_clean, flags=re.IGNORECASE).strip()
                base_daddy_name = re.sub(r'\s+', ' ', base_daddy_name).strip() # Rimuovi spazi doppi
                base_daddy_name = base_daddy_name.upper()
                
                # Rinominare i canali Sky Calcio e Sky Calcio 7 specifici di Daddylive
                # Questo avviene DOPO la pulizia iniziale e l'uppercase,
                # e PRIMA della gestione dei duplicati e dell'aggiunta di "(D)"
                sky_calcio_rename_map = {
                    "SKY CALCIO 1": "SKY SPORT 251",
                    "SKY CALCIO 2": "SKY SPORT 252",
                    "SKY CALCIO 3": "SKY SPORT 253",
                    "SKY CALCIO 4": "SKY SPORT 254",
                    "SKY CALCIO 5": "SKY SPORT 255",
                    "SKY CALCIO 6": "SKY SPORT 256",
                    "SKY CALCIO 7": "DAZN 1"
                }

                if base_daddy_name in sky_calcio_rename_map:
                    original_bdn_for_log = base_daddy_name
                    base_daddy_name = sky_calcio_rename_map[base_daddy_name]
                    print(f"Rinominato canale Daddylive (HTML) da '{original_bdn_for_log}' a '{base_daddy_name}'")


                # Gestione skip DAZN (usa il nome base trasformato per il check)
                # clean_channel_name potrebbe giÃ  aver trasformato "dazn 1" in "DAZN2"
                if base_daddy_name == "DAZN" or base_daddy_name == "DAZN2":
                    print(f"Skipping canale Daddylive (HTML) a causa della regola DAZN: {raw_name} (base trasformato: {base_daddy_name})")
                    continue
                
                # 3. Gestione duplicati basata sul nome base trasformato di Daddylive
                count = seen_daddy_transformed_base_names.get(base_daddy_name, 0) + 1
                seen_daddy_transformed_base_names[base_daddy_name] = count
                
                # 4. Costruzione del nome finale per Daddylive
                final_name = base_daddy_name
                if count > 1:
                    final_name = f"{base_daddy_name} ({count})" # Es. NOME CANALE (2)
                final_name = f"{final_name} (D)" # Es. NOME CANALE (D) o NOME CANALE (2) (D)
                
                processed_scraped_channels.append((final_name, stream_url))

            all_fetched_channels.extend(processed_scraped_channels)
        else:
            print("\n--- Skipping Daddylive channels: CANALI_DADDY is not 'si' ---")

        # 3. Canali manuali
        manual_channels_data = get_manual_channels()

        # Organizzazione di tutti i canali raccolti
        print("\n--- Organizzazione canali ---")
        organized_channels = {category: [] for category in CATEGORY_KEYWORDS.keys()}

        # Processa canali da Vavoo e Daddylive HTML (formato: (nome, url))
        for name, url in all_fetched_channels:
            # 'name' Ã¨ il nome finale che verrÃ  visualizzato, 
            # es. "CANALE SPORT (D) (2)" o "CANALE NEWS (3)" (da Vavoo)
            category = classify_channel(name)

            # Crea un nome base per il lookup di EPG e Logo:
            name_for_lookup = name
            # Rimuovi il suffisso (D) specifico di Daddylive, se presente
            if name_for_lookup.upper().endswith(" (D)"): # Controllo case-insensitive per robustezza
                # Rimuove l'ultima occorrenza di " (D)" (case insensitive)
                match_d_suffix = re.search(r'\s*\([Dd]\)$', name_for_lookup)
                if match_d_suffix:
                    name_for_lookup = name_for_lookup[:match_d_suffix.start()]
            
            # Rimuovi suffissi numerici per duplicati, es. (2), (3)...
            name_for_lookup = re.sub(r'\s*\(\d+\)$', '', name_for_lookup).strip()
            # A questo punto, name_for_lookup dovrebbe essere il nome del canale "pulito" 
            # es. "CANALE SPORT" o "CANALE NEWS" (giÃ  in maiuscolo se da Daddylive)

            # Logica per assegnazione logo
            final_logo_url = DEFAULT_TVG_ICON # Inizializza con il logo di default
            sky_sport_daddy_logo = "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/italy/hd/sky-sport-hd-it.png"

            # Controlla se il canale Ã¨ uno dei canali Daddylive SKY SPORT 251-256
            # name_for_lookup Ã¨ il nome base pulito (es. "SKY SPORT 251")
            # name Ã¨ il nome completo con suffisso (es. "SKY SPORT 251 (D)")
            if name.upper().endswith(" (D)"): # Verifica se Ã¨ un canale Daddylive
                if re.match(r"SKY SPORT (25[1-6])$", name_for_lookup.upper()):
                    # Ã un canale Daddylive SKY SPORT 251-256
                    final_logo_url = sky_sport_daddy_logo
                    print(f"Logo specifico '{final_logo_url}' assegnato a Daddylive channel '{name}' (lookup name: '{name_for_lookup}')")
                else:
                    # Ã un canale Daddylive, ma non uno dei SKY SPORT 251-256 target, usa il lookup normale
                    final_logo_url = logos_dict.get(name_for_lookup.lower(), DEFAULT_TVG_ICON)
            else:
                # Non Ã¨ un canale Daddylive (es. Vavoo), usa il lookup normale
                final_logo_url = logos_dict.get(name_for_lookup.lower(), DEFAULT_TVG_ICON)

            organized_channels.setdefault(category, []).append({
                "name": name, # Nome completo da visualizzare
                "url": url,
                "tvg_id": channel_id_map.get(normalize_channel_name(name_for_lookup), ""), # Usa il nome pulito per tvg-id
                "logo": final_logo_url # Usa il logo determinato dalla logica sopra
            })

        # Processa canali manuali (formato: dict)
        for ch_data_manual in manual_channels_data:
            cat = ch_data_manual.get("category") or classify_channel(ch_data_manual["name"])
            # Construct the dictionary to append, ensuring all necessary fields are included
            channel_entry = {
                "name": ch_data_manual["name"],
                "url": ch_data_manual["url"],
                "tvg_id": ch_data_manual.get("tvg_id", ""),
                "logo": ch_data_manual.get("logo", DEFAULT_TVG_ICON)
            }
            if "http_headers" in ch_data_manual: # Pass through http_headers if they exist
                channel_entry["http_headers"] = ch_data_manual["http_headers"]
            
            organized_channels.setdefault(cat, []).append(channel_entry)


        save_m3u8(organized_channels)
        print(f"\nFile {OUTPUT_FILE} creato con successo!")

    if __name__ == "__main__":
        main()

# Funzione per il settimo script (world_channels_generator.py)
def world_channels_generator():
    # Codice del settimo script qui
    # Aggiungi il codice del tuo script "world_channels_generator.py" in questa funzione.
    print("Eseguendo il world_channels_generator.py...")
    # Il codice che avevi nello script "world_channels_generator.py" va qui, senza modifiche.
    import requests
    import re
    import os
    from collections import defaultdict
    from dotenv import load_dotenv
    
    # Carica le variabili d'ambiente dal file .env
    load_dotenv()

    OUTPUT_FILE = "world.m3u8"
    BASE_URLS = [
        "https://vavoo.to"
    ]
    
    # Scarica la lista dei canali
    def fetch_channels(base_url):
        try:
            response = requests.get(f"{base_url}/channels", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Errore durante il download da {base_url}: {e}")
            return []
    
    # Pulisce il nome del canale
    def clean_channel_name(name):
        return re.sub(r"\s*(\|E|\|H|\(6\)|\(7\)|\.c|\.s)", "", name).strip()
    
    # Salva il file M3U8 con i canali ordinati alfabeticamente per categoria
    def save_m3u8(channels):
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
    
        # Raggruppa i canali per nazione (group-title)
        grouped_channels = defaultdict(list)
        for name, url, country in channels:
            grouped_channels[country].append((name, url))
    
        # Ordina le categorie alfabeticamente e i canali dentro ogni categoria
        sorted_categories = sorted(grouped_channels.keys())
    
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write('#EXTM3U\n\n')
    
            for country in sorted_categories:
                # Ordina i canali in ordine alfabetico dentro la categoria
                grouped_channels[country].sort(key=lambda x: x[0].lower())
    
                for name, url in grouped_channels[country]:
                    f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{country}", {name}\n')
                    vavoo_headers = {"User-Agent": "VAVOO/2.6", "Referer": "https://vavoo.to/", "Origin": "https://vavoo.to"}
                    vlc_opt_lines = headers_to_extvlcopt(vavoo_headers)
                    for line in vlc_opt_lines:
                        f.write(f'{line}\n')
                    f.write(f"{url}\n\n")
    
    # Funzione principale
    def main():
        all_channels = []
        for url in BASE_URLS:
            channels = fetch_channels(url)
            for ch in channels:
                clean_name = clean_channel_name(ch["name"])
                country = ch.get("country", "Unknown")  # Estrai la nazione del canale, default ÃÂ¨ "Unknown"
                all_channels.append((clean_name, f"{url}/play/{ch['id']}/index.m3u8", country))
    
        save_m3u8(all_channels)
        print(f"File {OUTPUT_FILE} creato con successo!")
    
    if __name__ == "__main__":
        main()

def removerworld():
    import os
    
    canali_daddy_flag = os.getenv("CANALI_DADDY", "no").strip().lower()
    
    # Lista dei file da eliminare
    files_to_delete = ["world.m3u8", "channels_italy.m3u8"]
    
    # Condizionalmente aggiungi eventi.m3u8 e eventi.xml alla lista di eliminazione
    if canali_daddy_flag == "si":
        files_to_delete.append("eventi.m3u8")
        files_to_delete.append("eventi.xml")
    else:
        print("[INFO] Skipping deletion of eventi.m3u8 and eventi.xml in removerworld as CANALI_DADDY is not 'si'.")
    
    for filename in files_to_delete:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"File eliminato: {filename}")
            except Exception as e:
                print(f"Errore durante l'eliminazione di {filename}: {e}")
        else:
            print(f"File non trovato: {filename}")

def remover():
    import os
    
    canali_daddy_flag = os.getenv("CANALI_DADDY", "no").strip().lower()

    # Lista dei file da eliminare
    files_to_delete = ["channels_italy.m3u8"]

    # Condizionalmente aggiungi eventi.m3u8 alla lista di eliminazione
    if canali_daddy_flag == "si":
        files_to_delete.append("eventi.m3u8")
        files_to_delete.append("eventi.xml")
    else:
        print("[INFO] Skipping deletion of eventi.m3u8 and eventi.xml in remover as CANALI_DADDY is not 'si'.")
    
    for filename in files_to_delete:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"File eliminato: {filename}")
            except Exception as e:
                print(f"Errore durante l'eliminazione di {filename}: {e}")
        else:
            print(f"File non trovato: {filename}")

# Funzione principale che esegue tutti gli script
def main():
    load_daddy_cache()
    try:
        canali_daddy_flag = os.getenv("CANALI_DADDY", "no").strip().lower()
        if canali_daddy_flag == "si":
            try:
                schedule_success = schedule_extractor()
            except Exception as e:
                print(f"Errore durante l'esecuzione di schedule_extractor: {e}")

        # Leggi le variabili d'ambiente
        eventi_en = os.getenv("EVENTI_EN", "no").strip().lower()
        world_flag = os.getenv("WORLD", "si").strip().lower()

        # EPG Eventi
        # Genera eventi.xml solo se CANALI_DADDY è "si"
        if canali_daddy_flag == "si": # Questa riga è corretta
            try: # Questo blocco 'try' deve essere indentato sotto l'if
                if eventi_en == "si":
                    epg_eventi_generator_world()
                else:
                    epg_eventi_generator()
            except Exception as e:
                print(f"Errore durante la generazione EPG eventi: {e}")
                return # Interrompi l'esecuzione se la generazione EPG fallisce
        else: # Questo blocco 'else' deve essere l'else dell'if, non del try
            print("[INFO] Generazione eventi.xml saltata: CANALI_DADDY non è 'si'.")

        # Eventi M3U8
        try:
            if canali_daddy_flag == "si":
                if eventi_en == "si":
                    eventi_m3u8_generator_world()
                else:
                    eventi_m3u8_generator()
            else:
                print("[INFO] Generazione eventi.m3u8 saltata: CANALI_DADDY non è 'si'.")
        except Exception as e:
            print(f"Errore durante la generazione eventi.m3u8: {e}")
            return

        # EPG Merger
        try:
            epg_merger()
        except Exception as e:
            print(f"Errore durante l'esecuzione di epg_merger: {e}")
            return

        # Canali Italia
        try:
            italy_channels()
        except Exception as e:
            print(f"Errore durante l'esecuzione di italy_channels: {e}")
            return

        # Canali World e Merge finale
        try:
            if world_flag == "si":
                world_channels_generator()
                merger_playlistworld()
                removerworld()
            elif world_flag == "no":
                merger_playlist()
                remover()
            else:
                print(f"Valore WORLD non valido: '{world_flag}'. Usa 'si' o 'no'.")
                return
        except Exception as e:
            print(f"Errore nella fase finale: {e}")
            return

        print("Tutti gli script sono stati eseguiti correttamente!")
    finally:
        save_daddy_cache()
        
if __name__ == "__main__":
    main()
    # Dopo la generazione di lista.m3u, aggiungi i canali MPD
    if os.path.exists('mpd.m3u'):
        aggiungi_mpd_in_lista('lista.m3u', 'mpd.m3u', 'lista.m3u')
