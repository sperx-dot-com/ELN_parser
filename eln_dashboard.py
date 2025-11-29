# eln_dashboard.py
#
# Dashboard für aus ELN-Einträgen extrahierte Daten
#
# Voraussetzungen:
#   pip install shiny pandas matplotlib
#
# Start:
#   shiny run --reload eln_dashboard.py
#   (oder: python -m shiny run --reload eln_dashboard.py)

from shiny import App, ui, render, reactive
import pandas as pd
import matplotlib.pyplot as plt

# -------------------------------------------------------------------
# Daten laden
# -------------------------------------------------------------------

df = pd.read_csv("eln_extracted_lmstudio.csv")

# Erwartete Spalten (deine Liste):
# ['experiment_id', 'date', 'protein', 'host', 'medium',
#  'od600_induction', 'iptg_mM', 'temp_C', 'induction_h',
#  'uses_ni_nta', 'uses_sec', 'imidazol_max_mM',
#  'yield_mg_per_L', 'notes_summary', 'raw_eln_text']

# Numerische Spalten sicher als numeric casten
for col in ["yield_mg_per_L", "iptg_mM", "temp_C", "od600_induction", "induction_h", "imidazol_max_mM"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# Hilfsfunktion für Filter-Choices
def make_choices(series: pd.Series):
    vals = sorted(x for x in series.dropna().unique())
    return ["All"] + vals

protein_choices = make_choices(df["protein"])
host_choices = make_choices(df["host"])
medium_choices = make_choices(df["medium"])

# -------------------------------------------------------------------
# UI
# -------------------------------------------------------------------

app_ui = ui.page_navbar(
    # Tab 1: Overview
    ui.nav_panel(
        "Overview",
        ui.layout_sidebar(
            ui.sidebar(
                ui.h4("Filter"),
                ui.input_select(
                    "protein_filter",
                    "Protein",
                    choices=protein_choices,
                    selected="All",
                ),
                ui.input_select(
                    "host_filter",
                    "Host",
                    choices=host_choices,
                    selected="All",
                ),
                ui.input_select(
                    "medium_filter",
                    "Medium",
                    choices=medium_choices,
                    selected="All",
                ),
                open="desktop",
                bg="#f8f8f8",
            ),
            ui.layout_columns(
                ui.card(
                    ui.h3("Experimente"),
                    ui.p("Gefilterte ELN-Experimente basierend auf den ausgewählten Kriterien."),
                    ui.output_table("tbl_experiments"),
                ),
                ui.card(
                    ui.h3("Details zum ausgewählten Experiment"),
                    ui.p("Wähle eine Zeile in der Tabelle aus (per Index), um Details zu sehen."),
                    ui.input_numeric("detail_row", "Zeilenindex (1-basiert)", 1, min=1),
                    ui.output_table("tbl_experiment_detail"),
                    ui.hr(),
                    ui.h4("Notes summary"),
                    ui.output_text_verbatim("txt_notes_summary"),
                )
            ),
        ),
    ),

    # Tab 2: Aggregates
    ui.nav_panel(
        "Aggregates",
        ui.layout_columns(
            ui.card(
                ui.h3("Yield nach Protein"),
                ui.output_table("tbl_yield_by_protein"),
            ),
            ui.card(
                ui.h3("Yield nach Host"),
                ui.output_table("tbl_yield_by_host"),
            ),
            ui.card(
                ui.h3("Yield nach Medium"),
                ui.output_table("tbl_yield_by_medium"),
            ),
        ),
    ),

    # Tab 3: Plots
    ui.nav_panel(
        "Plots",
        ui.layout_columns(
            ui.card(
                ui.h3("Boxplot: Yield nach Medium"),
                ui.output_plot("plot_box_yield_medium"),
            ),
            ui.card(
                ui.h3("Scatter: IPTG vs Yield"),
                ui.output_plot("plot_scatter_iptg_yield"),
            ),
        ),
    ),

    title="ELN Analytics Dashboard",
    id="page",
)

# -------------------------------------------------------------------
# Server
# -------------------------------------------------------------------

def server(input, output, session):
    # Reaktiver Filter auf Basis der Dropdowns
    @reactive.calc
    def filtered_df():
        d = df.copy()

        pf = input.protein_filter()
        if pf != "All":
            d = d[d["protein"] == pf]

        hf = input.host_filter()
        if hf != "All":
            d = d[d["host"] == hf]

        mf = input.medium_filter()
        if mf != "All":
            d = d[d["medium"] == mf]

        return d

    # Tabelle mit gefilterten Experimenten
    @output
    @render.table
    def tbl_experiments():
        d = filtered_df()
        cols_order = [
            "experiment_id",
            "date",
            "protein",
            "host",
            "medium",
            "od600_induction",
            "iptg_mM",
            "temp_C",
            "induction_h",
            "yield_mg_per_L",
        ]
        cols_present = [c for c in cols_order if c in d.columns]
        return d[cols_present] if cols_present else d

    # Detailansicht für eine ausgewählte Zeile (per Index)
    @reactive.calc
    def selected_row():
        d = filtered_df().reset_index(drop=True)
        # input.detail_row ist 1-basiert, DataFrame 0-basiert
        idx = input.detail_row() - 1
        if len(d) == 0:
            return None
        # Clamp Index in gültigen Bereich
        idx = max(0, min(idx, len(d) - 1))
        return d.iloc[idx : idx + 1]

    @output
    @render.table
    def tbl_experiment_detail():
        row = selected_row()
        if row is None:
            return pd.DataFrame()
        cols_order = [
            "experiment_id",
            "date",
            "protein",
            "host",
            "medium",
            "od600_induction",
            "iptg_mM",
            "temp_C",
            "induction_h",
            "uses_ni_nta",
            "uses_sec",
            "imidazol_max_mM",
            "yield_mg_per_L",
        ]
        cols_present = [c for c in cols_order if c in row.columns]
        return row[cols_present] if cols_present else row

    @output
    @render.text
    def txt_notes_summary():
        row = selected_row()
        if row is None or "notes_summary" not in row.columns:
            return "Keine Notizen verfügbar."
        return str(row["notes_summary"].iloc[0])

    # Aggregates: Yield nach Protein
    @output
    @render.table
    def tbl_yield_by_protein():
        d = filtered_df()
        if "yield_mg_per_L" not in d.columns:
            return pd.DataFrame()
        grouped = (
            d.groupby("protein")["yield_mg_per_L"]
            .agg(["count", "mean", "std"])
            .reset_index()
        )
        return grouped

    # Aggregates: Yield nach Host
    @output
    @render.table
    def tbl_yield_by_host():
        d = filtered_df()
        if "yield_mg_per_L" not in d.columns:
            return pd.DataFrame()
        grouped = (
            d.groupby("host")["yield_mg_per_L"]
            .agg(["count", "mean", "std"])
            .reset_index()
        )
        return grouped

    # Aggregates: Yield nach Medium
    @output
    @render.table
    def tbl_yield_by_medium():
        d = filtered_df()
        if "yield_mg_per_L" not in d.columns:
            return pd.DataFrame()
        grouped = (
            d.groupby("medium")["yield_mg_per_L"]
            .agg(["count", "mean", "std"])
            .reset_index()
        )
        return grouped

    # Plot: Boxplot Yield nach Medium
    @output
    @render.plot
    def plot_box_yield_medium():
        d = filtered_df()
        if "medium" not in d.columns or "yield_mg_per_L" not in d.columns:
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, "Keine Daten für Medium/Yield", ha="center", va="center")
            ax.axis("off")
            return fig

        fig, ax = plt.subplots()
        d.boxplot(column="yield_mg_per_L", by="medium", ax=ax)
        ax.set_title("Yield nach Medium")
        plt.suptitle("")
        ax.set_ylabel("Yield [mg/L]")
        return fig

    # Plot: Scatter IPTG vs Yield
    @output
    @render.plot
    def plot_scatter_iptg_yield():
        d = filtered_df()
        if "iptg_mM" not in d.columns or "yield_mg_per_L" not in d.columns:
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, "Keine Daten für IPTG/Yield", ha="center", va="center")
            ax.axis("off")
            return fig

        d2 = d.dropna(subset=["iptg_mM", "yield_mg_per_L"])
        fig, ax = plt.subplots()
        ax.scatter(d2["iptg_mM"], d2["yield_mg_per_L"])
        ax.set_xlabel("IPTG [mM]")
        ax.set_ylabel("Yield [mg/L]")
        ax.set_title("IPTG vs Yield")
        return fig


app = App(app_ui, server)

if __name__ == "__main__":
    app.run()