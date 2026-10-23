"""Gemeinsame Grundlage der Migrationsskripte: welche Adressen uebernommen
werden, wo der Schnappschuss liegt und wie aus einer alten Adresse ein
Hugo-Inhaltspfad wird.

Dieses Modul trifft keine Entscheidungen - es haelt die fest, die getroffen
wurden. Was wegfaellt, steht in FORT_SEITEN und FORT_BEITRAEGE und nirgends
sonst; die Ausliefer-Regeln in deploy/Caddyfile.container muessen dazu passen
(geprueft von _build/verify.py).
"""
import json
import os
import re

BASIS = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(BASIS)
SNAPSHOT = os.path.join(BASIS, 'reference')
WP = os.path.join(BASIS, 'wp')
HOST = 'https://www.datamate.org'

# ---------------------------------------------------------------- Umfang
# Ganze Bereiche, die nicht mitkommen (Entscheidung vom 21.10.2026).
FORT_PRAEFIXE = ('/hero/', '/hilfe/')
FORT_SEITEN = {
    '/voip/',               # Telefonie eingestellt
    '/3cx/',
    '/goldenrosskaserne/',
    '/odoo/',
    '/consulting/',
    '/roadmap/',            # Roadmap von 2018
    '/seafile/seamate/',    # PHP-Generator, lieferte live schon HTTP 500.
                            # Die Adresse leitet weiter, siehe EXTERN
                            # in _build/gen_redirects.py.
}
FORT_BEITRAEGE = {
    # Haengt vollstaendig an downloads/firmware und downloads/manuals,
    # die mit 1,4 GB nicht mitkommen.
    'voip-ip-telefone-firmware-handbuecher-und-standard-passwoerter',
}


def faellt_fort(pfad):
    return pfad in FORT_SEITEN or pfad.startswith(FORT_PRAEFIXE)


# ---------------------------------------------------------------- Laden
def lade(name):
    with open(os.path.join(WP, name), encoding='utf-8') as f:
        return json.load(f)


def seiten():
    """Alle Seiten der alten Installation, nach Adresse sortiert."""
    return sorted(lade('pages.json'), key=lambda s: s['link'])


def beitraege():
    """Alle Beitraege, neueste zuerst."""
    alle = lade('posts-1.json') + lade('posts-2.json')
    return sorted(alle, key=lambda b: b['date'], reverse=True)


def kategorien():
    return lade('categories.json')


def schlagwoerter():
    return lade('tags-1.json') + lade('tags-2.json')


def autoren():
    return {a['id']: a for a in lade('users.json')}


def pfad_von(eintrag):
    """Adresse eines WP-Eintrags als Pfad mit fuehrendem und folgendem /."""
    return eintrag['link'][len(HOST):]


def schnappschuss(pfad):
    """Der gerenderte alte Stand einer Adresse."""
    datei = os.path.join(SNAPSHOT, pfad.strip('/'), 'index.html')
    if pfad == '/':
        datei = os.path.join(SNAPSHOT, 'index.html')
    with open(datei, encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------- Zerlegen
def rumpf(html):
    """Alles zwischen </header> und <footer id="footer">.

    Genau dieser Ausschnitt ist der Seiteninhalt: Kopf und Fussleiste
    erzeugt spaeter das Hugo-Layout. Beide Marken kommen in jeder Seite
    genau einmal vor - das prueft diese Funktion mit.
    """
    a = html.index('</header>') + len('</header>')
    b = html.index('<footer id="footer"')
    assert html.count('</header>') == 1, 'mehr als ein </header>'
    assert html.count('<footer id="footer"') == 1, 'mehr als ein <footer>'
    return html[a:b].strip('\n')


def schema(html):
    """Der JSON-LD-Graph, den Yoast SEO in die Seite geschrieben hat.

    Daraus kommen die Angaben, die sonst nirgends stehen: die Abmessungen
    und die Beschriftung des Beitragsbilds, die Brotkrumen und die
    Personen-Kennung des Autors. Sie werden in den Vorspann uebernommen,
    damit das Layout denselben Graphen wieder erzeugen kann, ohne etwas zu
    erfinden.
    """
    m = re.search(r'class="yoast-schema-graph">(.*?)</script>', html, re.S)
    if not m:
        return {}
    graph = json.loads(m.group(1))['@graph']
    aus = {}
    for knoten in graph:
        art = knoten.get('@type')
        if art == 'ImageObject' and knoten.get('@id', '').endswith(
                '#primaryimage'):
            aus['bild_breite'] = knoten.get('width')
            aus['bild_hoehe'] = knoten.get('height')
            aus['bild_beschriftung'] = knoten.get('caption')
        elif art == 'BreadcrumbList':
            aus['brotkrumen'] = [
                {'name': e.get('name'), 'item': e.get('item', '')}
                for e in knoten.get('itemListElement', [])]
        elif art == 'Person':
            aus['person_id'] = knoten.get('@id')
        elif art == 'Article':
            aus['wortzahl'] = knoten.get('wordCount')
    return aus


def _meta(html, muster):
    m = re.search(muster, html)
    return m.group(1) if m else None


def kopf(html):
    """Titel, Beschreibung, Canonical, Robots und die og-Angaben."""
    return {
        'titel': _meta(html, r'<title>(.*?)</title>'),
        'beschreibung': _meta(
            html, r'<meta name="description" content="(.*?)" ?/>'),
        'canonical': _meta(
            html, r'<link rel="canonical" href="(.*?)" ?/>'),
        'robots': _meta(html, r"<meta name='robots' content='(.*?)' ?/>"),
        'og_bild': _meta(
            html, r'<meta property="og:image" content="(.*?)" ?/>'),
        'og_typ': _meta(
            html, r'<meta property="og:type" content="(.*?)" ?/>'),
        'og_url': _meta(
            html, r'<meta property="og:url" content="(.*?)" ?/>'),
        'og_bild_breite': _meta(
            html, r'<meta property="og:image:width" content="(.*?)" ?/>'),
        'og_bild_hoehe': _meta(
            html, r'<meta property="og:image:height" content="(.*?)" ?/>'),
        'og_bild_typ': _meta(
            html, r'<meta property="og:image:type" content="(.*?)" ?/>'),
        'veroeffentlicht': _meta(
            html,
            r'<meta property="article:published_time" content="(.*?)" ?/>'),
        'geaendert': _meta(
            html,
            r'<meta property="article:modified_time" content="(.*?)" ?/>'),
        # Yoast schreibt zwei Beschriftungs/Wert-Paare fuer die
        # Twitter-Karte. Welches Paar was enthaelt, haengt davon ab, ob die
        # Adresse eine Seite oder ein Beitrag ist - deshalb unverändert
        # uebernehmen statt deuten.
        'twitter_label1': _meta(
            html, r'<meta name="twitter:label1" content="(.*?)" ?/>'),
        'twitter_data1': _meta(
            html, r'<meta name="twitter:data1" content="(.*?)" ?/>'),
        'twitter_label2': _meta(
            html, r'<meta name="twitter:label2" content="(.*?)" ?/>'),
        'twitter_data2': _meta(
            html, r'<meta name="twitter:data2" content="(.*?)" ?/>'),
    }


# ------------------------------------------------- Mechanische Ersetzungen
# Diese Regeln greifen in jedem uebernommenen Seitenrumpf. Sie stehen hier
# und nicht im Generator, weil _build/verify.py sie auf den Schnappschuss
# anwendet, bevor er mit der gebauten Seite verglichen wird: so bleibt der
# Vergleich zeichengenau und die Regeln koennen nicht auseinanderlaufen.
#
# Alles, was ueber diese Regeln hinausgeht, ist eine Handaenderung und
# braucht einen Eintrag in _build/abweichungen.json.

# Bereiche, die es nach dem Umzug nicht mehr gibt. Verweise darauf werden
# aufgeloest: der Linktext bleibt stehen, das <a> faellt weg.
#
# /seafile/seamate und /seamate stehen hier mit Absicht NICHT, obwohl die
# Seite wegfaellt: die Adressen leiten auf die Seafile-Admin-Doku weiter
# (EXTERN in _build/gen_redirects.py), der Verweis darf also bleiben.
TOTE_ZIELE = (
    '/hero', '/hilfe', '/3cx', '/voip', '/odoo', '/consulting',
    '/roadmap', '/goldenrosskaserne',
    '/downloads/firmware', '/downloads/manuals',
    '/voip-ip-telefone-firmware-handbuecher-und-standard-passwoerter',
)
_TOT = '|'.join(re.escape(z) for z in TOTE_ZIELE)

ERSETZUNGEN = [
    # Der Shop ist abgeschaltet (Stand 21.10.2026).
    (re.compile(r'<!--\s*<a href="https://shop\.datamate\.org[^>]*>.*?</a>\s*-->',
                re.S), '', 'Shop-Verweis (war auskommentiert)'),
    (re.compile(r'<a [^>]*href="https://shop\.datamate\.org[^"]*"[^>]*>(.*?)</a>',
                re.S), r'\1', 'Shop-Verweis aufgeloest'),
    # Eingestellte Bereiche: Linktext behalten, Verweis entfernen.
    (re.compile(r'<a [^>]*href="(?:https://www\.datamate\.org)?(?:'
                + _TOT + r')(?:/[^"]*)?"[^>]*>(.*?)</a>', re.S),
     r'\1', 'Verweis auf eingestellten Bereich aufgeloest'),
    # Eigene Adressen relativ machen. Absolute Adressen wuerden beim
    # Bauen und Pruefen auf die alte Live-Seite zeigen und damit genau die
    # fehlenden Dateien verdecken, die gefunden werden sollen.
    (re.compile(r'(?:https?:)?//www\.datamate\.org/'), '/',
     'eigene Adresse relativ gemacht'),
    # Das Canvas-Template legte seine Dateien unter /static/ ab, im
    # WordPress-Theme liegen sie unter images/. Der Verweis blieb stehen
    # und lieferte auf acht Seiten 404 - die Datei ist da, nur anderswo.
    (re.compile(r'/static/images/icons/widget-link\.png'),
     '/wp-content/themes/datamate-theme/images/icons/widget-link.png',
     'Pfad des Listenpunkt-Bilds korrigiert'),
    # Die Domain ist seit Jahren abgeschaltet, das Skript laedt nichts mehr.
    (re.compile(r'\s*<!--\[if lt IE 9\]>.*?<!\[endif\]-->', re.S), '',
     'IE-Weiche auf css3-mediaqueries-js.googlecode.com'),
]


def normalisiere(rumpf_html):
    """Wendet ERSETZUNGEN an und meldet, welche Regel wie oft gegriffen hat."""
    treffer = {}
    for muster, ersatz, grund in ERSETZUNGEN:
        rumpf_html, n = muster.subn(ersatz, rumpf_html)
        if n:
            treffer[grund] = treffer.get(grund, 0) + n
    return rumpf_html, treffer


# ------------------------------------------------------- Handaenderungen
# Stellen, an denen der uebernommene Text nicht mehr stimmt, weil der
# Bereich, von dem er spricht, eingestellt ist. Jede Aenderung steht hier
# mit Begruendung; _build/verify.py wendet sie auf den Schnappschuss an,
# bevor er mit der gebauten Seite verglichen wird. Was hier nicht steht,
# ist ein Fehler.
#
# Aufbau: Pfad -> Liste von (vorher, nachher, Grund)
HANDAENDERUNGEN = {
    '/': [(
        """
<!--
<div id="hero" class="section height858 nomargin noborder" style="background: url('/wp-content/themes/datamate-theme/images/frontpage/Hero.jpg') no-repeat center center;">
\t<div class="vertical-middle">
\t<div class="container clearfix">
\t\t<div class="col-2 col-md-6"></div>
\t\t<div class="col-10 col-md-6 text-center datamate-dark-boxes">
\t\t\t<h2 style="font-size: 2.4em;">datamate Hero</h2>
\t\t\t<p style="font-size: 1.6em;">All-in-one Rescue Stick <br/>Reinigen, Retten und Reparieren</p>
\t\t\tMehr erfahren Jetzt kaufen 
\t\t</div>
\t</div>
\t</div>
</div>
--> """,
        '',
        'Produktkasten Hero - der Bereich faellt weg. Stand schon im '
        'WordPress in einem HTML-Kommentar, war also unsichtbar.',
    )],
    '/buddy/': [(
        '\t\t\t<div class="col-sm-4">\n'
        '\t\t\t\t<span style="color:#5E994A;">datamate Hero</span>\n'
        '\t\t\t\t<h2>Allzweckwaffe</h2>\t\t\n'
        '\t\t\t\t<img decoding="async" loading="lazy" width="800" '
        'height="800" src="/wp-content/uploads/2017/05/Hero_800x800.png" '
        'style="padding:10%;" alt="datamate Hero - die Allzweckwaffe für '
        'Systemadministratoren" class="alignnone size-full wp-image-2247" '
        'srcset="/wp-content/uploads/2017/05/Hero_800x800.png 800w, '
        '/wp-content/uploads/2017/05/Hero_800x800-150x150.png 150w, '
        '/wp-content/uploads/2017/05/Hero_800x800-300x300.png 300w, '
        '/wp-content/uploads/2017/05/Hero_800x800-768x768.png 768w" '
        'sizes="(max-width: 800px) 100vw, 800px" />\n'
        '\t\t\t\t<p>Das schweizer Taschenmesser für IT-ler - der Rescue '
        'Stick zum prüfen, reparieren, retten und neuinstallieren.</p>\n'
        '\t\t\t</div>\n',
        '',
        'Hero-Spalte in "Ergaenzungen zu Buddy" entfernt - das Produkt '
        'faellt weg. Die Reihe zeigt jetzt zwei statt drei Spalten.',
    )],
    '/seafile/': [(
        """\t\t\t\t\t\t\t<p>Es ist kinderleicht das Seafile-Logo durch eine eigene Grafik zu ersetzen. Mit Seamate, dem Webcustomizer von datamate, kann man auch die gesamte Farbgebung von Seafile austauschen um das System ganz individuell an das eigenen Corporate Design anzupassen. Es ist keine Programmierung erforderlich, da lediglich ein von Seamate erzeugter CSS-Code hinterlegt werden muss.
\t\t\t\t\t\t\t</p>
\t\t\t\t\t\t\t<p><a href="/seafile/seamate" class="button button-3d"> Mehr über Seamate erfahren</a></p>""",
        """\t\t\t\t\t\t\t<p>Es ist kinderleicht das Seafile-Logo durch eine eigene Grafik zu ersetzen. Auch die gesamte Farbgebung von Seafile lässt sich austauschen, um das System ganz individuell an das eigene Corporate Design anzupassen. Eine Programmierung ist dafür nicht erforderlich: Ein Farbwähler erzeugt den CSS-Code, der nur noch hinterlegt werden muss.
\t\t\t\t\t\t\t</p>
\t\t\t\t\t\t\t<p><a href="/seafile/seamate" class="button button-3d"> Mehr über Seamate erfahren</a> <a href="/seafile/customizing/" class="button button-3d"> Mehr über das Customizing erfahren</a></p>""",
        'Der Absatz nannte Seamate einen Webcustomizer von datamate. Den '
        'Generator gibt es nicht mehr; den Farbwaehler, der den CSS-Code '
        'erzeugt, gibt es weiter in der Seafile-Admin-Doku. Der Verweis '
        'auf /seafile/seamate bleibt und leitet dorthin; dazu kommt der '
        'Verweis auf /seafile/customizing/.',
    )],
    '/deutsche-seafile-webseite-veroeffentlicht/': [(
        'href="www.seafile.com"',
        'href="https://www.seafile.com"',
        'Verweis ohne Schema - zeigte auf '
        '/deutsche-seafile-webseite-veroeffentlicht/www.seafile.com '
        'und war schon im WordPress kaputt.',
    )],
    '/seafile/customizing/': [(
        'href="/seafile/seafile_client_plattformen/"',
        'href="/seafile/client-plattformen/"',
        'Schreibfehler im Verweis - die Seite heisst '
        '/seafile/client-plattformen/, die verwiesene Adresse liefert '
        'schon im WordPress 404.',
    )],
    '/autoprovisionierung-von-ip-telefonen-mit-factory-reset/': [(
        'href="/blog/wechseln-sie-zum-anschluss-der-zukunft-sonst-wir-der-vertrag-gekuendigt/"',
        'href="/wechseln-sie-zum-anschluss-der-zukunft-sonst-wird-der-vertrag-gekuendigt/"',
        'Schreibfehler im Verweis ("sonst-wir" statt "sonst-wird") - '
        'liefert schon im WordPress 404.',
    )],
    '/teil-4-synchronisation-mit-sabredav/': [(
        'src="h/wp-content/uploads/2017/08/thunderbird-termine1.png"',
        'src="/wp-content/uploads/2017/08/thunderbird-termine1.png"',
        'Tippfehler im Bildpfad ("h/" statt "/") - das Bild fehlte schon '
        'im WordPress.',
    )],
}


def handaenderungen(pfad, rumpf_html):
    """Wendet die Handaenderungen einer Adresse an.

    Jede muss genau einmal passen. Passt eine nicht mehr, hat sich der
    Inhalt geaendert und die Aenderung muss nachgezogen werden - das ist
    ein Fehler und kein stiller Durchlaeufer.
    """
    angewandt = []
    for vorher, nachher, grund in HANDAENDERUNGEN.get(pfad, []):
        n = rumpf_html.count(vorher)
        if n != 1:
            raise AssertionError(
                'Handaenderung fuer %s passt %dx statt 1x: %s'
                % (pfad, n, grund))
        rumpf_html = rumpf_html.replace(vorher, nachher)
        angewandt.append(grund)
    return rumpf_html, angewandt
