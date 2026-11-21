#!/usr/bin/env python3
"""Rend les ERD Mermaid (docs/security-assessment/erd/*.mmd) en SVG et PNG avec Chrome headless.

À lancer après bin/generate-erd.py. Mermaid n'est pas fourni par le dépôt :
  curl -o /tmp/mermaid.min.js https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js
  python3 bin/render-erd.py /tmp/mermaid.min.js
"""
import html
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/security-assessment/erd'
OUTPUT = SOURCE / 'images'
CHROME = ['google-chrome', '--headless=new', '--disable-gpu']


def render_svg(mermaid, mmd, work):
    page = work / (mmd.stem + '.html')
    page.write_text(f"""<!doctype html><meta charset="utf-8"><body>
<div id="out"></div><pre id="err"></pre>
<script src="{mermaid.as_uri()}"></script>
<script>
mermaid.initialize({{startOnLoad:false, securityLevel:'strict', theme:'neutral',
  fontFamily:'DejaVu Sans, Arial, sans-serif', er:{{useMaxWidth:false, layoutDirection:'TB',
  minEntityWidth:100, entityPadding:12}}}});
mermaid.render('erd', {json.dumps(mmd.read_text())})
  .then(r => document.getElementById('out').innerHTML = r.svg)
  .catch(e => document.getElementById('err').textContent = 'ERROR ' + e);
</script>""")
    dom = subprocess.run(CHROME + ['--virtual-time-budget=15000', '--dump-dom', page.as_uri()],
                         capture_output=True, text=True, timeout=120).stdout
    error = re.search(r'<pre id="err">(.*?)</pre>', dom, re.S)
    if error and error[1].strip():
        raise SystemExit(f'{mmd.name} : {html.unescape(error[1])[:400]}')
    svg = re.search(r'<svg.*</svg>', dom, re.S)
    if not svg:
        raise SystemExit(f'{mmd.name} : aucun SVG produit')
    text = svg[0].replace('<br>', '<br/>')
    if 'xmlns="http://www.w3.org/2000/svg"' not in text:
        text = text.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + text + '\n'


def main():
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_file():
        raise SystemExit(__doc__)
    mermaid = Path(sys.argv[1]).resolve()
    OUTPUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for mmd in sorted(SOURCE.glob('*.mmd')):
            svg = OUTPUT / (mmd.stem + '.svg')
            svg.write_text(render_svg(mermaid, mmd, work))
            box = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"', svg.read_text())
            width, height = int(float(box[1])) + 80, int(float(box[2])) + 20
            png = OUTPUT / (mmd.stem + '.png')
            subprocess.run(CHROME + ['--hide-scrollbars', '--force-device-scale-factor=2',
                                     f'--window-size={width},{height}', f'--screenshot={png}', svg.as_uri()],
                           capture_output=True, timeout=120, check=True)
            print(f'{mmd.name} -> {svg.name}, {png.name}')


if __name__ == '__main__':
    main()
