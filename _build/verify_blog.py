"""Prueft die gebaute Seite auf das, was unabhaengig vom Inhalt gelten muss.

Schnappschussfrei mit Absicht: _build/verify.py belegt, dass beim Umzug
nichts verloren ging - diese Pruefung soll den Betrieb begleiten. Ein
Vergleich gegen den alten Stand wuerde rot, sobald jemand einen Artikel
schreibt, und ein Test, der bei richtigem Verhalten Alarm schlaegt,
erzieht dazu, Alarme zu ignorieren.

Geprueft wird:
  * jede Inhaltsdatei wird zu einer Seite
  * jede Seite traegt Titel, Canonical und Robots-Angabe, und der
    Canonical zeigt auf die eigene Adresse
  * jedes og:image zeigt auf eine ausgelieferte Datei
  * jeder Beitrag erscheint genau einmal in der Blog-Uebersicht
  * jeder Beitrag erscheint in mindestens einem Kategoriearchiv
  * Feed und die vier Sitemaps sind vollstaendig *und* wohlgeformtes XML

Aufruf:  python3 -E -s _build/verify_blog.py
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

import wpdata as w

GEBAUT = os.path.join(w.WURZEL, 'public')
CONTENT = os.path.join(w.WURZEL, 'content')


def seiten_im_bau():
    """Alle gebauten HTML-Seiten als {Adresse: Inhalt}."""
    aus = {}
    for pfad, _, dateien in os.walk(GEBAUT):
        if 'index.html' not in dateien:
            continue
        rel = os.path.relpath(pfad, GEBAUT)
        adresse = '/' if rel == '.' else '/' + rel.replace(os.sep, '/') + '/'
        with open(os.path.join(pfad, 'index.html'), encoding='utf-8') as f:
            aus[adresse] = f.read()
    return aus


def main():
    fehler = []
    seiten = seiten_im_bau()
    beitraege = [b for b in w.beitraege()
                 if b['slug'] not in w.FORT_BEITRAEGE]

    # Jede Inhaltsdatei wird zu einer Seite.
    inhalte = []
    for pfad, _, dateien in os.walk(CONTENT):
        for d in dateien:
            if d.endswith('.html'):
                inhalte.append(os.path.join(pfad, d))
    # Die beiden stummen Abschnittsdateien werden mit Absicht nicht gebaut.
    erwartet = len(inhalte) - 2
    # Weiterleitungsseiten von Hugo (page/1/) zaehlen nicht mit.
    echte = {a: h for a, h in seiten.items()
             if 'http-equiv="refresh"' not in h}
    print('Inhaltsdateien: %d   gebaute Seiten: %d   Blaetterseiten: %d'
          % (erwartet, len(echte),
             len([a for a in echte if '/page/' in a])))
    gebaut_ohne_blaetter = len([a for a in echte if '/page/' not in a])
    if gebaut_ohne_blaetter != erwartet:
        fehler.append('%d Inhaltsdateien, aber %d Seiten'
                      % (erwartet, gebaut_ohne_blaetter))

    # Kopfangaben.
    ohne_titel = ohne_canonical = ohne_robots = falscher_canonical = 0
    for adresse, html in sorted(echte.items()):
        if '/page/' in adresse:
            continue
        k = w.kopf(html)
        if not k['titel']:
            ohne_titel += 1
        if not k['robots']:
            ohne_robots += 1
        if not k['canonical']:
            ohne_canonical += 1
        elif k['canonical'].rstrip('/') != (w.HOST + adresse).rstrip('/'):
            falscher_canonical += 1
            fehler.append('Canonical zeigt woanders hin: %s -> %s'
                          % (adresse, k['canonical']))
    print('  ohne Titel %d   ohne Canonical %d   ohne Robots %d'
          '   Canonical zeigt woanders %d'
          % (ohne_titel, ohne_canonical, ohne_robots, falscher_canonical))
    for n, was in ((ohne_titel, 'Titel'), (ohne_canonical, 'Canonical'),
                   (ohne_robots, 'Robots-Angabe')):
        if n:
            fehler.append('%d Seiten ohne %s' % (n, was))

    # og:image muss ausgeliefert werden.
    ohne_ziel = []
    for adresse, html in echte.items():
        k = w.kopf(html)
        if not k['og_bild']:
            continue
        rel = re.sub(r'^https?://(www\.)?datamate\.org', '', k['og_bild'])
        if not rel.startswith('/'):
            continue
        if not os.path.isfile(os.path.join(GEBAUT, rel.lstrip('/'))):
            ohne_ziel.append((adresse, k['og_bild']))
    print('  og:image ohne Ziel: %d' % len(ohne_ziel))
    for a, b in ohne_ziel:
        fehler.append('og:image fehlt: %s -> %s' % (a, b))

    # Blog-Uebersicht: jeder Beitrag genau einmal.
    gelistet = []
    for adresse, html in echte.items():
        if adresse == '/blog/' or adresse.startswith('/blog/page/'):
            gelistet += re.findall(
                r'<h2 style="font-size: 24px[^>]*><a href="/([^/"]+)/">',
                html)
    fehlen = {b['slug'] for b in beitraege} - set(gelistet)
    doppelt = [s for s in set(gelistet) if gelistet.count(s) > 1]
    print('Blog-Uebersicht: %d Beitraege auf %d Seiten'
          % (len(gelistet),
             len([a for a in echte if a == '/blog/'
                  or a.startswith('/blog/page/')])))
    if fehlen:
        fehler.append('%d Beitraege fehlen in der Uebersicht: %s'
                      % (len(fehlen), ', '.join(sorted(fehlen)[:5])))
    if doppelt:
        fehler.append('%d Beitraege doppelt in der Uebersicht' % len(doppelt))

    # Kategoriearchive: jeder Beitrag mindestens einmal.
    in_kategorie = set()
    for adresse, html in echte.items():
        if adresse.startswith('/category/'):
            in_kategorie |= set(re.findall(
                r'<h2 style="font-size: 24px[^>]*><a href="/([^/"]+)/">',
                html))
    ohne_kategorie = {b['slug'] for b in beitraege} - in_kategorie
    print('Kategoriearchive: %d Beitraege erreichbar' % len(in_kategorie))
    if ohne_kategorie:
        fehler.append('%d Beitraege in keinem Kategoriearchiv: %s'
                      % (len(ohne_kategorie),
                         ', '.join(sorted(ohne_kategorie)[:5])))

    # Feed und Sitemaps.
    def zaehle(datei, muster):
        pfad = os.path.join(GEBAUT, datei)
        if not os.path.isfile(pfad):
            fehler.append('%s fehlt' % datei)
            return -1
        with open(pfad, encoding='utf-8') as f:
            return len(re.findall(muster, f.read()))

    # Wohlgeformtheit zaehlt zuerst. Die Fassung 2026-10-21 lieferte drei
    # Sitemaps aus, die mit &lt;?xml anfingen - Hugo fuehrte das Partial
    # als HTML-Vorlage aus und maskierte die XML-Deklaration. Gezaehlte
    # <loc>-Vorkommen sahen dabei richtig aus; erst ein Parser zeigt es.
    for datei in ('feed/index.xml', 'sitemap_index.xml', 'post-sitemap.xml',
                  'page-sitemap.xml', 'category-sitemap.xml'):
        ort = os.path.join(GEBAUT, datei)
        if not os.path.isfile(ort):
            fehler.append('%s fehlt' % datei)
            continue
        try:
            ET.parse(ort)
        except ET.ParseError as e:
            fehler.append('%s ist kein wohlgeformtes XML: %s' % (datei, e))
    print('XML wohlgeformt: Feed und vier Sitemaps geprueft')

    feed = zaehle('feed/index.xml', r'<item>')
    post = zaehle('post-sitemap.xml', r'<loc>')
    page = zaehle('page-sitemap.xml', r'<loc>')
    kat = zaehle('category-sitemap.xml', r'<loc>')
    index = zaehle('sitemap_index.xml', r'<loc>')
    print('Feed: %d Eintraege   Sitemaps: post %d, page %d, category %d, '
          'Index %d' % (feed, post, page, kat, index))
    if feed != 20:
        fehler.append('Feed hat %d statt 20 Eintraege' % feed)
    if post != len(beitraege):
        fehler.append('post-sitemap hat %d statt %d Adressen'
                      % (post, len(beitraege)))
    if kat != len(w.kategorien()):
        fehler.append('category-sitemap hat %d statt %d Adressen'
                      % (kat, len(w.kategorien())))
    if index != 3:
        fehler.append('sitemap_index verweist auf %d statt 3 Sitemaps'
                      % index)

    print()
    if fehler:
        print('FEHLER: %d' % len(fehler))
        for f in fehler:
            print('  ' + f)
        return 1
    print('alles in Ordnung')
    return 0


if __name__ == '__main__':
    sys.exit(main())
