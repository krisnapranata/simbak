/* Tema Glass: perilaku UI kecil di kerangka base.html (disalin dari casemixiDRG).
 * - Sidebar desktop: mouse masuk -> body.sidebar-expanded (sidebar melebar DAN
 *   konten bergeser ke kanan), mouse keluar -> kelas dilepas. Lebar & geseran
 *   diatur CSS dari kelas itu; :hover di CSS hanya cadangan kalau JS gagal.
 * - Mode PIN:
 *   #sidebarToggle mengganti body.sidebar-pinned dan menyimpannya ke
 *   localStorage 'simrs-sidebar-pinned'. Status awal diterapkan oleh skrip
 *   inline di awal <body> supaya tidak berkedip.
 * - Penanda menu aktif disinkronkan antara sidebar desktop dan offcanvas
 *   mobile: new-base-navigation.js (SPA) hanya menandai link yang diklik.
 * - Kelas body page-dense / page-dashboard diperbarui setelah navigasi SPA.
 * - Ctrl+K / Cmd+K memfokuskan kotak pencarian topbar.
 */
(function () {
    if (window._themeGlassInit) return;
    window._themeGlassInit = true;

    var KUNCI = 'simbak-sidebar-pinned';

    function simpan(pin) {
        try { localStorage.setItem(KUNCI, pin ? '1' : '0'); } catch (e) { /* mode privat */ }
    }

    function tombolPin() {
        var btn = document.getElementById('sidebarToggle');
        if (!btn) return;
        function tandai() {
            btn.setAttribute('aria-pressed', document.body.classList.contains('sidebar-pinned') ? 'true' : 'false');
        }
        tandai();
        btn.addEventListener('click', function () {
            var pin = document.body.classList.toggle('sidebar-pinned');
            simpan(pin);
            tandai();
        });
    }

    function hoverSidebar() {
        var aside = document.getElementById('sidebar');
        if (!aside) return;
        var body = document.body;
        var diAtas = false;
        function fokusKeyboard() {
            var el = document.activeElement;
            try { return !!(el && aside.contains(el) && el.matches(':focus-visible')); } catch (e) { return false; }
        }
        function buka() { body.classList.add('sidebar-expanded'); }
        function tutup() { if (!diAtas && !fokusKeyboard()) body.classList.remove('sidebar-expanded'); }
        aside.addEventListener('mouseenter', function () { diAtas = true; buka(); });
        aside.addEventListener('mouseleave', function () { diAtas = false; tutup(); });
        // hanya fokus KEYBOARD (Tab) yang menahan sidebar tetap lebar; fokus
        // sisa klik mouse tidak, supaya sidebar mengecil saat mouse ke konten.
        aside.addEventListener('focusin', function () { if (fokusKeyboard()) buka(); });
        aside.addEventListener('focusout', function () { setTimeout(tutup, 0); });
    }

    /* Navigasi SPA (new-base-navigation.js) hanya mengganti isi #workspace,
     * jadi kelas body dari halaman PERTAMA tertinggal: login -> Dashboard
     * (page-dashboard, bulatan terang) lalu klik Ranap = Ranap ikut terang.
     * Kelas dihitung ulang dari isi #workspace setiap kali isinya diganti. */
    function kelasHalaman() {
        var ws = document.getElementById('workspace');
        if (!ws || typeof MutationObserver === 'undefined') return;
        var body = document.body;
        function terapkan() {
            var dash = !!ws.querySelector('.dash-bento');
            body.classList.toggle('page-dashboard', dash);
            body.classList.toggle('page-dense', !dash);
        }
        new MutationObserver(function (daftar) {
            for (var i = 0; i < daftar.length; i++) {
                if (daftar[i].target === ws) { terapkan(); return; }
            }
        }).observe(ws, { childList: true });
    }

    function sinkronAktif() {
        document.addEventListener('click', function (e) {
            var link = e.target.closest('.spa-link');
            if (!link) return;
            var href = link.getAttribute('href');
            if (!href || href === '#') return;
            document.querySelectorAll('.sidebar-link.spa-link').forEach(function (l) {
                l.classList.toggle('active', l.getAttribute('href') === href);
            });
            var diPenunjang = !!link.closest('.sidebar-submenu');
            document.querySelectorAll('.sidebar-dropdown-toggle').forEach(function (t) {
                t.classList.toggle('child-active', diPenunjang);
            });
        });
    }

    function pintasanCari() {
        document.addEventListener('keydown', function (e) {
            if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
                var inp = document.getElementById('topbarSearch');
                if (!inp || !inp.offsetParent) return;
                e.preventDefault();
                inp.focus();
            }
        });
    }

    /* Pil "sorot" yang meluncur ke menu di bawah mouse (CSS: .sb-sorot di
       theme-glass.css bagian 3). Satu pil per <nav class="sidebar-nav">.
       Posisi dihitung ulang lewat ResizeObserver: sidebar melebar 76->240px
       dan submenu buka/tutup mengubah ukuran/letak link SESUDAH mouse diam. */
    function sorotSidebar() {
        document.querySelectorAll('.sidebar .sidebar-nav').forEach(function (nav) {
            if (nav.querySelector('.sb-sorot')) return;
            var pil = document.createElement('span');
            pil.className = 'sb-sorot';
            pil.setAttribute('aria-hidden', 'true');
            nav.insertBefore(pil, nav.firstChild);
            nav.classList.add('sb-sorot-on');
            var kini = null;

            function letakkan() {
                if (!kini || !kini.offsetParent) { pil.classList.remove('tampil'); return; }
                var n = nav.getBoundingClientRect();
                var r = kini.getBoundingClientRect();
                pil.style.transform = 'translate(' + (r.left - n.left) + 'px,' + (r.top - n.top) + 'px)';
                pil.style.width = r.width + 'px';
                pil.style.height = r.height + 'px';
            }
            nav.addEventListener('mouseover', function (e) {
                var link = e.target.closest('.sidebar-link');
                if (!link || !nav.contains(link) || link === kini) return;
                var baru = !pil.classList.contains('tampil');
                kini = link;
                if (baru) {
                    /* muncul pertama kali: langsung di tempat, tanpa meluncur dari atas */
                    pil.style.transition = 'none';
                    letakkan();
                    void pil.offsetWidth;
                    pil.style.transition = '';
                } else {
                    letakkan();
                }
                pil.classList.add('tampil');
                pil.classList.remove('kilau');
                void pil.offsetWidth;
                pil.classList.add('kilau');
            });
            nav.addEventListener('mouseleave', function () {
                kini = null;
                pil.classList.remove('tampil');
            });
            if (window.ResizeObserver) new ResizeObserver(letakkan).observe(nav);
        });
    }

    function mulai() {
        tombolPin();
        hoverSidebar();
        sorotSidebar();
        kelasHalaman();
        sinkronAktif();
        pintasanCari();
    }

    if (document.readyState !== 'loading') {
        mulai();
    } else {
        document.addEventListener('DOMContentLoaded', mulai);
    }
})();
