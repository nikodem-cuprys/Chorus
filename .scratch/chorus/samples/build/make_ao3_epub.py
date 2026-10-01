"""Build a synthetic EPUB laid out like an AO3 download: a preface page with
work metadata, summary and beginning notes, chapters with their own chapter
notes, and end notes. The story text is public domain (Kafka, tr. Wyllie);
all AO3 metadata and author notes are invented test fixtures."""
import pathlib, zipfile, html, re

PASS = pathlib.Path(r"D:\projcets\Chorus\.scratch\chorus\samples\passages")
OUT = pathlib.Path(r"D:\projcets\Chorus\.scratch\chorus\samples\import\ao3-style-with-notes.epub")

pars = [p for p in (PASS / "05-metamorphosis-opening.txt").read_text(encoding="utf-8").split("\n\n")
        if p.strip() and not p.startswith("#")]
half = len(pars) // 2

def ptag(p):
    s = html.escape(p, quote=False)
    s = re.sub(r"_(.+?)_", r"<em>\1</em>", s)
    # Render Gregor's quoted thoughts in italics too, as many fanfic authors do.
    s = re.sub(r"(“[^”]*”) he thought", r"<em>\1</em> he thought", s)
    return f"<p>{s}</p>"

def page(title, inner):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>{title}</title><link rel="stylesheet" type="text/css" href="stylesheet.css"/></head>
<body>{inner}</body></html>"""

preface = page("Preface", """
<div class="meta">
<h1>The Morning After</h1>
<div class="byline">by <a rel="author" href="https://archiveofourown.org/users/test_author/pseuds/test_author">test_author</a></div>
<p>Posted originally on the <a href="https://archiveofourown.org/">Archive of Our Own</a> at <a href="https://archiveofourown.org/works/00000000">https://archiveofourown.org/works/00000000</a>.</p>
<dl class="tags">
<dt>Rating:</dt><dd>General Audiences</dd>
<dt>Archive Warning:</dt><dd>No Archive Warnings Apply</dd>
<dt>Fandom:</dt><dd>Die Verwandlung | The Metamorphosis - Franz Kafka</dd>
<dt>Characters:</dt><dd>Gregor Samsa, Grete Samsa, Mr. Samsa, Mrs. Samsa, The Chief Clerk</dd>
<dt>Additional Tags:</dt><dd>Canon Rewrite, Inner Monologue, Family Drama</dd>
<dt>Language:</dt><dd>English</dd>
<dt>Stats:</dt><dd>Published: 2026-01-01 Completed: 2026-01-08 Chapters: 2/2 Words: 1600</dd>
</dl>
<h2>The Morning After</h2>
<blockquote class="userstuff"><p><strong>Summary:</strong></p><p>Gregor wakes up. Things are not fine. (Synthetic test fixture; story text is public domain.)</p></blockquote>
<p><strong>Notes:</strong></p>
<blockquote class="userstuff"><p>Hi all! This is my first fic in this fandom, please be gentle. Huge thanks to my beta for putting up with my comma addiction. Unbeta'd mistakes are my own!</p><p>See the end of the work for more <a href="#endnotes">notes</a>.</p></blockquote>
</div>""")

def chapter(n, title, body, notes_start, notes_end):
    return page(f"Chapter {n}", f"""
<div class="meta group"><h2 class="heading">Chapter {n}: {title}</h2>
<p><strong>Chapter Notes</strong></p><blockquote class="userstuff"><p>{notes_start}</p></blockquote>
<p>See the end of the chapter for <a href="#chapter_{n}_endnotes">more notes</a></p></div>
<div class="userstuff">{''.join(ptag(p) for p in body)}</div>
<div class="endnote-link" id="chapter_{n}_endnotes"><p><strong>Chapter End Notes</strong></p><blockquote class="userstuff"><p>{notes_end}</p></blockquote></div>""")

ch1 = chapter(1, "Transformed", pars[:half], "CW: body horror (mild). Enjoy!",
              "Cliffhanger, sorry not sorry. Kudos and comments feed the author!")
ch2 = chapter(2, "The Door", pars[half:], "Thank you so much for all the lovely comments on chapter one!!",
              "That's it for now. Come yell at me on my blog.")
after = page("Afterword", """<div id="endnotes"><h2>Afterword</h2><p><strong>End Notes</strong></p>
<blockquote class="userstuff"><p>Thanks for reading! This work may be recorded as a podfic, just link back and let me know.</p></blockquote>
<div id="series"><p>Please drop by the archive and comment to let the author know if you enjoyed their work!</p></div></div>""")

files = [("preface.xhtml", preface), ("chapter1.xhtml", ch1), ("chapter2.xhtml", ch2), ("afterword.xhtml", after)]
manifest = "".join(f'<item id="f{i}" href="{n}" media-type="application/xhtml+xml"/>' for i, (n, _) in enumerate(files))
spine = "".join(f'<itemref idref="f{i}"/>' for i in range(len(files)))
opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="uid">urn:uuid:chorus-test-ao3-00000000</dc:identifier>
<dc:title>The Morning After</dc:title><dc:creator>test_author</dc:creator><dc:language>en</dc:language>
<dc:publisher>Archive of Our Own</dc:publisher>
<meta property="dcterms:modified">2026-09-29T00:00:00Z</meta></metadata>
<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="css" href="stylesheet.css" media-type="text/css"/>{manifest}</manifest>
<spine>{spine}</spine></package>"""
nav = page("Contents", """<nav epub:type="toc"><ol>
<li><a href="preface.xhtml">Preface</a></li><li><a href="chapter1.xhtml">Chapter 1: Transformed</a></li>
<li><a href="chapter2.xhtml">Chapter 2: The Door</a></li><li><a href="afterword.xhtml">Afterword</a></li></ol></nav>""")
container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>"""

OUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUT, "w") as z:
    z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
    z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr("OEBPS/stylesheet.css", "blockquote.userstuff{margin-left:1em}", compress_type=zipfile.ZIP_DEFLATED)
    for n, c in files:
        z.writestr(f"OEBPS/{n}", c, compress_type=zipfile.ZIP_DEFLATED)
print(OUT)
