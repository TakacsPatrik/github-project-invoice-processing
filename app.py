# Csak ha digitális a PDF akkor működik ez a kód! Ha a PDF szkennelt, akkor OCR-re van szükség.

import streamlit as st
import fitz
import time
import re
import pandas as pd
import io
import traceback

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
            try:
                time_start = time.time()
                
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                
                # --- VIZUÁLIS SORRENDEZÉS (Layout-aware) ---
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
                aktualis_telefon = None

                for i in range(len(sorok)):
                    sor = sorok[i].strip()

                    # Globális összesítők szigorú kihagyása az elején
                    if "számla összesen" in sor.lower() or "fizetendő" in sor.lower():
                        continue

                    if "mennyiség" in sor or "egység" in sor or "Szolgáltatás TESZOR" in sor:
                        continue
                    
                    # --- KAPUK KEZELÉSE ---
                    if "Mobil hívószám" in sor:
                        parts = sor.split("Mobil hívószám")
                        if len(parts) > 1 and parts[1].strip():
                            aktualis_telefon = parts[1].replace(":", "").strip()
                        else:
                            if i + 1 < len(sorok):
                                aktualis_telefon = sorok[i+1].strip().replace(":", "")
                        continue 
                    
                    if "Utólag" in sor and "összesen" in sor:
                        aktualis_telefon = None 
                        continue

                    # Kapu kinyitása a számla végi közös tételeknek
                    if "Folyószámla szintű" in sor or "e-Pack" in sor or "Készüléktörlesztés" in sor:
                        if aktualis_telefon is None:
                            aktualis_telefon = "Számlaszintű tételek"

                    if aktualis_telefon is None:
                        continue
                    
                    # --- TÉTELEK KERESÉSE (TESZOR vagy Készülék) ---
                    teszor_match = re.search(r'TESZOR\s*([\d\.]+)', sor)
                    egyeb_tetel = "Készüléktörlesztés" in sor or "e-Pack" in sor
                    
                    if teszor_match or egyeb_tetel:    
                        teszor_szam = teszor_match.group(1) if teszor_match else "Egyéb Tétel"
                        arak = []
                        
                        arak.extend(re.findall(r'-?\d{1,3}(?:\.\d{3})*,\d{2}', sor))

                        # Ha a vizuális tördelés miatt a következő sorba csúszott az ár
                        if not arak:
                            for j in range(1, 3):
                                if i + j < len(sorok):
                                    kov_sor = sorok[i + j].strip()
                                    if "TESZOR" in kov_sor or "Mobil hívószám" in kov_sor:
                                        break
                                    arak.extend(re.findall(r'-?\d{1,3}(?:\.\d{3})*,\d{2}', kov_sor))
                                    if arak: break

                        valos_arak = []
                        for a in arak:
                            try:
                                val = float(a.replace('.', '').replace(',', '.'))
                                valos_arak.append((a, val))
                            except ValueError:
                                pass

                        netto_ar = None
                        afa_ertek = 0.0
                        afa_idx = -1
                        
                        # ÁFA horgony keresése (27, 5, 18, vagy 0)
                        for idx in reversed(range(1, len(valos_arak))):
                            if valos_arak[idx][1] in [27.0, 5.0, 18.0, 0.0]:
                                afa_idx = idx
                                break
                        
                        if afa_idx != -1:
                            netto_ar = valos_arak[afa_idx - 1][0]
                            # Bónusz: Ha tudjuk, kimentjük a konkrét ÁFA értéket is a listából
                            if afa_idx + 1 < len(valos_arak):
                                afa_ertek = valos_arak[afa_idx + 1][1]
                        else:
                            if len(valos_arak) >= 6:
                                netto_ar = valos_arak[2][0]
                            elif len(valos_arak) >= 4:
                                netto_ar = valos_arak[0][0]
                            elif len(valos_arak) > 0:
                                netto_ar = valos_arak[-1][0]

                        if netto_ar:
                            adatok.append({
                                "Sorszám": len(adatok) + 1,
                                "Telefonszám": aktualis_telefon,
                                "TESZOR": teszor_szam,
                                "Nettó Ár": netto_ar,
                                "Kinyert ÁFA Érték": afa_ertek,
                                "Kinyert Árak": str([x[0] for x in valos_arak]),
                                "Kiváltó Sor": sor
                            })

                if len(adatok) == 0:
                    st.warning("⚠️ A program lefutott, de nem talált kinyerhető adatot a PDF-ben.")
                else:
                    ###############################################
                    # ADATOK VESZTESÉGMENTES ÖSSZEGZÉSE
                    ###############################################
                    telefon_osszesito = {}

                    for adat in adatok:
                        tel = adat["Telefonszám"]
                        teszor = adat["TESZOR"]
                        netto_str = str(adat["Nettó Ár"])
                        afa_ertek = adat.get("Kinyert ÁFA Érték", 0.0)
                        
                        if tel not in telefon_osszesito:
                            telefon_osszesito[tel] = {"Tételek": {}, "Extra_AFA": 0.0}
                            
                        try:
                            tisztitott = netto_str.replace('.', '').replace(',', '.')
                            netto_ertek = float(tisztitott)
                        except ValueError:
                            netto_ertek = 0.0

                        if teszor not in telefon_osszesito[tel]["Tételek"]:
                            telefon_osszesito[tel]["Tételek"][teszor] = 0.0
                        
                        telefon_osszesito[tel]["Tételek"][teszor] += netto_ertek
                        
                        # Ha a tétel NEM a fix 6 teszor egyike, eltároljuk a kinyert ÁFA-t is, hogy ne veszítsük el
                        ismert_teszorok = ["61.20.12", "61.20.13", "61.20.14", "61.20.30", "51.21.24", "61.20.42"]
                        if teszor not in ismert_teszorok:
                            telefon_osszesito[tel]["Extra_AFA"] += afa_ertek

                    vegleges_sorok = []
                    sorszam = 1

                    for tel, adathalmaz in telefon_osszesito.items():
                        teszorok = adathalmaz["Tételek"]
                        extra_afa = adathalmaz["Extra_AFA"]
                        
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
                        
                        # Minden EGYÉB teszor összegzése (hogy ne vesszen el adat!)
                        ismert_teszorok = ["61.20.12", "61.20.13", "61.20.14", "61.20.30", "51.21.24", "61.20.42"]
                        egyeb_netto = sum(ertek for kod, ertek in teszorok.items() if kod not in ismert_teszorok)
                        
                        veg_netto = sum_3 + t_61_20_30 + t_51_21_24 + t_61_20_42 + egyeb_netto
                        veg_afa = sum_3_27 + t_61_20_30_27 + t_51_21_24_27 + t_61_20_42_5 + extra_afa
                        
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
                            "Egyéb Tétel Nettó (Ft)": round(egyeb_netto, 2),
                            "Egyéb Tétel ÁFA (Ft)": round(extra_afa, 2),
                            "Összes nettó (Ft)": round(veg_netto, 2), 
                            "Összes ÁFA (Ft)": round(veg_afa, 2), 
                            "Összes bruttó (Ft)": round(veg_netto + veg_afa, 2) 
                        })
                        sorszam += 1

                    df_vegleges = pd.DataFrame(vegleges_sorok)
                    df_debug = pd.DataFrame(adatok) 

                    osszesen_sor = {col: "" for col in df_vegleges.columns}
                    utolso_oszlopok = df_vegleges.columns[2:] 
                    
                    for col in utolso_oszlopok:
                        osszesen_sor[col] = round(df_vegleges[col].sum(), 2)
                    osszesen_sor["sorszám"] = "Összesen"

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
            
            except Exception as e:
                st.error("❌ Kritikus hiba történt a feldolgozás során!")
                st.code(traceback.format_exc())
