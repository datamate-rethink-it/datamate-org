"""Fuellt webroot/ mit den Dateien, die die Seite wirklich verwendet.

Die alte Installation hat 7734 Dateien, davon 6700 Bilder - WordPress legt
von jedem Bild mehrere Groessen und zusaetzlich eine webp-Fassung an. Nach
Ordner auszuwaehlen waere falsch in beide Richtungen: es kaeme Unbenutztes
mit und Benutztes blieb liegen. Darum wird ueber die tatsaechlichen
Verweise gegangen.

Gelesen werden: src, href, srcset, poster, data-dark-logo, url(...) in
Stilangaben, content in <meta> - das og:image steht nur dort - und die
url(...) in den uebernommenen CSS-Dateien, rekursiv, denn dort haengen die
Schriften und Hintergrundbilder des Themes.

Gelesen wird die *gebaute* Seite in public/, nicht der Quellbaum: nur dort
stehen die Verweise so, wie ein Besucher sie bekommt. Darum zwei Durchgaenge:

    hugo --destination public      # Verweise entstehen
    python3 -E -s _build/gen_static.py
    hugo --destination public      # mit webroot/ nochmal

Fehlende Dateien beim ersten Durchgang stoeren den Bau nicht - Hugo
verlinkt sie nur.

Aufruf:  python3 -E -s _build/gen_static.py
"""
import os
import re
import shutil
import sys
import urllib.parse

import wpdata as w

QUELLE = os.path.join(w.BASIS, 'wporig', 'wordpress')
ZIEL = os.path.join(w.WURZEL, 'webroot')

# Dateien, die zur Seite gehoeren, aber in keiner Seite verlinkt sind.
IMMER = [
    # robots.txt erzeugte WordPress selbst und liegt deshalb nicht im
    # Dateibestand, sondern als eigene Datei in webroot-eigen/.
    'ads.txt',
    'favicon.ico',
    'downloads/Datamate-AGB.pdf',       # in der Fussleiste jeder Seite
    'downloads/Datamate-AGB-old.pdf',   # aus Beitraegen verlinkt
    'downloads/Voraussetzungen.pdf',
    'downloads/ovpn-split.sh',
]

# Verweise auf diese Praefixe gehoeren zu eingestellten Bereichen und
# werden nicht uebernommen (siehe _build/wpdata.py).
NICHT = ('/downloads/firmware/', '/downloads/manuals/', '/seafcss/')

RE_ATTR = re.compile(
    r'(?:src|href|poster|data-dark-logo|data-slb-asset)\s*=\s*"([^"]+)"')
RE_SRCSET = re.compile(r'srcset\s*=\s*"([^"]+)"')
RE_URL = re.compile(r'url\(\s*[\'"]?([^\'")]+)')
RE_META = re.compile(r'<meta[^>]+content\s*=\s*"([^"]+)"')


def kandidaten(text):
    """Alle Pfade, die ein Text auf eigene Dateien verweist."""
    aus = set()
    for m in RE_ATTR.finditer(text):
        aus.add(m.group(1))
    for m in RE_SRCSET.finditer(text):
        for teil in m.group(1).split(','):
            aus.add(teil.strip().split(' ')[0])
    for m in RE_URL.finditer(text):
        aus.add(m.group(1))
    for m in RE_META.finditer(text):
        # <meta content="..."> traegt auch Beschreibungstexte. Nur was
        # keine Leerzeichen hat, kann ein Pfad sein - das og:image steht
        # nur hier und darf nicht durchfallen.
        wert = m.group(1)
        if ' ' not in wert.strip():
            aus.add(wert)
    return aus


def normiere(pfad, von):
    """Macht einen Verweis zu einem Pfad unterhalb der Wurzel, oder None."""
    pfad = pfad.strip().split('#')[0].split('?')[0]
    if not pfad or pfad.startswith(('data:', 'mailto:', 'tel:', 'javascript:')):
        return None
    if ' ' in pfad:
        return None
    # Dateinamen mit Umlaut stehen in den Seiten prozentkodiert.
    pfad = urllib.parse.unquote(pfad)
    pfad = re.sub(r'^https?://(www\.)?datamate\.org', '', pfad)
    if '://' in pfad or pfad.startswith('//'):
        return None            # fremde Adresse
    if not pfad.startswith('/'):
        pfad = os.path.normpath(os.path.join(os.path.dirname(von), pfad))
        if not pfad.startswith('/'):
            pfad = '/' + pfad
    if pfad.startswith(NICHT):
        return None
    if pfad.startswith(('/eigen/', '/pagefind/')):
        return None            # selbst geschrieben, liegt in webroot-eigen/
    if not os.path.splitext(pfad)[1]:
        return None            # Seitenadresse, keine Datei
    return pfad


def main():
    if not os.path.isdir(QUELLE):
        sys.exit('%s fehlt - siehe README, Abschnitt "Neu aufsetzen".'
                 % QUELLE)
    gesehen, offen, fehlt = set(), [], []

    # Startpunkte: jede gebaute Seite und jede gebaute Sitemap.
    gebaut = os.path.join(w.WURZEL, 'public')
    if not os.path.isdir(gebaut):
        sys.exit('public/ fehlt - erst "hugo" laufen lassen.')
    for pfad, _, dateien in os.walk(gebaut):
        for d in dateien:
            if not d.endswith(('.html', '.xml')):
                continue
            datei = os.path.join(pfad, d)
            with open(datei, encoding='utf-8', errors='replace') as f:
                text = f.read()
            von = '/' + os.path.relpath(pfad, gebaut).lstrip('.') + '/'
            for k in kandidaten(text):
                n = normiere(k, von)
                if n:
                    offen.append(n)
    offen += ['/' + p for p in IMMER]

    # Rekursiv: CSS kann weitere Dateien nachziehen (Schriften, Bilder).
    uebernommen = 0
    while offen:
        pfad = offen.pop()
        if pfad in gesehen:
            continue
        gesehen.add(pfad)
        quelle = os.path.join(QUELLE, pfad.lstrip('/'))
        if not os.path.isfile(quelle):
            fehlt.append(pfad)
            continue
        ziel = os.path.join(ZIEL, pfad.lstrip('/'))
        os.makedirs(os.path.dirname(ziel), exist_ok=True)
        shutil.copy2(quelle, ziel)
        uebernommen += 1
        if pfad.endswith('.css'):
            with open(quelle, encoding='utf-8', errors='replace') as f:
                for k in RE_URL.finditer(f.read()):
                    n = normiere(k.group(1), os.path.dirname(pfad) + '/')
                    if n and n not in gesehen:
                        offen.append(n)

    groesse = sum(
        os.path.getsize(os.path.join(p, d))
        for p, _, ds in os.walk(ZIEL) for d in ds)
    print('uebernommen %d Dateien, %.1f MB' % (uebernommen,
                                               groesse / 1048576.0))
    vorhanden = sum(len(ds) for _, _, ds in os.walk(QUELLE))
    print('im alten Dateibestand: %d Dateien' % vorhanden)
    if fehlt:
        print('\nverwiesen, aber nicht im Dateibestand: %d' % len(fehlt))
        for p in sorted(set(fehlt)):
            print('  ' + p)


if __name__ == '__main__':
    main()
