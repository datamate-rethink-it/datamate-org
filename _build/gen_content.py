"""Erzeugt content/ aus dem Schnappschuss und den REST-Daten.

Migrationswerkzeug, kein Teil des Builds: einmal gelaufen, liegt das
Ergebnis im Repo und wird dort von Hand weitergepflegt. Ein zweiter Lauf
ueberschreibt Handaenderungen - deshalb erst nach Rueckfrage laufen lassen
(--force).

Zwei Quellen, mit Absicht:
  * der gerenderte Schnappschuss liefert den Text - nur er enthaelt die
    <!--more-->-Marke als <span id="more-NNN">, an der WordPress den Teaser
    abschneidet. Die REST-API verschluckt sie.
  * die REST-API liefert die Metadaten (Datum, Kategorien, Autor), die im
    gerenderten HTML nur in Prosa stehen.

Aufruf:  python3 -E -s _build/gen_content.py [--force]
"""
import html as htmllib
import json
import os
import re
import sys

import wpdata as w

CONTENT = os.path.join(w.WURZEL, 'content')

A_EINTRAG = '<div class="entry clearfix">'
E_EINTRAG = '</div> <!-- ipost clearfix -->'

RE_BLOGBILD = re.compile(
    r'<div class="blog-header" style="background-image: url\((.*?)\);')
RE_H1 = re.compile(
    r'<div class="entry-title">\s*<h1[^>]*>(.*?)</h1>', re.S)
RE_AUTORBOX = re.compile(
    r'\s*<!-- Post Author Info\s*=+ -->.*$', re.S)
RE_MORE = re.compile(r'<span id="more-\d+"></span>')


def toml_wert(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, dict):
        return '{' + ', '.join(
            '%s = %s' % (k, toml_wert(x)) for k, x in v.items()) + '}'
    if isinstance(v, list):
        return '[' + ', '.join(toml_wert(x) for x in v) + ']'
    return '"' + str(v).replace('\\', '\\\\').replace('"', '\\"') + '"'


def schreibe(pfad, vorspann, rumpf):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    zeilen = ['+++']
    for k, v in vorspann.items():
        if v is None or v == '':
            continue
        zeilen.append('%s = %s' % (k, toml_wert(v)))
    zeilen.append('+++')
    with open(pfad, 'w', encoding='utf-8') as f:
        f.write('\n'.join(zeilen) + '\n' + rumpf.rstrip() + '\n')


def stumm(pfad, name):
    """Abschnittsseite, die nicht gebaut wird - fuer Ordner ohne eigene Adresse."""
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, 'w', encoding='utf-8') as f:
        f.write('+++\ntitle = %s\n[build]\nrender = \'never\'\n'
                'list = \'never\'\n+++\n' % toml_wert(name))


# ------------------------------------------------------------------ Seiten
def inhaltspfad_seite(pfad):
    """/seafile/architektur/ -> content/seafile/architektur.html"""
    if pfad == '/':
        return os.path.join(CONTENT, '_index.html')
    teile = pfad.strip('/').split('/')
    if pfad == '/blog/':
        return os.path.join(CONTENT, 'blog', '_index.html')
    # Eine Seite mit Unterseiten wird zum Abschnitt.
    return os.path.join(CONTENT, *teile[:-1], teile[-1] + '.html')


def hat_kinder(pfad, alle_pfade):
    return any(p != pfad and p.startswith(pfad) for p in alle_pfade)


def seiten_schreiben(bericht):
    alle = w.seiten()
    pfade = [w.pfad_von(s) for s in alle]
    behalten = [s for s in alle if not w.faellt_fort(w.pfad_von(s))]
    for s in behalten:
        p = w.pfad_von(s)
        roh = w.schnappschuss(p)
        rumpf, treffer = w.normalisiere(w.rumpf(roh))
        rumpf, hand = w.handaenderungen(p, rumpf)
        bericht['hand'] += [(p, g) for g in hand]
        k = w.kopf(roh)
        sch = w.schema(roh)
        ziel = inhaltspfad_seite(p)
        if p != '/' and p != '/blog/' and hat_kinder(p, pfade):
            ziel = os.path.join(CONTENT, p.strip('/'), '_index.html')
        vorspann = {
            'title': htmllib.unescape(s['title']['rendered']),
            'titel_html': k['titel'],
            'beschreibung': k['beschreibung'],
            'robots': k['robots'],
            'og_bild': k['og_bild'],
            'og_typ': k['og_typ'],
            'og_url': k['og_url'],
            'canonical': k['canonical'],
            'og_bild_breite': k['og_bild_breite'],
            'og_bild_hoehe': k['og_bild_hoehe'],
            'og_bild_typ': k['og_bild_typ'],
            'veroeffentlicht': k['veroeffentlicht'],
            'geaendert': k['geaendert'],
            'twitter_label1': k['twitter_label1'],
            'twitter_data1': k['twitter_data1'],
            'twitter_label2': k['twitter_label2'],
            'twitter_data2': k['twitter_data2'],
            'brotkrumen': sch.get('brotkrumen'),
            'wp_id': s['id'],
            'date': s['date'],
            'lastmod': s['modified'],
            # Fuer das JSON-LD und den Feed, die beide UTC schreiben.
            'datum_utc': s['date_gmt'] + '+00:00',
            'geaendert_utc': s['modified_gmt'] + '+00:00',
        }
        if p == '/blog/':
            # Die Uebersicht erzeugt layouts/blog/section.html neu - der
            # gerenderte Rumpf des alten Stands waere eine Momentaufnahme
            # der Beitragsliste und damit sofort veraltet. Uebernommen
            # werden nur Kopfangaben und das Kopfbild.
            m = RE_BLOGBILD.search(roh)
            kb = m.group(1) if m else None
            if kb:
                # Das alte Template schrieb den Pfad relativ ("../wp-...").
                kb = '/' + kb.lstrip('./')
            vorspann['kopfbild'] = kb
            rumpf = ''
        schreibe(ziel, vorspann, rumpf)
        bericht['seiten'] += 1
        for g, n in treffer.items():
            bericht['regeln'][g] = bericht['regeln'].get(g, 0) + n
    # /software/ und /category/ waren nie eigene Adressen. Ohne diese
    # beiden Dateien baut Hugo fuer die Abschnitte je eine Uebersichtsseite
    # und erfindet damit zwei Adressen, die es nie gab.
    for abschnitt, name in (('software', 'Software'), ('category', 'Kategorien')):
        stumm(os.path.join(CONTENT, abschnitt, '_index.html'), name)


# --------------------------------------------------------------- Beitraege
def beitraege_schreiben(bericht):
    autoren = w.autoren()
    kat_nach_id = {k['id']: k for k in w.kategorien()}
    tag_nach_id = {t['id']: t for t in w.schlagwoerter()}
    for b in w.beitraege():
        if b['slug'] in w.FORT_BEITRAEGE:
            continue
        p = w.pfad_von(b)
        roh = w.schnappschuss(p)
        k = w.kopf(roh)
        sch = w.schema(roh)
        i = roh.index(A_EINTRAG) + len(A_EINTRAG)
        e = roh.index(E_EINTRAG)
        text = roh[i:e]
        # Die Autorenbox erzeugt das Layout aus dem Vorspann neu.
        text = RE_AUTORBOX.sub('', text)
        # Das schliessende </div> gehoert zu <div class="entry clearfix">,
        # das das Layout oeffnet - sonst waere die Inhaltsdatei fuer sich
        # nicht ausgewogen.
        text = re.sub(r'\s*</div>\s*$', '', text)
        text, treffer = w.normalisiere(text.strip('\n'))
        text, hand = w.handaenderungen(p, text)
        bericht['hand'] += [(p, g) for g in hand]
        m = RE_BLOGBILD.search(roh)
        bild = m.group(1) if m else None
        if bild:
            bild, _ = w.normalisiere(bild)
        h1 = RE_H1.search(roh)
        vorspann = {
            'title': htmllib.unescape(b['title']['rendered']),
            'titel_html': k['titel'],
            'ueberschrift': h1.group(1) if h1 else None,
            'beschreibung': k['beschreibung'],
            'robots': k['robots'],
            'og_bild': k['og_bild'],
            'og_typ': k['og_typ'],
            'og_url': k['og_url'],
            'canonical': k['canonical'],
            'og_bild_breite': k['og_bild_breite'],
            'og_bild_hoehe': k['og_bild_hoehe'],
            'og_bild_typ': k['og_bild_typ'],
            'veroeffentlicht': k['veroeffentlicht'],
            'geaendert': k['geaendert'],
            'twitter_label1': k['twitter_label1'],
            'twitter_data1': k['twitter_data1'],
            'twitter_label2': k['twitter_label2'],
            'twitter_data2': k['twitter_data2'],
            'beitragsbild': bild,
            'bild_breite': sch.get('bild_breite'),
            'bild_hoehe': sch.get('bild_hoehe'),
            'bild_beschriftung': sch.get('bild_beschriftung'),
            'brotkrumen': sch.get('brotkrumen'),
            'wortzahl': sch.get('wortzahl'),
            'autor': autoren[b['author']]['name'],
            'autor_kurz': autoren[b['author']]['slug'],
            'kategorien': [kat_nach_id[c]['slug'] for c in b['categories']
                           if c in kat_nach_id],
            # Schlagwortseiten waren nie verlinkt und standen in keiner
            # Sitemap - sie werden nicht gebaut. Die Begriffe stehen hier,
            # weil Yoast sie als keywords ins JSON-LD geschrieben hat.
            'schlagwoerter': [htmllib.unescape(tag_nach_id[t]['name'])
                              for t in b['tags'] if t in tag_nach_id],
            'wp_id': b['id'],
            'slug': b['slug'],
            'url': p,
            'date': b['date'],
            'lastmod': b['modified'],
            'datum_utc': b['date_gmt'] + '+00:00',
            'geaendert_utc': b['modified_gmt'] + '+00:00',
        }
        # Nur Beitraege mit Galeriebildern laden lightbox.js und -css.
        if 'data-slb-active' in text:
            vorspann['lightbox'] = True
        if not RE_MORE.search(text):
            bericht['ohne_more'].append(p)
        schreibe(os.path.join(CONTENT, 'blog', b['slug'] + '.html'),
                 vorspann, text)
        bericht['beitraege'] += 1
        for g, n in treffer.items():
            bericht['regeln'][g] = bericht['regeln'].get(g, 0) + n


# -------------------------------------------------------------- Kategorien
def kategorien_schreiben(bericht):
    kats = w.kategorien()
    nach_id = {k['id']: k for k in kats}

    def pfad(k):
        teile = [k['slug']]
        while k['parent']:
            k = nach_id[k['parent']]
            teile.insert(0, k['slug'])
        return teile

    for k in kats:
        teile = pfad(k)
        # Immer als Abschnitt (_index.html), auch ohne Unterkategorien:
        # Hugo blaettert nur in Abschnitten, und /category/<pfad>/page/2/
        # muss es weiter geben.
        ziel = os.path.join(CONTENT, 'category', *teile, '_index.html')
        p = '/category/' + '/'.join(teile) + '/'
        roh = w.schnappschuss(p)
        kk = w.kopf(roh)
        # Alle Nachfahren: die Archivseite zeigt sie mit an, so wie bisher.
        nachfahren = [k['slug']]
        offen = [k['id']]
        while offen:
            eltern = offen.pop()
            for x in kats:
                if x['parent'] == eltern:
                    nachfahren.append(x['slug'])
                    offen.append(x['id'])
        schreibe(ziel, {
            'title': htmllib.unescape(k['name']),
            'titel_html': kk['titel'],
            'beschreibung': kk['beschreibung'],
            'robots': kk['robots'],
            'canonical': kk['canonical'],
            'og_url': kk['og_url'],
            'og_typ': kk['og_typ'],
            'og_bild': kk['og_bild'],
            'brotkrumen': w.schema(roh).get('brotkrumen'),
            'type': 'kategorie',
            'kategorie': k['slug'],
            'kategorie_mit': nachfahren,
            'wp_id': k['id'],
        }, '')
        bericht['kategorien'] += 1


def daten_schreiben(bericht):
    """data/ fuer die Layouts: Kategoriebaum und Autoren.

    Beides steckt im WordPress in der Datenbank. Als Datei im Repo ist es
    im Layout mit zwei Zeilen erreichbar - ein Kategoriebaum aus
    verschachtelten Inhaltsseiten waere in Hugo-Vorlagen unlesbar.
    """
    kats = w.kategorien()
    nach_id = {k['id']: k for k in kats}

    def kette(k):
        teile = [k['slug']]
        while k['parent']:
            k = nach_id[k['parent']]
            teile.insert(0, k['slug'])
        return teile

    eintraege = {}
    for k in kats:
        teile = kette(k)
        nachfahren = [k['slug']]
        offen = [k['id']]
        while offen:
            e = offen.pop()
            for x in kats:
                if x['parent'] == e:
                    nachfahren.append(x['slug'])
                    offen.append(x['id'])
        eintraege[k['slug']] = {
            'slug': k['slug'],
            'name': htmllib.unescape(k['name']),
            'pfad': '/category/' + '/'.join(teile) + '/',
            'eltern': nach_id[k['parent']]['slug'] if k['parent'] else '',
            'mit': nachfahren,
            'kinder': [],
        }

    # Geschachtelt und je Ebene alphabetisch - so stand die Liste in der
    # Seitenleiste des WordPress-Widgets.
    def sortiert(eintraege_):
        return sorted(eintraege_, key=lambda e: e['name'].lower())

    for e in eintraege.values():
        if e['eltern']:
            eintraege[e['eltern']]['kinder'].append(e)
    for e in eintraege.values():
        e['kinder'] = sortiert(e['kinder'])
    baum = sortiert([e for e in eintraege.values() if not e['eltern']])

    # Die Personen-Kennung im JSON-LD ist ein Hash, den Yoast gebildet
    # hat. Nachrechnen koennte man ihn nicht - er wird aus den Beitraegen
    # abgelesen, damit die Kennungen dieselben bleiben.
    person_id = {}
    for b in w.beitraege():
        if b['slug'] in w.FORT_BEITRAEGE:
            continue
        sch = w.schema(w.schnappschuss(w.pfad_von(b)))
        kurz = w.autoren()[b['author']]['slug']
        if sch.get('person_id') and kurz not in person_id:
            person_id[kurz] = sch['person_id']

    autoren = {}
    for a in w.autoren().values():
        autoren[a['slug']] = {
            'name': a['name'],
            'beschreibung': a['description'],
            'person_id': person_id.get(a['slug'], ''),
        }

    daten = os.path.join(w.WURZEL, 'data')
    os.makedirs(daten, exist_ok=True)
    # Flache Zuordnung Slug -> Name: das JSON-LD braucht die Namen der
    # Kategorien eines Beitrags, der Vorspann kennt nur die Slugs.
    namen = {k['slug']: htmllib.unescape(k['name']) for k in kats}

    for name, inhalt in (('kategorien', baum), ('autoren', autoren),
                         ('kategoriennamen', namen)):
        with open(os.path.join(daten, name + '.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(inhalt, f, ensure_ascii=False, indent=2,
                      sort_keys=True)
            f.write('\n')
    bericht['daten'] = len(baum)


def main():
    if os.path.isdir(CONTENT) and '--force' not in sys.argv:
        sys.exit('content/ existiert schon. Ein zweiter Lauf ueberschreibt '
                 'Handaenderungen - mit --force erzwingen.')
    bericht = {'seiten': 0, 'beitraege': 0, 'kategorien': 0,
               'regeln': {}, 'ohne_more': [], 'hand': []}
    seiten_schreiben(bericht)
    beitraege_schreiben(bericht)
    kategorien_schreiben(bericht)
    daten_schreiben(bericht)
    print('Seiten     %3d' % bericht['seiten'])
    print('Beitraege  %3d' % bericht['beitraege'])
    print('Kategorien %3d' % bericht['kategorien'])
    print('\nErsetzungen:')
    for g, n in sorted(bericht['regeln'].items(), key=lambda x: -x[1]):
        print('  %-48s %5d' % (g, n))
    print('\nHandaenderungen: %d' % len(bericht['hand']))
    for p_, g in bericht['hand']:
        print('  %-44s %s' % (p_, g))
    if bericht['ohne_more']:
        print('\nohne <!--more-->-Marke (Teaser = erster Absatz): %d'
              % len(bericht['ohne_more']))
        for p in bericht['ohne_more']:
            print('  ' + p)


if __name__ == '__main__':
    main()
