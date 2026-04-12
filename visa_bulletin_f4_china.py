def to_markdown_table(results: list[dict]) -> str:
    lines = [
        "| Bulletin | Final Action Date (China F4) | Date for Filing (China F4) |",
        "|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['bulletin']} | {r['final_action_date']} | {r['dates_for_filing']} |"
        )
    return "\n".join(lines)
