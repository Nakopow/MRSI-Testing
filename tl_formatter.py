"""
tl_formatter.py
Reads tl_output_{topic}_{date}.json and builds branded .docx files.
Document design matches the Exoasia_MRSI_ThoughtLeadership_Template.docx exactly.
Pure Python / zipfile — works on Windows, macOS, Linux.

Usage:
    python tl_formatter.py                        # all tl_output_*.json next to this script
    python tl_formatter.py --input tl_output_ai_Mar11.json
    python tl_formatter.py --outdir TLPs
"""

import os, sys, re, json, base64, argparse, zipfile, uuid
from datetime import datetime
from glob import glob
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE   = os.path.join(SCRIPT_DIR, "Exoasia_MRSI_ThoughtLeadership_Template.docx")
DEFAULT_OUTDIR_NAME = "TLPs"

TOPIC_SLUG = {"ai": "AI", "cybersecurity": "CyberSec", "web3": "Web3"}

PLATFORM_EMOJIS = {
    "linkedin":  "💼",
    "youtube":   "🎬",
    "instagram": "📱",
    "facebook":  "👍",
    "tiktok":    "🎵",
}


def _find_docx_files(search_root: str) -> list[str]:
    """Best-effort discovery to help users point --template at the right .docx."""
    direct = glob(os.path.join(search_root, "*.docx"))
    recursive = glob(os.path.join(search_root, "**", "*.docx"), recursive=True)
    out: list[str] = []
    seen: set[str] = set()
    for p in direct + recursive:
        norm = os.path.normpath(p)
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _resolve_outdir(outdir_arg: Optional[str]) -> str:
    outdir = outdir_arg or DEFAULT_OUTDIR_NAME
    if os.path.isabs(outdir):
        return outdir
    return os.path.join(SCRIPT_DIR, outdir)

# ── XML helpers ───────────────────────────────────────────────────────────────

def esc(text):
    return (str(text)
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

def t(text):
    s = esc(text)
    sp = ' xml:space="preserve"' if text and (text[0]==" " or text[-1]==" ") else ""
    return f"<w:t{sp}>{s}</w:t>"

def pid():
    return uuid.uuid4().hex[:8].upper()

# ── Cover page paragraphs ─────────────────────────────────────────────────────

def p_cover_spacer():
    """Opening spacer with 2400 before — exactly as template."""
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:spacing w:before="2400"/></w:pPr>'
            f'</w:p>')

def p_cover_brand():
    """EXOASIA INNOVATION HUB — spacing after="40", letter-spaced, purple bold."""
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:spacing w:after="40"/></w:pPr>'
            f'<w:r><w:rPr>'
            f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
            f'<w:b/><w:bCs/><w:color w:val="7B3FA0"/>'
            f'<w:spacing w:val="120"/><w:sz w:val="20"/><w:szCs w:val="20"/>'
            f'</w:rPr><w:t>EXOASIA INNOVATION HUB</w:t></w:r></w:p>')

def p_cover_subtitle():
    """Market Research & Strategic Insight — purple bottom border, after="20"."""
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr>'
            f'<w:pBdr><w:bottom w:val="single" w:color="7B3FA0" w:sz="8" w:space="1"/></w:pBdr>'
            f'<w:spacing w:after="20"/>'
            f'</w:pPr>'
            f'<w:r><w:rPr><w:color w:val="8A8099"/></w:rPr>'
            f'<w:t>Market Research &amp; Strategic Insight</w:t></w:r></w:p>')

def p_cover_title(text):
    """Large dark title — before="600" after="80"."""
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:spacing w:before="600" w:after="80"/></w:pPr>'
            f'<w:r><w:rPr>'
            f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
            f'<w:b/><w:bCs/><w:color w:val="2D0A28"/>'
            f'<w:sz w:val="48"/><w:szCs w:val="48"/>'
            f'</w:rPr>{t(text)}</w:r></w:p>')

def p_cover_hook(text):
    """Purple subtitle line — before="80" after="40". rPr in both pPr and run."""
    rpr = ('<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
           '<w:color w:val="7B3FA0"/><w:sz w:val="28"/><w:szCs w:val="28"/>')
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:spacing w:before="80" w:after="40"/>'
            f'<w:rPr>{rpr}</w:rPr></w:pPr>'
            f'<w:r><w:rPr>{rpr}</w:rPr>{t(text)}</w:r></w:p>')

def p_cover_based_on(text):
    """Grey 'Based on' line — before="80" after="40". rPr in both pPr and run."""
    hook_rpr = ('<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
                '<w:color w:val="7B3FA0"/><w:sz w:val="28"/><w:szCs w:val="28"/>')
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:spacing w:before="80" w:after="40"/>'
            f'<w:rPr>{hook_rpr}</w:rPr></w:pPr>'
            f'<w:r><w:rPr><w:color w:val="8A8099"/></w:rPr>{t(text)}</w:r></w:p>')

def p_cover_tagline(text):
    """Light purple tagline — no extra spacing."""
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:r><w:rPr><w:color w:val="B095C5"/></w:rPr>{t(text)}</w:r></w:p>')

def p_cover_prepared():
    """'Prepared by MRSI Content Team' — before="1200"."""
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:spacing w:before="1200"/></w:pPr>'
            f'<w:r><w:rPr><w:color w:val="8A8099"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
            f'<w:t>Prepared by MRSI Content Team</w:t></w:r></w:p>')

def p_page_break():
    """Simple page break paragraph."""
    return (f'<w:p w14:paraId="{pid()}"><w:r><w:br w:type="page"/></w:r></w:p>')

def p_page_break_with_font():
    """Page break styled with large D4C5E8 font — used between piece sections."""
    rpr = ('<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
           '<w:b/><w:bCs/><w:color w:val="D4C5E8"/><w:sz w:val="56"/><w:szCs w:val="56"/>')
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:rPr>{rpr}</w:rPr></w:pPr>'
            f'<w:r><w:rPr>{rpr}</w:rPr><w:br w:type="page"/></w:r></w:p>')

# ── Section structure ─────────────────────────────────────────────────────────

def p_empty():
    """Bare empty paragraph."""
    return f'<w:p w14:paraId="{pid()}"/>'

def p_section_number(num_str):
    """Large light-purple section number — before="360" after="80". rPr in pPr too."""
    rpr = ('<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
           '<w:b/><w:bCs/><w:color w:val="D4C5E8"/><w:sz w:val="56"/><w:szCs w:val="56"/>')
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:spacing w:before="360" w:after="80"/>'
            f'<w:rPr>{rpr}</w:rPr></w:pPr>'
            f'<w:r><w:rPr>{rpr}</w:rPr>{t(num_str)}</w:r></w:p>')

def p_platform_title(emoji, rest):
    """Emoji + platform · angle — after="60"."""
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:spacing w:after="60"/></w:pPr>'
            f'<w:r><w:rPr>'
            f'<w:rFonts w:ascii="Segoe UI Symbol" w:hAnsi="Segoe UI Symbol" w:eastAsia="Arial" w:cs="Segoe UI Symbol"/>'
            f'<w:b/><w:bCs/><w:color w:val="2D0A28"/><w:sz w:val="28"/><w:szCs w:val="28"/>'
            f'</w:rPr>{t(emoji)}</w:r>'
            f'<w:r><w:rPr>'
            f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
            f'<w:b/><w:bCs/><w:color w:val="2D0A28"/><w:sz w:val="28"/><w:szCs w:val="28"/>'
            f'</w:rPr>{t("  " + rest)}</w:r></w:p>')

def p_divider():
    """Purple bottom-border rule — before="200" after="200", sz="6"."""
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr>'
            f'<w:pBdr><w:bottom w:val="single" w:color="7B3FA0" w:sz="6" w:space="1"/></w:pBdr>'
            f'<w:spacing w:before="200" w:after="200"/>'
            f'</w:pPr></w:p>')

def _label_rpr():
    return ('<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
            '<w:b/><w:bCs/><w:color w:val="7B3FA0"/>'
            '<w:spacing w:val="80"/><w:sz w:val="16"/><w:szCs w:val="16"/>')

def p_label(text):
    """Purple spaced small-caps label. rPr in both pPr and run, followed by empty label para."""
    rpr = _label_rpr()
    # label paragraph
    label_p = (f'<w:p w14:paraId="{pid()}">'
               f'<w:pPr><w:rPr>{rpr}</w:rPr></w:pPr>'
               f'<w:r><w:rPr>{rpr}</w:rPr>{t(text)}</w:r></w:p>')
    # empty paragraph with same pPr/rPr (template always has one after each label)
    empty_p = (f'<w:p w14:paraId="{pid()}">'
               f'<w:pPr><w:rPr>{rpr}</w:rPr></w:pPr>'
               f'</w:p>')
    return label_p + "\n" + empty_p

def p_body(text):
    """Plain body paragraph."""
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:r><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
            f'{t(text)}</w:r></w:p>')

# ── Copy block (purple left border, shaded) ───────────────────────────────────

def _copy_ppr(sz=20):
    return (f'<w:pBdr><w:left w:val="single" w:color="7B3FA0" w:sz="8" w:space="8"/></w:pBdr>'
            f'<w:shd w:val="clear" w:color="auto" w:fill="F5F3F8"/>'
            f'<w:ind w:left="202" w:right="202"/><w:jc w:val="both"/>'
            f'<w:rPr><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>')

def p_copy_empty():
    """Empty copy-block paragraph (sz=21 matches template opening line)."""
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr>{_copy_ppr(sz=21)}</w:pPr></w:p>')

def p_copy_line(text):
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr>{_copy_ppr(sz=20)}</w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
            f'{t(text)}</w:r></w:p>')

def copy_block(text):
    lines = [p_copy_empty()]
    for line in text.split("\n"):
        line = line.strip()
        lines.append(p_copy_line(line) if line else p_copy_empty())
    lines.append(p_copy_empty())
    return "\n".join(lines)

# ── Notes block (shaded, no border) ──────────────────────────────────────────

def _notes_ppr():
    return ('<w:shd w:val="clear" w:color="auto" w:fill="F5F3F8"/>'
            '<w:ind w:right="200"/><w:jc w:val="both"/>'
            '<w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>')

def p_notes_empty():
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr>{_notes_ppr()}</w:pPr></w:p>')

def p_notes_line(text):
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr>{_notes_ppr()}</w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
            f'{t(text)}</w:r></w:p>')

def notes_block(text):
    lines = [p_notes_empty()]
    for line in text.split("\n"):
        line = line.strip()
        lines.append(p_notes_line(line) if line else p_notes_empty())
    return "\n".join(lines)

# ── Caption block (shaded, indented both sides) ───────────────────────────────

def p_caption_line(text):
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr>'
            f'<w:shd w:val="clear" w:color="auto" w:fill="F5F3F8"/>'
            f'<w:ind w:left="200" w:right="200"/><w:jc w:val="both"/>'
            f'<w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
            f'</w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
            f'{t(text)}</w:r></w:p>')

def p_caption_empty():
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr>'
            f'<w:shd w:val="clear" w:color="auto" w:fill="F5F3F8"/>'
            f'<w:ind w:left="200" w:right="200"/>'
            f'<w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
            f'</w:pPr></w:p>')

def caption_block(text):
    lines = [p_caption_empty()]
    for line in text.split("\n"):
        line = line.strip()
        lines.append(p_caption_line(line) if line else p_caption_empty())
    lines.append(p_caption_empty())
    return "\n".join(lines)

# ── Slide breakdown ───────────────────────────────────────────────────────────

def p_slide_title(text):
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:spacing w:line="360" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>'
            f'<w:r><w:rPr>'
            f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
            f'<w:b/><w:bCs/><w:color w:val="2D0A28"/>'
            f'</w:rPr>{t(text)}</w:r></w:p>')

def p_slide_content(text):
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:jc w:val="both"/></w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
            f'{t(text)}</w:r></w:p>')

def slides_block(slides):
    lines = []
    for i, slide_text in enumerate(slides, 1):
        lines.append(p_slide_title(f"Slide {i}"))
        for line in slide_text.split("\n"):
            line = line.strip()
            if line:
                lines.append(p_slide_content(line))
        lines.append(p_empty())
    return "\n".join(lines)

# ── COMMENTS block ────────────────────────────────────────────────────────────

def comments_block():
    """Two empty paragraphs, COMMENTS:, two empty paragraphs — exactly as template."""
    return "\n".join([
        p_empty(),
        p_empty(),
        f'<w:p w14:paraId="{pid()}"><w:r><w:t>COMMENTS:</w:t></w:r></w:p>',
        p_empty(),
        p_empty(),
    ])

# ── Image (VML inline) ────────────────────────────────────────────────────────

IMG_DIMS = {
    "linkedin":  (171.75, 159.75),
    "youtube":   (199.5,  112.5),
    "instagram": (199.5,  111.0),
    "facebook":  (160.5,  135.75),
    "tiktok":    (113.25, 187.5),
}

def plat_key(platform_str):
    p = platform_str.lower()
    if "linkedin"  in p: return "linkedin"
    if "youtube"   in p or "video" in p: return "youtube"
    if "instagram" in p: return "instagram"
    if "facebook"  in p: return "facebook"
    if "tiktok"    in p: return "tiktok"
    return "linkedin"

def p_image_vml(rId, width_pt, height_pt):
    """Image paragraph matching template structure exactly: rPr with label styling."""
    vml_id = f"_x0000_i{abs(hash(rId)) % 9000 + 1000}"
    rpr = _label_rpr()
    return (f'<w:p w14:paraId="{pid()}">'
            f'<w:pPr><w:rPr>{rpr}</w:rPr></w:pPr>'
            f'<w:r><w:rPr>{rpr}</w:rPr>'
            f'<w:pict>'
            f'<v:shape id="{vml_id}" o:spt="75" type="#_x0000_t75" '
            f'style="height:{height_pt}pt;width:{width_pt}pt;" filled="f" '
            f'o:preferrelative="t" stroked="f" coordsize="21600,21600">'
            f'<v:path/><v:fill on="f" focussize="0,0"/>'
            f'<v:stroke on="f" joinstyle="miter"/>'
            f'<v:imagedata r:id="{rId}" o:title="image"/>'
            f'<o:lock v:ext="edit" aspectratio="t"/>'
            f'<w10:wrap type="none"/><w10:anchorlock/>'
            f'</v:shape></w:pict></w:r></w:p>')

# ── Overview table ────────────────────────────────────────────────────────────

def build_overview_table(pieces):
    """Exact replica of template table: dark header 2D0A28, alternating data rows."""

    def header_cell(text, w):
        return (f'<w:tc><w:tcPr>'
                f'<w:tcW w:w="{w}" w:type="dxa"/>'
                f'<w:tcBorders>'
                f'<w:top w:val="nil"/><w:left w:val="nil"/>'
                f'<w:bottom w:val="single" w:color="7B3FA0" w:sz="4" w:space="0"/>'
                f'<w:right w:val="nil"/>'
                f'</w:tcBorders>'
                f'<w:shd w:val="clear" w:color="auto" w:fill="2D0A28"/>'
                f'<w:tcMar>'
                f'<w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
                f'<w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/>'
                f'</w:tcMar></w:tcPr>'
                f'<w:p w14:paraId="{pid()}">'
                f'<w:r><w:rPr>'
                f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
                f'<w:b/><w:bCs/><w:color w:val="FFFFFF"/>'
                f'<w:sz w:val="18"/><w:szCs w:val="18"/>'
                f'</w:rPr>{t(text)}</w:r></w:p></w:tc>')

    def data_cell(text, w, bg):
        return (f'<w:tc><w:tcPr>'
                f'<w:tcW w:w="{w}" w:type="dxa"/>'
                f'<w:tcBorders>'
                f'<w:top w:val="nil"/><w:left w:val="nil"/>'
                f'<w:bottom w:val="single" w:color="D4C5E8" w:sz="0" w:space="0"/>'
                f'<w:right w:val="nil"/>'
                f'</w:tcBorders>'
                f'<w:shd w:val="clear" w:color="auto" w:fill="{bg}"/>'
                f'<w:tcMar>'
                f'<w:top w:w="60" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
                f'<w:bottom w:w="60" w:type="dxa"/><w:right w:w="120" w:type="dxa"/>'
                f'</w:tcMar></w:tcPr>'
                f'<w:p w14:paraId="{pid()}">'
                f'<w:r><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
                f'{t(text)}</w:r></w:p></w:tc>')

    tbl_borders = ('<w:tblBorders>'
                   '<w:top w:val="single" w:color="auto" w:sz="4" w:space="0"/>'
                   '<w:left w:val="single" w:color="auto" w:sz="4" w:space="0"/>'
                   '<w:bottom w:val="single" w:color="auto" w:sz="4" w:space="0"/>'
                   '<w:right w:val="single" w:color="auto" w:sz="4" w:space="0"/>'
                   '<w:insideH w:val="single" w:color="auto" w:sz="4" w:space="0"/>'
                   '<w:insideV w:val="single" w:color="auto" w:sz="4" w:space="0"/>'
                   '</w:tblBorders>')
    tbl_cell_mar = ('<w:tblCellMar>'
                    '<w:top w:w="0" w:type="dxa"/><w:left w:w="10" w:type="dxa"/>'
                    '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="10" w:type="dxa"/>'
                    '</w:tblCellMar>')

    header_row = (f'<w:tr w14:paraId="{pid()}">'
                  f'<w:tblPrEx>{tbl_borders}{tbl_cell_mar}</w:tblPrEx>'
                  + header_cell("#", 600)
                  + header_cell("PLATFORM", 2200)
                  + header_cell("FORMAT", 3560)
                  + header_cell("BASED ON QUESTION", 3000)
                  + '</w:tr>')

    # Last row has nil bottom borders instead of D4C5E8
    def data_row(piece, bg, is_last=False):
        def cell(text, w):
            bot_border = (f'<w:bottom w:val="nil"/>' if is_last
                          else f'<w:bottom w:val="single" w:color="D4C5E8" w:sz="0" w:space="0"/>')
            return (f'<w:tc><w:tcPr>'
                    f'<w:tcW w:w="{w}" w:type="dxa"/>'
                    f'<w:tcBorders>'
                    f'<w:top w:val="nil"/><w:left w:val="nil"/>'
                    f'{bot_border}'
                    f'<w:right w:val="nil"/>'
                    f'</w:tcBorders>'
                    f'<w:shd w:val="clear" w:color="auto" w:fill="{bg}"/>'
                    f'<w:tcMar>'
                    f'<w:top w:w="60" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
                    f'<w:bottom w:w="60" w:type="dxa"/><w:right w:w="120" w:type="dxa"/>'
                    f'</w:tcMar></w:tcPr>'
                    f'<w:p w14:paraId="{pid()}">'
                    f'<w:r><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
                    f'{t(text)}</w:r></w:p></w:tc>')

        return (f'<w:tr w14:paraId="{pid()}">'
                f'<w:tblPrEx>{tbl_borders}{tbl_cell_mar}</w:tblPrEx>'
                + cell(piece["number"], 600)
                + cell(piece["platform"], 2200)
                + cell(piece.get("format", piece.get("angle", "")), 3560)
                + cell(piece.get("based_on", "All 5 Questions"), 3000)
                + '</w:tr>')

    data_rows = ""
    for i, piece in enumerate(pieces):
        # Template: odd rows = F5F3F8, even rows = FFFFFF (1-indexed)
        bg = "F5F3F8" if (i + 1) % 2 == 1 else "FFFFFF"
        is_last = (i == len(pieces) - 1)
        data_rows += data_row(piece, bg, is_last=is_last)

    return (f'<w:tbl>'
            f'<w:tblPr>'
            f'<w:tblStyle w:val="9"/>'
            f'<w:tblW w:w="9360" w:type="dxa"/>'
            f'<w:tblInd w:w="0" w:type="dxa"/>'
            f'{tbl_borders}'
            f'<w:tblLayout w:type="autofit"/>'
            f'{tbl_cell_mar}'
            f'</w:tblPr>'
            f'<w:tblGrid>'
            f'<w:gridCol w:w="600"/><w:gridCol w:w="2200"/>'
            f'<w:gridCol w:w="3560"/><w:gridCol w:w="3000"/>'
            f'</w:tblGrid>'
            + header_row + data_rows + '</w:tbl>')

# ── Piece section builder ─────────────────────────────────────────────────────

def build_piece_section(piece, rId, is_last=False):
    parts = []
    pk = plat_key(piece["platform"])
    emoji = PLATFORM_EMOJIS.get(pk, "📄")
    title_rest = piece["platform"] + " · " + piece["angle"]
    img_w, img_h = IMG_DIMS.get(pk, (171.75, 159.75))

    parts.append(p_section_number(piece["number"]))
    parts.append(p_platform_title(emoji, title_rest))
    parts.append(p_divider())

    # FORMAT label + empty + body + empty
    parts.append(p_label("FORMAT"))
    parts.append(p_body(piece.get("format", "")))
    parts.append(p_empty())

    # OBJECTIVE label + empty + body + empty
    parts.append(p_label("OBJECTIVE"))
    parts.append(p_body(piece.get("objective", "")))
    parts.append(p_empty())

    # IMAGE / THUMBNAIL label + empty + image + two empties
    img_label = "THUMBNAIL" if pk in ("youtube", "tiktok") else "IMAGE"
    parts.append(p_label(img_label))
    if rId:
        parts.append(p_image_vml(rId, img_w, img_h))
    else:
        parts.append(p_empty())
    parts.append(p_empty())
    parts.append(p_empty())

    # Content — varies by platform
    if pk == "instagram":
        parts.append(p_label("SLIDE BREAKDOWN"))
        parts.append(slides_block(piece.get("slides", [])))
        parts.append(p_label("CAPTION"))
        parts.append(caption_block(piece.get("caption", "")))

    elif pk in ("youtube", "tiktok"):
        parts.append(p_label("SCRIPT"))
        parts.append(copy_block(piece.get("script", "")))
        if pk == "tiktok" and piece.get("caption"):
            parts.append(p_label("CAPTION"))
            parts.append(caption_block(piece.get("caption", "")))

    else:  # LinkedIn, Facebook
        parts.append(p_label("COPY"))
        parts.append(copy_block(piece.get("copy", "")))

    # POSTING NOTES / PRODUCTION NOTES label
    notes_label = "PRODUCTION NOTES" if pk == "youtube" else "POSTING NOTES"
    parts.append(p_label(notes_label))
    parts.append(notes_block(piece.get("posting_notes", "")))

    # COMMENTS block (2 empties, COMMENTS:, 2 empties)
    parts.append(comments_block())

    # Page break between sections (styled with big font rPr — matches template)
    if not is_last:
        parts.append(p_page_break_with_font())

    return "\n".join(parts)

# ── Full body builder ─────────────────────────────────────────────────────────

def build_body(data, rId_map):
    parts = []
    pieces = data.get("pieces", [])
    topic_display_map = {
        "ai": "AI Industry Briefing",
        "cybersecurity": "Cyber Security Briefing",
        "web3": "Crypto, Fintech & Web3 Briefing"
    }
    hook = topic_display_map.get(data.get("_topic_key", ""), "Daily Intelligence Briefing")

    # ── Cover page ──
    parts.append(p_cover_spacer())
    parts.append(p_cover_brand())
    parts.append(p_cover_subtitle())
    parts.append(p_cover_title("Thought Leadership Content Pack"))
    parts.append(p_cover_hook(hook))
    parts.append(p_cover_based_on(f"Based on MRSI Daily Insight \u2014 {data.get('_date', '')}"))
    parts.append(p_cover_tagline("5 Platforms  \u00b7  5 Content Pieces  \u00b7  Ready to Publish"))
    parts.append(p_cover_prepared())
    parts.append(p_page_break())

    # ── Content Overview ──
    ov_pid = uuid.uuid4().hex[:8].upper()
    parts.append(f'<w:p w14:paraId="{ov_pid}"><w:pPr><w:pStyle w:val="2"/></w:pPr>'
                 f'<w:r><w:t>Content Overview</w:t></w:r></w:p>')
    parts.append(p_divider())
    parts.append(build_overview_table(pieces))
    parts.append(p_page_break())

    # ── Platform sections ──
    for i, piece in enumerate(pieces):
        rId = rId_map.get(piece["number"])
        is_last = (i == len(pieces) - 1)
        parts.append(build_piece_section(piece, rId, is_last=is_last))

    return "\n".join(parts)

# ── Relationships ─────────────────────────────────────────────────────────────

BASE_RELS = """<?xml version="1.0" encoding="utf-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
  <Relationship Id="rId10" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/>
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
"""

def build_rels(img_rid_files):
    img_part = ""
    for rId, fname in img_rid_files.items():
        img_part += (f'  <Relationship Id="{rId}" '
                     f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                     f'Target="media/{fname}"/>\n')
    return BASE_RELS + img_part + "</Relationships>"

# ── Placeholder PNG ───────────────────────────────────────────────────────────

def _placeholder_png():
    import struct, zlib
    def chunk(name, data):
        c = struct.pack(">I", len(data)) + name + data
        return c + struct.pack(">I", zlib.crc32(c[4:]) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xaa\xaa\xaa")
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", idat)
            + chunk(b"IEND", b""))

# ── DOCX generator ────────────────────────────────────────────────────────────

def generate_docx(data, output_path, template=None):
    if template is None:
        template = TEMPLATE

    members = {}
    with zipfile.ZipFile(template, "r") as zin:
        for name in zin.namelist():
            members[name] = zin.read(name)

    # Embed images — rId5+ for each piece
    rId_map = {}
    rid_files = {}
    for i, piece in enumerate(data.get("pieces", [])):
        rId = f"rId{5 + i}"
        fname = f"image_piece{piece['number']}.png"
        rId_map[piece["number"]] = rId
        rid_files[rId] = fname
        b64 = piece.get("_img_b64")
        members[f"word/media/{fname}"] = (base64.b64decode(b64) if b64
                                           else _placeholder_png())

    # Patch document.xml
    orig = members["word/document.xml"].decode("utf-8")
    body_start = orig.index("<w:body>") + len("<w:body>")
    prefix = orig[:body_start]
    sect_m = re.search(r"<w:sectPr[\s\S]*?</w:sectPr>", orig)
    suffix = ("\n" + sect_m.group(0) if sect_m else "") + "\n</w:body>\n</w:document>"
    members["word/document.xml"] = (prefix + "\n" + build_body(data, rId_map) + suffix).encode("utf-8")

    # Patch relationships
    members["word/_rels/document.xml.rels"] = build_rels(rid_files).encode("utf-8")

    # Update footer date
    month_year = datetime.now().strftime("%B %Y")
    for name in list(members.keys()):
        if re.match(r"word/footer\d+\.xml", name):
            fxml = members[name].decode("utf-8")
            fxml = re.sub(
                r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}",
                month_year, fxml)
            members[name] = fxml.encode("utf-8")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, d in members.items():
            zout.writestr(name, d)
    return True

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",   default=None)
    ap.add_argument("--outdir",  default=None, help=f"Output folder (default: {DEFAULT_OUTDIR_NAME} under this repo)")
    ap.add_argument("--template", default=TEMPLATE)
    args = ap.parse_args()

    template_path = args.template
    if not os.path.exists(template_path):
        print(f"Error: template not found at '{template_path}'")
        docx_files = [p for p in _find_docx_files(SCRIPT_DIR)]
        if docx_files:
            print("\nFound these .docx files in the repo (use one with --template if appropriate):")
            for p in docx_files:
                print(f"  - {p}")
        print("\nFix options:")
        print(f"  1) Put your Thought Leadership template at: {TEMPLATE}")
        print("  2) Or pass the correct path: python tl_formatter.py --template <path-to-docx>")
        sys.exit(1)

    json_files = [args.input] if args.input else sorted(glob(os.path.join(SCRIPT_DIR, "tl_output_*.json")))
    if not json_files:
        print("No tl_output_*.json files found. Run tl_summarizer.py first.")
        sys.exit(1)

    outdir = _resolve_outdir(args.outdir)
    os.makedirs(outdir, exist_ok=True)
    date_slug = datetime.now().strftime("%b%d")

    for json_path in json_files:
        print(f"Processing {os.path.basename(json_path)} ...")
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        topic_key = data.get("_topic_key", "unknown")
        slug = TOPIC_SLUG.get(topic_key, topic_key.capitalize())
        out_path = os.path.join(outdir, f"Exoasia_MRSI_ThoughtLeadership_{date_slug}_{slug}.docx")
        ok = generate_docx(data, out_path, template=args.template)
        print(f"  {'OK' if ok else 'FAILED'}  {os.path.basename(out_path)}")

if __name__ == "__main__":
    main()