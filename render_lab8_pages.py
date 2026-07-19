"""Render Lab8 PDF simulation pages and extract embedded images."""
import fitz
import re
import os
import sys
from pathlib import Path
from PIL import Image

# Force UTF-8 stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PDF_PATH = r"c:\Users\lance\OneDrive\College\Fall2025Undergrad\ECEN3314_Devices_Documents\LAB Documents\LAB files\ECEN3314_Lab8_CS_Amplifier.pdf"
OUT_DIR = Path(r"C:\Users\lance\tcl-mcp-server\lab8_pages")
EMBED_DIR = OUT_DIR / "embedded"
ZOOM = 2.5

FIG6_TERMS = ["figure 6", "fig. 6", "fig 6"]
SIM_TERMS = ["simulation", "simulate", "pspice", "bode", "ac sweep", "transient"]
FIG4_TERMS = ["figure 4", "fig. 4", "fig 4"]
SEC6_TERMS = ["section 6", "6. simulation", "6 simulation"]


def page_hits(text: str) -> list[str]:
    tl = text.lower()
    hits = []
    if any(t in tl for t in FIG6_TERMS):
        hits.append("Figure6")
    if any(t in tl for t in FIG4_TERMS):
        hits.append("Figure4")
    if any(t in tl for t in SIM_TERMS):
        hits.append("Simulation")
    if any(t in tl for t in SEC6_TERMS) or re.search(r"\b6\.\d", text):
        hits.append("Section6")
    return hits


def ascii_preview(path: Path, width: int = 100) -> str:
    im = Image.open(path).convert("L")
    w, h = im.size
    new_w = width
    new_h = max(1, int(h * (new_w / w) * 0.45))
    im = im.resize((new_w, new_h))
    px = im.load()
    chars = " .:-=+*#%@"
    return "\n".join(
        "".join(chars[min(len(chars) - 1, px[x, y] * len(chars) // 256)] for x in range(new_w))
        for y in range(new_h)
    )


def dump_labels(page, ymin=0, ymax=99999):
    h = page.rect.height
    items = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for sp in line.get("spans", []):
                t = sp["text"].strip()
                if not t:
                    continue
                y = sp["bbox"][1]
                x = sp["bbox"][0]
                if ymin <= y <= ymax:
                    items.append((y, x, t))
    items.sort()
    return items


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EMBED_DIR.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(PDF_PATH)
    print(f"PDF: {PDF_PATH}")
    print(f"Pages: {doc.page_count}\n")

    # --- Scan all pages ---
    render_pages = set()
    page_info = {}
    for i in range(doc.page_count):
        p1 = i + 1
        text = doc[i].get_text()
        hits = page_hits(text)
        n_imgs = len(doc[i].get_images())
        page_info[p1] = {"hits": hits, "images": n_imgs, "text": text}
        if hits and ("Figure6" in hits or "Simulation" in hits or "Figure4" in hits):
            render_pages.add(p1)
        # Also render pages with embedded images in section 6 context
        if "Section6" in hits and n_imgs > 0:
            render_pages.add(p1)

    # Ensure pages with figure captions even if only in images
    for i in range(doc.page_count):
        p1 = i + 1
        text = doc[i].get_text().lower()
        if any(t in text for t in FIG6_TERMS + FIG4_TERMS):
            render_pages.add(p1)

    mat = fitz.Matrix(ZOOM, ZOOM)
    saved_pngs = []

    print("=== PAGE SCAN ===")
    for p1 in range(1, doc.page_count + 1):
        info = page_info[p1]
        flag = "RENDER" if p1 in render_pages else "skip"
        print(f"  Page {p1:2d}: {flag:6s} hits={info['hits']} embedded_images={info['images']}")

    print("\n=== RENDER FULL PAGES ===")
    for p1 in sorted(render_pages):
        pix = doc[p1 - 1].get_pixmap(matrix=mat, alpha=False)
        out_path = OUT_DIR / f"page_{p1:02d}.png"
        pix.save(out_path.as_posix())
        size = out_path.stat().st_size
        saved_pngs.append(out_path)
        print(f"SUCCESS: {out_path.resolve()} ({size:,} bytes)  {pix.width}x{pix.height}px")

    # --- Extract embedded images ---
    print("\n=== EXTRACT EMBEDDED IMAGES ===")
    img_counter = 0
    for p1 in range(1, doc.page_count + 1):
        page = doc[p1 - 1]
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                base = doc.extract_image(xref)
                ext = base["ext"]
                data = base["image"]
                w, h = base.get("width"), base.get("height")
                out_path = EMBED_DIR / f"page{p1:02d}_img{img_index:02d}_xref{xref}.{ext}"
                out_path.write_bytes(data)
                size = out_path.stat().st_size
                saved_pngs.append(out_path)
                img_counter += 1
                print(
                    f"EMBED: {out_path.resolve()} ({size:,} bytes)  {w}x{h}px  ext={ext}"
                )
            except Exception as e:
                print(f"FAIL page{p1} xref{xref}: {e}")

    # --- Crop Figure 6 if identifiable ---
    print("\n=== FIGURE CROPS ===")
    fig6_page = None
    for p1 in range(1, doc.page_count + 1):
        tl = page_info[p1]["text"].lower()
        if any(t in tl for t in FIG6_TERMS):
            fig6_page = p1
            break

    if fig6_page:
        page = doc[fig6_page - 1]
        labels = dump_labels(page)
        # Find "Figure 6" caption y
        fig6_y = None
        for y, x, t in labels:
            if re.search(r"figure\s*6|fig\.\s*6", t, re.I):
                fig6_y = y
                break
        r = page.rect
        # Schematic usually above caption
        if fig6_y:
            clip = fitz.Rect(r.x0 + 0.05 * r.width, r.y0 + 0.05 * r.height,
                             r.x0 + 0.95 * r.width, fig6_y - 5)
        else:
            clip = fitz.Rect(r.x0 + 0.05 * r.width, r.y0 + 0.05 * r.height,
                             r.x0 + 0.95 * r.width, r.y0 + 0.55 * r.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=clip, alpha=False)
        crop_path = OUT_DIR / f"ECEN3314_Lab8_page{fig6_page:02d}_fig6_schematic.png"
        pix.save(crop_path.as_posix())
        saved_pngs.append(crop_path)
        print(f"CROP Fig6: {crop_path.resolve()} ({crop_path.stat().st_size:,} bytes)")

    # Figure 4 crop
    fig4_page = None
    for p1 in range(1, doc.page_count + 1):
        tl = page_info[p1]["text"].lower()
        if any(t in tl for t in FIG4_TERMS):
            fig4_page = p1
            break
    if fig4_page:
        page = doc[fig4_page - 1]
        labels = dump_labels(page)
        fig4_y = None
        for y, x, t in labels:
            if re.search(r"figure\s*4|fig\.\s*4", t, re.I):
                fig4_y = y
                break
        r = page.rect
        if fig4_y:
            clip = fitz.Rect(r.x0 + 0.05 * r.width, r.y0 + 0.05 * r.height,
                             r.x0 + 0.95 * r.width, fig4_y - 5)
        else:
            clip = fitz.Rect(r.x0 + 0.05 * r.width, r.y0 + 0.30 * r.height,
                             r.x0 + 0.95 * r.width, r.y0 + 0.75 * r.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=clip, alpha=False)
        crop_path = OUT_DIR / f"ECEN3314_Lab8_page{fig4_page:02d}_fig4_schematic.png"
        pix.save(crop_path.as_posix())
        saved_pngs.append(crop_path)
        print(f"CROP Fig4: {crop_path.resolve()} ({crop_path.stat().st_size:,} bytes)")

    # --- Full text dump for section 6 ---
    print("\n=== SECTION 6 TEXT (all pages mentioning Section 6 / simulation) ===")
    sec6_text = ""
    for p1 in range(1, doc.page_count + 1):
        text = page_info[p1]["text"]
        tl = text.lower()
        if "section 6" in tl or re.search(r"\b6\.\d", text) or any(t in tl for t in SIM_TERMS):
            sec6_text += f"\n===== PAGE {p1} =====\n{text}\n"
            print(f"\n===== PAGE {p1} (len={len(text)}) =====")
            print(text if len(text) <= 6000 else text[:6000] + "\n...[truncated]")

    # --- Figure 6 label positions (orientation inventory) ---
    print("\n=== FIGURE 6 ORIENTATION INVENTORY (label positions) ===")
    if fig6_page:
        page = doc[fig6_page - 1]
        h = page.rect.height
        labels = dump_labels(page, 0, h)
        print(f"Figure 6 found on page {fig6_page}, page size {page.rect.width:.0f}x{h:.0f}")
        # Partition by vertical thirds for orientation
        for y, x, t in labels:
            zone = "TOP" if y < h * 0.33 else ("MID" if y < h * 0.66 else "BOT")
            print(f"  [{zone:3s}] y={y:6.1f} x={x:6.1f} | {t}")

        # Drawing analysis on schematic region
        dr = page.get_drawings()
        hv = {"h": 0, "v": 0, "other": 0}
        schematic_ymax = fig6_y if fig6_y else h * 0.55
        for d in dr:
            rect = d.get("rect")
            if not rect or rect.y0 > schematic_ymax:
                continue
            for it in d.get("items", []):
                if not it:
                    continue
                if it[0] == "l" and len(it) >= 3:
                    p1pt, p2pt = it[1], it[2]
                    dx, dy = abs(p2pt.x - p1pt.x), abs(p2pt.y - p1pt.y)
                    if dx > dy * 2:
                        hv["h"] += 1
                    elif dy > dx * 2:
                        hv["v"] += 1
                    else:
                        hv["other"] += 1
        print(f"  Schematic wire segments (above caption): h={hv['h']} v={hv['v']} other={hv['other']}")

    # --- Component value extraction from section 6 ---
    print("\n=== COMPONENT VALUES IN SECTION 6 TEXT ===")
    patterns = [
        r"(R[DGLS\d]*|C\d+|VDD|VGG|VSIN|M\d?)\s*[=:]\s*([^\n,;]+)",
        r"(\d+\.?\d*\s*[kKmMuUnNpP]?[ΩFHzV]?)",
        r"(RD|RL|RG|RS|C1|C2|VDD|VGG|VSIN|NMOS|PMOS|MOSFET)[^\n]{0,80}",
    ]
    found = set()
    for pat in patterns:
        for m in re.finditer(pat, sec6_text, re.I):
            s = m.group(0).replace("\n", " ").strip()
            if re.search(r"\d|[kKmM]", s) or s.upper() in ("VDD", "VGG", "VSIN", "RD", "RL", "C1"):
                found.add(s)
    for item in sorted(found):
        print(f"  {item}")

    # --- ASCII preview of fig6 crop ---
    fig6_crop = OUT_DIR / f"ECEN3314_Lab8_page{fig6_page:02d}_fig6_schematic.png" if fig6_page else None
    if fig6_crop and fig6_crop.exists():
        print("\n=== FIGURE 6 ASCII PREVIEW ===")
        print(ascii_preview(fig6_crop))

    # --- Summary of saved files ---
    print("\n=== SAVED PNG SUMMARY ===")
    for p in sorted(set(saved_pngs)):
        if p.exists():
            print(f"{p.resolve()} | {p.stat().st_size:,} bytes")

    doc.close()


if __name__ == "__main__":
    main()
