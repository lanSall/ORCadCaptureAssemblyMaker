"""Render Lab5 voltage doubler PDF pages and extract embedded images."""
import fitz
import re
import sys
from pathlib import Path
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PDF_PATH = (
    r"c:\Users\lance\OneDrive\College\Fall2025Undergrad\ECEN3314_Devices_Documents"
    r"\LAB Documents\LAB files\ECEN3314_Lab5_Voltage_Doubler.pdf"
)
OUT_DIR = Path(r"C:\Users\lance\tcl-mcp-server\labs\lab5_pages")
EMBED_DIR = OUT_DIR / "embedded"
ZOOM = 2.5

FIG1_TERMS = ["figure 1", "fig. 1", "fig 1"]
FIG4_TERMS = ["figure 4", "fig. 4", "fig 4"]


def page_hits(text: str) -> list[str]:
    tl = text.lower()
    hits = []
    if any(t in tl for t in FIG1_TERMS):
        hits.append("Figure1")
    if any(t in tl for t in FIG4_TERMS):
        hits.append("Figure4")
    return hits


def dump_labels(page, ymin=0, ymax=99999):
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


def find_figure_page(page_info, terms):
    for p1 in sorted(page_info):
        tl = page_info[p1]["text"].lower()
        if any(t in tl for t in terms):
            return p1
    return None


def crop_figure(doc, page_info, p1, terms, out_name):
    page = doc[p1 - 1]
    labels = dump_labels(page)
    caption_y = None
    for y, x, t in labels:
        if any(re.search(rf"{re.escape(term.replace(' ', r'\\s*'))}", t, re.I) for term in terms):
            caption_y = y
            break
    r = page.rect
    if caption_y:
        clip = fitz.Rect(
            r.x0 + 0.05 * r.width,
            r.y0 + 0.05 * r.height,
            r.x0 + 0.95 * r.width,
            caption_y - 5,
        )
    else:
        clip = fitz.Rect(
            r.x0 + 0.05 * r.width,
            r.y0 + 0.20 * r.height,
            r.x0 + 0.95 * r.width,
            r.y0 + 0.70 * r.height,
        )
    pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=clip, alpha=False)
    crop_path = OUT_DIR / out_name
    pix.save(crop_path.as_posix())
    return crop_path


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EMBED_DIR.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(PDF_PATH)
    print(f"PDF: {PDF_PATH}")
    print(f"Pages: {doc.page_count}\n")

    page_info = {}
    render_pages = set()
    for i in range(doc.page_count):
        p1 = i + 1
        text = doc[i].get_text()
        hits = page_hits(text)
        n_imgs = len(doc[i].get_images())
        page_info[p1] = {"hits": hits, "images": n_imgs, "text": text}
        if hits:
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
        saved_pngs.append(out_path)
        print(f"SUCCESS: {out_path.resolve()} ({out_path.stat().st_size:,} bytes)  {pix.width}x{pix.height}px")

    print("\n=== EXTRACT EMBEDDED IMAGES (Figure 4 pages) ===")
    fig4_pages = {p1 for p1 in render_pages if "Figure4" in page_info[p1]["hits"]}
    for p1 in sorted(fig4_pages):
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
                saved_pngs.append(out_path)
                print(
                    f"EMBED: {out_path.resolve()} ({out_path.stat().st_size:,} bytes)  {w}x{h}px  ext={ext}"
                )
            except Exception as e:
                print(f"FAIL page{p1} xref{xref}: {e}")

    print("\n=== FIGURE CROPS ===")
    fig1_page = find_figure_page(page_info, FIG1_TERMS)
    fig4_page = find_figure_page(page_info, FIG4_TERMS)
    if fig1_page:
        crop = crop_figure(
            doc,
            page_info,
            fig1_page,
            ["figure 1", "fig. 1", "fig 1"],
            f"ECEN3314_Lab5_page{fig1_page:02d}_fig1_schematic.png",
        )
        saved_pngs.append(crop)
        print(f"CROP Fig1: {crop.resolve()} ({crop.stat().st_size:,} bytes)")
    if fig4_page:
        crop = crop_figure(
            doc,
            page_info,
            fig4_page,
            ["figure 4", "fig. 4", "fig 4"],
            f"ECEN3314_Lab5_page{fig4_page:02d}_fig4_schematic.png",
        )
        saved_pngs.append(crop)
        print(f"CROP Fig4: {crop.resolve()} ({crop.stat().st_size:,} bytes)")

    print("\n=== FULL TEXT (Figure 1 / Figure 4 pages) ===")
    for p1 in sorted(render_pages):
        text = page_info[p1]["text"]
        print(f"\n===== PAGE {p1} (len={len(text)}) =====")
        print(text if len(text) <= 8000 else text[:8000] + "\n...[truncated]")

    print("\n=== LABEL INVENTORY ===")
    for fig_name, fig_page in [("Figure 1", fig1_page), ("Figure 4", fig4_page)]:
        if not fig_page:
            continue
        page = doc[fig_page - 1]
        h = page.rect.height
        labels = dump_labels(page)
        print(f"\n{fig_name} on page {fig_page}:")
        for y, x, t in labels:
            zone = "TOP" if y < h * 0.33 else ("MID" if y < h * 0.66 else "BOT")
            print(f"  [{zone:3s}] y={y:6.1f} x={x:6.1f} | {t}")

    fig4_crop = OUT_DIR / f"ECEN3314_Lab5_page{fig4_page:02d}_fig4_schematic.png" if fig4_page else None
    if fig4_crop and fig4_crop.exists():
        print("\n=== FIGURE 4 ASCII PREVIEW ===")
        print(ascii_preview(fig4_crop))

    print("\n=== SAVED PNG SUMMARY ===")
    for p in sorted(set(saved_pngs), key=lambda x: str(x)):
        if p.exists():
            print(f"{p.resolve()} | {p.stat().st_size:,} bytes")

    doc.close()


if __name__ == "__main__":
    main()
