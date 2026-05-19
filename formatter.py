"""
formatter.py  —  Exoasia MRSI Daily Insight generator
Produces one .docx per topic from output.txt, pixel-perfect vs the template.

Strategy: unpack template → replace body XML → pack with pack.py

Usage:
    python formatter.py
    python formatter.py --input output.txt --outdir ./reports

Requires in same folder:
    Exoasia_MRSI_DailyInsight_Mar9_AI.docx
"""

import os, re, sys, zipfile, tempfile, argparse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE   = os.path.join(SCRIPT_DIR, "Exoasia_MRSI_DailyInsight_Mar9_AI.docx")

TOPIC_MAP = {
    "ARTIFICIAL INTELLIGENCE": ("AI Briefing",                         "AI"),
    "AI":                      ("AI Briefing",                         "AI"),
    "CYBERSECURITY":           ("Cyber Security Briefing",             "CyberSec"),
    "CYBER SECURITY":          ("Cyber Security Briefing",             "CyberSec"),
    "WEB3 / BLOCKCHAIN":       ("Crypto, Fintech, and Web3 Briefing",  "Web3"),
    "WEB3":                    ("Crypto, Fintech, and Web3 Briefing",  "Web3"),
    "BLOCKCHAIN":              ("Crypto, Fintech, and Web3 Briefing",  "Web3"),
}

# ── XML helpers ───────────────────────────────────────────────────────────────

def x(s):
    """XML-escape."""
    return (s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
             .replace('"',"&quot;"))

# ── Paragraph XML builders (copied exactly from template structure) ────────────

def p_title(text):
    return f"""<w:p>
  <w:pPr>
    <w:spacing w:before="59"/>
    <w:ind w:left="180"/>
    <w:rPr>
      <w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>
      <w:b/><w:bCs/>
      <w:color w:val="2C0928"/>
      <w:sz w:val="56"/><w:szCs w:val="56"/>
    </w:rPr>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>
      <w:b/><w:bCs/>
      <w:color w:val="2C0928"/>
      <w:sz w:val="56"/><w:szCs w:val="56"/>
    </w:rPr>
    <w:t>{x(text)}</w:t>
  </w:r>
</w:p>"""

def p_subtitle(text):
    return f"""<w:p>
  <w:pPr>
    <w:spacing w:before="59"/>
    <w:ind w:left="180"/>
    <w:rPr>
      <w:rFonts w:ascii="Arial"/>
      <w:b/>
      <w:sz w:val="26"/>
    </w:rPr>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:rFonts w:ascii="Arial"/>
      <w:b/>
      <w:color w:val="7A3E9F"/>
      <w:sz w:val="26"/>
    </w:rPr>
    <w:t>{x(text)}</w:t>
  </w:r>
</w:p>"""

def p_section_heading(text):
    """'Executive Summary', '5 Questions...', 'Sources' — style 2"""
    return f"""<w:p>
  <w:pPr>
    <w:pStyle w:val="2"/>
    <w:spacing w:before="242"/>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:color w:val="491040"/>
    </w:rPr>
    <w:t>{x(text)}</w:t>
  </w:r>
</w:p>"""

def p_exec_bullet(label, body):
    """Exec summary bullet — style 9, numId 1, optional bold label."""
    label_run = ""
    if label:
        label_run = f"""  <w:r>
    <w:rPr>
      <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
      <w:b/>
      <w:color w:val="1A1A1A"/>
    </w:rPr>
    <w:t xml:space="preserve">{x(label.rstrip(':'))}: </w:t>
  </w:r>
"""
    return f"""<w:p>
  <w:pPr>
    <w:pStyle w:val="9"/>
    <w:numPr>
      <w:ilvl w:val="0"/>
      <w:numId w:val="1"/>
    </w:numPr>
    <w:tabs><w:tab w:val="left" w:pos="900"/></w:tabs>
    <w:spacing w:before="118"/>
    <w:ind w:right="435"/>
  </w:pPr>
{label_run}  <w:r>
    <w:rPr>
      <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
      <w:color w:val="1A1A1A"/>
    </w:rPr>
    <w:t>{x(body)}</w:t>
  </w:r>
</w:p>"""

def p_body_subheading(text):
    """Body section sub-heading — style 5, bold, color 491040, 14pt, justified.
    Exact match of template P08/P12."""
    return f"""<w:p>
  <w:pPr>
    <w:pStyle w:val="5"/>
    <w:keepNext w:val="0"/>
    <w:widowControl w:val="0"/>
    <w:spacing w:before="298" w:after="120"/>
    <w:ind w:left="187" w:right="173"/>
    <w:jc w:val="both"/>
    <w:rPr>
      <w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>
      <w:b/><w:bCs/>
      <w:color w:val="491040"/>
      <w:sz w:val="28"/><w:szCs w:val="28"/>
    </w:rPr>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>
      <w:b/><w:bCs/>
      <w:color w:val="491040"/>
      <w:sz w:val="28"/><w:szCs w:val="28"/>
    </w:rPr>
    <w:t>{x(text)}</w:t>
  </w:r>
</w:p>"""

def p_body_para(text):
    """Body paragraph — style 5, justified, color 1A1A1A. Exact match of template P09."""
    return f"""<w:p>
  <w:pPr>
    <w:pStyle w:val="5"/>
    <w:keepNext w:val="0"/>
    <w:widowControl w:val="0"/>
    <w:spacing w:after="120"/>
    <w:ind w:left="187" w:right="173"/>
    <w:jc w:val="both"/>
    <w:rPr>
      <w:color w:val="1A1A1A"/>
    </w:rPr>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:color w:val="1A1A1A"/>
    </w:rPr>
    <w:t>{x(text)}</w:t>
  </w:r>
</w:p>"""

def p_body_bullet(text):
    """Bullet inside body section — same style 9 / numId 1 as exec bullets."""
    return f"""<w:p>
  <w:pPr>
    <w:pStyle w:val="9"/>
    <w:numPr>
      <w:ilvl w:val="0"/>
      <w:numId w:val="1"/>
    </w:numPr>
    <w:spacing w:before="61"/>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
      <w:color w:val="1A1A1A"/>
    </w:rPr>
    <w:t>{x(text)}</w:t>
  </w:r>
</w:p>"""

def p_question(text):
    """Numbered question — style 9, numId 2. Exact match of template P26."""
    return f"""<w:p>
  <w:pPr>
    <w:pStyle w:val="9"/>
    <w:numPr>
      <w:ilvl w:val="0"/>
      <w:numId w:val="2"/>
    </w:numPr>
    <w:tabs>
      <w:tab w:val="left" w:pos="898"/>
      <w:tab w:val="left" w:pos="900"/>
    </w:tabs>
    <w:spacing w:before="162"/>
    <w:ind w:right="237"/>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:color w:val="1A1A1A"/>
    </w:rPr>
    <w:t>{x(text)}</w:t>
  </w:r>
</w:p>"""

def p_source(text):
    """Source line — style 9, NO numId, gray, 10pt. Exact match of template P34."""
    return f"""<w:p>
  <w:pPr>
    <w:pStyle w:val="9"/>
    <w:tabs><w:tab w:val="left" w:pos="482"/></w:tabs>
    <w:spacing w:before="120"/>
    <w:ind w:left="180" w:right="180" w:firstLine="0"/>
    <w:rPr>
      <w:sz w:val="20"/>
    </w:rPr>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:color w:val="666666"/>
      <w:sz w:val="20"/>
    </w:rPr>
    <w:t>{x(text)}</w:t>
  </w:r>
</w:p>"""

def p_spacer():
    return "<w:p/>"

def p_footer_produced():
    """Exact copy of template P36 'Produced by Exoasia Innovation Hub...'"""
    return """<w:p>
  <w:pPr>
    <w:spacing w:before="202"/>
    <w:ind w:right="1"/>
    <w:jc w:val="center"/>
    <w:rPr><w:sz w:val="20"/></w:rPr>
  </w:pPr>
  <w:r><w:rPr><w:color w:val="666666"/><w:sz w:val="20"/></w:rPr><w:t xml:space="preserve">Produced by </w:t></w:r>
  <w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:b/><w:color w:val="491040"/><w:sz w:val="20"/></w:rPr><w:t xml:space="preserve">Exoasia Innovation Hub</w:t></w:r>
  <w:r><w:rPr><w:color w:val="666666"/><w:sz w:val="20"/></w:rPr><w:t xml:space="preserve"> &#x2014; Market Research and Strategic Insight (MRSI)</w:t></w:r>
</w:p>"""

def p_footer_tagline():
    """Exact copy of template P37 'For thought leadership...'"""
    return """<w:p>
  <w:pPr>
    <w:spacing w:before="39"/>
    <w:ind w:left="1" w:right="1"/>
    <w:jc w:val="center"/>
    <w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:b/><w:i/><w:sz w:val="20"/></w:rPr>
  </w:pPr>
  <w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:i/><w:color w:val="666666"/><w:sz w:val="20"/></w:rPr><w:t xml:space="preserve">For thought leadership, custom research, and position papers &#x2014; </w:t></w:r>
  <w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:b/><w:i/><w:color w:val="491040"/><w:sz w:val="20"/></w:rPr><w:t>contact our team.</w:t></w:r>
</w:p>"""

# ── Output.txt parser ─────────────────────────────────────────────────────────

def split_topics(filepath):
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()
    topics, cur_key, cur_lines = {}, None, []
    for line in lines:
        s = line.strip()
        m = re.match(r"^##\s+(.+)$", s)
        if m:
            candidate = m.group(1).strip().upper()
            if cur_key: topics[cur_key]["lines"] = cur_lines
            if candidate in TOPIC_MAP:
                display, slug = TOPIC_MAP[candidate]
                topics[candidate] = {"display": display, "slug": slug, "lines": []}
                cur_key, cur_lines = candidate, []
            else:
                cur_key, cur_lines = None, []
            continue
        if cur_key is not None:
            cur_lines.append(line.rstrip())
    if cur_key: topics[cur_key]["lines"] = cur_lines
    return topics

RE_SEP   = re.compile(r"^[=\-]{4,}$")
RE_EXEC  = re.compile(r"^Executive Summary\s*:?\s*$", re.I)
RE_DET   = re.compile(r"^(Detailed Examination|Conclusion)\s*:?\s*$", re.I)
RE_QHDR  = re.compile(r"targeted questions|questions for thought|5 questions", re.I)
RE_SRC   = re.compile(r"^Sources?\s*:?\s*$", re.I)
RE_QLINE = re.compile(r"^\d+[\.\)]+\s*(.+)$")   # matches "1.) text" or "1. text"
RE_DASH  = re.compile(r"^-\s+(.+)$")

def _is_subheading(s):
    if not s: return False
    for p in (RE_EXEC, RE_DET, RE_SRC):
        if p.match(s): return False
    if RE_QHDR.search(s) or RE_QLINE.match(s) or RE_DASH.match(s): return False
    if "[" in s or s.endswith("."): return False  # citations or sentence = not a heading
    # Accept lines ending with colon (old style) OR short title-case lines without period
    if s.endswith(":"):
        return len(s) <= 120 and bool(re.match(r"^[A-Z]", s))
    # Plain sub-heading (no colon): short, starts capital, no lowercase run suggesting prose
    if len(s) > 80: return False
    if not re.match(r"^[A-Z]", s): return False
    # Must look like a title: mostly capitalized words, not a prose sentence
    words = s.split()
    if len(words) < 2 or len(words) > 10: return False
    # If more than half words are lowercase (excluding short connectors), it's prose
    non_connectors = [w for w in words if w.lower() not in ("a","an","the","and","or","of","in","to","for","with","by","on","at","its","is","are","was","were","has","have")]
    cap_count = sum(1 for w in non_connectors if w and w[0].isupper())
    return cap_count >= len(non_connectors) * 0.6

def parse_topic(lines):
    out = {"title": "", "subtitle": "", "exec": [], "body": [], "questions": [], "sources": []}
    clean = [l.rstrip() for l in lines if not RE_SEP.match(l.strip())]
    while clean and not clean[0].strip(): clean.pop(0)

    mode = None
    cur_h, cur_p = None, []

    def flush():
        if cur_h is not None or cur_p:
            out["body"].append({"heading": cur_h, "paras": list(cur_p)})

    for line in clean:
        s = line.strip()

        # Article title — first real line that isn't a subtitle
        if not out["title"] and s and mode is None:
            if "Briefing:" in s: out["subtitle"] = s
            else:                out["title"] = s
            mode = "pre"; continue

        # Subtitle — second meaningful line containing "Briefing:"
        if not out["subtitle"] and "Briefing:" in s and mode == "pre":
            out["subtitle"] = s; continue

        if RE_EXEC.match(s):  mode = "exec"; continue
        if RE_DET.match(s):   flush(); cur_h, cur_p = None, []; mode = "body"; continue
        if RE_QHDR.search(s): flush(); cur_h, cur_p = None, []; mode = "q";    continue
        if RE_SRC.match(s):   flush(); cur_h, cur_p = None, []; mode = "src";  continue
        if not s: continue

        if mode == "exec":
            dm = RE_DASH.match(s)
            text = dm.group(1).strip() if dm else s
            # Try **BoldLabel:** format (Gemini uses ** for exec labels only)
            lm = re.match(r"^\*\*(.+?)\*\*:?\s+(.+)$", text)
            if not lm:
                lm = re.match(r"^([A-Z][A-Za-z0-9 /\-]+):\s+(.+)$", text)
            if lm and len(lm.group(1)) < 60:
                out["exec"].append({"label": lm.group(1).strip(), "text": lm.group(2).strip()})
            else:
                out["exec"].append({"label": "", "text": text})

        elif mode == "body":
            if _is_subheading(s):
                flush(); cur_h = s.rstrip(":"); cur_p = []
            elif RE_DASH.match(s):
                cur_p.append("•" + RE_DASH.match(s).group(1).strip())
            else:
                cur_p.append(s)

        elif mode == "q":
            qm = RE_QLINE.match(s)
            if qm: out["questions"].append(qm.group(1).strip())
            elif not re.match(r"^In light", s, re.I): out["questions"].append(s)

        elif mode == "src":
            out["sources"].append(s)

    flush()
    return out

# ── Body XML assembler ────────────────────────────────────────────────────────

def build_body(content, topic_display, date_str):
    parts = []
    subtitle = content["subtitle"] or f"{topic_display}: {date_str}"

    parts.append(p_title(content["title"] or topic_display))
    parts.append(p_subtitle(subtitle))
    parts.append(p_section_heading("Executive Summary"))

    for item in content["exec"]:
        parts.append(p_exec_bullet(item["label"], item["text"]))

    for section in content["body"]:
        if section["heading"]:
            parts.append(p_body_subheading(section["heading"]))
        for para in section["paras"]:
            if not para.strip(): continue
            if para.startswith("•"):
                parts.append(p_body_bullet(para[1:].strip()))
            else:
                parts.append(p_body_para(para))

    if content["questions"]:
        parts.append(p_section_heading("5 Questions for Thought Leadership"))
        for q in content["questions"]:
            parts.append(p_question(q))

    if content["sources"]:
        parts.append(p_section_heading("Sources"))
        for src in content["sources"]:
            parts.append(p_source(src))

    parts.append(p_spacer())
    parts.append(p_footer_produced())
    parts.append(p_footer_tagline())

    return "\n".join(parts)

# ── DOCX generator ────────────────────────────────────────────────────────────

def _update_header_date(xml, new_month, new_day, new_year):
    """Update split date runs in header XML. Template stores date as
    separate <w:t> runs: 'March'  ' '  '09,'  ' '  '2026'"""
    xml = re.sub(
        r"(<w:t[^>]*>)(January|February|March|April|May|June|July|"
        r"August|September|October|November|December)(</w:t>)",
        lambda m: m.group(1) + new_month + m.group(3), xml)
    xml = re.sub(
        r"(<w:t[^>]*>)(\d{2},)(</w:t>)",
        lambda m: m.group(1) + new_day + m.group(3), xml)
    xml = re.sub(
        r"(<w:t[^>]*>)(20\d{2})(</w:t>)",
        lambda m: m.group(1) + new_year + m.group(3), xml)
    return xml


def generate_docx(content, topic_display, date_str, output_path, template=None):
    """Pure-Python docx generator — works on Windows, Linux, and macOS.
    Reads template zip, patches document.xml and headers in-memory, writes new zip."""
    if template is None:
        template = TEMPLATE

    new_month = datetime.now().strftime("%B")   # e.g. "March"
    new_day   = datetime.now().strftime("%d,")  # e.g. "11,"
    new_year  = datetime.now().strftime("%Y")   # e.g. "2026"

    try:
        # ── Read all files from the template zip into memory ──────────────────
        members = {}
        with zipfile.ZipFile(template, "r") as zin:
            for name in zin.namelist():
                members[name] = zin.read(name)

        # ── Patch word/document.xml ───────────────────────────────────────────
        orig = members["word/document.xml"].decode("utf-8")

        BAR = "7EDAEDFB"
        if BAR in orig:
            pos    = orig.index(BAR)
            end    = orig.index("</w:p>", pos) + len("</w:p>")
            prefix = orig[:end]
        else:
            prefix = orig[:orig.index("<w:body>") + len("<w:body>")]

        sect_m = re.search(r"<w:sectPr[\s\S]*?</w:sectPr>", orig)
        suffix = ("\n" + sect_m.group(0) if sect_m else "") + "\n</w:body>\n</w:document>"

        new_doc = prefix + "\n" + build_body(content, topic_display, date_str) + suffix
        members["word/document.xml"] = new_doc.encode("utf-8")

        # ── Patch headers ─────────────────────────────────────────────────────
        for name in list(members.keys()):
            if re.match(r"word/header\d+\.xml", name):
                hxml = members[name].decode("utf-8")
                hxml = _update_header_date(hxml, new_month, new_day, new_year)
                members[name] = hxml.encode("utf-8")

        # ── Write new zip ─────────────────────────────────────────────────────
        # Ensure output directory exists
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for name, data in members.items():
                zout.writestr(name, data)

    except Exception as e:
        print(f"  Error generating {os.path.basename(output_path)}: {e}")
        return False

    return True

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Exoasia MRSI Daily Insight generator")
    ap.add_argument("--input",    default="output.txt")
    ap.add_argument("--template", default=TEMPLATE)
    ap.add_argument("--outdir",   default="insights")
    args = ap.parse_args()


    if not os.path.exists(args.input):
        print(f"Error: '{args.input}' not found."); sys.exit(1)
    if not os.path.exists(args.template):
        print(f"Error: template not found at '{args.template}'"); sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)
    date_str  = datetime.now().strftime("%B %d, %Y")
    date_slug = datetime.now().strftime("%b%d")

    print(f"Parsing {args.input} ...")
    topics = split_topics(args.input)
    if not topics:
        print("No topics found. Expected: ## AI  ## CYBERSECURITY  ## WEB3 / BLOCKCHAIN")
        sys.exit(1)
    print(f"Found {len(topics)} topic(s): {', '.join(topics)}\n")

    for key, data in topics.items():
        print(f"Generating {data['display']} ...")
        content  = parse_topic(data["lines"])
        filename = f"Exoasia_MRSI_DailyInsight_{date_slug}_{data['slug']}.docx"
        ok = generate_docx(content, data["display"], date_str,
                           os.path.join(args.outdir, filename), args.template)
        if ok:
            print(f"  ✓  {filename}")

    print(f"\nDone — {len(topics)} document(s) in '{args.outdir}'")

if __name__ == "__main__":
    main()
