# test_lmstudio_connection.py
#
# Ziel:
# - Verbindung zu LM Studio testen
# - Modell "Qwen/Qwen2.5-Coder-32B-Instruct-GGUF" ansprechen
# - Antwort in JSON-Form extrahieren, auch wenn das Modell Codeblöcke und Text drumherum schreibt

import json      # Für json.dumps und json.loads
import requests  # Für HTTP Requests an den lokalen Server
import re        # Für reguläre Ausdrücke, um JSON aus dem Text zu extrahieren


LMSTUDIO_BASE_URL = "http://127.0.0.1:1234"  # Adresse deines LM Studio Servers
LMSTUDIO_CHAT_URL = f"{LMSTUDIO_BASE_URL}/v1/chat/completions"  # Chat API Pfad
LMSTUDIO_MODEL_NAME = "Qwen/Qwen2.5-Coder-32B-Instruct-GGUF"    # Dein Modellname


def extract_json_from_content(content: str) -> dict:
    """
    Versucht, ein JSON Objekt aus dem Text 'content' zu extrahieren.
    Unterstützt:
    - reines JSON
    - ```json ... ``` Codeblöcke
    - Text um das JSON herum
    """

    # 1) Nach ```json ... ``` suchen
    codeblock_match = re.search(
        r"```json(.*?)```",            # Muster für einen json-codeblock
        content,
        flags=re.DOTALL | re.IGNORECASE
    )

    if codeblock_match:
        # Wenn gefunden, nur den Inhalt zwischen den Backticks nehmen
        json_text = codeblock_match.group(1).strip()
        return json.loads(json_text)

    # 2) Falls kein Codeblock: Bereich zwischen erstem '{' und letztem '}' suchen
    start = content.find("{")
    end = content.rfind("}")

    if start != -1 and end != -1 and end > start:
        json_text = content[start:end+1].strip()
        return json.loads(json_text)

    # 3) Wenn nichts davon funktioniert, Fehler auswerfen
    raise ValueError(f"Kein parsebares JSON gefunden:\n{content}")


def main():
    # Einfache Test-Funktion, die einen Prompt an das Modell schickt

    # Prompt so formulieren, dass wir das gewünschte Verhalten testen
    prompt = (
        "Gib bitte NUR ein JSON-Objekt zurück, ohne Erklärung, ohne Codeblock. "
        "Das JSON-Objekt soll so aussehen: {\"test_ok\": true}"
    )

    headers = {
        "Content-Type": "application/json",  # Wir senden JSON im Request
    }

    body = {
        "model": LMSTUDIO_MODEL_NAME,  # Name des Modells
        "messages": [
            {
                "role": "user",
                "content": prompt,      # Unser Prompt mit der Anweisung
            }
        ],
        "temperature": 0.0,            # deterministisch
    }

    body_json = json.dumps(body)       # Body in JSON String konvertieren

    print(f"Schicke Testanfrage an: {LMSTUDIO_CHAT_URL}")
    print(f"Modell: {LMSTUDIO_MODEL_NAME}")

    response = requests.post(
        LMSTUDIO_CHAT_URL,
        headers=headers,
        data=body_json,
        timeout=60,
    )

    response.raise_for_status()        # Fehler, falls HTTP Status nicht 2xx

    result = response.json()           # Antwort als dict interpretieren

    content = result["choices"][0]["message"]["content"]  # Text vom Modell

    print("\nRohantwort vom Modell:")
    print(content)

    # Jetzt versuchen wir, das JSON robust zu extrahieren
    try:
        parsed = extract_json_from_content(content)
        print("\nExtrahiertes JSON als dict:")
        print(parsed)
    except ValueError as e:
        print("\nFehler bei der JSON-Extraktion:")
        print(e)


if __name__ == "__main__":
    main()
