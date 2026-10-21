/* Suche unter /suche/.
 *
 * Die WordPress-Suche lief auf dem Server (/?s=...). Hier sucht der
 * Browser: Pagefind legt beim Bauen einen Index neben die Seite und laedt
 * davon nur die Teile, die zur Eingabe passen.
 *
 * Die Beschriftungen stehen hier und nicht in einer Sprachdatei, weil es
 * genau diese eine Oberflaeche ist.
 */
const { PagefindUI } = await import('/pagefind/pagefind-ui.js');

new PagefindUI({
	element: '#suche',
	showSubResults: true,
	showImages: false,
	pageSize: 10,
	translations: {
		placeholder: 'Suchbegriff',
		clear_search: 'Leeren',
		load_more: 'Weitere Ergebnisse',
		search_label: 'Diese Seite durchsuchen',
		filters_label: 'Filter',
		zero_results: 'Keine Treffer für [SEARCH_TERM]',
		many_results: '[COUNT] Treffer für [SEARCH_TERM]',
		one_result: 'Ein Treffer für [SEARCH_TERM]',
		alt_search:
			'Keine Treffer für [SEARCH_TERM]. Stattdessen Ergebnisse für [DIFFERENT_TERM]',
		search_suggestion:
			'Keine Treffer für [SEARCH_TERM]. Versuche einen dieser Begriffe:',
		searching: 'Suche nach [SEARCH_TERM] …',
	},
});

/* Mit einem Begriff in der Adresse direkt suchen - so fuehrt das Suchfeld
   in der Seitenleiste jeder Seite hierher. Dieselbe Mechanik faengt auch
   die alte WordPress-Form /?s=... ab, die der Webserver hierher
   weiterleitet. */
const begriff = new URLSearchParams(location.search).get('q');
if (begriff) {
	const feld = document.querySelector('#suche input[type="text"]');
	if (feld) {
		feld.value = begriff;
		feld.dispatchEvent(new Event('input', { bubbles: true }));
	}
}
