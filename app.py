# Csak ha digitális a PDF akkor működik ez a kód! Ha a PDF szkennelt, akkor OCR-re van szükség.

import streamlit as st
import fitz
import time
import re
import pandas as pd
import io

# --- STREAMLIT FELÜLET BEÁLLÍTÁSA (Középre zárt elrendezés) ---
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

            # --- 2. Szövegkereső rész (Új, robusztus logika) ---
            adatok = []
            aktualis_telefon = None
            aktualis_teszor = "61.20.12" # Alapértelmezett, ha nincs más
            
            # Reguláris kifejezések az árakhoz és mértékegységekhez
            ar_pattern = r'-?\d{1,3}(?:\.\d{3})*,\d{2}'
            mertekegyseg_pattern = r'\b(hó|db|p:mp|perc|%|10kbyte|alk\.)\b'

            # Végigmegyünk a sorokon (indexelve, hogy lássuk a következőt is, többsoros tételek miatt)
            i = 0
            while i < len(sorok):
                sor = sorok[i].strip()
                if not sor:
                    i += 1
                    continue
                
                # Ugrás a szükségtelen fejléc sorokon
                if "mennyiség" in sor or "egység nettó egységár" in sor:
                    i += 1
                    continue

                # 1. Telefon vagy folyószámla beállítása
                tel_match = re.search(r'Mobil hívószám\s*(\(\d+\)\s*\d+)', sor)
                if tel_match:
                    aktualis_telefon = tel_match.group(1)
                    aktualis_teszor = "61.20.12" # Reset
                    i += 1
                    continue
                
                if "ACCLEVCONTR" in sor:
                    acc_match = re.search(r'ACCLEVCONTR\s*(\d+)', sor)
                    if acc_match:
                        aktualis_telefon = "Folyószámla: " + acc_match.group(1)
                        aktualis_teszor = "61.20.12" # Reset
                    i += 1
                    continue

                # Ha még nem találtunk telefont, a sor nem releváns a tételek szempontjából
                if nem aktualis_telefon:
                    i += 1
                    continue
                
                # Ha elértük az összesítőt (a hívószám végét), töröljük a fókuszban lévő telefont
                if "Utólag" in sor and "összesen" in sor:
                    aktualis_telefon = None
                    i += 1
                    continue

                # 2. TESZOR kód blokk beállítása (pl. "SMS küldés (TESZOR 61.20.13)")
                # Sokszor a blokk címe tartalmazza a TESZOR-t, ami az alatta lévő sorokra (pl. "SMS Yettel") is igaz.
                blokk_teszor_match = re.search(r'\(TESZOR\s*([\d\.]+)\)', sor)
                if blokk_teszor_match and not re.search(mertekegyseg_pattern, sor) and not re.search(ar_pattern, sor):
                    # Ez csak egy cím, elmentjük az aktív TESZOR-t
                    aktualis_teszor = blokk_teszor_match.group(1)
                    i += 1
                    continue
                elif "Előfizetési díjak" in sor and "TESZOR" not in sor:
                    aktualis_teszor = "61.20.12" # Alap előfizetési blokk

                # 3. Tétel felismerése és kinyerése
                # A tétel onnan ismerhető fel, hogy van benne mértékegység és ár (vagy a következő sorban van az ár)
                has_mertekegyseg = re.search(mertekegyseg_pattern, sor)
                arak_sorban = re.findall(ar_pattern, sor)
                
                kovetkezo_sor = sorok[i+1].strip() if i+1 < len(sorok) else ""
                next_has_mertekegyseg = re.search(mertekegyseg_pattern, kovetkezo_sor)
                arak_kovetkezoben = re.findall(ar_pattern, kovetkezo_sor)

                # Megnézzük, van-e a tételsorban (vagy a kétsoros tétel első sorában) specifikus TESZOR
                targy_teszor = aktualis_teszor
                sor_teszor_match = re.search(r'TESZOR\s*([\d\.]+)', sor)
                if sor_teszor_match:
                    targy_teszor = sor_teszor_match.group(1)

                netto_ar = None
                
                # Eset A: A mértékegység és az ár is egy sorban van
                if has_mertekegyseg and arak_sorban:
                    # Rendszerint 3 ár van: (egységár, nettó, bruttó). A nettó az utolsó előtti.
                    if len(arak_sorban) >= 3:
                        netto_ar = arak_sorban[-2]
                    # Ha csak 2 ár van (pl. kedvezmény), akkor a nettó az első.
                    elif len(arak_sorban) == 2:
                        netto_ar = arak_sorban[0]
                    # Ha csak 1 ár van
                    elif len(arak_sorban) == 1:
                        netto_ar = arak_sorban[0]
                
                # Eset B: A sor csak szöveg, de a KÖVETKEZŐ sorban ott a mértékegység és az ár (Többsoros tétel)
                elif not has_mertekegyseg and not arak_sorban and next_has_mertekegyseg and arak_kovetkezoben:
                    if len(arak_kovetkezoben) >= 3:
                        netto_ar = arak_kovetkezoben[-2]
                    elif len(arak_kovetkezoben) == 2:
                        netto_ar = arak_kovetkezoben[0]
                    elif len(arak_kovetkezoben) == 1:
                        netto_ar = arak_kovetkezoben[0]
                    # Mivel feldolgoztuk a következő sort is, azt átugorhatjuk a ciklusban
                    i += 1 

                if netto_ar:
                    # Beletesszük a listába (még akkor is, ha 0,00, a szummánál nem zavar)
                    adatok.append({
                        "Telefonszám": aktualis_telefon,
                        "TESZOR": targy_teszor,
                        "Nettó Ár": netto_ar
                    })
                
                i += 1


            # --- 3. ADATOK ÖSSZEGZÉSE ÉS SOROKBA RENDEZÉSE (Dinamikus) ---
            telefon_osszesito = {}
            osszes_talalt_teszor = set()

            for adat in adatok:
                tel = adat["Telefonszám"]
                teszor = adat["TESZOR"]
                netto_str = str(adat["Nettó Ár"])
                
                if tel not in telefon_osszesito:
                    telefon_osszesito[tel] = {}
                    
                try:
                    tisztitott = netto_str.replace('.', '').replace(',', '.')
                    netto_ertek = float(tisztitott)
                except ValueError:
                    netto_ertek = 0.0

                if teszor not in telefon_osszesito[tel]:
                    telefon_osszesito[tel][teszor] = 0.0
                
                telefon_osszesito[tel][teszor] += netto_ertek
                osszes_talalt_teszor.add(teszor)

            # Rendezzük a TESZOR kódokat (pl. 61.20.12 legyen elöl)
            osszes_talalt_teszor = sorted(list(osszes_talalt_teszor))

            # Az 5%-os áfakulcs alá tartozó TESZOR kódok (a Telekomnál jellemzően a 61.20.42, 61.20.43)
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
                
                for t_kod in osszes_talalt_teszor:
                    netto_ertek = teszorok.get(t_kod, 0.0)
                    
                    if t_kod in afa_5_teszorok:
                        afa_kulcs = "5%"
                        netto_5_osszesen += netto_ertek
                    else:
                        afa_kulcs = "27%"
                        netto_27_osszesen += netto_ertek
                        
                    sor_adat[f"TESZOR {t_kod} ({afa_kulcs}) nettó (Ft)"] = round(netto_ertek, 2)
                
                # Fő aggregátumok
                sor_adat["Összes 27% ÁFÁ-s nettó (Ft)"] = round(netto_27_osszesen, 2)
                sor_adat["27% ÁFA (Ft)"] = round(netto_27_osszesen * 0.27, 2)
                
                sor_adat["Összes 5% ÁFÁ-s nettó (Ft)"] = round(netto_5_osszesen, 2)
                sor_adat["5% ÁFA (Ft)"] = round(netto_5_osszesen * 0.05, 2)
                
                # Mindösszesen
                osszes_netto = netto_27_osszesen + netto_5_osszesen
                osszes_afa = (netto_27_osszesen * 0.27) + (netto_5_osszesen * 0.05)
                
                sor_adat["Mindösszesen nettó (Ft)"] = round(osszes_netto, 2)
                sor_adat["Mindösszesen ÁFA (Ft)"] = round(osszes_afa, 2)
                sor_adat["Mindösszesen bruttó (Ft)"] = round(osszes_netto + osszes_afa, 2)

                vegleges_sorok.append(sor_adat)
                sorszam += 1

            # --- 4. EXCEL EXPORTÁLÁS ---
            df_vegleges = pd.DataFrame(vegleges_sorok)

            # Legalsó "Összesen" sor hozzáadása
            osszesen_sor = {col: "" for col in df_vegleges.columns}
            osszesen_sor["Mobilszám / Folyószámla"] = "ÖSSZESEN"
            
            # Minden oszlopot összegzünk, ami a 3. oszloptól (a számoktól) kezdődik
            for col in df_vegleges.columns[2:]:
                osszesen_sor[col] = round(df_vegleges[col].sum(), 2)

            df_vegleges = pd.concat([df_vegleges, pd.DataFrame([osszesen_sor])], ignore_index=True)

            time_end = time.time()
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_vegleges.to_excel(writer, index=False, sheet_name='Összesítő')
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.success(f"Feldolgozás kész! (Futási idő: {time_end - time_start:.2f} másodperc)")
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
