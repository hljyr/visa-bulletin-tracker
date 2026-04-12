import re
from visa_bulletin_f4_china import main, to_markdown_table

README = "README.md"
START = "<!-- VISA_TABLE_START -->"
END   = "<!-- VISA_TABLE_END -->"

results = main(n_months=12)
table   = to_markdown_table(results)

with open(README, "r", encoding="utf-8") as f:
    content = f.read()

new_section = f"{START}\n\n{table}\n\n{END}"
updated = re.sub(
    rf"{re.escape(START)}.*?{re.escape(END)}",
    new_section,
    content,
    flags=re.DOTALL
)

if updated == content:
    print("WARNING: markers not found in README.md — check the file has the comment markers.")
else:
    with open(README, "w", encoding="utf-8") as f:
        f.write(updated)
    print("README.md updated successfully.")
    print("Table preview:")
    print(table)
