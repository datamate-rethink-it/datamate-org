"""Prueft alle seiteninternen Verweise der gebauten Seite.

Ein Verweis gilt als in Ordnung, wenn sein Ziel in public/ liegt: eine
Datei, oder ein Verzeichnis mit index.html. Externe Adressen werden nicht
abgefragt - das waere ein Netzzugriff bei jedem Durchlauf und wuerde rot,
wenn eine fremde Seite kurz nicht erreichbar ist.

BEKANNT_KAPUTT sind Verweise, die schon im WordPress ins Leere zeigten -
nachgeprueft an der laufenden Seite am 21.10.2026. Sie stehen hier, damit
die Pruefung "NEU kaputt: 0" aussagen kann, ohne dass jemand erst
nachsehen muss, ob eine Meldung alt oder neu ist.

Aufruf:  python3 -E -s _build/linkcheck.py
"""
import json
import os
import re
import sys
import urllib.parse

import wpdata as w

GEBAUT = os.path.join(w.WURZEL, 'public')

BEKANNT_KAPUTT = {
    # Das Canvas-Template legte Dateien unter /static/ ab. Fuer
    # widget-link.png ist der Pfad korrigiert (die Datei gibt es im
    # Theme), dieses Hintergrundbild gibt es nirgends.
    '/static/images/parallax/2.jpg':
        'Datei existiert in keiner Fassung des Themes, live 404',
    # Verweis aus einer Theme-CSS auf ein Bild, das es nicht gibt.
    '/wp-content/themes/datamate-theme/images/parallax/parallax-bg.jpg':
        'Verweis aus canvas.css, live 404',
    # Bild aus einem fremden Wiki, im Beitrag ohne Hostnamen eingefuegt.
    # Dasselbe Bild steht im selben Beitrag ein zweites Mal, dort mit
    # vollstaendiger Adresse.
    '/gigawiki/download/attachments/7405655/rtaImage.jpg':
        'Verweis ohne Hostnamen in '
        '/autoprovisionierung-von-ip-telefonen-mit-factory-reset/, live 404',
    # Verweise auf Adressen, die es im WordPress ebenfalls nicht gab.
    # Alle fuenf am 21.10.2026 an der laufenden Seite nachgeprueft.
    '/blog/seafile-professional-server-6-3':
        'Beitrag existiert nicht (mehr), live 404 - '
        'verlinkt aus /multi-tenancy-in-seafile/',
    '/shop/small-business':
        'Pfad des abgeschalteten Shops, live 404 - '
        'verlinkt aus /odoo-crm-mit-der-voip-telefonanlage-verbinden/',
    '/sso-seafile-keycloak/':
        'Beitrag existiert nicht, live 404 - verlinkt aus '
        '/mehrere-gruende-warum-it-profis-auf-die-cloud-setzen-sollten/',
    '/teamviewerDL/':
        'Adresse existiert nicht, live 404 - verlinkt aus /fellow/. '
        'Gemeint war vermutlich https://get.teamviewer.com/datamate, '
        'das in der Fussleiste steht.',
}

RE_VERWEIS = re.compile(r'(?:href|src|poster)\s*=\s*"([^"]+)"')
RE_SRCSET = re.compile(r'srcset\s*=\s*"([^"]+)"')


def ziele(html):
    aus = set()
    for m in RE_VERWEIS.finditer(html):
        aus.add(m.group(1))
    for m in RE_SRCSET.finditer(html):
        for teil in m.group(1).split(','):
            aus.add(teil.strip().split(' ')[0])
    return aus


def auflosen(ziel, von):
    ziel = ziel.strip().split('#')[0]
    if not ziel or ziel.startswith(
            ('data:', 'mailto:', 'tel:', 'javascript:', '//')):
        return None
    if re.match(r'^[a-z]+:', ziel):
        return None                      # fremde Adresse
    ziel = ziel.split('?')[0]
    if not ziel:
        return None
    if not ziel.startswith('/'):
        ziel = os.path.normpath(os.path.join(von, ziel))
    return urllib.parse.unquote(ziel)


def weiterleitungen():
    """Adressen, die der Webserver beantwortet, ohne dass eine Datei
    danebenliegt - erzeugt von _build/gen_redirects.py."""
    datei = os.path.join(w.BASIS, 'weiterleitungen.json')
    if not os.path.isfile(datei):
        sys.exit('_build/weiterleitungen.json fehlt - erst '
                 '_build/gen_redirects.py laufen lassen.')
    with open(datei, encoding='utf-8') as f:
        return json.load(f)


WEITER = weiterleitungen()


def vorhanden(pfad):
    ort = os.path.join(GEBAUT, pfad.lstrip('/'))
    if os.path.isfile(ort):
        return True
    # Der Feed liegt als index.xml, nicht als index.html.
    for name in ('index.html', 'index.xml'):
        if os.path.isfile(os.path.join(ort, name)):
            return True
    # Vom Webserver weitergeleitet (Pfadpraefix wie bei Caddys handle).
    kurz = pfad.rstrip('/')
    for quelle in (pfad, kurz, kurz + '/'):
        if quelle in WEITER:
            return True
    return any(kurz.startswith(q.rstrip('/'))
               for q in WEITER if q.rstrip('/'))


def main():
    kaputt = {}
    seiten = 0
    verweise = 0
    for ordner, _, dateien in os.walk(GEBAUT):
        for d in dateien:
            if not d.endswith('.html'):
                continue
            datei = os.path.join(ordner, d)
            rel = os.path.relpath(ordner, GEBAUT)
            von = '/' if rel == '.' else '/' + rel.replace(os.sep, '/')
            with open(datei, encoding='utf-8') as f:
                html = f.read()
            seiten += 1
            for z in ziele(html):
                pfad = auflosen(z, von)
                if pfad is None:
                    continue
                verweise += 1
                if not vorhanden(pfad):
                    kaputt.setdefault(pfad, set()).add(von)

    neu = {p: v for p, v in kaputt.items() if p not in BEKANNT_KAPUTT}
    alt = {p: v for p, v in kaputt.items() if p in BEKANNT_KAPUTT}

    print('%d Seiten, %d seiteninterne Verweise' % (seiten, verweise))
    print('  schon vorher kaputt:    %3d' % len(alt))
    for p in sorted(alt):
        print('      %-62s %s' % (p, BEKANNT_KAPUTT[p]))
    print('  NEU kaputt:             %3d' % len(neu))
    for p in sorted(neu):
        quellen = sorted(kaputt[p])
        print('      %-62s von %s%s'
              % (p, ', '.join(quellen[:3]),
                 ' (+%d weitere)' % (len(quellen) - 3)
                 if len(quellen) > 3 else ''))
    # Verweise auf eingestellte Bereiche duerfen nicht uebrig sein - der
    # Generator loest sie auf (siehe TOTE_ZIELE in _build/wpdata.py).
    reste = [p for p in neu
             if p.rstrip('/').startswith(w.TOTE_ZIELE)]
    if reste:
        print('\n  davon Verweise auf eingestellte Bereiche: %d' % len(reste))
    return 1 if neu else 0


if __name__ == '__main__':
    sys.exit(main())
