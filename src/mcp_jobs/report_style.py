"""CSS for the unified report HTML render (single source of truth for style).

Decisions (2026-08-15):
- Text font: Calibri (R2)
- Metadata rows (.meta, .match, .priority-flag, .footer): 8 pt (R3)
- Base body: 10.5 pt
- A4 @page for print/PDF
"""

CSS = """\
@page { size: A4; margin: 18mm 16mm; }

body {
  font-family: "Calibri", "Segoe UI", sans-serif;
  font-size: 10.5pt;
  line-height: 1.35;
  color: #1a1a1a;
  margin: 0;
}

h1 { font-size: 15pt; margin: 0 0 4pt 0; color: #0b2e4f; }
h2 { font-size: 12pt; margin: 10pt 0 3pt 0; border-bottom: 1px solid #c8c8c8; padding-bottom: 2pt; color: #0b2e4f; }
h3 { font-size: 11pt; margin: 8pt 0 2pt 0; }

p { margin: 3pt 0; }

/* Metadata rows — ALL 8 pt (R3). Was 12 pt, too large for metadata. */
.meta, .match, .priority-flag, .footer {
  font-size: 8pt;
  color: #555;
  line-height: 1.3;
}
.meta { color: #444; }
.match { color: #7a5c00; font-weight: 600; }
.priority-flag { color: #b00020; font-weight: 600; }

table { width: 100%; border-collapse: collapse; font-size: 9pt; margin: 4pt 0; }
th, td { border: 1px solid #ddd; padding: 2pt 6pt; text-align: left; }
th { background: #f2f5f8; }

a { color: #1155cc; text-decoration: none; }
a:hover { text-decoration: underline; }

blockquote {
  margin: 2pt 0 2pt 8pt;
  padding-left: 6pt;
  border-left: 2px solid #d5d5d5;
  color: #333;
}

ol { margin: 3pt 0 3pt 16pt; padding: 0; }
li { margin: 4pt 0; }
/* Ad titles: base 10.5pt -> 13.65pt (+30%, 2026-08-19) */
ol li strong { font-size: 13.65pt; color: #0b2e4f; }

code { font-family: Consolas, monospace; font-size: 9pt; background: #f4f4f4; padding: 0 2pt; }

hr { border: 0; border-top: 1px solid #ccc; margin: 8pt 0; }
"""
