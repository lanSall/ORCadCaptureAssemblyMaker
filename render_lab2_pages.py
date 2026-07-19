import fitz
import re
import os

pdf_path = r"c:\Users\lance\OneDrive\College\Fall2025Undergrad\ECEN3314_Devices_Documents\LAB Documents\LAB files\ECEN3314_Lab2_OpAmp_updated_saif.pdf"
out_dir = r"C:\Users\lance\tcl-mcp-server\lab2_pages"

doc = fitz.open(pdf_path)
print(f"PDF has {doc.page_count} pages")

pages_1based = [8, 9, 10]
zoom = 2.0
mat = fitz.Matrix(zoom, zoom)

for p1 in pages_1based:
    idx = p1 - 1
    if idx >= doc.page_count:
        print(f"WARNING: page {p1} out of range")
        continue
    page = doc[idx]
    pix = page.get_pixmap(matrix=mat, alpha=False)
    out_path = os.path.join(out_dir, f"page_{p1}.png")
    pix.save(out_path)
    size = os.path.getsize(out_path)
    print(f"SUCCESS: {out_path} ({size:,} bytes)")

all_text = ""
for p1 in pages_1based:
    idx = p1 - 1
    if idx < doc.page_count:
        t = doc[idx].get_text()
        all_text += f"\n===== PAGE {p1} =====\n" + t
        print(f"\n===== PAGE {p1} (len={len(t)}) =====")
        print(t if len(t) <= 4000 else t[:4000] + "\n...[truncated]")

print("\n--- Figure 8 context ---")
lower = all_text.lower()
fig8_idx = -1
for term in ["figure 8", "fig. 8", "fig 8"]:
    fig8_idx = lower.find(term)
    if fig8_idx >= 0:
        break

if fig8_idx >= 0:
    start = max(0, fig8_idx - 500)
    end = min(len(all_text), fig8_idx + 2000)
    print(all_text[start:end])
else:
    print("Figure 8 not found on pages 8-10; searching document...")
    full_parts = []
    for i in range(doc.page_count):
        full_parts.append(doc[i].get_text())
    full = "\n".join(full_parts)
    for term in ["Figure 8", "FIGURE 8", "Fig. 8", "Fig 8"]:
        pos = full.find(term)
        if pos >= 0:
            cum = 0
            for p1 in range(1, doc.page_count + 1):
                pt = doc[p1 - 1].get_text()
                if cum <= pos < cum + len(pt) + 1:
                    print(f"Found '{term}' on page {p1}")
                    break
                cum += len(pt) + 1
            print(full[max(0, pos - 500) : pos + 2000])
            fig8_idx = pos
            all_text = full
            break

search_text = all_text
if fig8_idx >= 0:
    search_text = all_text[max(0, fig8_idx - 800) : fig8_idx + 2500]

print("\n--- Resistor values found ---")
found = set()
for m in re.finditer(
    r"(R[1-4]|RF|RI|Rf|Ri)\s*[=:]\s*([\d.]+\s*[kKmM]?\s*Ω?)", search_text, re.I
):
    found.add(m.group(0))
for m in re.finditer(r"(R[1-4]|RF|RI)\b[^\n]{0,100}", search_text, re.I):
    s = m.group(0).replace("\n", " ").strip()
    if re.search(r"\d", s):
        found.add(s)
for m in re.finditer(r"(R[1-4]|RF|RI|Rf|Ri)[^\n]{0,100}", all_text, re.I):
    s = m.group(0).replace("\n", " ").strip()
    if re.search(r"\d", s):
        found.add(s)

if found:
    for item in sorted(found):
        print(item)
else:
    print("(no explicit R1-R4/RF/RI numeric values in extracted text)")

doc.close()
