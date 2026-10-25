from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import content_disposition_header
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from apps.inti.utils import ip_klien
from apps.inti.views import IzinMixin

from . import services
from .forms import FormDokumen, FormDokumenBaru, FormFilterDokumen, FormTautkanEP, FormVersi
from .models import MIME_PRATINJAU, BuktiEP, DokumenVersi
from .permissions import (
    bisa_buat_dokumen,
    bisa_edit_dokumen,
    bisa_hapus_dokumen,
    bisa_lepas_bukti,
    bisa_tautkan_ep,
    bisa_unduh_versi,
    bisa_unggah_versi,
    queryset_dokumen_untuk,
    queryset_ep_tautan,
)


def _pesan_validasi(e: ValidationError) -> str:
    return " ".join(e.messages)


class DokumenMixin:
    """Ambil dokumen dari queryset yang disaring hak akses → 404 bila tidak berhak melihat."""

    def get_dokumen(self):
        if not hasattr(self, "_dokumen"):
            self._dokumen = get_object_or_404(
                queryset_dokumen_untuk(self.request.user).select_related("versi_aktif"),
                pk=self.kwargs["pk"],
            )
        return self._dokumen


class DokumenListView(ListView):
    template_name = "dokumen/dokumen_list.html"
    context_object_name = "daftar_dokumen"
    paginate_by = 25

    def get_queryset(self):
        qs = queryset_dokumen_untuk(self.request.user).select_related("pokja", "versi_aktif")
        self.form = FormFilterDokumen(self.request.GET or None)
        if self.form.is_valid():
            d = self.form.cleaned_data
            if d["q"]:
                qs = qs.filter(Q(judul__icontains=d["q"]) | Q(nomor__icontains=d["q"]))
            if d["status"]:
                qs = qs.filter(status=d["status"])
            if d["jenis"]:
                qs = qs.filter(jenis_dokumen=d["jenis"])
        return qs.annotate(jumlah_ep=Count("bukti__elemen_penilaian", distinct=True)).order_by(
            "-dibuat_pada"
        )

    def get_template_names(self):
        if self.request.htmx:
            return ["dokumen/partials/dokumen_tabel.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = self.form
        ctx["bisa_buat"] = bisa_buat_dokumen(self.request.user)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["query_filter"] = params.urlencode()
        return ctx


class DokumenCreateView(IzinMixin, CreateView):
    template_name = "dokumen/dokumen_form.html"
    form_class = FormDokumenBaru

    def cek_izin(self):
        return bisa_buat_dokumen(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        ep_id, jenis = self.request.GET.get("ep"), self.request.GET.get("jenis")
        if ep_id:
            ep = (
                queryset_ep_tautan(self.request.user)
                .select_related("standar__bab")
                .filter(pk=ep_id)
                .first()
            )
            if ep:
                initial.update(
                    ep=ep, jenis_bukti=jenis or ep.jenis_bukti[0], pokja=ep.standar.bab.pokja
                )
                self.ep_awal = ep
        return initial

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            dokumen = services.buat_dokumen(
                user=self.request.user,
                data=d,
                file=d["file"],
                catatan_perubahan=d["catatan_perubahan"],
                ep=d["ep"],
                jenis_bukti=d["jenis_bukti"] or None,
            )
        except ValidationError as e:
            form.add_error(None, _pesan_validasi(e))
            return self.form_invalid(form)
        messages.success(self.request, "Dokumen dibuat sebagai draft.")
        return redirect("dokumen:detail", pk=dokumen.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["ep_awal"] = getattr(self, "ep_awal", None)
        return ctx


class DokumenDetailView(DokumenMixin, DetailView):
    template_name = "dokumen/dokumen_detail.html"
    context_object_name = "dokumen"

    def get_object(self, queryset=None):
        return self.get_dokumen()

    def get_context_data(self, **kwargs):
        from apps.verifikasi.services import AKSI_WAJIB_CATATAN, aksi_tersedia

        ctx = super().get_context_data(**kwargs)
        dok, user = self.object, self.request.user
        ctx.update(
            daftar_versi=dok.versi.select_related("diunggah_oleh"),
            daftar_bukti=_daftar_bukti(dok),
            log_verifikasi=dok.log_verifikasi.select_related("user"),
            aksi=aksi_tersedia(user, dok),
            aksi_wajib_catatan=AKSI_WAJIB_CATATAN,
            bisa_edit=bisa_edit_dokumen(user, dok),
            bisa_unggah=bisa_unggah_versi(user, dok),
            bisa_hapus=bisa_hapus_dokumen(user, dok),
            bisa_tautkan=queryset_ep_tautan(user).exists(),
        )
        return ctx


def _daftar_bukti(dokumen):
    return dokumen.bukti.select_related("elemen_penilaian__standar__bab").order_by(
        "elemen_penilaian__standar__bab__kode",
        "elemen_penilaian__standar__urutan",
        "elemen_penilaian__urutan",
    )


class DokumenUpdateView(DokumenMixin, IzinMixin, UpdateView):
    template_name = "dokumen/dokumen_form.html"
    form_class = FormDokumen

    def cek_izin(self):
        return bisa_edit_dokumen(self.request.user, self.get_dokumen())

    def get_object(self, queryset=None):
        return self.get_dokumen()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        services.ubah_dokumen(dokumen=self.object, user=self.request.user, data=form.cleaned_data)
        messages.success(self.request, "Dokumen diperbarui.")
        return redirect("dokumen:detail", pk=self.object.pk)


class UnggahVersiView(DokumenMixin, IzinMixin, FormView):
    template_name = "dokumen/versi_form.html"
    form_class = FormVersi

    def cek_izin(self):
        return bisa_unggah_versi(self.request.user, self.get_dokumen())

    def form_valid(self, form):
        try:
            versi = services.unggah_versi(
                dokumen=self.get_dokumen(),
                user=self.request.user,
                file=form.cleaned_data["file"],
                catatan_perubahan=form.cleaned_data["catatan_perubahan"],
            )
        except ValidationError as e:
            form.add_error("file", _pesan_validasi(e))
            return self.form_invalid(form)
        messages.success(self.request, f"Versi {versi.nomor_versi} diunggah.")
        return redirect("dokumen:detail", pk=self.get_dokumen().pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["dokumen"] = self.get_dokumen()
        return ctx


class HapusDokumenView(DokumenMixin, IzinMixin, View):
    http_method_names = ["post"]

    def cek_izin(self):
        return bisa_hapus_dokumen(self.request.user, self.get_dokumen())

    def post(self, request, pk):
        services.hapus_dokumen(dokumen=self.get_dokumen(), user=request.user)
        messages.success(request, "Dokumen dihapus.")
        return redirect("dokumen:list")


class CariEPView(DokumenMixin, View):
    """HTMX: cari EP yang dapat ditautkan ke dokumen ini."""

    def get(self, request, pk):
        dokumen = self.get_dokumen()
        q = request.GET.get("q", "").strip()
        hasil = []
        if len(q) >= 2:
            hasil = (
                queryset_ep_tautan(request.user)
                .filter(
                    Q(standar__kode__icontains=q)
                    | Q(standar__bab__kode__iexact=q)
                    | Q(uraian__icontains=q)
                )
                .select_related("standar__bab")
                .order_by("standar__bab__kode", "standar__urutan", "urutan")[:20]
            )
        return render(
            request, "dokumen/partials/hasil_cari_ep.html", {"dokumen": dokumen, "hasil": hasil}
        )


class TautkanEPView(DokumenMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        dokumen = self.get_dokumen()
        form = FormTautkanEP(request.POST, user=request.user)
        galat = None
        if form.is_valid():
            ep = form.cleaned_data["elemen_penilaian"]
            if not bisa_tautkan_ep(request.user, dokumen, ep):
                galat = "Anda tidak berhak menautkan dokumen ke EP ini."
            else:
                try:
                    services.tautkan_ep(
                        dokumen=dokumen,
                        ep=ep,
                        jenis_bukti=form.cleaned_data["jenis_bukti"],
                        keterangan=form.cleaned_data["keterangan"],
                        user=request.user,
                    )
                except ValidationError as e:
                    galat = _pesan_validasi(e)
        else:
            galat = "EP atau jenis bukti tidak valid."
        return _respon_bukti(request, dokumen, galat)


class LepasBuktiView(DokumenMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, bukti_pk):
        dokumen = self.get_dokumen()
        bukti = get_object_or_404(
            BuktiEP.objects.select_related("elemen_penilaian__standar__bab"),
            pk=bukti_pk,
            dokumen=dokumen,
        )
        galat = None
        if bisa_lepas_bukti(request.user, bukti):
            services.lepas_bukti(bukti=bukti, user=request.user)
        else:
            galat = "Anda tidak berhak melepas tautan ini."
        return _respon_bukti(request, dokumen, galat)


def _respon_bukti(request, dokumen, galat):
    if request.htmx:
        return render(
            request,
            "dokumen/partials/daftar_bukti.html",
            {"dokumen": dokumen, "daftar_bukti": _daftar_bukti(dokumen), "galat": galat},
        )
    if galat:
        messages.error(request, galat)
    return redirect("dokumen:detail", pk=dokumen.pk)


class UnduhView(DokumenMixin, View):
    """Satu-satunya jalan mengunduh/melihat file bukti. Tidak berhak → 404."""

    def get(self, request, pk, versi_pk):
        dokumen = self.get_dokumen()
        versi = get_object_or_404(DokumenVersi, pk=versi_pk, dokumen=dokumen)
        if not bisa_unduh_versi(request.user, dokumen, versi):
            raise Http404
        lihat = request.GET.get("lihat") == "1" and versi.mime in MIME_PRATINJAU
        services.catat_unduhan(
            versi=versi,
            user=request.user,
            ip=ip_klien(request),
            keterangan="lihat" if lihat else "",
        )
        return kirim_file(versi, lampiran=not lihat)


def kirim_file(versi: DokumenVersi, *, lampiran=True):
    if settings.UNDUH_X_ACCEL:
        response = HttpResponse(content_type=versi.mime)
        response["X-Accel-Redirect"] = f"{settings.UNDUH_X_ACCEL_PREFIX}{versi.file.name}"
        response["Content-Disposition"] = content_disposition_header(lampiran, versi.nama_file_asli)
    else:
        response = FileResponse(
            versi.file.open("rb"),
            as_attachment=lampiran,
            filename=versi.nama_file_asli,
            content_type=versi.mime,
        )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    if not lampiran and versi.mime != "application/pdf":
        # Gambar/video ditampilkan dalam dokumen terisolasi (penampil PDF browser tidak
        # berjalan dalam sandbox, jadi PDF dikecualikan).
        response["Content-Security-Policy"] = (
            "sandbox; default-src 'none'; img-src 'self'; media-src 'self'"
        )
    return response
