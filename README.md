# ELN LLM Analytics Dashboard

This project is a small end to end prototype for using a **local LLM** to extract structured data from **Electronic Laboratory Notebook (ELN)** entries and explore the results in a **Shiny for Python** dashboard.

Everything runs locally:

- ELN text is parsed by a local model in **LM Studio** (for example `Qwen/Qwen2.5-Coder-32B-Instruct-GGUF`)
- The model is exposed via LM Studio’s **OpenAI compatible HTTP API**
- Extracted fields are written to a CSV file
- A Shiny for Python dashboard reads this CSV and provides interactive exploration

This is meant as a realistic simulation of the kind of AI and genAI work mentioned in DSP / bioprocess data science job descriptions: extracting insights from unstructured ELNs and turning them into something you can actually analyze.

---

## Features

- Example ELN entries in mixed German / English lab style
- LLM based extraction of:
  - `experiment_id`
  - `date`
  - `protein`
  - `host`
  - `medium`
  - `od600_induction`
  - `iptg_mM`
  - `temp_C`
  - `induction_h`
  - `uses_ni_nta`
  - `uses_sec`
  - `imidazol_max_mM`
  - `yield_mg_per_L`
  - `notes_summary`
- Robust JSON parsing from LLM output (handles code fences and extra text)
- CSV export for further use
- Shiny for Python dashboard with:
  - Filters for protein, host and medium
  - Table of experiments
  - Detail view for a selected experiment
  - Aggregated tables (yield by protein, host, medium)
  - Plots:
    - Boxplot of yield by medium
    - Scatter plot of IPTG vs yield

---

## Project structure

Typical layout:

```text
ELN_parser/
├─ eln_lmstudio_extraction.py   # LLM based ELN → CSV extraction
├─ eln_dashboard.py             # Shiny for Python dashboard
├─ eln_extracted_lmstudio.csv   # Generated CSV with extracted data (not strictly required in Git)
└─ README.md
