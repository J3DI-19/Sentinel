from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.oxml.ns import qn


path = Path(r"E:\Traceveil\docs\Completion Report.docx")
document = Document(path)
table = document.tables[1]
checked = 0

for row in table.rows[1:]:
    for column_index in (1, 2):
        cell = row.cells[column_index]
        if cell.text.strip() != "Complete":
            continue
        shading = cell._tc.get_or_add_tcPr().findall(qn("w:shd"))
        assert len(shading) == 1, f"Expected one fill, found {len(shading)}"
        assert shading[0].get(qn("w:fill")) == "E8F5E9"
        checked += 1

with ZipFile(path) as archive:
    assert archive.testzip() is None

print(f"Verified {checked} Complete cells; DOCX archive is valid")
