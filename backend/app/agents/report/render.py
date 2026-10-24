# app/agents/report/render.py
"""Markdown version of the report (what the student copies or downloads)."""

NO_NARRATIVE = "_The agent could not write a summary backed by the data for this section; the figures below are from the simulation._"


def _cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(columns: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(_cell(c) for c in columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    lines.extend("| " + " | ".join(_cell(v) for v in row) + " |" for row in rows)
    return lines


def render_markdown(title: str, generated_at: str, simulation_id: str, sections: list[dict]) -> str:
    lines = [f"# {title}", "", f"Generated on {generated_at} · Simulation `{simulation_id}`", ""]
    for section in sections:
        lines += [f"## {section['title']}", ""]
        if section["key"] == "disclaimer":
            lines += [f"_{section['narrative']}_", ""]
            continue
        lines += [section["narrative"] or NO_NARRATIVE, ""]
        if section["rows"]:
            lines += _table(["Item", "Value"], [[r["label"], r["value"]] for r in section["rows"]]) + [""]
        if section.get("table"):
            lines += _table(section["table"]["columns"], section["table"]["rows"]) + [""]
        if section.get("note"):
            lines += [f"_{section['note']}_", ""]
    return "\n".join(lines).rstrip() + "\n"
