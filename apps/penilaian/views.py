import io

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView

from apps.akun.permissions import bisa_lihat_semua_bab
from apps.dokumen.models import BuktiEP, StatusDokumen
from apps.dokumen.permissions import bisa_buat_dokumen, queryset_dokumen_untuk
from apps.inti.models import PengaturanSistem
from apps.inti.views import IzinMixin
from apps.pps.permissions import queryset_pps_untuk
from apps.standar.models import ElemenPenilaian, JenisBukti, Standar
from apps.standar.permissions import queryset_bab_untuk

from . import capaian, laporan, services
from . import target as target_svc
from .forms import FormPeriode, FormTarget, FormTargetBanyak
from .models import CatatanPenilaian, PenilaianEP, PeriodeAkreditasi, SkorEP, TargetPokja
from .permissions import (
    bisa_beri_catatan,
    bisa_kelola_periode,
    bisa_kelola_target,
    bisa_nilai_bab,
    queryset_target_untuk,
)
from .tugas import langkah_persiapan, tugas_untuk


def pilih_periode(request) -> PeriodeAkreditasi | None:
    """Periode dari ?periode=, atau periode aktif."""
    pk = request.GET.get("periode")
    if pk and pk.isdigit():
        periode = PeriodeAkreditasi.objects.filter(pk=pk).first()
        if periode:
            return periode
    return services.periode_aktif()


class PeriodeMixin:
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["periode"] = self.periode
        ctx["daftar_periode"] = PeriodeAkreditasi.objects.all()
        return ctx

    def dispatch(self, request, *args, **kwargs):
        self.periode = pilih_periode(request)
        return super().dispatch(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class DashboardView(PeriodeMixin, TemplateView):
    template_name = "penilaian/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        baris = capaian.capaian_per_bab(periode=self.periode, bab_qs=queryset_bab_untuk(user))
        ctx.update(
            baris_bab=baris,
            per_pokja=capaian.capaian_per_pokja(baris),
            total=capaian.total(baris),
        )
        if bisa_lihat_semua_bab(user):
            ctx["predikat"], ctx["predikat_diatur"] = capaian.evaluasi_predikat(baris)
            ctx["tampilkan_predikat"] = True

        dok_qs = queryset_dokumen_untuk(user)
        jumlah = dict(dok_qs.values_list("status").annotate(n=Count("id")))
        ctx["status_dokumen"] = [(s.label, s.value, jumlah.get(s.value, 0)) for s in StatusDokumen]

        jatuh_tempo = capaian.dokumen_jatuh_tempo(
            dok_qs, maks_hari=max(PengaturanSistem.ambil().daftar_hari_pengingat or [90])
        )
        ctx["jatuh_tempo"] = jatuh_tempo
        ctx["ringkas_jatuh_tempo"] = [
            (h, sum(1 for d in jatuh_tempo if d.sisa_hari <= h))
            for h in sorted(PengaturanSistem.ambil().daftar_hari_pengingat)
        ]

        ep_qs = capaian.ep_aktif([b.pk for b, _ in baris])
        tanpa_bukti = capaian.ep_tanpa_bukti(ep_qs).select_related("standar__bab")
        ctx["jumlah_ep_tanpa_bukti"] = tanpa_bukti.count()
        ctx["ep_tanpa_bukti"] = tanpa_bukti.order_by("standar__bab__kode", "standar__urutan")[:15]
        usang = capaian.bukti_pelaksanaan_usang(dok_qs, periode=self.periode)
        ctx["jumlah_bukti_usang"] = usang.count()
        ctx["bukti_usang"] = usang.select_related("pokja")[:15]
        ctx["batas_usia_bukti"] = PengaturanSistem.ambil().batas_usia_bukti_bulan
        if self.periode is not None:
            hasil = target_svc.evaluasi(queryset_target_untuk(user).filter(periode=self.periode))
            ctx["ringkas_target"] = target_svc.ringkas(hasil) if hasil else None
            ctx["target_tertinggal"] = [h for h in hasil if h.tertinggal][:8]
        ctx["tugas"] = tugas_untuk(user, self.periode)
        persiapan = langkah_persiapan(user)
        if persiapan and not all(langkah.selesai for langkah in persiapan):
            ctx["persiapan"] = persiapan
        return ctx


# ---------------------------------------------------------------------------
# Periode
# ---------------------------------------------------------------------------


class PeriodeListView(IzinMixin, ListView):
    template_name = "penilaian/periode_list.html"
    context_object_name = "daftar_periode"
    queryset = PeriodeAkreditasi.objects.annotate(jumlah_penilaian=Count("penilaian"))

    def cek_izin(self):
        return bisa_kelola_periode(self.request.user)


class PeriodeSimpanMixin(IzinMixin):
    template_name = "penilaian/periode_form.html"
    form_class = FormPeriode
    model = PeriodeAkreditasi

    def cek_izin(self):
        return bisa_kelola_periode(self.request.user)

    def form_valid(self, form):
        periode = services.simpan_periode(user=self.request.user, periode=form.save(commit=False))
        form.save_m2m()
        messages.success(self.request, f"Periode {periode} disimpan.")
        return redirect("penilaian:periode_list")


class PeriodeCreateView(PeriodeSimpanMixin, CreateView):
    pass


class PeriodeUpdateView(PeriodeSimpanMixin, UpdateView):
    pass


class AktifkanPeriodeView(IzinMixin, View):
    http_method_names = ["post"]

    def cek_izin(self):
        return bisa_kelola_periode(self.request.user)

    def post(self, request, pk):
        periode = get_object_or_404(PeriodeAkreditasi, pk=pk)
        services.aktifkan_periode(user=request.user, periode=periode)
        messages.success(request, f"Periode {periode} sekarang aktif.")
        return redirect("penilaian:periode_list")


# ---------------------------------------------------------------------------
# Penilaian mandiri
# ---------------------------------------------------------------------------


class PenilaianBabListView(PeriodeMixin, TemplateView):
    template_name = "penilaian/bab_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["baris_bab"] = capaian.capaian_per_bab(
            periode=self.periode, bab_qs=queryset_bab_untuk(self.request.user)
        )
        return ctx


def ep_dengan_konteks(ep_qs, *, periode, user):
    """Prefetch penilaian, bukti yang boleh dilihat user, dan catatan untuk satu periode."""
    return ep_qs.select_related("standar__bab").prefetch_related(
        Prefetch(
            "penilaian",
            queryset=PenilaianEP.objects.filter(periode=periode).select_related("dinilai_oleh"),
            to_attr="penilaian_periode",
        ),
        Prefetch(
            "bukti",
            queryset=BuktiEP.objects.filter(dokumen__in=queryset_dokumen_untuk(user))
            .select_related("dokumen")
            .order_by("jenis_bukti"),
            to_attr="bukti_terlihat",
        ),
        Prefetch(
            "catatan_penilaian",
            queryset=CatatanPenilaian.objects.filter(periode=periode).select_related("penulis"),
            to_attr="catatan_periode",
        ),
    )


def lengkapi_ep(daftar_ep, ep_qs):
    """Tambahkan atribut tampilan: nilai, jenis bukti tercakup, status lengkap."""
    tercakup = capaian.bukti_disetujui(ep_qs)
    for ep in daftar_ep:
        ep.nilai = ep.penilaian_periode[0] if ep.penilaian_periode else None
        ep.tercakup = tercakup.get(ep.pk, set())
        ep.lengkap = set(ep.jenis_bukti) <= ep.tercakup
    return daftar_ep


def _konteks_baris(request, periode, bab):
    user = request.user
    return {
        "periode": periode,
        "bab": bab,
        "bisa_nilai": periode is not None and not periode.terkunci and bisa_nilai_bab(user, bab),
        "bisa_catat": periode is not None and bisa_beri_catatan(user, bab),
        "pilihan_skor": SkorEP.choices,
        "bisa_unggah_bukti": bisa_buat_dokumen(user),
    }


class PenilaianBabView(PeriodeMixin, TemplateView):
    template_name = "penilaian/bab_penilaian.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        bab = get_object_or_404(queryset_bab_untuk(user), pk=self.kwargs["pk"])
        ep_qs = ElemenPenilaian.objects.filter(standar__bab=bab).order_by("urutan", "kode")
        daftar_standar = list(
            Standar.objects.filter(bab=bab)
            .order_by("urutan", "kode")
            .prefetch_related(
                Prefetch(
                    "elemen_penilaian",
                    queryset=ep_dengan_konteks(ep_qs, periode=self.periode, user=user),
                    to_attr="daftar_ep",
                )
            )
        )
        semua_ep = [ep for s in daftar_standar for ep in s.daftar_ep]
        lengkapi_ep(semua_ep, ep_qs)
        ctx.update(_konteks_baris(self.request, self.periode, bab))
        ctx["daftar_standar"] = daftar_standar
        ctx["capaian_bab"] = capaian.capaian_per_bab(
            periode=self.periode, bab_qs=queryset_bab_untuk(user).filter(pk=bab.pk)
        )[0][1]
        return ctx


class _AksiEPView(View):
    http_method_names = ["post"]

    def ambil(self, request, periode_pk, ep_pk):
        periode = get_object_or_404(PeriodeAkreditasi, pk=periode_pk)
        ep = get_object_or_404(
            ElemenPenilaian.objects.select_related("standar__bab").filter(
                standar__bab__in=queryset_bab_untuk(request.user)
            ),
            pk=ep_pk,
        )
        return periode, ep

    def render_baris(self, request, periode, ep, galat=None):
        ep_qs = ElemenPenilaian.objects.filter(pk=ep.pk)
        ep = lengkapi_ep(list(ep_dengan_konteks(ep_qs, periode=periode, user=request.user)), ep_qs)[
            0
        ]
        ctx = _konteks_baris(request, periode, ep.standar.bab)
        ctx.update(ep=ep, galat=galat)
        if not request.htmx:
            if galat:
                messages.error(request, galat)
            url = reverse("penilaian:bab", args=[ep.standar.bab_id])
            return redirect(f"{url}?periode={periode.pk}")
        return render(request, "penilaian/partials/baris_ep.html", ctx)


class NilaiEPView(_AksiEPView):
    def post(self, request, periode_pk, ep_pk):
        periode, ep = self.ambil(request, periode_pk, ep_pk)
        galat = None
        try:
            services.nilai_ep(
                user=request.user,
                periode=periode,
                ep=ep,
                nilai=request.POST.get("nilai", ""),
                catatan=request.POST.get("catatan", ""),
                fakta_analisis=request.POST.get("fakta_analisis", ""),
            )
        except PermissionDenied:
            galat = "Anda tidak berhak menilai EP ini."
        except ValidationError as e:
            galat = " ".join(e.messages)
        return self.render_baris(request, periode, ep, galat)


class CatatanEPView(_AksiEPView):
    def post(self, request, periode_pk, ep_pk):
        periode, ep = self.ambil(request, periode_pk, ep_pk)
        galat = None
        try:
            services.tambah_catatan(
                user=request.user, periode=periode, ep=ep, isi=request.POST.get("isi", "")
            )
        except PermissionDenied:
            galat = "Anda tidak berhak memberi catatan pada EP ini."
        except ValidationError as e:
            galat = " ".join(e.messages)
        return self.render_baris(request, periode, ep, galat)


# ---------------------------------------------------------------------------
# Detail EP, kekurangan bukti, laporan, pencarian
# ---------------------------------------------------------------------------


def _xlsx(wb, nama_file):
    buffer = io.BytesIO()
    wb.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = content_disposition_header(True, nama_file)
    return response


class EPDetailView(PeriodeMixin, TemplateView):
    """Satu halaman untuk satu EP: bukti per jenis, skor & riwayat, catatan, wawancara, PPS."""

    template_name = "penilaian/ep_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ep_qs = ElemenPenilaian.objects.filter(
            pk=self.kwargs["pk"], standar__bab__in=queryset_bab_untuk(user)
        )
        daftar = list(
            ep_dengan_konteks(ep_qs, periode=self.periode, user=user).prefetch_related(
                "item_wawancara"
            )
        )
        if not daftar:
            raise Http404
        ep = lengkapi_ep(daftar, ep_qs)[0]
        ctx.update(_konteks_baris(self.request, self.periode, ep.standar.bab))
        ctx["ep"] = ep
        ctx["bukti_per_jenis"] = [
            (kode, JenisBukti(kode).label, [b for b in ep.bukti_terlihat if b.jenis_bukti == kode])
            for kode in ep.jenis_bukti
        ]
        ctx["riwayat"] = (
            PenilaianEP.objects.filter(elemen_penilaian=ep)
            .select_related("periode", "dinilai_oleh")
            .order_by("-periode__tanggal_mulai")
        )
        ctx["daftar_pps"] = (
            queryset_pps_untuk(user).filter(elemen_penilaian=ep).select_related("pj", "periode")
        )
        return ctx


class KekuranganView(TemplateView):
    template_name = "penilaian/kekurangan.html"

    def get(self, request, *args, **kwargs):
        bab_qs = queryset_bab_untuk(request.user)
        self.daftar_bab = list(bab_qs.order_by("kelompok__urutan", "urutan", "kode"))
        self.bab = None
        pk = request.GET.get("bab", "")
        if pk.isdigit():
            self.bab = next((b for b in self.daftar_bab if b.pk == int(pk)), None)
            if self.bab is None:
                raise Http404
            bab_qs = bab_qs.filter(pk=self.bab.pk)
        self.kekurangan = laporan.kekurangan_untuk(bab_qs)
        if request.GET.get("format") == "xlsx":
            nama = f"kekurangan_bukti_{self.bab.kode if self.bab else 'semua'}.xlsx"
            return _xlsx(laporan.laporan_kekurangan(self.kekurangan), nama)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        halaman = Paginator(self.kekurangan, 100).get_page(self.request.GET.get("page"))
        ctx.update(
            daftar_bab=self.daftar_bab,
            bab=self.bab,
            halaman=halaman,
            jumlah=len(self.kekurangan),
            jumlah_proses=sum(1 for k in self.kekurangan if k.proses),
            bisa_unggah_bukti=bisa_buat_dokumen(self.request.user),
        )
        return ctx


class LaporanPenilaianView(PeriodeMixin, View):
    def get(self, request):
        hasil_target = None
        if self.periode is not None:
            hasil_target = target_svc.evaluasi(
                queryset_target_untuk(request.user).filter(periode=self.periode)
            )
        wb = laporan.laporan_penilaian(
            periode=self.periode,
            bab_qs=queryset_bab_untuk(request.user),
            hasil_target=hasil_target,
        )
        nama = f"penilaian_mandiri_{self.periode.nama if self.periode else 'tanpa_periode'}.xlsx"
        return _xlsx(wb, nama)


class CariView(TemplateView):
    template_name = "penilaian/cari.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        q = self.request.GET.get("q", "").strip()
        ctx["q"] = q
        if len(q) < 2:
            return ctx
        ctx["daftar_ep"] = (
            ElemenPenilaian.objects.filter(standar__bab__in=queryset_bab_untuk(user))
            .filter(
                Q(standar__kode__icontains=q)
                | Q(uraian__icontains=q)
                | Q(standar__uraian__icontains=q)
            )
            .select_related("standar__bab")
            .order_by("standar__bab__kode", "standar__urutan", "urutan")[:50]
        )
        ctx["daftar_dokumen"] = (
            queryset_dokumen_untuk(user)
            .filter(Q(judul__icontains=q) | Q(nomor__icontains=q) | Q(keterangan__icontains=q))
            .select_related("pokja")
            .order_by("-diubah_pada")[:50]
        )
        return ctx


# ---------------------------------------------------------------------------
# Target pokja
# ---------------------------------------------------------------------------


class TargetListView(PeriodeMixin, TemplateView):
    """Monitoring target per pokja terhadap jadwal (untuk direktur, komite, dan pokja)."""

    template_name = "penilaian/target_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        hasil = []
        if self.periode is not None:
            hasil = target_svc.evaluasi(queryset_target_untuk(user).filter(periode=self.periode))
        status = self.request.GET.get("status", "")
        ctx.update(
            ringkas=target_svc.ringkas(hasil),
            jumlah_semua=len(hasil),
            daftar=[h for h in hasil if not status or h.status == status],
            status_dipilih=status,
            bisa_kelola=bisa_kelola_target(user),
        )
        return ctx

    def get(self, request, *args, **kwargs):
        if request.GET.get("format") == "xlsx" and self.periode is not None:
            hasil = target_svc.evaluasi(
                queryset_target_untuk(request.user).filter(periode=self.periode)
            )
            return _xlsx(laporan.laporan_target(hasil), f"target_pokja_{self.periode.nama}.xlsx")
        return super().get(request, *args, **kwargs)


class TargetCreateView(IzinMixin, FormView):
    template_name = "penilaian/target_form.html"
    form_class = FormTargetBanyak

    def cek_izin(self):
        return bisa_kelola_target(self.request.user)

    def get_initial(self):
        return {"periode": services.periode_aktif()}

    def form_valid(self, form):
        d = form.cleaned_data
        dibuat, diperbarui = target_svc.buat_target_banyak(
            user=self.request.user,
            periode=d["periode"],
            daftar_pokja=d["daftar_pokja"],
            ukuran=d["ukuran"],
            nilai_target=d["nilai_target"],
            tanggal_mulai=d["tanggal_mulai"],
            tenggat=d["tenggat"],
            keterangan=d["keterangan"],
        )
        pesan = f"{dibuat} target dibuat"
        if diperbarui:
            pesan += f", {diperbarui} target yang sudah ada diperbarui"
        messages.success(self.request, pesan + ".")
        return redirect(f"{reverse('penilaian:target_list')}?periode={d['periode'].pk}")


class TargetUpdateView(IzinMixin, UpdateView):
    template_name = "penilaian/target_form.html"
    form_class = FormTarget
    queryset = TargetPokja.objects.select_related("pokja", "periode")

    def cek_izin(self):
        return bisa_kelola_target(self.request.user)

    def form_valid(self, form):
        target = target_svc.simpan_target(user=self.request.user, target=form.save(commit=False))
        messages.success(self.request, "Target diperbarui.")
        return redirect(f"{reverse('penilaian:target_list')}?periode={target.periode_id}")


class TargetHapusView(IzinMixin, View):
    http_method_names = ["post"]

    def cek_izin(self):
        return bisa_kelola_target(self.request.user)

    def post(self, request, pk):
        target = get_object_or_404(TargetPokja, pk=pk)
        target_svc.hapus_target(user=request.user, target=target)
        messages.success(request, "Target dihapus.")
        return redirect(f"{reverse('penilaian:target_list')}?periode={target.periode_id}")
