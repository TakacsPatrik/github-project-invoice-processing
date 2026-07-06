import os
import re
import pandas as pd
import streamlit as st
import fitz

# =====================================================================
# INNENTŐL KEZDŐDIK A TE EREDETI KÓDOD (VÁLTOZTATÁS NÉLKÜL)
# =====================================================================

# 1. Beolvassuk a számla szövegét tartalmazó fájlt
fajlnev = r"C:\Users\takacspatrik\Desktop\programming\szamlafeldolgozo_program\szamla_szoveg.txt"

def read_all_numbers(fajlnev):
    """Ez a függvény beolvassa a megadott fájlt, és kikeresi az összes "Mobil hívószám" előfordulást, 
    majd kiírja azokat."""

    if not os.path.exists(fajlnev):
        print(f"Hiba: A '{fajlnev}' fájl nem található a mappában!")
        return
    
    else:
        with open(fajlnev, "r", encoding="utf-8") as f:
            szoveg = f.read()
        
    # 2. Meghatározzuk a keresési mintát (Regex)
    # Ez keresi a "Mobil hívószám" szöveget, majd a zárójeles részt és a számokat, szóközöket is beleértve
    minta = r"Mobil hívószám\s*\(?\d+\)?[\d\s]+"
    
    # 3. Kikeressük az összes találatot
    talalatok = re.findall(minta, szoveg)
    
    # 4. Megtisztítjuk és kiírjuk a talált számokat
    print(f"Sikeresen megtaláltam {len(talalatok)} hívószámot:\n")
    
    for talalat in talalatok:
        # Eltávolítjuk a "Mobil hívószám" feliratot, hogy csak a tiszta szám maradjon
        tiszta_szam = talalat.replace("Mobil hívószám", "").strip()
        print(tiszta_szam)

def read_all_data(fajlnev):
    if not os.path.exists(fajlnev):
        print(f"Hiba: A '{fajlnev}' fájl nem található a mappában!")
        return
    
    with open(fajlnev, "r", encoding="utf-8") as f:
        szoveg = f.read()

    # 1. MEGOLDÁS A HIBÁRA: Regex helyett daraboljuk fel a szöveget!
    # A "Mobil hívószám" mentén pontosan 262+1 blokkra hasítjuk a 67 oldalt.
    nyers_blokkok = szoveg.split("Mobil hívószám")
    
    # Az első elem (0. index) a számla fejléce (a legelső telefonszám előtti bevezető), ezt eldobjuk.
    blokkok = nyers_blokkok[1:]
    
    print(f"Összesen {len(blokkok)} egyedi hívószám-blokkot találtam.\n")
    
    # Vizsgáljuk meg az első 2 blokkot
    for i in range(min(2, len(blokkok))):
        print(f"=== {i+1}. HÍVÓSZÁM BLOKKJA ===")
        
        # Visszatesszük az elejére a megkeresett szót, amit a split() kivágott
        aktualis_blokk = "Mobil hívószám" + blokkok[i]
        
        # Kiszűrjük belőle csak a lényeget (a telefonszám kezdetétől a fizetendő összeg végéig)
        sorok = aktualis_blokk.split("\n")
        tisztitott_sorok = []
        
        talalt_osszesen = False
        plusz_sorok = 0 # Számláló, hogy az összeg alatti 2 sort (nettó és bruttó) is megkapjuk
        
        for sor in sorok:
            tisztitott_sorok.append(sor)
            
            # Ha elérjük a blokk végét jelentő sort...
            if "Utólag fizetendő összesen" in sor:
                talalt_osszesen = True
            
            # ...akkor még hozzáadunk 2 sort, mert a PDF-ben ott vannak a forint összegek, majd lezárjuk a blokkot
            if talalt_osszesen:
                plusz_sorok += 1
                if plusz_sorok >= 3: 
                    break
        
        # Kiírjuk a szépen megtisztított blokkot
        print("\n".join(tisztitott_sorok).strip())
        print("=" * 40 + "\n")

def parse_block(fajlnev):
    if not os.path.exists(fajlnev):
        print(f"Hiba: A '{fajlnev}' fájl nem található!")
        return

    with open(fajlnev, "r", encoding="utf-8") as f:
        szoveg = f.read()

    # Feldarabolás a hívószámok mentén (az előző bevált módszer)
    nyers_blokkok = szoveg.split("Mobil hívószám")
    blokkok = nyers_blokkok[1:]

    # Vizsgáljuk meg a legelső blokkot (az index [0])
    aktualis_blokk = "Mobil hívószám" + blokkok[0]
    sorok = [s.strip() for s in aktualis_blokk.split("\n") if s.strip()] # Csak a nem üres sorok

    print("=== NYERS SZÁMLA TÉTELEK KINYERÉSE (1. HÍVÓSZÁM) ===\n")
    
    # Keresési minták
    # Ár minta: Megkeresi a sor végén lévő 2 vagy 3 db számot (nettó egységár, nettó, bruttó). Pld: 1.590,00 1.537,00 1.951,99
    ar_minta = r"((?:-?\d{1,3}(?:\.\d{3})*,\d{2}\s*)+)$" 
    
    # Végigmegyünk a blokk sorain
    for i, sor in enumerate(sorok):
        # Ha a sorban benne van az Utólag fizetendő, akkor vége a tételeknek
        if "Utólag fizetendő összesen" in sor:
            break

        # Kihagyjuk a sallangokat
        if sor.startswith("Mobil hívószám") or sor.startswith("A számhordozás") or "Előfizetési díjak" in sor or "Forgalmi" in sor or "Egyéb" in sor:
            continue

        # Ellenőrizzük, hogy van-e a sor végén ár
        ar_talalat = re.search(ar_minta, sor)
        
        if ar_talalat:
            # A sor eleje a megnevezés
            megnevezes = sor[:ar_talalat.start()].strip()
            
            # A megnevezésből kiszedjük a mennyiséget és az egységet (pl. "29/30 hó" vagy "3 db")
            # Ez egy kicsit trükkös, mert a PDF-ből másolt szövegben ezek sokszor a sor legvégén vannak, az árak előtt.
            mennyiseg_egyseg_minta = r"(\d+(?:/\d+)?)\s*(hó|db|alk\.|p:mp)\s*$"
            m_e_talalat = re.search(mennyiseg_egyseg_minta, megnevezes)
            
            tisztitott_megnevezes = megnevezes
            if m_e_talalat:
                 tisztitott_megnevezes = megnevezes[:m_e_talalat.start()].strip()
            
            # TESZOR kód kinyerése a megnevezésből
            teszor = "61.20.12" # Alapértelmezett (hang)
            teszor_talalat = re.search(r"TESZOR\s*([\d\.]+)", tisztitott_megnevezes)
            if teszor_talalat:
                teszor = teszor_talalat.group(1)
            elif "SMS" in tisztitott_megnevezes:
                teszor = "61.20.13"
            elif "MMS" in tisztitott_megnevezes:
                teszor = "61.20.14"

            # Az árak (nettó egységár, nettó összeg, bruttó összeg)
            arak_szoveg = ar_talalat.group(1).strip().split()
            
            # A nettó összeg (a táblázatodba ez kell) általában az utolsó előtti, 
            # de ha csak 2 szám van (pl. egyedi díjaknál), akkor az első.
            if len(arak_szoveg) >= 3:
                netto_str = arak_szoveg[-2] 
            elif len(arak_szoveg) == 2:
                netto_str = arak_szoveg[0]
            else:
                 netto_str = arak_szoveg[0]

            # Átalakítás float formátumba (1.537,00 -> 1537.00)
            netto_float = float(netto_str.replace(".", "").replace(",", "."))

            print(f"Megnevezés: {tisztitott_megnevezes[:40]:<40} | TESZOR: {teszor} | Nettó: {netto_float} Ft")

def is_noise_line(line):
    """Kiszűri az oldaltöréseket, fejléceket és mértékegységeket a V3 kód alapján."""
    l = line.strip()
    if not l: return True
    
    # Mértékegységek
    if l.lower() in ['hó', 'hỏ', 'db', 'perc', 'p:mp', '10kbyte', '%', 'alk.']: return True
    
    # Mennyiségek (tiszta egész számok, törtek)
    if re.match(r'^\d+$', l) or re.match(r'^\d+/\d+$', l) or re.match(r'^\d+:\d+$', l): return True
    
    # Oldaltörés elemek és fejlécek
    noise_phrases = [
        "A számhordozás megvalósulásának", "Adóigazgatási azonosításra", "e-bill",
        "Folyószámlaszám", "oldal / page", "oldal/page", "Számla száma", "MT azonosító",
        "mennyiség", "egység nettó egységár (Ft)", "nettó összeg (Ft)", "bruttó összeg (Ft)"
    ]
    
    if any(phrase.lower() in l.lower() for phrase in noise_phrases): return True
    
    # Ez okozta a hibát a 9. számnál!
    if l.startswith("Szolgáltatás TESZOR"): return True
    
    return False

def get_teszor(desc):
    match = re.search(r'TESZOR\s*([\d\.]+)', desc, re.IGNORECASE)
    if match: return match.group(1)
    
    desc_lower = desc.lower()
    if "sms" in desc_lower: return "61.20.13"
    if "mms" in desc_lower: return "61.20.14"
    if "m2m" in desc_lower: return "61.20.30"
    if "multisim" in desc_lower or "multi-sim" in desc_lower: return "82.99.19"
    if any(k in desc_lower for k in ["adat", "net", "internet", "apn", "netgarancia", "gprs", "éjszaka", "csúcsid", "egyéb id"]): 
        return "61.20.42"
    if "parkolás" in desc_lower: return "51.21.24"
    
    return "61.20.12"

def get_netto(prices):
    if not prices: return 0.0
    net_str = prices[-2] if len(prices) >= 2 else prices[0]
    return float(net_str.replace(".", "").replace(",", "."))

def get_acclev_netto(szoveg):
    """Kinyeri az ACCLEVCONTR (Forgalmi tájékoztató) nettó összegét a számla végéről."""
    acclev_netto = 0.0
    if "ACCLEVCONTR" in szoveg:
        acclev_blokk = szoveg.split("ACCLEVCONTR")[-1]
        sorok = [s.strip() for s in acclev_blokk.split("\n") if s.strip()]
        
        ar_minta_bovebb = re.compile(r'^-?\d{1,3}(?:\.\d{3})*[,\.]\d{2}$')
        
        acclev_arak = []
        talalt_osszesen = False
        for sor in sorok:
            tiszta_sor = sor.replace('|', '').strip()
            if "Utólag fizetend" in tiszta_sor:
                talalt_osszesen = True
                continue
            
            if talalt_osszesen:
                if ar_minta_bovebb.match(tiszta_sor):
                    acclev_arak.append(tiszta_sor)
                if len(acclev_arak) == 2:
                    break
                    
        if acclev_arak:
            acclev_netto_str = acclev_arak[0].replace(',', '.')
            if acclev_netto_str.count('.') > 1:
                parts = acclev_netto_str.split('.')
                acclev_netto_str = "".join(parts[:-1]) + "." + parts[-1]
            acclev_netto = float(acclev_netto_str)
            
    return acclev_netto

def process_invoice(fajlnev, limit=None):
    if not os.path.exists(fajlnev):
        print(f"Hiba: A '{fajlnev}' fájl nem található!")
        return

    with open(fajlnev, "r", encoding="utf-8") as f:
        szoveg = f.read()

    # Szöveg feldarabolása és a fejléc eldobása
    blokkok = szoveg.split("Mobil hívószám")[1:]
    
    # DINAMIKUS LIMIT BEÁLLÍTÁSA
    if limit is None or limit <= 0:
        feldolgozando_blokkok = blokkok
    else:
        feldolgozando_blokkok = blokkok[:limit]

    print(f"Összesen {len(blokkok)} hívószám van a dokumentumban.")
    print(f"Ebből most feldolgozásra kerül: {len(feldolgozando_blokkok)} db\n")
    
    ar_minta = re.compile(r'^-?\d{1,3}(?:\.\d{3})*,\d{2}$')

    # Végigmegyünk a kijelölt blokkokon
    for index, blokk in enumerate(feldolgozando_blokkok):
        aktualis_blokk = "Mobil hívószám" + blokk
        sorok = [s.strip() for s in aktualis_blokk.split("\n") if s.strip()]
        
        telefonszam = sorok[0].replace("Mobil hívószám", "").strip()

        print(f"=== {index + 1}. HÍVÓSZÁM: {telefonszam} ===")
        
        current_desc_lines = []
        current_prices = []
        teszor_osszesito = {}

        for sor in sorok:
            if "Utólag fizetend" in sor:
                if current_prices:
                    desc = " ".join(current_desc_lines)
                    teszor = get_teszor(desc)
                    netto = get_netto(current_prices)
                    teszor_osszesito[teszor] = teszor_osszesito.get(teszor, 0.0) + netto
                    print(f"  [{teszor}] {desc[:50]:<50}... | {netto:>8.2f} Ft")
                break

            if sor.startswith("Mobil hívószám"):
                continue
                
            # ZAJ SZŰRÉSE
            if is_noise_line(sor):
                continue

            if ar_minta.match(sor):
                current_prices.append(sor)
            else:
                if current_prices:
                    desc = " ".join(current_desc_lines)
                    teszor = get_teszor(desc)
                    netto = get_netto(current_prices)
                    teszor_osszesito[teszor] = teszor_osszesito.get(teszor, 0.0) + netto
                    
                    print(f"  [{teszor}] {desc[:50]:<50}... | {netto:>8.2f} Ft")
                    
                    current_desc_lines = [sor]
                    current_prices = []
                else:
                    current_desc_lines.append(sor)

        print("-" * 40)
        print("  Összesítő erre a számra:")
        for t, ossz in teszor_osszesito.items():
            print(f"  TESZOR {t}: {ossz:>8.2f} Ft")
        print("=" * 60 + "\n")

    
    acclev_netto = get_acclev_netto(szoveg)
    if acclev_netto > 0:
        print(f"=== EGYÉB TÉTEL: Forgalmi tájékoztató ===")
        print(f"  [61.20.30] Elektronikus Forgalmi Tájékoztató... | {acclev_netto:>8.2f} Ft")
        print("-" * 40)
        print(f"  TESZOR 61.20.30: {acclev_netto:>8.2f} Ft")
        print("=" * 60 + "\n")

def export_to_excel(fajlnev, kimenet_fajlnev="telekom_szamla_osszesito.xlsx"):
    """
    Kinyeri az összes telefonszámhoz tartozó TESZOR összesítőt és a számlakészítési díjat,
    majd kimenti egy Excel táblázatba. Dinamikusan a teljes dokumentumot feldolgozza.
    """
    if not os.path.exists(fajlnev):
        print(f"Hiba: A '{fajlnev}' fájl nem található!")
        return

    with open(fajlnev, "r", encoding="utf-8") as f:
        szoveg = f.read()

    blokkok = szoveg.split("Mobil hívószám")[1:]
    feldolgozando_blokkok = blokkok

    print(f"📊 Excel generálása mind a(z) {len(feldolgozando_blokkok)} hívószám alapján...")
    
    ar_minta = re.compile(r'^-?\d{1,3}(?:\.\d{3})*,\d{2}$')
    vegleges_sorok = []
    sorszam = 1

    for blokk in feldolgozando_blokkok:
        aktualis_blokk = "Mobil hívószám" + blokk
        sorok = [s.strip() for s in aktualis_blokk.split("\n") if s.strip()]
        telefonszam = sorok[0].replace("Mobil hívószám", "").strip()
        
        current_desc_lines = []
        current_prices = []
        teszorok = {}

        for sor in sorok:
            if "Utólag fizetend" in sor:
                if current_prices:
                    desc = " ".join(current_desc_lines)
                    teszor = get_teszor(desc)
                    if teszor == "52.21.24": teszor = "51.21.24" 
                    netto = get_netto(current_prices)
                    teszorok[teszor] = teszorok.get(teszor, 0.0) + netto
                break

            if sor.startswith("Mobil hívószám") or is_noise_line(sor):
                continue

            if ar_minta.match(sor):
                current_prices.append(sor)
            else:
                if current_prices:
                    desc = " ".join(current_desc_lines)
                    teszor = get_teszor(desc)
                    if teszor == "52.21.24": teszor = "51.21.24" 
                    netto = get_netto(current_prices)
                    teszorok[teszor] = teszorok.get(teszor, 0.0) + netto
                    
                    current_desc_lines = [sor]
                    current_prices = []
                else:
                    current_desc_lines.append(sor)
        
        t_61_20_12 = teszorok.get("61.20.12", 0.0)
        t_61_20_13 = teszorok.get("61.20.13", 0.0)
        t_61_20_14 = teszorok.get("61.20.14", 0.0)
        sum_3 = t_61_20_12 + t_61_20_13 + t_61_20_14
        sum_3_27 = sum_3 * 0.27
        
        t_61_20_30 = teszorok.get("61.20.30", 0.0)
        t_61_20_30_27 = t_61_20_30 * 0.27
        
        t_51_21_24 = teszorok.get("51.21.24", 0.0)
        t_51_21_24_27 = t_51_21_24 * 0.27
        
        t_62_09_20 = teszorok.get("62.09.20", 0.0)
        t_62_09_20_27 = t_62_09_20 * 0.27
        
        t_82_99_19 = teszorok.get("82.99.19", 0.0)
        t_82_99_19_27 = t_82_99_19 * 0.27
        
        t_61_20_42 = teszorok.get("61.20.42", 0.0)
        t_61_20_42_5 = t_61_20_42 * 0.05
        
        total_netto = sum_3 + t_61_20_30 + t_51_21_24 + t_82_99_19 + t_62_09_20 + t_61_20_42
        total_afa = sum_3_27 + t_61_20_30_27 + t_51_21_24_27 + t_82_99_19_27 + t_62_09_20_27 + t_61_20_42_5
        
        vegleges_sorok.append({
            "sorszám": sorszam, 
            "mobilszám": telefonszam, 
            "61.20.12 : 27%-os nettó (Ft)": round(t_61_20_12, 2), 
            "61.20.13 : 27%-os nettó (Ft)": round(t_61_20_13, 2), 
            "61.20.14 : 27%-os nettó (Ft)": round(t_61_20_14, 2), 
            "27%-os rész nettó (Ft)": round(sum_3, 2), 
            "27% ÁFA Összesített": round(sum_3_27, 2), 
            "61.20.30 : 27%-os nettó (Ft)": round(t_61_20_30, 2), 
            "27% ÁFA 61.20.30": round(t_61_20_30_27, 2), 
            "51.21.24 : 27%-os nettó (Ft)": round(t_51_21_24, 2), 
            "27% ÁFA 51.21.24": round(t_51_21_24_27, 2), 
            "62.09.20 : 27%-os nettó (Ft)": round(t_62_09_20, 2),
            "27% ÁFA 62.09.20": round(t_62_09_20_27, 2),
            "82.99.19 : 27%-os nettó (Ft)": round(t_82_99_19, 2), 
            "27% ÁFA 82.99.19": round(t_82_99_19_27, 2),            
            "61.20.42 : 5%-os nettó (Ft)": round(t_61_20_42, 2), 
            "5% ÁFA 61.20.42": round(t_61_20_42_5, 2), 
            "Összes nettó (Ft)": round(total_netto, 2), 
            "Összes ÁFA (Ft)": round(total_afa, 2), 
            "Összes bruttó (Ft)": round(total_netto + total_afa, 2) 
        })
        sorszam += 1

    acclev_netto = get_acclev_netto(szoveg)
    if acclev_netto > 0:
        sum_3_27 = acclev_netto * 0.27
        vegleges_sorok.append({
            "sorszám": sorszam, 
            "mobilszám": "számlakészítési díj", 
            "61.20.12 : 27%-os nettó (Ft)": round(acclev_netto, 2), 
            "61.20.13 : 27%-os nettó (Ft)": 0.0, 
            "61.20.14 : 27%-os nettó (Ft)": 0.0, 
            "27%-os rész nettó (Ft)": round(acclev_netto, 2), 
            "27% ÁFA Összesített": round(sum_3_27, 2), 
            "61.20.30 : 27%-os nettó (Ft)": 0.0, 
            "27% ÁFA 61.20.30": 0.0, 
            "51.21.24 : 27%-os nettó (Ft)": 0.0, 
            "27% ÁFA 51.21.24": 0.0, 
            "62.09.20 : 27%-os nettó (Ft)": 0.0,
            "27% ÁFA 62.09.20": 0.0,
            "82.99.19 : 27%-os nettó (Ft)": 0.0, 
            "27% ÁFA 82.99.19": 0.0,            
            "61.20.42 : 5%-os nettó (Ft)": 0.0, 
            "5% ÁFA 61.20.42": 0.0, 
            "Összes nettó (Ft)": round(acclev_netto, 2), 
            "Összes ÁFA (Ft)": round(sum_3_27, 2), 
            "Összes bruttó (Ft)": round(acclev_netto + sum_3_27, 2) 
        })
        
    df_vegleges = pd.DataFrame(vegleges_sorok)

    osszesen_sor = {col: "" for col in df_vegleges.columns}
    utolso_3_oszlop = df_vegleges.columns[-3:]
            
    for col in utolso_3_oszlop:
        osszesen_sor[col] = round(df_vegleges[col].sum(), 2)

    df_vegleges = pd.concat([df_vegleges, pd.DataFrame([osszesen_sor])], ignore_index=True)

    df_vegleges.to_excel(kimenet_fajlnev, index=False, sheet_name='Összesítő')
    print(f"✅ SIKER! Az Excel táblázat elkészült és elmentve ide: {kimenet_fajlnev}\n")


# =====================================================================
# STREAMLIT FELÜLET
# =====================================================================

st.set_page_config(page_title="Telekom Számla Feldolgozó", layout="centered")

st.markdown("<h1 style='text-align: center;'>📄 Telekom Számla Feldolgozó</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Töltsd fel a számlát .pdf formátumban a feldolgozás megkezdéséhez.</p>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Számla feltöltése (.pdf)", type=["pdf"])

if uploaded_file is not None:
    # JAVÍTÁS 2: width="stretch" használata a deprecation warning miatt
    if st.button("🚀 Feldolgozás indítása", width="stretch"):
        with st.spinner("Feldolgozás folyamatban..."):
            
            temp_txt_filename = "kivont_szoveg.txt"
            temp_output_filename = "kigeneralt_osszesito.xlsx"
            
            # 1. JAVÍTÁS: A V3-as kódodból ismert, jól működő PyMuPDF (fitz) használata!
            try:
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                kivont_szoveg = ""
                for page in doc:
                    kivont_szoveg += page.get_text() + "\n"
                        
                # A kinyert szöveget elmentjük a .txt fájlba a feldolgozónak
                with open(temp_txt_filename, "w", encoding="utf-8") as f:
                    f.write(kivont_szoveg)
                    
            except Exception as e:
                st.error(f"Hiba a PDF beolvasása során: {e}")
                st.stop()
                
            # 2. A feldolgozó függvény meghívása a generált TXT fájlra
            try:
                export_to_excel(temp_txt_filename, kimenet_fajlnev=temp_output_filename)
                
                if os.path.exists(temp_output_filename):
                    st.success("✅ A feldolgozás sikeresen befejeződött!")
                    
                    df_eredmeny = pd.read_excel(temp_output_filename)
                    st.subheader("📊 Eredmények előnézete")
                    # JAVÍTÁS 2: width="stretch"
                    st.dataframe(df_eredmeny, width="stretch")
                    
                    with open(temp_output_filename, "rb") as f:
                        excel_data = f.read()
                        
                    # JAVÍTÁS 2: width="stretch"
                    st.download_button(
                        label="📥 Elkészült fájl letöltése Excelben",
                        data=excel_data,
                        file_name="telekom_szamla_osszesito.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch"
                    )
                else:
                    st.error("❌ Hiba történt: Nem jött létre az Excel fájl.")
                    
            except Exception as e:
                st.error(f"❌ Váratlan hiba történt a feldolgozás során: {e}")
                
            # 3. Takarítás (az ideiglenes fájlokat töröljük)
            finally:
                for temp_file in [temp_txt_filename, temp_output_filename]:
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
