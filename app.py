# Csak ha digitális a PDF akkor működik ez a kód! Ha a PDF szkennelt, akkor OCR-re van szükség.

import streamlit as st
import fitz
import time
import re
import pandas as pd
import io

# --- STREAMLIT FELÜLET BEÁLLÍTÁSA ---
st.set_page_config(page_title="Telekom Számlafeldolgozó", layout="centered")

st.markdown("<h1 style='text-align: center;'>📄 Telekom Számlafeldolgozó</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Töltsd fel a digitális Telekom PDF számlát, majd kattints a feldolgozás gombra!</p>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Telekom számla feltöltése (PDF)", type=["pdf"])

if uploaded_file is not None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        start_button = st.button("🚀 Számla feldolgozása", use_container_width=True)

    if start_button:
        with st.spinner("Számla feldolgozása folyamatban..."):
            time_start = time.time()
            
            # --- 1. Szövegkiolvasó rész ---
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            
            teljes_szoveg = ""
            for page in doc:
                teljes_szoveg += page.get_text() + "\n"
            
            sorok = teljes_szoveg.splitlines()

            # --- 2. Szövegkereső rész ---
            adatok = []
            aktualis_telefon = None
            aktualis_teszor = "61.20.12" 
            
            # Regex minták a mértékegységekhez és árakhoz
            unit_pattern = r'^(hó|hỏ|db|p:mp|perc|%|10kbyte|alk\.)(.*)$'
            ar_pattern_nyers = r'-?\d{1,3}(?:[\.\s]\d{3})*[,.]\d{2}'

            i = 0
            while i < len(sorok):
                sor = sorok[i].strip()
                if not sor:
                    i += 1
                    continue
                
                # Fejlécek és zajszűrés
                if "mennyiség" in sor or "egység nettó egységár" in sor:
                    i += 1
                    continue

                # 1. Telefon azonosítása (visszatérve a Te eredeti, jól bevált split-es megoldásodra!)
                if "Mobil hívószám" in sor:
                    parts = sor.split("Mobil hívószám")
                    if len(parts) > 1:
                        aktualis_telefon = parts[1].strip()
                    aktualis_teszor = "61.20.12" 
                    i += 1
                    continue
                
                # 1/B. Folyószámla szintű tételek bekérése (pl. ACCLEVCONTR)
                if "ACCLEVCONTR" in sor:
                    parts = sor.split("ACCLEVCONTR")
                    if len(parts) > 1:
                        aktualis_telefon = "Folyószámla: " + parts[1].strip()
                    aktualis_teszor = "61.20.12"
                    i += 1
                    continue

                # Ha nem tudjuk kihez tartozik a tétel, ugrunk
                if not aktualis_telefon:
                    i += 1
                    continue
                
                # Adott telefonszám blokkjának lezárása
                if "Utólag" in sor and "összesen" in sor:
                    aktualis_telefon = None
                    i += 1
                    continue

                # 2. TESZOR kód frissítése a blokk fejlécéből
                blokk_teszor_match = re.search(r'\(TESZOR\s*([\d\.]+)\)', sor)
                if blokk_teszor_match:
                    aktualis_teszor = blokk_teszor_match.group(1)
                elif "Előfizetési díjak" in sor and "TESZOR" not in sor:
                    aktualis_teszor = "61.20.12"

                # 3. Tétel felismerése a mértékegység alapján
                if re.match(unit_pattern, sor):
                    targy_teszor = aktualis_teszor
                    
                    # Visszanézünk 1-4 sort, hátha van egyedi TESZOR (pl. mobil parkolásnál)
                    for back_j in range(1, 5):
                        if i - back_j >= 0:
                            prev_line = sorok[i - back_j].strip()
                            explicit_teszor_match = re.search(r'TESZOR\s*([\d\.]+)', prev_line)
                            if explicit_teszor_match:
                                targy_teszor = explicit_teszor_match.group(1)
                                break
                    
                    # Előrenézünk az árakért a következő sorokban
                    prices = []
                    for j in range(1, min(6, len(sorok) - i)):
                        next_line = sorok[i+j].strip()
                        talalatok = re.findall(ar_pattern_nyers, next_line)
                        
                        if talalatok:
                            prices.extend(talalatok)
                        elif next_line and len(next_line) > 3 and not re.match(r'^\d+[,.]\d+$', next_line):
                            break # Ha már szöveg jön ár helyett, megszakítjuk
                            
                    if prices:
                        # Általában 3 ár van (Egységár, Nettó, Bruttó). A nettó az utolsó előtti. 
                        # Ha csak 2 ár van (pl. kedvezmény), akkor az első a nettó.
                        if len(prices) >= 3:
                            netto_ar = prices[-2]
                        else:
                            netto_ar = prices[0]
                            
                        adatok.append({
                            "Telefonszám": aktualis_telefon,
                            "TESZOR": targy_teszor,
                            "Nettó Ár": netto_ar
                        })
                
                i += 1


            # --- 3. ADATOK ÖSSZEGZÉSE (Dinamikus) ---
            telefon_osszesito = {}
            osszes_talalt_teszor = set()

            for adat in adatok:
                tel = adat["Telefonszám"]
                teszor = adat["TESZOR"]
                netto_str = str(adat["Nettó Ár"])
                
                if tel not in telefon_osszesito:
                    telefon_osszesito[tel] = {}
                    
                # Szám formázása okosan (elírt tizedespontok és szóközök kezelése a Telekom PDF-ből)
                try:
                    p = re.sub(r'\s+', '', netto_str)
                    match = re.search(r'[,.](\d{2})$', p)
                    if match:
                        p_no_decimals = p[:-3].replace('.', '').replace(',', '')
                        netto_ertek = float(p_no_decimals + '.' + match.group(1))
                    else:
                        netto_ertek = float(p.replace('.', '').replace(',', ''))
                except ValueError:
                    netto_ertek = 0.0

                if teszor not in telefon_osszesito[tel]:
                    telefon_osszesito[tel][teszor] = 0.0
                
                telefon_osszesito[tel][teszor] += netto_ertek
                osszes_talalt_teszor.add(teszor)

            # Rendezzük az oszlopokat (hogy a 61.20.12 kerüljön előre)
            osszes_talalt_teszor = sorted(list(osszes_talalt_teszor))
            afa_5_teszorok = ["61.20.42", "61.20.43"]

            vegleges_sorok = []
            sorszam = 1

            for tel, teszorok in telefon_osszesito.items():
                sor_adat = {
                    "Sorszám": sorszam,
                    "Mobilszám / Folyószámla": tel
                }
                
                netto_27_osszesen = 0.0
                netto_5_osszesen = 0.0
                
                # Dinamikusan létrehozzuk az oszlopokat az összes megtalált TESZOR alapján
                for t_kod in osszes_talalt_teszor:
                    netto_ertek = teszorok.get(t_kod, 0.0)
                    
                    if t_kod in afa_5_teszorok:
                        afa_kulcs = "5%"
                        netto_5_osszesen += netto_ertek
                    else:
                        afa_kulcs = "27%"
                        netto_27_osszesen += netto_ertek
                        
                    sor_adat[f"TESZOR {t_kod} ({afa_kulcs}) nettó (Ft)"] = round(netto_ertek, 2)
                
                # Fő aggregátumok számítása a kerekítési hibák elkerülése végett
                sor_adat["Összes 27% ÁFÁ-s nettó (Ft)"] = round(netto_27_osszesen, 2)
                sor_adat["27% ÁFA (Ft)"] = round(netto_27_osszesen * 0.27, 2)
                
                sor_adat["Összes 5% ÁFÁ-s nettó (Ft)"] = round(netto_5_osszesen, 2)
                sor_adat["5% ÁFA (Ft)"] = round(netto_5_osszesen * 0.05, 2)
                
                osszes_netto = netto_27_osszesen + netto_5_osszesen
                osszes_afa = (netto_27_osszesen * 0.27) + (netto_5_osszesen * 0.05)
                
                sor_adat["Mindösszesen nettó (Ft)"] = round(osszes_netto, 2)
                sor_adat["Mindösszesen ÁFA (Ft)"] = round(osszes_afa, 2)
                sor_adat["Mindösszesen bruttó (Ft)"] = round(osszes_netto + osszes_afa, 2)

                vegleges_sorok.append(sor_adat)
                sorszam += 1

            # --- 4. EXCEL EXPORTÁLÁS ---
            if not vegleges_sorok:
                st.error("❌ Nem találtam feldolgozható adatot a számlában! Győződj meg róla, hogy helyes PDF-et töltöttél fel.")
            else:
                df_vegleges = pd.DataFrame(vegleges_sorok)

                # Legalsó "Összesen" sor hozzáadása
                osszesen_sor = {col: "" for col in df_vegleges.columns}
                osszesen_sor["Mobilszám / Folyószámla"] = "ÖSSZESEN"
                
                # Az oszlopok szummázása a számadatoknál
                for col in df_vegleges.columns[2:]:
                    osszesen_sor[col] = round(df_vegleges[col].sum(), 2)

                df_vegleges = pd.concat([df_vegleges, pd.DataFrame([osszesen_sor])], ignore_index=True)

                time_end = time.time()
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_vegleges.to_excel(writer, index=False, sheet_name='Összesítő')
                
                st.markdown("<br>", unsafe_allow_html=True)
                st.success(f"✅ Feldolgozás kész! {sorszam-1} telefonszám/folyószámla tétele feldolgozva. (Futási idő: {time_end - time_start:.2f} másodperc)")
                st.dataframe(df_vegleges, use_container_width=True)
                
                dl_col1, dl_col2, dl_col3 = st.columns([1, 2, 1])
                with dl_col2:
                    st.download_button(
                        label="📥 Eredmény letöltése Excel (.xlsx) fájlként",
                        data=buffer.getvalue(),
                        file_name="telekom_szamla_osszesito.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
