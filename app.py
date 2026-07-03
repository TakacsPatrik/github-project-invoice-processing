# Csak ha digitális a PDF akkor működik ez a kód! Ha a PDF szkennelt, akkor OCR-re van szükség.

import streamlit as st
import fitz
import time
import re
import pandas as pd
import io

# --- STREAMLIT FELÜLET BEÁLLÍTÁSA (Középre zárt elrendezés) ---
st.set_page_config(page_title="Telekom Számlafeldolgozó", layout="centered")

# Szövegek középre igazítása HTML formázással
st.markdown("<h1 style='text-align: center;'>📄 Telekom Számlafeldolgozó</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Töltsd fel a digitális Telekom PDF számlát, majd kattints a feldolgozás gombra!</p>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True) # Egy kis térköz

# Fájlfeltöltő modul
uploaded_file = st.file_uploader("Telekom számla feltöltése (PDF)", type=["pdf"])

if uploaded_file is not None:
    # A gomb középre igazítása oszlopok segítségével
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        start_button = st.button("🚀 Számla feldolgozása", use_container_width=True)

    if start_button:
        with st.spinner("Számla feldolgozása folyamatban..."):
            time_start = time.time() # időmérés kezdete
            
            #############################################
            # Szövegkiolvasó rész
            #############################################
            
            # PDF megnyitása a feltöltött fájlból (memóriából)
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            
            teljes_szoveg = ""
            for page in doc:
                text = page.get_text()
                teljes_szoveg += text + "\n"
            
            # A korábbi txt fájl soronkénti olvasásának szimulálása
            sorok = teljes_szoveg.splitlines(True)

            ###############################################
            # Szövegkereső rész (AZ EREDETI LOGIKÁD JAVÍTÁSA)
            ###############################################

            adatok = []
            aktualis_telefon = None

            # --- ÁLLAPOTGÉP VÁLTOZÓI ---
            forgalmi_blokkban_vagyunk = False
            forgalmi_netto_osszeg = 0.0
            aktualis_forgalmi_teszor = "61.20.42" 

            for i in range(len(sorok)):
                sor = sorok[i].strip()

                if "mennyiség" in sor or "egység" in sor or "Szolgáltatás TESZOR" in sor:
                    continue
                
                # JAVÍTÁS: A split megtartása mellett re.sub-bal kikapjuk a belső felesleges szóközöket a hívószámból
                if "Mobil hívószám" in sor:
                    nyers_szam = sor.split("Mobil hívószám")[1].strip()
                    aktualis_telefon = re.sub(r'\s+', '', nyers_szam)
                    continue 
                
                # JAVÍTÁS: Folyószámla szintű tételek (pl. EFT központi díj) beemelése
                if "ACCLEVCONTR" in sor:
                    aktualis_telefon = "Folyószámla: " + sor.split("ACCLEVCONTR")[1].strip()
                    continue
                
                if aktualis_telefon is None:
                    continue
                
                if "Forgalmi díjak - M2M NG" in sor:
                    forgalmi_blokkban_vagyunk = True
                    forgalmi_netto_osszeg = 0.0
                    continue

                if "Forgalmi díj kedvezmények" in sor:
                    if forgalmi_blokkban_vagyunk:
                        formazott_osszeg = f"{forgalmi_netto_osszeg:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        adatok.append({
                            "Sorszám": len(adatok) + 1,
                            "Telefonszám": aktualis_telefon,
                            "TESZOR": aktualis_forgalmi_teszor,
                            "Nettó Ár": formazott_osszeg
                        })
                    forgalmi_blokkban_vagyunk = False

                if forgalmi_blokkban_vagyunk:
                    if "TESZOR" in sor:
                        teszor_match = re.search(r'TESZOR\s*([\d\.]+)', sor)
                        if teszor_match:
                            aktualis_forgalmi_teszor = teszor_match.group(1)
                    
                    if sor == "10kbyte":
                        if i + 2 < len(sorok):
                            netto_szam_str = sorok[i + 2].strip()
                            match = re.search(r'-?\d{1,3}(?:\.\d{3})*,\d{2}', netto_szam_str)
                            if match:
                                tisztitott_szam = match.group(0).replace('.', '').replace(',', '.')
                                try:
                                    forgalmi_netto_osszeg += float(tisztitott_szam)
                                except ValueError:
                                    pass
                    continue 

                # JAVÍTÁS: Kibővítettük a kulcsszavakat, hogy az SMS és MMS sorok árait se ugorja át a kódod
                keresett_nevek = ["TESZOR", "Mobil telefon szolg.", "Vállalati e-Pack kedvezmény", "SMS", "MMS", "Parkolás", "Tájékoztató"]
                megnevezes = next((nev for nev in keresett_nevek if nev in sor), None)

                if megnevezes:    
                    teszor_match = re.search(r'TESZOR\s*([\d\.]+)', sor)
                    teszor_szam = teszor_match.group(1) if teszor_match else "61.20.12"

                    arak = []
                    for j in range(1, 12):
                        if i + j < len(sorok):
                            kovetkezo_sor = sorok[i + j].strip()
                            
                            if "Mobil hívószám" in kovetkezo_sor or ("Utólag" in kovetkezo_sor and "összesen" in kovetkezo_sor) or "ACCLEVCONTR" in kovetkezo_sor:
                                break
                            elif "TESZOR" in kovetkezo_sor:
                                if "mennyiség" in kovetkezo_sor or "egység" in kovetkezo_sor:
                                    continue 
                                else:
                                    break     
                            
                            talalatok = re.findall(r'-?\d{1,3}(?:\.\d{3})*[,.]\d{2}', kovetkezo_sor)
                            arak.extend(talalatok)

                    if len(arak) >= 3:
                        netto_ar = arak[1]  
                    elif len(arak) == 2:
                        netto_ar = arak[0]
                    elif len(arak) == 1:
                        netto_ar = arak[0]  
                    else:
                        netto_ar = f"Nem találom a Nettó árat, {len(arak)} ár található"

                    adatok.append({
                        "Sorszám": len(adatok) + 1,
                        "Telefonszám": aktualis_telefon,
                        "TESZOR": teszor_szam,
                        "Nettó Ár": netto_ar if netto_ar else "Nem található"
                    })

                if "Utólag" in sor and "összesen" in sor:
                    aktualis_telefon = None 

            ###############################################
            # ADATOK ÖSSZEGZÉSE ÉS SOROKBA RENDEZÉSE (AZ EREDETI EXCEL STRUKTÚRÁD)
            ###############################################

            telefon_osszesito = {}

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

            vegleges_sorok = []
            sorszam = 1

            for tel, teszorok in telefon_osszesito.items():
                
                t_61_20_12 = teszorok.get("61.20.12", 0.0)
                t_61_20_13 = teszorok.get("61.20.13", 0.0)
                t_61_20_14 = teszorok.get("61.20.14", 0.0)
                
                sum_3 = t_61_20_12 + t_61_20_13 + t_61_20_14
                sum_3_27 = sum_3 * 0.27
                
                t_61_20_30 = teszorok.get("61.20.30", 0.0)
                t_61_20_30_27 = t_61_20_30 * 0.27
                
                # JAVÍTÁS: 51.21.24 helyett a jó 52.21.24 kód használata
                t_52_21_24 = teszorok.get("52.21.24", 0.0)
                t_52_21_24_27 = t_52_21_24 * 0.27
                
                # JAVÍTÁS: Két új, számlán szereplő 27%-os TESZOR oszlop beemelése az összegek pontosságáért
                t_62_09_20 = teszorok.get("62.09.20", 0.0)
                t_62_09_20_27 = t_62_09_20 * 0.27
                
                t_82_99_19 = teszorok.get("82.99.19", 0.0)
                t_82_99_19_27 = t_82_99_19 * 0.27
                
                t_61_20_42 = teszorok.get("61.20.42", 0.0)
                t_61_20_42_5 = t_61_20_42 * 0.05
                
                # Összesítések kiszámítása
                mind_netto = sum_3 + t_61_20_30 + t_52_21_24 + t_62_09_20 + t_82_99_19 + t_61_20_42
                mind_afa = sum_3_27 + t_61_20_30_27 + t_52_21_24_27 + t_62_09_20_27 + t_82_99_19_27 + t_61_20_42_5

                vegleges_sorok.append({
                    "sorszám": sorszam, 
                    "mobilszám": tel, 
                    "61.20.12 : 27%-os nettó (Ft)": round(t_61_20_12, 2), 
                    "61.20.13 : 27%-os nettó (Ft)": round(t_61_20_13, 2), 
                    "61.20.14 : 27%-os nettó (Ft)": round(t_61_20_14, 2), 
                    "27%-os rész nettó (Ft)": round(sum_3, 2), 
                    "27% ÁFA Összesített": round(sum_3_27, 2), 
                    "61.20.30 : 27%-os nettó (Ft)": round(t_61_20_30, 2), 
                    "27% ÁFA 61.20.30": round(t_61_20_30_27, 2), 
                    "52.21.24 : 27%-os nettó (Ft)": round(t_52_21_24, 2), 
                    "27% ÁFA 52.21.24": round(t_52_21_24_27, 2), 
                    "62.09.20 : 27%-os nettó (Ft)": round(t_62_09_20, 2),
                    "27% ÁFA 62.09.20": round(t_62_09_20_27, 2),
                    "82.99.19 : 27%-os nettó (Ft)": round(t_82_99_19, 2),
                    "27% ÁFA 82.99.19": round(t_82_99_19_27, 2),
                    "61.20.42 : 5%-os nettó (Ft)": round(t_61_20_42, 2), 
                    "5% ÁFA 61.20.42": round(t_61_20_42_5, 2), 
                    "Összes nettó (Ft)": round(mind_netto, 2), 
                    "Összes ÁFA (Ft)": round(mind_afa, 2), 
                    "Összes bruttó (Ft)": round(mind_netto + mind_afa, 2) 
                })
                sorszam += 1

            df_vegleges = pd.DataFrame(vegleges_sorok)

            # Alsó Összegző sor felépítése
            osszesen_sor = {col: "" for col in df_vegleges.columns}
            osszesen_sor["mobilszám"] = "ÖSSZESEN"
            utolso_oszlopok = df_vegleges.columns[2:]
            
            for col in utolso_oszlopok:
                osszesen_sor[col] = round(df_vegleges[col].sum(), 2)

            df_vegleges = pd.concat([df_vegleges, pd.DataFrame([osszesen_sor])], ignore_index=True)

            time_end = time.time()
            
            # Excel export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_vegleges.to_excel(writer, index=False, sheet_name='Összesítő')
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.success(f"Feldolgozás kész! (Futási idő: {time_end - time_start:.2f} másodperc)")
            st.dataframe(df_vegleges, use_container_width=True)
            
            # Letöltő gomb
            dl_col1, dl_col2, dl_col3 = st.columns([1, 2, 1])
            with dl_col2:
                st.download_button(
                    label="📥 Eredmény letöltése Excel (.xlsx) fájlként",
                    data=buffer.getvalue(),
                    file_name="telekom_szamla_osszesito.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
