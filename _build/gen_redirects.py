"""Erzeugt deploy/redirects.caddy und _build/weiterleitungen.json.

Die alte Installation hat auf vier Wegen weitergeleitet, und nur einer
davon war sichtbar:

  1. Das Plugin *Redirection* mit 24 gepflegten Regeln. Sie liegen als
     _build/redirects-redirection-export.csv im Repo.
  2. WordPress selbst leitete jede Unterseite von ihrer nackten Adresse
     auf den vollen Pfad - /architektur/ auf /seafile/architektur/. Das
     steht nirgends geschrieben und faellt erst auf, wenn es fehlt.
  3. Ebenso /blog/<slug>/ auf /<slug>/ fuer jeden Beitrag. Die Beitraege
     lagen vor einem Umbau unter /blog/ und werden so noch verlinkt.
  4. Yoast SEO leitete die Anhangseiten eines Beitrags - /<beitrag>/<bild>/ -
     auf die Bilddatei.

Dazu kommen die Adressen der eingestellten Bereiche. Sie antworten mit
410 Gone und nicht mit 404: 410 sagt einer Suchmaschine, dass die Adresse
absichtlich weg ist, und raeumt sie schneller aus dem Index.

Aufruf:  python3 -E -s _build/gen_redirects.py
"""
import csv
import glob
import json
import os
import re
import sys

import wpdata as w

ZIEL_CADDY = os.path.join(w.WURZEL, 'deploy', 'redirects.caddy')
ZIEL_JSON = os.path.join(w.BASIS, 'weiterleitungen.json')

# Adressen, die auf eine fremde Seite weiterleiten. Die Seite dazu gibt es
# bei uns nicht mehr (sie steht in wpdata.FORT_SEITEN), der Inhalt aber
# woanders weiter. Darum eine Weiterleitung statt 410: die Adresse ist von
# aussen verlinkt, und das Ziel beantwortet dieselbe Frage.
_SEAMATE = ('https://datamate-rethink-it.github.io/'
            'seafile-admin-docs/customization/main-color/')
EXTERN = {
    '/seafile/seamate': _SEAMATE,
    '/seamate': _SEAMATE,       # nackte Adresse, von WordPress umgeleitet
}


def medien():
    """Alle Mediendateien als {(Beitrags-Slug, Anhang-Slug): Adresse}."""
    nach_id = {}
    for datei in sorted(glob.glob(os.path.join(w.WP, 'media-*.json'))):
        with open(datei, encoding='utf-8') as f:
            for m in json.load(f):
                nach_id[m['id']] = m
    beitrag_slug = {b['id']: b['slug'] for b in w.beitraege()}
    beitrag_slug.update({s['id']: w.pfad_von(s).strip('/').split('/')[-1]
                         for s in w.seiten()})
    aus = {}
    for m in nach_id.values():
        eltern = beitrag_slug.get(m.get('post') or 0)
        if not eltern or not m.get('slug'):
            continue
        pfad = re.sub(r'^https?://(www\.)?datamate\.org', '',
                      m.get('source_url') or '')
        if pfad.startswith('/'):
            aus[(eltern, m['slug'])] = pfad
    return aus


def anhangseiten():
    """Anhangseiten, die aus den Inhalten heraus verlinkt werden."""
    karte = medien()
    beitraege = {b['slug'] for b in w.beitraege()}
    seiten = {w.pfad_von(s).strip('/').split('/')[-1] for s in w.seiten()}
    verlinkt, ohne_ziel = {}, []
    muster = re.compile(r'href="(/([^/"]+)/([^/"]+)/)"')
    for datei in glob.glob(os.path.join(w.WURZEL, 'content', '**', '*.html'),
                           recursive=True):
        with open(datei, encoding='utf-8') as f:
            for m in muster.finditer(f.read()):
                adresse, eltern, kind = m.groups()
                if eltern not in beitraege and eltern not in seiten:
                    continue
                if kind in beitraege or kind in seiten:
                    continue            # echte Unterseite, kein Anhang
                if (eltern, kind) in karte:
                    verlinkt[adresse] = karte[(eltern, kind)]
                else:
                    ohne_ziel.append(adresse)
    return verlinkt, sorted(set(ohne_ziel))


def plugin_regeln():
    """Die 24 Regeln des Plugins Redirection, nach Art getrennt."""
    datei = os.path.join(w.BASIS, 'redirects-redirection-export.csv')
    einfach, muster, verfallen = {}, [], []
    with open(datei, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            quelle = r['source']
            ziel = re.sub(r'^https?://(www\.)?datamate\.org', '', r['target'])
            if ziel.startswith(w.TOTE_ZIELE) or '/downloads/manuals' in ziel \
                    or '/downloads/firmware' in ziel \
                    or '3CX_Installation' in ziel:
                verfallen.append((quelle, ziel))
            elif r['regex'] == '1':
                muster.append((quelle, ziel))
            else:
                einfach[quelle] = ziel
    return einfach, muster, verfallen


def kindslugs():
    """Nackte Adressen der Unterseiten - was WordPress selbst umleitete."""
    alle = w.seiten()
    pfade = {w.pfad_von(s): s for s in alle}
    beitraege = {b['slug'] for b in w.beitraege()}
    oberste = {p.strip('/') for p in pfade if p.count('/') == 2}
    bleibt, fort, kollision = {}, [], []
    for p in sorted(pfade):
        teile = p.strip('/').split('/')
        if len(teile) < 2:
            continue
        slug = teile[-1]
        if slug in beitraege or slug in oberste:
            kollision.append(slug)
            continue
        if w.faellt_fort(p):
            fort.append('/' + slug + '/')
        else:
            bleibt['/' + slug + '/'] = p
    return bleibt, sorted(set(fort)), sorted(set(kollision))


def main():
    einfach, muster, verfallen = plugin_regeln()
    kind_bleibt, kind_fort, kollision = kindslugs()
    anhang, anhang_ohne = anhangseiten()

    # Einzelne Adressen, die WordPress aus einem Teil des Slugs erraten hat
    # (redirect_guess_404_permalink). Nur die, die aus den Inhalten heraus
    # verlinkt sind - erraten laesst sich das nicht nachbauen.
    geraten = {
        '/openproject': '/openproject-6-0-was-bringt-das-neue-major-release/',
        '/windows-benutzerpasswort-vergessen-hero-eilt-zur-hilfe/'
        'mit-der-windows-wiederherstellung-defekte-systeme-munter-machen':
            '/mit-der-windows-wiederherstellung-defekte-systeme-munter-machen/',
        '/aus-ipv4-in-ipv6-serverzugriff-aus-dem-mobilfunknetz/'
        'nat-loopback-oder-wie-dyndns-fuers-interne-netzwerk-fit-gemacht-werden-kann':
            '/nat-loopback-oder-wie-dyndns-fuers-interne-netzwerk-fit-gemacht-werden-kann/',
        '/datenschutz': '/datenschutzerklaerung/',
        '/sitemap.xml': '/sitemap_index.xml',
    }

    z = []
    a = z.append
    a('# Weiterleitungen und entfallene Adressen.')
    a('#')
    a('# ERZEUGT von _build/gen_redirects.py - nicht von Hand aendern.')
    a('# Eingebunden von Caddyfile.container. Die Reihenfolge der')
    a('# handle-Bloecke ist die Logik: der erste passende gewinnt.')
    a('#')
    a('# Die redir-Zeilen tragen den Matcher * : ohne ihn liest Caddy das')
    a('# Ziel, weil es mit / beginnt, als Pfadmuster und leitet nicht um.')
    a('')

    # ---------------------------------------------------------------
    # Einzelne Adressen mit festem Ziel: eine Tabelle statt vieler
    # handle-Bloecke. handle nimmt nur ein Pfadmuster, und 60 Bloecke
    # waeren 60 Stellen, an denen ein zu weites Muster eine echte Adresse
    # einfangen kann - genau das ist mit /software* passiert, das auch
    # /software/lizenzbedingungen/ erwischte. Die Tabelle trifft exakt.
    tabelle = {}
    tabelle.update(einfach)
    tabelle.update(kind_bleibt)
    tabelle.update(anhang)
    tabelle.update(geraten)
    tabelle.update(EXTERN)

    a('# --- 1. Adressen mit festem Ziel -------------------------------')
    a('# Zusammengefasst aus fuenf Quellen:')
    a('#   * gepflegte Regeln des Plugins Redirection (ohne Platzhalter)')
    a('#   * nackte Adressen der Unterseiten: /architektur/ ->')
    a('#     /seafile/architektur/, von WordPress selbst umgeleitet')
    a('#   * Anhangseiten -> Bilddatei, von Yoast SEO umgeleitet')
    a('#   * Adressen, die WordPress aus einem Teil des Slugs erraten hat')
    a('#   * Adressen, deren Inhalt jetzt auf einer fremden Seite steht')
    a('map {path} {ziel} {')
    for q, zl in sorted(tabelle.items()):
        muster_q = '~^' + re.escape(q.rstrip('/')).replace('/', '/') + '/?$'
        if '|' in q:
            muster_q = ('~^' + re.escape(q.rstrip('/|'))
                        + r'/(\||%7C)$')
        a('\t%-78s %s' % (muster_q, zl))
    a('\tdefault ""')
    a('}')
    a('@mit_ziel expression `{ziel} != ""`')
    a('handle @mit_ziel {')
    a('\tredir * {ziel} permanent')
    a('}')
    a('')

    a('# --- 2. Alte Beitragsadressen mit geaendertem Slug -------------')
    a('# Diese Beitraege lagen unter /blog/ und wurden danach umbenannt.')
    for q, zl in sorted(muster):
        alt = q.replace('^', '').replace('(.*?)', '')
        if alt.startswith('/blog/wp-content') or \
                alt.startswith('/blog/page/wp-content'):
            continue
        a('handle %s* {' % alt)
        a('\tredir * %s permanent' % zl.replace('$1', ''))
        a('}')
    a('')

    a('# --- 3. Bilder, die unter /blog/ verlinkt wurden ---------------')
    a('# 23 458 Aufrufe im Zaehler des Plugins - alte Beitragsbilder.')
    a('@blogbilder path_regexp blogbilder ^/blog/(?:page/)?wp-content/'
      'uploads/(.*)$')
    a('handle @blogbilder {')
    a('\tredir * /wp-content/uploads/{re.blogbilder.1} permanent')
    a('}')
    a('')

    a('# --- 4. Blog-Uebersicht und ihre Blaetterseiten ----------------')
    a('# Muss vor Regel 5 stehen: /blog/page/2/ ist eine echte Adresse,')
    a('# kein alter Beitragspfad.')
    a('handle /blog/page/* {')
    a('\ttry_files {path} {path}/index.html')
    a('\tfile_server')
    a('}')
    a('handle /blog/ {')
    a('\ttry_files {path}index.html')
    a('\tfile_server')
    a('}')
    a('')

    a('# --- 5. /blog/<slug>/ -> /<slug>/ ------------------------------')
    a('# Jeder Beitrag war einmal unter /blog/ erreichbar; WordPress hat')
    a('# diese Adressen selbst umgeleitet.')
    a('@blogslug path_regexp blogslug ^/blog/(.+)$')
    a('handle @blogslug {')
    a('\tredir * /{re.blogslug.1} permanent')
    a('}')
    a('')

    a('# --- 9. Suche --------------------------------------------------')
    a('# Die WordPress-Suche lief ueber /?s=... - jetzt sucht Pagefind')
    a('# unter /suche/ im Browser.')
    a('@suche query s=*')
    a('handle @suche {')
    a('\tredir * /suche/?q={http.request.uri.query.s} permanent')
    a('}')
    a('')

    a('# --- 10. Eingestellte Bereiche: 410 Gone -----------------------')
    a('# Entscheidung vom 21.10.2026, siehe README. 410 statt 404, damit')
    a('# Suchmaschinen die Adressen zuegig aus dem Index nehmen.')
    # Pfadmuster fuer 410. Zwei Formen, und der Unterschied ist
    # wesentlich:
    #   /hero  /hero/*    der Bereich samt allem darunter
    #   /windows  /windows/   genau diese Adresse
    # Ein einziges /windows* wuerde auch
    # /windows-benutzerpasswort-vergessen-hero-eilt-zur-hilfe/ einfangen -
    # einen Beitrag, der bleibt. Zehn Beitraege waren davon betroffen.
    gone = []

    def genau(pfad):
        gone.append(pfad.rstrip('/'))
        gone.append(pfad.rstrip('/') + '/')

    def unterbaum(pfad):
        gone.append(pfad.rstrip('/'))
        gone.append(pfad.rstrip('/') + '/*')

    for p in sorted(w.FORT_SEITEN):
        genau(p)
    for p in w.FORT_PRAEFIXE:
        unterbaum(p)
    genau('/seamate')
    for p in ('/downloads/firmware', '/downloads/manuals', '/manuals',
              '/firmware'):
        unterbaum(p)
    for b in sorted(w.FORT_BEITRAEGE):
        genau('/' + b)
    for q in kind_fort:
        genau(q)
    genau('/software/roadmap')
    gone.append('/wp-content/uploads/2018/12/'
                'datamate_Auftragsformular_3CXInstallation.pdf')
    gone.append('/wp-content/uploads/2019/04/'
                '3CX_Installation_Bestellformular-1.pdf')

    # Was auf eine fremde Seite weiterleitet, antwortet nicht mit 410.
    # Regel 1 steht vorher und wuerde ohnehin gewinnen; hier faellt die
    # Adresse heraus, damit die Absicht an einer Stelle steht.
    extern_pfade = {q.rstrip('/') for q in EXTERN}
    gone = [g for g in gone if g.rstrip('/*') not in extern_pfade]

    a('@entfallen path %s' % ' '.join(sorted(set(gone))))
    a('handle @entfallen {')
    a('\terror 410')
    a('}')
    a('')

    os.makedirs(os.path.dirname(ZIEL_CADDY), exist_ok=True)
    with open(ZIEL_CADDY, 'w', encoding='utf-8') as f:
        f.write('\n'.join(z) + '\n')

    # Fuer _build/linkcheck.py: welche Adressen beantwortet der Webserver,
    # obwohl in public/ keine Datei liegt.
    karte = {}
    karte.update({q: zl for q, zl in einfach.items()})
    karte.update(kind_bleibt)
    karte.update(anhang)
    karte.update(geraten)
    karte.update(EXTERN)
    for q, zl in muster:
        karte[q.replace('^', '').replace('(.*?)', '')] = zl.replace('$1', '')
    for g in gone:
        karte[g.rstrip('*')] = '410'
    for b in w.beitraege():
        if b['slug'] not in w.FORT_BEITRAEGE:
            karte['/blog/' + b['slug'] + '/'] = '/' + b['slug'] + '/'
    with open(ZIEL_JSON, 'w', encoding='utf-8') as f:
        json.dump(karte, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')

    print('deploy/redirects.caddy: %d Zeilen' % len(z))
    print('  Adressen mit festem Ziel      %3d' % len(tabelle))
    print('    davon Plugin-Regeln         %3d' % len(einfach))
    print('  Plugin-Regeln, Slug geaendert %3d' % len(muster))
    print('  nackte Unterseiten-Adressen   %3d' % len(kind_bleibt))
    print('  Anhangseiten                  %3d' % len(anhang))
    print('  erratene Adressen             %3d' % len(geraten))
    print('  Ziel auf fremder Seite        %3d' % len(EXTERN))
    print('  410 Gone (Pfadmuster)         %3d' % len(set(gone)))
    print('  verfallene Plugin-Regeln      %3d  (Ziel faellt weg -> 410)'
          % len(verfallen))
    if kollision:
        print('\nnackte Adresse nicht umgeleitet, weil sie schon belegt '
              'ist: %s' % ', '.join(kollision))
    if anhang_ohne:
        print('\nAnhangseite verlinkt, aber kein Medium dazu gefunden: %d'
              % len(anhang_ohne))
        for x in anhang_ohne:
            print('  ' + x)
    return 0


def _pfad(q):
    """Caddy-Pfadmuster aus einer Regel des Plugins."""
    return q.replace('|', '%7C')


if __name__ == '__main__':
    sys.exit(main())
