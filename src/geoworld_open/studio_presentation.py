"""Public presentation only: readable Studio layout and offline run reports.

No scientific rendering, private imports, or network calls live here. Figures
are the unchanged image artifacts already returned by the authenticated API.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from html import escape
from importlib.resources import files
from string import Template

from geoworld_open.client.models import JobResult
from geoworld_open.studio_runtime import human_citation_lines


@dataclass(frozen=True)
class DisplayOptions:
    text_px: int = 18
    figure_px: int = 880
    layout: str = "Auto"
    fit_figures: bool = True

    def __post_init__(self) -> None:
        if type(self.text_px) is not int or not 16 <= self.text_px <= 24:
            raise ValueError("Text size must be between 16 and 24 pixels.")
        if type(self.figure_px) is not int or not 480 <= self.figure_px <= 1200:
            raise ValueError("Figure width must be between 480 and 1200 pixels.")
        if self.layout not in {"Auto", "One column", "Two columns"}:
            raise ValueError("Layout must be Auto, One column, or Two columns.")
        if type(self.fit_figures) is not bool:
            raise ValueError("Fit figures must be a boolean.")


def studio_display_css(options: DisplayOptions) -> str:
    """Scope size overrides to the main app; never stretch scientific images."""
    # Load print/privacy styling with the page, not after potentially slow result
    # rendering. Native Ctrl+P must work even before the Save controls arrive.
    export_css = files("geoworld_open").joinpath("assets", "studio_export.css").read_text(encoding="utf-8")
    figure_width = "100%" if options.fit_figures else f"min(100%, {options.figure_px}px)"
    # Measure available MAIN content width, not the window including the sidebar.
    # A narrow device stays usable even if the user explicitly requests two columns.
    threshold = 1020 if options.layout == "Auto" else 800
    columns = "" if options.layout == "One column" else f"""
    @container studio (min-width: {threshold}px) {{
        .st-key-studio_workspace_layout:has(.st-key-studio_results [data-testid="stTabs"]) {{
            grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
        }}
    }}
    @media print {{
        @container studio (min-width: 800px) {{
            .st-key-studio_workspace_layout:has(.st-key-studio_results [data-testid="stTabs"]) {{
                grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
            }}
        }}
    }}"""
    return f"""<style>
    [data-testid="stMainBlockContainer"] {{
        width: 100%; max-width: none; margin-inline: 0;
        padding: 3.5rem 1.25rem 1rem; min-height: 0; flex: 0 0 auto;
        container: studio / inline-size;
    }}
    .st-key-studio_workspace_layout {{
        display: grid !important; grid-template-columns: minmax(0, 1fr);
        width: 100% !important; gap: 1.5rem !important; align-items: start;
    }}
    .st-key-studio_workspace_layout > *,
    .st-key-studio_workflow, .st-key-studio_results {{ min-width: 0; }}
    {columns}
    [data-testid="stMain"] [data-testid="stElementContainer"],
    [data-testid="stMain"] [data-testid="stImageContainer"],
    [data-testid="stMain"] [data-testid="stDataFrame"] {{
        max-width: 100% !important; min-width: 0 !important;
    }}
    [data-testid="stMain"] [data-testid="stDataFrame"] {{ overflow: auto; }}
    [data-testid="stMain"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stMain"] [data-testid="stMarkdownContainer"] li,
    [data-testid="stMain"] input, [data-testid="stMain"] textarea {{
        font-size: {options.text_px}px; line-height: 1.55;
    }}
    [data-testid="stMain"] [data-testid="stCaptionContainer"] p {{
        font-size: {max(14, options.text_px - 2)}px;
    }}
    [data-testid="stMain"] [data-testid="stImage"] {{
        max-width: {figure_width}; margin-inline: auto;
    }}
    [data-testid="stMain"] [data-testid="stImage"] img {{
        max-width: 100%; height: auto; object-fit: contain;
    }}
    .st-key-studio_workflow button p {{
        white-space: normal !important; overflow: visible; text-overflow: clip;
    }}
    @media (max-width: 640px) {{
        [data-testid="stMainBlockContainer"] {{ padding-inline: 1rem; }}
    }}
    {export_css}
    </style>"""


def studio_export_controls() -> str:
    """Static native-print action; deliberately accepts no user-supplied input."""
    assets = files("geoworld_open").joinpath("assets")
    html = assets.joinpath("studio_export.html").read_text(encoding="utf-8")
    script = assets.joinpath("studio_export.js").read_text(encoding="utf-8")
    return f"{html}<script>{script}</script>"


@dataclass(frozen=True)
class ReportFigure:
    name: str
    data: bytes

    def data_url(self) -> str:
        # Raster allowlist: do not inline HTML/SVG or accept remote URLs.
        if self.data.startswith(b"\x89PNG\r\n\x1a\n"):
            media_type = "image/png"
        elif self.data.startswith(b"\xff\xd8\xff"):
            media_type = "image/jpeg"
        elif self.data.startswith(b"RIFF") and self.data[8:12] == b"WEBP":
            media_type = "image/webp"
        else:
            raise ValueError("Clean reports support PNG, JPEG, and WebP figures only.")
        return f"data:{media_type};base64,{base64.b64encode(self.data).decode('ascii')}"


def build_clean_report(
    *,
    prompt: str | None,
    result: JobResult,
    figures: list[ReportFigure],
    options: DisplayOptions = DisplayOptions(),
) -> str:
    """Build a self-contained, escaped report with an explicit content allowlist.

    The caller supplies the *submitted* prompt, never the current editor value.
    Deliberately omit account data, backend URLs, tokens, raw metadata, and traces.
    This is a presentation export, not a replacement for the full run archive.
    """
    assets = files("geoworld_open").joinpath("assets")
    template = Template(assets.joinpath("studio_report.html").read_text(encoding="utf-8"))
    css = assets.joinpath("studio_report.css").read_text(encoding="utf-8")
    script = assets.joinpath("studio_report.js").read_text(encoding="utf-8")
    script_hash = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    labels = {
        "geoworld_grounded": "Answer cites GeoWorld knowledge",
        "evidence_insufficient": "Insufficient evidence for a grounded answer",
        "general_model_uncited": "General model answer — no GeoWorld knowledge citations",
    }
    status = labels.get(result.grounding_status, "Scientific workflow result")
    citations = "".join(f"<li>{escape(line)}</li>" for line in human_citation_lines(result.citations))
    assumptions = "".join(f"<li>{escape(item)}</li>" for item in result.assumptions)
    image_html = "".join(
        f'<figure><img src="{figure.data_url()}" alt="{escape(figure.name, quote=True)}">'
        f"<figcaption>{escape(figure.name)}</figcaption></figure>"
        for figure in figures
    )
    return template.substitute(
        css=css,
        script=script,
        script_hash=script_hash,
        text_px=options.text_px,
        figure_px=options.figure_px,
        prompt=escape(prompt or "The original submitted question is unavailable for this older session."),
        answer=escape(result.answer),
        status=escape(status),
        citations=f'<ul class="citations">{citations}</ul>' if citations else "",
        assumptions=f"<section><h2>Assumptions &amp; limits</h2><ul>{assumptions}</ul></section>" if assumptions else "",
        figures=f"<section><h2>Model &amp; figures</h2>{image_html}</section>" if figures else "",
    )
