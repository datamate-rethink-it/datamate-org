/* Bildergalerie fuer die Beitragsbilder.
 *
 * Ersetzt das WordPress-Plugin Simple Lightbox. Dessen Auslieferung
 * bestand aus sieben JavaScript-Dateien und einer zweiten Kopie von
 * jQuery; die Markierungen im Inhalt - data-slb-active und data-slb-group -
 * bleiben unveraendert, damit die Inhalte nicht angefasst werden muessen.
 *
 * Ohne JavaScript bleibt jedes Bild ein Verweis auf die grosse Fassung.
 */
(function () {
	'use strict';
	var verweise = Array.prototype.slice.call(
		document.querySelectorAll('a[data-slb-active] > img')
	).map(function (bild) { return bild.parentNode; });
	if (!verweise.length) return;

	var huelle, bild, beschriftung, aktuell = 0, gruppe = [];

	function baue() {
		huelle = document.createElement('div');
		huelle.className = 'dm-lightbox';
		huelle.setAttribute('role', 'dialog');
		huelle.setAttribute('aria-modal', 'true');
		huelle.innerHTML =
			'<button class="dm-lb-zu" aria-label="Schließen">&times;</button>' +
			'<button class="dm-lb-zurueck" aria-label="Vorheriges Bild">&#10094;</button>' +
			'<figure><img alt=""><figcaption></figcaption></figure>' +
			'<button class="dm-lb-vor" aria-label="Nächstes Bild">&#10095;</button>';
		document.body.appendChild(huelle);
		bild = huelle.querySelector('img');
		beschriftung = huelle.querySelector('figcaption');
		huelle.querySelector('.dm-lb-zu').onclick = zu;
		huelle.querySelector('.dm-lb-zurueck').onclick = function (e) {
			e.stopPropagation(); blaettern(-1);
		};
		huelle.querySelector('.dm-lb-vor').onclick = function (e) {
			e.stopPropagation(); blaettern(1);
		};
		huelle.onclick = function (e) { if (e.target === huelle) zu(); };
	}

	function zeige(i) {
		aktuell = (i + gruppe.length) % gruppe.length;
		var a = gruppe[aktuell];
		bild.src = a.getAttribute('href');
		var alt = a.querySelector('img').getAttribute('alt') || '';
		bild.alt = alt;
		beschriftung.textContent = alt;
		huelle.classList.toggle('dm-lb-einzeln', gruppe.length < 2);
	}

	function blaettern(n) { zeige(aktuell + n); }

	function zu() {
		huelle.classList.remove('dm-lb-offen');
		document.documentElement.style.overflow = '';
	}

	function auf(a) {
		if (!huelle) baue();
		var g = a.getAttribute('data-slb-group');
		gruppe = g
			? verweise.filter(function (x) {
					return x.getAttribute('data-slb-group') === g;
			  })
			: [a];
		zeige(gruppe.indexOf(a));
		huelle.classList.add('dm-lb-offen');
		document.documentElement.style.overflow = 'hidden';
		huelle.querySelector('.dm-lb-zu').focus();
	}

	verweise.forEach(function (a) {
		a.addEventListener('click', function (e) {
			if (e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
			e.preventDefault();
			auf(a);
		});
	});

	document.addEventListener('keydown', function (e) {
		if (!huelle || !huelle.classList.contains('dm-lb-offen')) return;
		if (e.key === 'Escape') zu();
		if (e.key === 'ArrowLeft') blaettern(-1);
		if (e.key === 'ArrowRight') blaettern(1);
	});
})();
