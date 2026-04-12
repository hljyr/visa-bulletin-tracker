import re
from visa_bulletin_f4_china import main, to_markdown_table

README = "README.md"
START = ""
END   = ""

results = main(n_months=12)
table   = to_markdown_table(results)

with open(README, "r") as f:
    content = f.read()

new_section = f"{START}\n\n{table}\n\n{END}"
updated = re.sub(
    rf"{re.escape(START)}.*?{re.escape(END)}",
    new_section,
    content,
    flags=re.DOTALL
)

with open(README, "w") as f:
    f.write(updated)

print("README.md updated successfully.")
