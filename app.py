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
            
            # PDF megnyitása és szöveg kinyerése
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            
            teljes_szoveg = ""
            for page in doc:
                teljes_szoveg += page.get_text() + "\n"
            
            sorok = teljes_szoveg.splitlines()

            # --- ÚJ, ROBUSTUSABB ÁLLAPOTGÉP ---
            adatok = []
            aktualis_telefon = None
            aktualis_teszor = "61.20.12" # Alapértelmezett TESZOR
            
            in_data_block = False
            current_block_numbers = []
            
            def process_block(nums, phone, teszor):
                """Feldolgozza az összegyűjtött árakat tartalmazó blokkot"""
                if not phone or len(nums) < 2:
                    return
                    
                # Az utolsó előtti szám mindig a nettó összeg, az utolsó a bruttó
                netto_str = nums[-2]
                brutto_str = nums[-1]
                
                # Számtisztító belső függvény
                def to_float(val_str):
                    m = re.search(r'([.,])(\d{2})$', val_str)
                    if m:
                        base = val_str[:m.start()].replace('.', '').replace(',', '')
                        dec = m.group(2)
                        return float(f"{base}.{dec}")
                    return 0.0
                    
                netto_val = to_float(netto_str)
                brutto_val = to_float(brutto_str)
                
                # PDF olvasási hiba javítása: Ha a bruttó mínuszos, de a nettón nincs mínusz jel
                if brutto_val < 0 and netto_val > 0:
                    netto_val = -netto_val
                    
                adatok.append({
                    "Telefonszám": phone,
                    "TESZOR": teszor,
                    "Nettó Ár": netto_val
                })

            for line in sorok:
                line = line.strip()
                
                # Ha véget ért az adatsor-blokk (nem '|'-al kezdődik), feldolgozzuk az addigi számokat
                if not line.startswith('|') and in_data_block:
                    process_block(current_block_numbers, aktualis_telefon, aktualis_teszor)
                    current_block_numbers = []
                    in_data_block = False
                    
                # Hívószám összegzésének vége -> új telefonszámot várunk
                if "Utólag" in line and "összesen" in line:
                    aktualis_telefon = None
                    continue
                    
                # Új telefonszám felismerése
                m = re.search(r'Mobil hívószám\s*(\(\d+\)\s*\d+)', line)
                if m:
                    aktualis_telefon = m.group(1).replace(' ', '')
                    aktualis_teszor = "61.20.12"
                    continue
                    
                if not aktualis_telefon:
                    continue
                    
                # Alapértelmezett 27%-os szolgáltatások visszakényszerítése, hogy ne örököljék az 5%-os Adat TESZOR-t
                if "e-Pack" in line or "Mobil telefon szolg." in line or "Előfizetési díj kedvezmények" in line:
                    aktualis_teszor = "61.20.12"
                    
                # Egyedi TESZOR kiolvasása az adott sorból
                m_teszor = re.search(r'TESZOR\s*([\d\.]+)', line)
                if m_teszor:
                    val = m_teszor.group(1)
                    if val == "61.20.121": val = "61.20.12" # Esetleges OCR/PDF elírás javítása
                    aktualis_teszor = val
                    
                # Értékek (árak) begyűjtése a '|' jellel kezdődő sorokból
                if line.startswith('|'):
                    in_data_block = True
                    # Elnézőbb regex, amely pontot és vesszőt is elfogad ezres/tizedes elválasztóként
                    prices = re.findall(r'-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2}', line)
                    current_block_numbers.extend(prices)

            # Az utolsó blokk feldolgozása a fájl végén, ha nyitva maradt
            if in_data_block:
                process_block(current_block_numbers, aktualis_telefon, aktualis_teszor)

            # --- ADATOK ÖSSZEGZÉSE ÉS DATAFRAME GENERÁLÁSA ---
            telefon_osszesito = {}

            for adat in adatok:
                tel = adat["Telefonszám"]
                teszor = adat["TESZOR"]
                netto_ertek = adat["Nettó Ár"]
                
                if tel not in telefon_osszesito:
                    telefon_osszesito[tel] = {}
                    
                if teszor not in telefon_osszesito[tel]:
                    telefon_osszesito[tel][teszor] = 0.0
                
                telefon_osszesito[tel][teszor] += netto_ertek

            vegleges_sorok = []
            sorszam = 1

            for tel, teszorok in telefon_osszesito.items():
                
                # 27% ÁFA körbe tartozó szolgáltatások
                t_61_20_12 = teszorok.get("61.20.12", 0.0)
                t_61_20_13 = teszorok.get("61.20.13", 0.0)
                t_61_20_14 = teszorok.get("61.20.14", 0.0)
                t_61_20_30 = teszorok.get("61.20.30", 0.0)
                t_52_21_24 = teszorok.get("52.21.24", 0.0) # Eredeti kódban hibásan 51.21.24 szerepelt
                t_62_09_20 = teszorok.get("62.09.20", 0.0) # Parkolás-Extra szolgáltatások
                t_82_99_19 = teszorok.get("82.99.19", 0.0) # Üzleti MultiSIM
                
                # 5% ÁFA körbe tartozó szolgáltatások (Mobil adat)
                t_61_20_42 = teszorok.get("61.20.42", 0.0)
                t_61_20_42_5 = t_61_20_42 * 0.05
                
                # 27%-os részösszegek
                all_27_netto = t_61_20_12 + t_61_20_13 + t_61_20_14 + t_61_20_30 + t_52_21_24 + t_62_09_20 + t_82_99_19
                all_27_afa = all_27_netto * 0.27
                
                osszes_netto = all_27_netto + t_61_20_42
                osszes_afa = all_27_afa + t_61_20_42_5
                
                vegleges_sorok.append({
                    "sorszám": sorszam, 
                    "mobilszám": tel, 
                    "61.20.12 : 27%-os nettó (Ft)": round(t_61_20_12, 2), 
                    "61.20.13 : 27%-os nettó (Ft)": round(t_61_20_13, 2), 
                    "61.20.14 : 27%-os nettó (Ft)": round(t_61_20_14, 2), 
                    "61.20.30 : 27%-os nettó (Ft)": round(t_61_20_30, 2), 
                    "52.21.24 : 27%-os nettó (Ft)": round(t_52_21_24, 2), 
                    "62.09.20 : 27%-os nettó (Ft)": round(t_62_09_20, 2),
                    "82.99.19 : 27%-os nettó (Ft)": round(t_82_99_19, 2),
                    "Összes 27% Nettó (Ft)": round(all_27_netto, 2), 
                    "Összes 27% ÁFA (Ft)": round(all_27_afa, 2), 
                    "61.20.42 : 5%-os nettó (Ft)": round(t_61_20_42, 2), 
                    "5% ÁFA 61.20.42 (Ft)": round(t_61_20_42_5, 2), 
                    "Összes nettó (Ft)": round(osszes_netto, 2), 
                    "Összes ÁFA (Ft)": round(osszes_afa, 2), 
                    "Összes bruttó (Ft)": round(osszes_netto + osszes_afa, 2) 
                })
                sorszam += 1

            df_vegleges = pd.DataFrame(vegleges_sorok)

            if not df_vegleges.empty:
                osszesen_sor = {col: "" for col in df_vegleges.columns}
                osszesen_sor["mobilszám"] = "ÖSSZESEN"
                
                # Oszlopok összegzése a 'mobilszám' és 'sorszám' oszlopok kihagyásával
                for col in df_vegleges.columns[2:]:
                    osszesen_sor[col] = round(df_vegleges[col].sum(), 2)

                # Modern, Warning nélküli sor hozzáadás DataFrame-hez
                df_vegleges = pd.concat([df_vegleges, pd.DataFrame([osszesen_sor])], ignore_index=True)

            time_end = time.time()
            
            # --- EXCEL EXPORT ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_vegleges.to_excel(writer, index=False, sheet_name='Összesítő')
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.success(f"Feldolgozás kész! (Futási idő: {time_end - time_start:.2f} másodperc)")
            st.dataframe(df_vegleges, use_container_width=True)
            
            # Letöltő gomb középre igazítása
            dl_col1, dl_col2, dl_col3 = st.columns([1, 2, 1])
            with dl_col2:
                st.download_button(
                    label="📥 Eredmény letöltése Excel (.xlsx) fájlként",
                    data=buffer.getvalue(),
                    file_name="telekom_szamla_osszesito.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
