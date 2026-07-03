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
            
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            
            # --- OKOS VIZUÁLIS SORRENDEZÉS ---
            sorok = []
            for page in doc:
                words = page.get_text("words")  
                if not words:
                    continue
                
                words.sort(key=lambda w: (w[1], w[0]))
                
                page_lines = []
                current_line = []
                if words:
                    current_y = words[0][1]
                    for w in words:
                        if abs(w[1] - current_y) <= 5:
                            current_line.append(w)
                        else:
                            current_line.sort(key=lambda word: word[0])
                            page_lines.append(" ".join([word[4] for word in current_line]))
                            current_line = [w]
                            current_y = w[1]
                    if current_line:
                        current_line.sort(key=lambda word: word[0])
                        page_lines.append(" ".join([word[4] for word in current_line]))
                
                for line in page_lines:
                    if line.strip():
                        sorok.append(line.strip())

            adatok = []
            
            # VISSZATETTÜK A TE EREDETI LOGIKÁDAT: Kezdetben NINCS telefon!
            aktualis_telefon = None

            forgalmi_blokkban_vagyunk = False
            forgalmi_netto_osszeg = 0.0
            aktualis_forgalmi_teszor = "61.20.42" 

            for i in range(len(sorok)):
                sor = sorok[i].strip()

                if "mennyiség" in sor or "egység" in sor or "Szolgáltatás TESZOR" in sor:
                    continue
                
                # Hívószám blokk kezdete
                if "Mobil hívószám" in sor:
                    parts = sor.split("Mobil hívószám")
                    if len(parts) > 1 and parts[1].strip():
                        aktualis_telefon = parts[1].replace(":", "").strip()
                    continue 

                # Hívószám blokk vége (Te eredeti logikád!)
                if "Utólag" in sor and "összesen" in sor:
                    aktualis_telefon = None
                    continue

                # KRITIKUS VÉDELEM: Ha nem vagyunk benne egy telefonszám blokkjában (pl. a számla elején az összesítőnél), ugorjuk át!
                if aktualis_telefon is None:
                    continue
                
                # --- M2M BLOKK KEZELÉSE ---
                if "Forgalmi díjak - M2M NG" in sor:
                    forgalmi_blokkban_vagyunk = True
                    forgalmi_netto_osszeg = 0.0
                    continue

                if "Forgalmi díj kedvezmények" in sor or "Forgalmi díjak összesen" in sor:
                    if forgalmi_blokkban_vagyunk:
                        formazott_osszeg = f"{forgalmi_netto_osszeg:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        adatok.append({
                            "Sorszám": len(adatok) + 1,
                            "Telefonszám": aktualis_telefon,
                            "TESZOR": aktualis_forgalmi_teszor,
                            "Nettó Ár": formazott_osszeg,
                            "Kinyert Árak": "M2M Számolt",
                            "Kiváltó Sor": "Forgalmi díjak - M2M NG blokk"
                        })
                    forgalmi_blokkban_vagyunk = False
                    continue

                if forgalmi_blokkban_vagyunk:
                    if "TESZOR" in sor:
                        teszor_match = re.search(r'TESZOR\s*([\d\.]+)', sor)
                        if teszor_match:
                            aktualis_forgalmi_teszor = teszor_match.group(1)
                    
                    if "10kbyte" in sor.lower() or "byte" in sor.lower():
                        m2m_arak = re.findall(r'-?\d{1,3}(?:\.\d{3})*,\d{2}', sor)
                        if not m2m_arak and i + 1 < len(sorok):
                            m2m_arak = re.findall(r'-?\d{1,3}(?:\.\d{3})*,\d{2}', sorok[i+1])
                        
                        if m2m_arak:
                            tisztitott_szam = m2m_arak[0].replace('.', '').replace(',', '.')
                            try:
                                forgalmi_netto_osszeg += float(tisztitott_szam)
                            except ValueError:
                                pass
                    continue 

                # --- ÁLTALÁNOS TÉTELEK KINYERÉSE ---
                teszor_match = re.search(r'TESZOR\s*([\d\.]+)', sor)
                
                if teszor_match:    
                    teszor_szam = teszor_match.group(1)
                    valos_arak = []
                    
                    sajat_arak = re.findall(r'-?\d{1,3}(?:\.\d{3})*,\d{2}', sor)
                    for a in sajat_arak:
                        val = float(a.replace('.', '').replace(',', '.'))
                        if val == 0.0 or val < 0.0 or (val >= 10.0 and val != 27.0 and val != 5.0):
                            valos_arak.append(a)

                    if not valos_arak:
                        for j in range(1, 3):
                            if i + j < len(sorok):
                                kovetkezo_sor = sorok[i + j].strip()
                                if any(szo in kovetkezo_sor.lower() for szo in ["teszor", "mobil hívószám", "összesen", "számla"]):
                                    break   
                                
                                kovetkezo_arak = re.findall(r'-?\d{1,3}(?:\.\d{3})*,\d{2}', kovetkezo_sor)
                                for a in kovetkezo_arak:
                                    val = float(a.replace('.', '').replace(',', '.'))
                                    if val == 0.0 or val < 0.0 or (val >= 10.0 and val != 27.0 and val != 5.0):
                                        valos_arak.append(a)
                                if valos_arak:
                                    break

                    if len(valos_arak) > 0:
                        netto_ar = valos_arak[0]
                        
                        adatok.append({
                            "Sorszám": len(adatok) + 1,
                            "Telefonszám": aktualis_telefon,
                            "TESZOR": teszor_szam,
                            "Nettó Ár": netto_ar,
                            "Kinyert Árak": str(valos_arak),
                            "Kiváltó Sor": sor
                        })

            ###############################################
            # ADATOK ÖSSZEGZÉSE ÉS SOROKBA RENDEZÉSE
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
                
                t_51_21_24 = teszorok.get("51.21.24", 0.0)
                t_51_21_24_27 = t_51_21_24 * 0.27
                
                t_61_20_42 = teszorok.get("61.20.42", 0.0)
                t_61_20_42_5 = t_61_20_42 * 0.05
                
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
                    "51.21.24 : 27%-os nettó (Ft)": round(t_51_21_24, 2), 
                    "27% ÁFA 51.21.24": round(t_51_21_24_27, 2), 
                    "61.20.42 : 5%-os nettó (Ft)": round(t_61_20_42, 2), 
                    "5% ÁFA 61.20.42": round(t_61_20_42_5, 2), 
                    "Összes nettó (Ft)": round(sum_3 + t_61_20_30 + t_51_21_24 + t_61_20_42, 2), 
                    "Összes ÁFA (Ft)": round(sum_3_27 + t_61_20_30_27 + t_51_21_24_27 + t_61_20_42_5, 2), 
                    "Összes bruttó (Ft)": round(sum_3 + t_61_20_30 + t_51_21_24 + t_61_20_42 + sum_3_27 + t_61_20_30_27 + t_51_21_24_27 + t_61_20_42_5, 2) 
                })
                sorszam += 1

            df_vegleges = pd.DataFrame(vegleges_sorok)
            df_debug = pd.DataFrame(adatok) 

            osszesen_sor = {col: "" for col in df_vegleges.columns}
            utolso_3_oszlop = df_vegleges.columns[-3:]
            
            for col in utolso_3_oszlop:
                osszesen_sor[col] = round(df_vegleges[col].sum(), 2)

            df_vegleges = pd.concat([df_vegleges, pd.DataFrame([osszesen_sor])], ignore_index=True)

            time_end = time.time()
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_vegleges.to_excel(writer, index=False, sheet_name='Összesítő')
                df_debug.to_excel(writer, index=False, sheet_name='Nyers Kinyert Adatok')
            
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
