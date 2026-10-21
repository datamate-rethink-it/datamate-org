# datamate.org – statische Seite mit Hugo

Ersetzt die WordPress-Installation von datamate.org vollständig. Nach dem
Umstieg kann das WordPress abgeschaltet werden.

Stand: 21.10.2026 · Hugo 0.168.0 (extended) · Pagefind 1.4.0 · Quellen:
`datamate-org.tar.gz` (der Dateibestand der Installation) und die
WordPress-REST-API der laufenden Seite.

Vorbild ist [ionas-com](https://github.com/datamate-rethink-it/ionas-com),
das im selben Muster gebaut ist. Übertragen wurde das Vorgehen und die
Auslieferung; die Werkzeuge in `_build/` sind neu geschrieben, weil sie an
den Inhalten hängen.

---

## Die Prüfungen

Vier Prüfungen laufen bei jedem Push in GitHub Actions. Sie sind so
zugeschnitten, dass sie normale Pflege überleben – ein Test, der bei
richtigem Verhalten Alarm schlägt, erzieht dazu, Alarme zu ignorieren.

```
$ python3 -E -s _build/verify.py
Seitenrumpf identisch: 168   abweichend: 0   fehlend: 0  (von 169, 1 bewusst nicht verglichen)
Titel, Description, Canonical, Robots unveraendert: 676 von 676

$ python3 -E -s _build/verify_blog.py
Inhaltsdateien: 190   gebaute Seiten: 210   Blaetterseiten: 20
  ohne Titel 0   ohne Canonical 0   ohne Robots 0   Canonical zeigt woanders 0
  og:image ohne Ziel: 0
Blog-Uebersicht: 136 Beitraege auf 14 Seiten
Kategoriearchive: 136 Beitraege erreichbar
Feed: 20 Eintraege   Sitemaps: post 136, page 33, category 20, Index 3
alles in Ordnung

$ python3 -E -s _build/linkcheck.py
232 Seiten, 10575 seiteninterne Verweise
  schon vorher kaputt:      5
  NEU kaputt:               0

$ docker run ... caddy validate ...
Valid configuration
```

**`verify.py`** vergleicht den *Seitenrumpf* – alles zwischen `</header>`
und `<footer id="footer">` – Zeichen für Zeichen mit dem Referenz-Render
des alten Stands in `_build/reference/`. Vor dem Vergleich laufen auf den
Schnappschuss dieselben Regeln, die auch der Generator angewandt hat
(`ERSETZUNGEN` und `HANDAENDERUNGEN` in `_build/wpdata.py`). Jede
Abweichung, die danach bleibt, ist ein Fehler. Aus dem Kopf werden Titel,
Beschreibung, Canonical und die Robots-Angabe geprüft: die stehen so in
Suchergebnissen und dürfen sich nicht ändern.

Kopf- und Fußleiste sind bewusst **nicht** Teil des Vergleichs. Sie
entwickeln sich weiter – der entfallene Menüpunkt 3CX, Font Awesome aus
dem eigenen Dateibestand, das Suchfeld, das jetzt auf `/suche/` führt.
Jede dieser Änderungen hätte sonst einen Eintrag in einer Ausnahmeliste
gebraucht, bis „identisch" nichts mehr bedeutet.

**`verify_blog.py`** prüft schnappschussfrei, was unabhängig vom Inhalt
gelten muss: dass jede Inhaltsdatei zu einer Seite wird, jede Seite Titel,
Canonical und Robots-Angabe trägt, der Canonical auf die eigene Adresse
zeigt, jedes `og:image` auf eine ausgelieferte Datei zeigt, jeder Beitrag
genau einmal in der Blog-Übersicht und mindestens einmal in einem
Kategoriearchiv erscheint, und Feed und Sitemaps vollständig sind. Diese
Prüfung begleitet den Betrieb; ein Byte-Vergleich wäre dort ein
Fehlalarmgenerator, sobald jemand einen Artikel schreibt.

**`linkcheck.py`** prüft alle seiteninternen Verweise gegen das, was
ausgeliefert wird – und gegen `_build/weiterleitungen.json`, damit ein
Verweis, den der Webserver umleitet, nicht als kaputt gilt. Die fünf
Verweise unter „schon vorher kaputt" zeigten auch im WordPress ins Leere;
sie stehen mit Begründung in `BEKANNT_KAPUTT`, damit „NEU kaputt: 0" eine
Aussage ist und nicht erst nachgesehen werden muss.

**Die Caddy-Prüfung** adaptiert `deploy/Caddyfile.container` samt der
erzeugten `deploy/redirects.caddy`. Dazu prüft der Workflow, dass
`redirects.caddy` zum Stand der Inhalte passt – sonst zeigen Regeln auf
Adressen, die es nicht mehr gibt, oder es fehlen welche.

## Struktur

```
hugo.toml                   Konfiguration (kommentiert)
content/                    192 Inhaltsdateien – nur Inhalt, kein Layout
  _index.html               Startseite
  <slug>.html               9 einfache Seiten (Impressum, Buddy, Presse, …)
  seafile/_index.html       /seafile/ und 16 Unterseiten
  dropbox-alternative/      /dropbox-alternative/ und 4 Unterseiten
  software/lizenzbedingungen.html
  blog/_index.html          Blog-Übersicht (nur Kopfangaben)
  blog/<slug>.html          136 Beiträge, Adresse ist /<slug>/
  category/<pfad>/_index.html  20 Kategoriearchive
  suche.html                Suchseite
layouts/                    Kopf, Fußleiste, Beitrag, Listen, Feed, Sitemaps
  baseof.html  page.html  home.html  section.html  404.html
  blog/page.html            einzelner Beitrag
  blog/section.html         Blog-Übersicht mit Blättern
  kategorie/section.html    Kategoriearchiv
  suche/page.html           Suchseite
  home.feed.xml             RSS unter /feed/
  home.yoast*.xml           die vier Sitemaps von Yoast SEO
  _partials/                kopf, site-header, site-footer, seitenleiste,
                            beitragsliste, blaettern, autorenbox, jsonld,
                            datum, urlset
data/
  kategorien.json           Kategoriebaum (im WordPress in der Datenbank)
  kategoriennamen.json      Slug → Name, für das JSON-LD
  autoren.json              Name, Beschreibung, Personen-Kennung
webroot/                    969 übernommene Dateien, 100 MB. Wird von
                            _build/gen_static.py erzeugt – nichts
                            hineinlegen, was man behalten will.
webroot-eigen/              selbst geschrieben: robots.txt, lightbox.js,
                            lightbox.css, suche.js, Font Awesome 5.0.9
deploy/                     Caddyfile, erzeugte redirects.caddy,
                            nginx-vhost, docker-compose
_build/                     Migrations- und Prüfwerkzeug, nicht Teil des Baus
```

## Bauen

```bash
hugo --gc                      # nach public/
npx pagefind --site public     # Suchindex für /suche/
```

Hugo und Pagefind werden nicht lokal gebraucht – der Container lädt beide
als Binärdatei (siehe `Dockerfile`). Für die Arbeit am Repo:

```bash
curl -fsSL https://github.com/gohugoio/hugo/releases/download/v0.168.0/hugo_extended_0.168.0_linux-amd64.tar.gz \
  | tar -C ~/.local/bin -xz hugo
curl -fsSL https://github.com/CloudCannon/pagefind/releases/download/v1.4.0/pagefind-v1.4.0-x86_64-unknown-linux-musl.tar.gz \
  | tar -C ~/.local/bin -xz
```

Container bauen und ansehen:

```bash
docker build -t datamate-org:dev .
docker run --rm -p 127.0.0.1:8099:80 datamate-org:dev
```

## Ausliefern

Image `ghcr.io/datamate-rethink-it/datamate-org:<datum>` (Caddy mit dem
gebauten HTML), davor das nativ installierte nginx des Servers. Der
Container hört auf `127.0.0.1:8082`; ionas.com liegt auf 8081.

Die **Ausliefer-Regeln stecken im Image**, nicht im Server-vhost: die
Weiterleitungen, die 410er, der Feed, `try_files`, 404. So sind sie mit dem
Inhalt zusammen versioniert, und ein Rückschritt auf eine ältere Fassung
nimmt die Regeln mit. Das war der Grund für den Container statt rsync.

```bash
git tag 2026-10-21 && git push --tags       # GitHub Actions baut und pusht
ssh server
cd /opt/datamate.org
sed -i 's/^DATAMATE_VERSION=.*/DATAMATE_VERSION=2026-10-21/' .env
docker compose pull && docker compose up -d
```

Beim ersten Mal: `deploy/docker-compose.yml` nach
`/opt/datamate.org/docker-compose.yml`, `deploy/nginx-vhost.conf` in die
nginx-Konfiguration, Zertifikatspfade prüfen.

## Was sich gegenüber dem WordPress ändert

| bisher | jetzt |
| --- | --- |
| WordPress 6.1.15, 18 Plugins, PHP | statisches HTML hinter Caddy |
| WordPress-Suche (`/?s=…`) | Pagefind unter `/suche/`, Index aus 169 Seiten. Das Suchfeld in der Seitenleiste führt dorthin, `/?s=…` wird umgeleitet |
| Blog-Übersicht zeigte 70 von 137 Beiträgen | alle 136 Beiträge auf 14 Seiten (siehe unten) |
| Kategoriearchive ohne Blätter-Verweise | `/category/<pfad>/page/2/` ist verlinkt |
| Simple Lightbox: 7 JavaScript-Dateien plus eine zweite Kopie von jQuery | `eigen/js/lightbox.js`, 100 Zeilen ohne jQuery, auf 44 Beiträgen |
| Font Awesome von `use.fontawesome.com` | dieselbe Datei aus dem eigenen Bestand. Der Integritäts-Hash, den die alte Seite angab, stimmt mit der heruntergeladenen Datei überein |
| `block-library/style.min.css`, 70 KB auf jeder Seite | weg – kein Inhalt benutzt eine `wp-block`-Klasse |
| `wp-emoji-release.min.js`, 14 KB, ersetzte Emoji durch Bilder von `s.w.org` | weg |
| IE-Weiche auf `css3-mediaqueries-js.googlecode.com` | weg, die Domain ist seit Jahren abgeschaltet |
| wp-statistics, Cookie-Hinweis | weg, kein Tracking. Zahlen kommen aus der Search Console |
| Gravity Forms installiert | weg – auf keiner der 60 Seiten eingebunden |
| OIDC-, SAML- und miniOrange-Login installiert | weg – kein geschützter Bereich auf der Seite |
| `/blog/page/8/` bis `/blog/page/15/` lieferten eine leere Seite mit Status 200 | `/blog/page/8/` bis `/blog/page/14/` haben Inhalt, `/blog/page/15/` liefert 404 |
| `/seafile/seamate/` lieferte HTTP 500 | 410 Gone, der Bereich ist eingestellt |
| 14 422 Dateien, 1,9 GB | 969 Dateien, 100 MB. Image 306 MB, davon 92 MB Bilder in einer eigenen Schicht |

### Der Fehler in der Blog-Übersicht

`blog-page.php` setzte in derselben Abfrage `paged` **und** `offset`:

```php
$count  = get_option('posts_per_page', 10);   // Einstellung der Seite: 20
$offset = ($paged - 1) * $count;              // Schrittweite 20

$args = array('posts_per_page' => 10, 'paged' => $paged, 'offset' => $offset);
```

Zehn angezeigte Beiträge bei einer Schrittweite von zwanzig: die Übersicht
zeigte jeden zweiten Zehnerblock und übersprang den anderen. **67 der 137
Beiträge waren über `/blog/` nie erreichbar**, nur über die Kategorien, die
Suche und die Sitemap. Zugleich hielt WordPress 14 Blätterseiten für
richtig und lieferte für die Seiten 8 bis 15 eine leere Seite mit Status
200 aus, mit einem Verweis auf die jeweils nächste.

Hier erscheinen alle Beiträge, zehn je Seite, auf 14 Seiten. Die Adressen
`/blog/page/2/` bis `/blog/page/7/` bleiben gültig, zeigen aber andere
Beiträge als vorher – die alte Aufteilung war kein Gestaltungswille.

## Was wegfällt

Entscheidung vom 21.10.2026. Alle diese Adressen antworten mit **410
Gone** und nicht mit 404: 410 sagt einer Suchmaschine, dass die Adresse
absichtlich weg ist, und räumt sie schneller aus dem Index.

| Bereich | Adressen | Grund |
| --- | --- | --- |
| `/hero/*` | 14 | VirtualHero, Stand 2017: Windows 7/8, Ubuntu 16.04/17.04, Avira- und Kaspersky-Rescue |
| `/hilfe/*` | 6 | Hilfe-Bereich, Stand 2019–2020 |
| `/voip/`, `/3cx/`, `/goldenrosskaserne/` | 3 | Telefonie eingestellt, siehe `/systemwerk/` |
| `/odoo/`, `/consulting/`, `/roadmap/` | 3 | eingestellt bzw. Roadmap von 2018 |
| `/seafile/seamate/`, `/seamate/` | 2 | PHP-Generator für Seafile-CSS, lieferte live schon HTTP 500 |
| `/downloads/firmware/*`, `/downloads/manuals/*` | 87 Dateien | Firmware und Handbücher für VoIP-Telefone (Snom, Yealink, Gigaset, Grandstream), 1,4 GB |
| `/manuals/*`, `/firmware/*` | – | alte Pfade derselben Dateien, zwei Plugin-Regeln |
| `/voip-ip-telefone-firmware-handbuecher-und-standard-passwoerter/` | 1 Beitrag | hing mit 93 Verweisen vollständig an diesen Dateien |
| `seafcss/*.css` | ~90 Dateien | Vorlagen des SeaMate-Generators |
| nackte Adressen der entfallenen Unterseiten | 15 | `/windows10/`, `/benutzer/`, `/clonezilla/` … |

Die Beiträge zu eingestellten Produktlinien **bleiben** – ein Blog ist ein
Archiv mit Datum, keine Verkaufsseite. Verweise aus den Texten auf
gelöschte Seiten sind aufgelöst: der Linktext steht noch da, der Verweis
ist weg (33 Stellen).

`/buddy/`, `/homie/`, `/fellow/` und `/presse/` bleiben.

## Die Weiterleitungen

`deploy/redirects.caddy` ist **erzeugt** – von `_build/gen_redirects.py`,
nicht von Hand. Die alte Installation hat auf vier Wegen weitergeleitet,
und nur einer davon war aufgeschrieben:

1. **Das Plugin *Redirection*** mit 24 gepflegten Regeln. Der Export liegt
   als `_build/redirects-redirection-export.csv` im Repo. Neun davon
   zeigten auf Firmware, Handbücher oder das 3CX-Bestellformular und
   antworten jetzt mit 410.
2. **WordPress selbst** leitete jede Unterseite von ihrer nackten Adresse
   auf den vollen Pfad: `/architektur/` → `/seafile/architektur/`. Das
   stand nirgends geschrieben und fällt erst auf, wenn es fehlt – 21
   Adressen.
3. **Ebenso `/blog/<slug>/` → `/<slug>/`** für jeden Beitrag. Die Beiträge
   lagen vor einem Umbau unter `/blog/` und werden so noch verlinkt. Dazu
   die Bilder: `/blog/wp-content/uploads/…` steht mit 23 458 Aufrufen im
   Zähler des Plugins.
4. **Yoast SEO** leitete die Anhangseiten eines Beitrags –
   `/<beitrag>/<bild>/` – auf die Bilddatei um. 20 solche Adressen sind aus
   den Texten verlinkt.

Dazu kommt, was WordPress aus einem Teil des Slugs **erraten** hat
(`redirect_guess_404_permalink`): `/openproject` →
`/openproject-6-0-…`, `/datenschutz` → `/datenschutzerklaerung/`. Erraten
lässt sich das nicht nachbauen; aufgenommen sind die fünf Adressen, die
aus den Inhalten heraus verlinkt sind.

**Gelernt:** Die `redir`-Zeilen brauchen den Matcher `*`. Ohne ihn liest
Caddy das Ziel, weil es mit `/` beginnt, als Pfadmuster – und leitet
stillschweigend nicht um, sondern antwortet mit einer leeren 200. Und die
410er-Muster müssen zwischen `/hero` `/hero/*` (Bereich samt allem
darunter) und `/windows` `/windows/` (genau diese Adresse) unterscheiden:
ein einziges `/windows*` fing auch
`/windows-benutzerpasswort-vergessen-hero-eilt-zur-hilfe/` ein. Zehn
Beiträge waren betroffen, bevor der Abgleich gegen den Container es zeigte.

## Von Hand geänderte Inhalte

Fünf Stellen, an denen der übernommene Text nicht mehr stimmte. Jede steht
mit Begründung in `HANDAENDERUNGEN` in `_build/wpdata.py`; `verify.py`
wendet sie auf den Schnappschuss an, bevor verglichen wird. Was dort nicht
steht, ist ein Fehler.

| Adresse | Änderung |
| --- | --- |
| `/` | Produktkasten Hero entfernt. Stand schon im WordPress in einem HTML-Kommentar, war also unsichtbar |
| `/buddy/` | Hero-Spalte in „Ergänzungen zu Buddy" entfernt; die Reihe zeigt zwei statt drei Spalten |
| `/seafile/` | Der Absatz versprach den SeaMate-Generator und verwies auf ihn. Er nennt jetzt nur noch, was bleibt, und verweist auf `/seafile/customizing/` |
| `/seafile/customizing/` | Schreibfehler im Verweis (`seafile_client_plattformen`), lieferte schon im WordPress 404 |
| `/deutsche-seafile-webseite-veroeffentlicht/` | Verweis ohne Schema (`href="www.seafile.com"`), zeigte unter die eigene Adresse |
| `/teil-4-synchronisation-mit-sabredav/` | Tippfehler im Bildpfad (`h/wp-content/…`), das Bild fehlte schon im WordPress |
| `/autoprovisionierung-von-ip-telefonen-mit-factory-reset/` | Tippfehler im Verweis (`sonst-wir` statt `sonst-wird`) |

Dazu eine mechanische Regel auf allen Seiten: `/static/images/icons/widget-link.png`
→ `/wp-content/themes/datamate-theme/images/icons/widget-link.png`. Das
Canvas-Template legte seine Dateien unter `/static/` ab, im Theme liegen
sie unter `images/`. Der Verweis blieb stehen und lieferte auf acht Seiten
404 – die Datei ist da, nur anderswo.

## Verweise, die schon vorher ins Leere zeigten

Alle fünf am 21.10.2026 an der laufenden Seite nachgeprüft. Sie bleiben
unverändert im Text und stehen in `BEKANNT_KAPUTT` in
`_build/linkcheck.py`:

| Verweis | aus | Lage |
| --- | --- | --- |
| `/blog/seafile-professional-server-6-3` | `/multi-tenancy-in-seafile/` | Beitrag existiert nicht (mehr) |
| `/gigawiki/download/attachments/7405655/rtaImage.jpg` | `/autoprovisionierung-von-ip-telefonen-mit-factory-reset/` | Verweis ohne Hostnamen. Dasselbe Bild steht im selben Beitrag ein zweites Mal, dort vollständig |
| `/shop/small-business` | `/odoo-crm-mit-der-voip-telefonanlage-verbinden/` | Pfad des abgeschalteten Shops |
| `/sso-seafile-keycloak/` | `/mehrere-gruende-warum-it-profis-auf-die-cloud-setzen-sollten/` | Beitrag existiert nicht |
| `/teamviewerDL/` | `/fellow/` | Gemeint war vermutlich `https://get.teamviewer.com/datamate`, das in der Fußleiste steht |

Dazu zwei Bilder, die in keiner Fassung des Themes existieren:
`/static/images/parallax/2.jpg` und
`/wp-content/themes/datamate-theme/images/parallax/parallax-bg.jpg`.

## Noch offen

* **`shop.datamate.org` ist abgeschaltet.** Alle Verweise darauf sind
  entfernt (10 Stellen, davon 7 schon im WordPress auskommentiert).
  Ob die Subdomain selbst noch DNS-Einträge hat, ist nicht geprüft.
* **Der Text auf `/buddy/` wirbt für die ionas-Support-Hotline** („IT-Support
  an 365 Tagen im Jahr"). Die Hotline ist seit dem 01.04.2020 eingestellt –
  so steht es auf `ionas.com/preise`. Der Text ist unverändert übernommen;
  eine Änderung ist eine inhaltliche Entscheidung.
* **`/presse/`** verweist auf Pressestimmen von 2018 und früher.
* **Schlagwortseiten** (`/tag/<slug>/`) sind nicht gebaut. Sie waren von
  keiner Seite verlinkt, standen in keiner Sitemap und hatten keine
  eigene Sitemap bei Yoast. Die Begriffe selbst stehen weiter im JSON-LD
  der 66 Beiträge, die welche haben.
* **Die Startseite liefert `canonical` ohne Schrägstrich**
  (`https://www.datamate.org`). Das war im WordPress so und ist
  unverändert übernommen.

## Neu aufsetzen

`_build/wporig/` – der entpackte WordPress-Dateibestand – ist nicht im
Repo: 533 MB, und darin steckt `wp-config.php` mit den
Datenbank-Zugangsdaten. Gebraucht wird er nur von
`_build/gen_static.py`. Aus dem Archiv:

```bash
mkdir -p _build/wporig
tar xzf datamate-org.tar.gz -C _build/wporig \
  --exclude='wordpress/wp-admin' --exclude='wordpress/wp-includes/[a-z]*' \
  --exclude='wordpress/wp-content/languages' \
  --exclude='wordpress/wp-content/upgrade' \
  --exclude='wordpress/wp-content/cache' \
  --exclude='wordpress/wp-content/aiowps_backups' \
  --exclude='wordpress/downloads/firmware' \
  --exclude='wordpress/downloads/manuals' \
  --exclude='wordpress/seafcss'
```

Die Werkzeuge in `_build/`, in der Reihenfolge, in der sie liefen:

| Skript | tut |
| --- | --- |
| `snapshot.sh` | ruft die 245 Adressen aus `urls.txt` an der laufenden Seite ab und legt sie in `reference/` – **die Grundlage jeder späteren Aussage „nichts verloren"** |
| `wpdata.py` | gemeinsame Grundlage: Umfang, Ersetzungen, Handänderungen, Zerlegen der Schnappschüsse |
| `gen_content.py` | erzeugt `content/` und `data/`. Einmal gelaufen; ein zweiter Lauf überschreibt Handänderungen und braucht `--force` |
| `gen_static.py` | erzeugt `webroot/` aus den tatsächlichen Verweisen der **gebauten** Seite |
| `gen_redirects.py` | erzeugt `deploy/redirects.caddy` und `weiterleitungen.json` |
| `verify.py`, `verify_blog.py`, `linkcheck.py` | die Prüfungen |

`_build/wp/` ist die letzte maschinenlesbare Kopie der WordPress-Daten:
Seiten, Beiträge, Kategorien, Schlagwörter, Autoren, Medien – **nicht
wegwerfen.** `_build/reference/` ebenso.

### Zwei Fallen der REST-API

* **`content` und `excerpt` abzufragen liefert kein JSON.** Die Antwort
  beginnt mit gerendertem HTML – irgendetwas in Theme oder Plugins gibt
  beim Rendern direkt aus. Alle Abfragen in `_build/wp/` benutzen deshalb
  `_fields=` ohne diese beiden Felder. Der Artikeltext kommt aus den
  gerenderten Seiten.
* **Nur die gerenderte Seite enthält die `<!--more-->`-Marke** als
  `<span id="more-NNN">`, an der WordPress den Teaser abschneidet. Die API
  verschluckt sie. Von 136 Beiträgen hat genau einer (`/systemwerk/`)
  keine Marke; dort ist der Teaser der erste Absatz.

## Als Vorlage für den nächsten Umzug

Was sich gegenüber [ionas-com](https://github.com/datamate-rethink-it/ionas-com)
als zusätzlich übertragbar erwiesen hat:

* **Weiterleitungen aus allen vier Quellen suchen, nicht nur aus dem
  Plugin.** Die 24 gepflegten Regeln waren ein Drittel der Wahrheit. Die
  nackten Unterseiten-Adressen, `/blog/<slug>/` und die Anhangseiten hat
  WordPress selbst erzeugt, ohne dass es irgendwo aufgeschrieben stand.
  Gefunden wurden sie, indem die Verweise der gebauten Seite gegen das
  Ausgelieferte geprüft und jeder Treffer an der laufenden Seite
  nachgesehen wurde.
* **Statuscodes des Containers gegen die der laufenden Seite abgleichen**,
  für jede Adresse des Schnappschusses. Dieser Abgleich hat die zehn
  Beiträge gefunden, die ein zu weites 410-Muster eingefangen hatte – der
  Linkcheck konnte es nicht sehen, weil die Verweise auf die Beiträge
  korrekt waren.
* **Alte Templates lesen, nicht nur ihre Ausgabe.** Der Fehler in der
  Blog-Übersicht war in der Ausgabe nicht zu sehen; erst `blog-page.php`
  erklärte, warum 70 statt 137 Beiträge erschienen.
* **Hugos Vorlagenmotor entfernt HTML-Kommentare** aus Layouts
  (`html/template` tut das). Ein Vergleich, der einen Kommentar als Marke
  benutzt, geht daran kaputt.
