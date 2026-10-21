"""Vergleicht die gebaute Seite mit dem Stand vor dem Umzug.

Geprueft wird der *Seitenrumpf* - alles zwischen </header> und
<footer id="footer"> - Zeichen fuer Zeichen. Auf den Schnappschuss werden
vorher dieselben Regeln angewandt, die der Generator angewandt hat
(_build/wpdata.py: ERSETZUNGEN und HANDAENDERUNGEN). Jede Abweichung, die
danach noch bleibt, ist ein Fehler.

Kopf und Fussleiste sind mit Absicht *nicht* Teil des Vergleichs: sie
werden weiterentwickelt - der entfallene Menuepunkt 3CX, Font Awesome aus
dem eigenen Bestand, das Suchfeld, das jetzt auf /suche/ fuehrt. Aus dem
Kopf geprueft werden stattdessen Titel, Beschreibung und Canonical: die
stehen so in Suchergebnissen und duerfen sich nicht veraendern.

Aufruf:  python3 -E -s _build/verify.py [--diff]
"""
import os
import re
import sys

import wpdata as w

GEBAUT = os.path.join(w.WURZEL, 'public')

# Adressen, deren Rumpf mit Absicht neu entsteht und darum nicht
# zeichenweise verglichen wird.
OHNE_RUMPFVERGLEICH = {
    # Die Blog-Uebersicht baut das Layout aus den Beitraegen neu. Der alte
    # Stand kann hier nicht Maßstab sein: er zeigte wegen des Fehlers in
    # blog-page.php nur jeden zweiten Zehnerblock (siehe README).
    '/blog/',
}


def entschaerft(text):
    """Macht zwei Schreibweisen vergleichbar, die gleich aussehen.

    Gos html/template - Hugos Vorlagenmotor - schreibt in Attributwerten
    + als &#43;. Im Browser steht beides als Pluszeichen da; fuer einen
    Zeichenvergleich muessen sie zusammenfallen.
    """
    return text.replace('&#43;', '+')


def rumpf_gebaut(html):
    a = html.index('</header>') + len('</header>')
    b = html.index('<footer id="footer"')
    return html[a:b].strip('\n')


def lies(pfad):
    datei = os.path.join(GEBAUT, pfad.strip('/'), 'index.html')
    if pfad == '/':
        datei = os.path.join(GEBAUT, 'index.html')
    with open(datei, encoding='utf-8') as f:
        return f.read()


def main():
    gleich = anders = fehlend = ohne = 0
    kopf_ok = kopf_fehler = 0
    abweichungen = []

    adressen = [w.pfad_von(s) for s in w.seiten()
                if not w.faellt_fort(w.pfad_von(s))]
    adressen += [w.pfad_von(b) for b in w.beitraege()
                 if b['slug'] not in w.FORT_BEITRAEGE]

    for p in adressen:
        alt_roh = w.schnappschuss(p)
        try:
            neu_roh = lies(p)
        except FileNotFoundError:
            fehlend += 1
            abweichungen.append((p, 'fehlt in public/', '', ''))
            continue

        # Kopfangaben
        a, n = w.kopf(alt_roh), w.kopf(neu_roh)
        for feld in ('titel', 'beschreibung', 'canonical', 'robots'):
            if entschaerft(a[feld] or '') != entschaerft(n[feld] or ''):
                kopf_fehler += 1
                abweichungen.append(
                    (p, 'Kopf: ' + feld, a[feld] or '', n[feld] or ''))
            else:
                kopf_ok += 1

        # Rumpf
        if p.strip('/') in [b['slug'] for b in w.beitraege()]:
            # Beitraege: das Layout baut Bildkopf, Titelzeile, Autorenbox
            # und Seitenleiste neu - verglichen wird der Artikeltext.
            def artikel(html):
                # Ende ist die Autorenbox. Im alten Stand steht darueber
                # ein HTML-Kommentar, im neuen nicht: Hugos Vorlagenmotor
                # (html/template) entfernt Kommentare aus Layouts. Darum
                # endet der Ausschnitt an der ersten der beiden Marken.
                i = html.index('<div class="entry clearfix">')
                i += len('<div class="entry clearfix">')
                e = html.find('<!-- Post Author Info')
                if e < 0:
                    e = html.index('<div class="team team-list clearfix">')
                return re.sub(r'\s+', ' ', html[i:e]).strip()
            alt = artikel(alt_roh)
            alt, _ = w.normalisiere(alt)
            alt, _ = w.handaenderungen(p, alt)
            # decoding="async" setzt WordPress nur in der Einzelansicht -
            # im Schnappschuss steht es, in der Liste nicht.
            neu = artikel(neu_roh)
        else:
            alt, _ = w.normalisiere(w.rumpf(alt_roh))
            alt, _ = w.handaenderungen(p, alt)
            alt = re.sub(r'\s+', ' ', alt).strip()
            neu = re.sub(r'\s+', ' ', rumpf_gebaut(neu_roh)).strip()

        if p in OHNE_RUMPFVERGLEICH:
            ohne += 1
        elif entschaerft(alt) == entschaerft(neu):
            gleich += 1
        else:
            anders += 1
            abweichungen.append((p, 'Rumpf', alt, neu))

    gesamt = len(adressen)
    print('Seitenrumpf identisch: %d   abweichend: %d   fehlend: %d  (von %d'
          ', %d bewusst nicht verglichen)'
          % (gleich, anders, fehlend, gesamt, ohne))
    print('Titel, Description, Canonical, Robots unveraendert: %d von %d'
          % (kopf_ok, kopf_ok + kopf_fehler))

    bericht = os.path.join(w.BASIS, 'verify-diff.txt')
    if not abweichungen and os.path.exists(bericht):
        os.remove(bericht)
    if abweichungen:
        with open(bericht, 'w', encoding='utf-8') as f:
            for p, art, alt, neu in abweichungen:
                f.write('=' * 70 + '\n%s  [%s]\n' % (p, art))
                if art.startswith('Kopf'):
                    f.write('  vorher: %s\n  jetzt : %s\n' % (alt, neu))
                else:
                    f.write(_unterschied(alt, neu))
        print('\n%d Abweichungen, Einzelheiten in %s'
              % (len(abweichungen), bericht))
        if '--diff' in sys.argv:
            print(open(bericht, encoding='utf-8').read()[:12000])
        return 1
    return 0


def _unterschied(alt, neu):
    """Die erste abweichende Stelle mit Umgebung - fuer lange HTML-Rumpfe
    ist das lesbarer als ein Zeilen-Diff."""
    i = 0
    while i < min(len(alt), len(neu)) and alt[i] == neu[i]:
        i += 1
    von = max(0, i - 120)
    return ('  gleich bis Zeichen %d von %d/%d\n'
            '  vorher: ...%s\n  jetzt : ...%s\n'
            % (i, len(alt), len(neu),
               alt[von:i + 200].replace('\n', ' '),
               neu[von:i + 200].replace('\n', ' ')))


if __name__ == '__main__':
    sys.exit(main())
