# eln_lmstudio_extraction.py
#
# Ziel:
# - Lokales LLM in LM Studio über OpenAI-kompatible API ansprechen
# - Frei geschriebene ELN-Einträge an das Modell schicken
# - Strukturierte JSON-Daten mit festen Feldern extrahieren
# - Alles in ein pandas DataFrame packen und als CSV speichern
#
# Voraussetzung:
# - LM Studio läuft und zeigt "Reachable at: http://127.0.0.1:1234"
# - Das Modell "Qwen/Qwen2.5-Coder-32B-Instruct-GGUF" ist geladen
# - Der OpenAI-kompatible Server in LM Studio ist aktiv

import json      # Für JSON-Konvertierung zwischen String und Python dict
import textwrap  # Für saubere Formatierung von mehrzeiligen Strings
import requests  # Für HTTP-Anfragen an den lokalen LM Studio Server
import re        # Für reguläre Ausdrücke, um JSON-Blöcke aus Text zu extrahieren
import pandas as pd  # Für DataFrame und CSV-Ausgabe

# Basis-URL deines LM Studio Servers
LMSTUDIO_BASE_URL = "http://127.0.0.1:1234"  # Lokal laufender Server auf Port 1234

# Vollständige URL für den Chat Completions Endpunkt
LMSTUDIO_CHAT_URL = f"{LMSTUDIO_BASE_URL}/v1/chat/completions"  # OpenAI-kompatibler Pfad

# Modellname muss zu dem passen, was LM Studio für die API verwendet
LMSTUDIO_MODEL_NAME = "Qwen/Qwen2.5-Coder-32B-Instruct-GGUF"  # Dein Modellname

# Beispiel ELN-Einträge.
# In echt würdest du diese Texte aus einem ELN oder einer Datenbank holen.
eln_entries = [
    """Experiment ID: EXP001
Datum: 2025-11-20
Protein: His6-CASPON-CandidateA
Host: E. coli BL21(DE3)
Medium: TB
Induktion: OD600 = 0.7, IPTG 0.5 mM, 20 °C, 16 h
Lysis: Sonifikation in PBS, 10 mM Imidazol
Purifikation: Ni-NTA, eluiert mit 250 mM Imidazol
Yield: 45 mg pro Liter Kultur
Notizen: lösliches Protein, kaum Aggregation, gutes SDS-PAGE-Band""",

    """Experiment: EXP002
Datum: 21.11.2025
Konstrukttyp: His6-CASPON-CandidateB
Wirt: E.coli Rosetta (DE3)
Medium: LB
Expression: Induktion bei OD600 ~0.6 mit 1 mM IPTG, 25°C für 6 h
Lyse: BugBuster + Lysozym + DNase
Aufreinigung: Ni-NTA, Imidazolgradient 50-300 mM
Ausbeute: 18 mg/L
Bemerkung: deutliche Aggregation, viel Material im Pellet""",

    """ID: EXP003
Date: 2025-11-22
Protein: His6-CASPON-CandidateA
Strain: BL21(DE3)
Medium: Terrific Broth (TB)
Induction at OD600 0.8 using 0.2 mM IPTG, 18 °C overnight (~20 h)
Lysis via sonication
Purification: HisTrap (Ni-NTA), elution with 250 mM imidazole, followed by SEC (Superdex 200)
Yield: approx. 60 mg/L culture
Notes: SEC shows nice monomeric peak""",

    """Experiment ID: EXP004
Protein: His6-CASPON-CandidateC
Host: BL21(DE3)
Medium: TB
Induktion bei OD600 0.9, 0.1 mM IPTG, 30°C, 5 h
Lyse: French Press
Chromatographie: Ni-NTA, Elution mit 100 mM Imidazol
Yield: 25 mg pro Liter
Kommentar: signifikanter Anteil unlöslich, aber ausreichend lösliches Protein""",

    """Exp: EXP005
Datum: 24-11-2025
Protein: His6-CASPON-CandidateA
Host strain: Rosetta(DE3)
Medium: EnPresso
Induction: started at OD600 = 1.5 with 0.05 mM IPTG, 25°C, 24 hours
Lysis by sonication in Tris/NaCl buffer (300 mM NaCl)
Purification: Ni-NTA, elution with 200 mM imidazole, then SEC on Superdex 75
Total yield: 85 mg/L
Note: best yield so far, main species monomer, minor dimer peak"""
]

def build_extraction_prompt(eln_text: str) -> str:
    """
    Baut einen Prompt, der dem Modell erklärt,
    wie es den ELN-Text in ein JSON mit festen Feldern extrahieren soll.
    """

    schema_description = """
    Du bist ein Assistent für Biotech-ELN-Datenextraktion.

    Aufgabe:
    - Lies den folgenden ELN-Eintrag.
    - Extrahiere die wichtigsten experimentellen Parameter.
    - Gib das Ergebnis als gültiges JSON-Objekt zurück (ohne zusätzliche Kommentare oder Text).

    Felder im JSON:
    - experiment_id: string oder null
    - date: string (ISO-ähnlich, z.B. "2025-11-20") oder null
    - protein: string oder null
    - host: string oder null
    - medium: string oder null
    - od600_induction: number oder null
    - iptg_mM: number oder null
    - temp_C: number oder null
    - induction_h: number oder null
    - uses_ni_nta: 0 oder 1
    - uses_sec: 0 oder 1
    - imidazol_max_mM: number oder null
    - yield_mg_per_L: number oder null
    - notes_summary: kurze string-Zusammenfassung der Notizen (max 2 Sätze)

    Regeln:
    - Wenn eine Information nicht sicher im Text steht, setze das Feld auf null.
    - Alle Zahlen bitte als reine Zahl ohne Einheit (z.B. 0.5 statt "0.5 mM").
    - 'uses_ni_nta' ist 1, wenn Ni-NTA oder HisTrap erwähnt wird, sonst 0.
    - 'uses_sec' ist 1, wenn SEC oder Size-Exclusion-Chromatographie erwähnt wird, sonst 0.
    - 'yield_mg_per_L' immer als mg pro Liter Kultur, falls andere Einheiten vorkommen entsprechend umrechnen.
    - Gib nur das JSON-Objekt zurück, ohne zusätzliche Erklärungen, ohne Codeblocks.
    """

    # Einrückungen aus dem mehrzeiligen String entfernen, damit der Prompt sauber ist
    schema_description = textwrap.dedent(schema_description)

    # Den finalen Prompt zusammenbauen, mit ELN-Text eingerahmt in """ ... """
    prompt = (
        schema_description
        + "\n\nELN-Eintrag:\n\"\"\"\n"
        + eln_text
        + "\n\"\"\"\n\nJSON-Antwort:"
    )

    return prompt  # Prompt an den Aufrufer zurückgeben

def extract_json_from_content(content: str) -> dict:
    """
    Versucht, aus einer Modellantwort (content) ein JSON-Objekt zu extrahieren.
    Unterstützt:
    - reines JSON
    - ```json ... ``` Codeblöcke
    - Text vor/nach dem JSON
    """

    # 1) Zuerst versuchen wir, einen ```json ... ``` Block zu finden
    codeblock_match = re.search(
        r"```json(.*?)```",                   # Pattern für ```json ... ```
        content,
        flags=re.DOTALL | re.IGNORECASE      # DOTALL: matcht auch Zeilenumbrüche, IGNORECASE: json/JSON egal
    )

    if codeblock_match:
        # Innenleben des Codeblocks extrahieren und trimmen
        json_text = codeblock_match.group(1).strip()
        return json.loads(json_text)         # In Python dict umwandeln

    # 2) Falls kein Codeblock, suchen wir die erste '{' und die letzte '}'
    start = content.find("{")               # Position der ersten '{'
    end = content.rfind("}")                # Position der letzten '}'

    if start != -1 and end != -1 and end > start:
        # Falls beide vorhanden sind und logisch angeordnet
        json_text = content[start:end+1].strip()  # Bereich dazwischen ausschneiden
        return json.loads(json_text)              # Versuchen, als JSON zu parsen

    # 3) Wenn alles fehlschlägt, Fehler melden
    raise ValueError(f"Kein parsebares JSON in der Antwort gefunden:\n{content}")

def extract_with_lmstudio(eln_text: str) -> dict:
    """
    Schickt einen ELN-Text an LM Studio (lokales LLM)
    und gibt ein dict mit den extrahierten Feldern zurück.
    """

    # Prompt für diesen ELN-Eintrag bauen
    prompt = build_extraction_prompt(eln_text)

    # HTTP Header für den Request
    headers = {
        "Content-Type": "application/json",  # Wir senden JSON im Request-Body
    }

    # Request-Body im OpenAI-Chat-Format
    body = {
        "model": LMSTUDIO_MODEL_NAME,  # Name des zu verwendenden Modells
        "messages": [
            {
                "role": "user",        # Rolle ist "user"
                "content": prompt,     # Unser Prompt mit Schema-Beschreibung und ELN-Text
            }
        ],
        "temperature": 0.0,            # Temperatur 0 für deterministischere Ergebnisse
    }

    # Python dict in JSON-String konvertieren
    body_json = json.dumps(body)

    # POST-Request an den LM Studio Chat Endpunkt senden
    response = requests.post(
        LMSTUDIO_CHAT_URL,  # URL: http://127.0.0.1:1234/v1/chat/completions
        headers=headers,    # HTTP Header (Content-Type)
        data=body_json,     # JSON-Body
        timeout=120,        # Timeout in Sekunden
    )

    # Fehler werfen, falls HTTP-Status kein Erfolg ist
    response.raise_for_status()

    # Antwort als Python dict interpretieren
    result = response.json()

    # Inhalt der ersten Choice auslesen
    raw_content = result["choices"][0]["message"]["content"]

    # JSON robust aus dem Inhalt extrahieren
    data = extract_json_from_content(raw_content)

    return data  # dict mit allen extrahierten Feldern zurückgeben

def extract_all_eln_entries() -> pd.DataFrame:
    """
    Wendet die LLM-Extraktion auf alle Beispiel-ELN-Einträge an
    und gibt ein pandas DataFrame mit einer Zeile pro Experiment zurück.
    """

    records = []  # Liste für alle dicts

    # Über alle ELN-Texte iterieren
    for i, eln_text in enumerate(eln_entries):
        print(f"Extrahiere Eintrag {i+1} ...")  # Fortschrittsausgabe

        # LLM-Extraktion durchführen
        record = extract_with_lmstudio(eln_text)

        # Rohtext mit abspeichern, z. B. für Traceability
        record["raw_eln_text"] = eln_text

        # dict in die Liste aufnehmen
        records.append(record)

    # Liste von dicts in ein DataFrame umwandeln
    df = pd.DataFrame(records)

    return df  # DataFrame zurückgeben

if __name__ == "__main__":
    # Wird ausgeführt, wenn das Skript direkt gestartet wird

    # Extraktion für alle Beispiel-ELNs durchführen
    df_extracted = extract_all_eln_entries()

    # DataFrame zur Kontrolle ausgeben
    print("\nExtrahierte strukturierte Daten:")
    print(df_extracted)

    # Als CSV speichern, z. B. für Shiny oder weitere Analysen
    output_csv = "eln_extracted_lmstudio.csv"  # Dateiname
    df_extracted.to_csv(output_csv, index=False)  # CSV ohne Index schreiben

    print(f"\nCSV gespeichert unter: {output_csv}")
