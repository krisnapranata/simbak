import hashlib
import itertools

import factory
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.akun.tests.factories import PokjaFactory, UserFactory
from apps.dokumen.models import BuktiEP, Dokumen, DokumenVersi, JenisDokumen, StatusDokumen

_n = itertools.count()


def isi_pdf() -> bytes:
    """PDF minimal unik (konten fiktif, tanpa data pasien)."""
    return (
        b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\n% " + str(next(_n)).encode() + b"\n%%EOF"
    )


def file_pdf(nama="bukti.pdf", isi=None):
    return SimpleUploadedFile(nama, isi or isi_pdf(), content_type="application/pdf")


class DokumenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Dokumen
        skip_postgeneration_save = True

    judul = factory.Sequence(lambda n: f"Dokumen contoh {n}")
    jenis_dokumen = JenisDokumen.SPO
    pokja = factory.SubFactory(PokjaFactory)
    status = StatusDokumen.DRAFT
    dibuat_oleh = factory.SubFactory(UserFactory)

    @factory.post_generation
    def dengan_file(self, create, extracted, **kwargs):
        if extracted is False:
            return
        isi = isi_pdf()
        versi = DokumenVersi.objects.create(
            dokumen=self,
            nomor_versi=1,
            file=SimpleUploadedFile("contoh.pdf", isi),
            nama_file_asli="Contoh Asli.pdf",
            mime="application/pdf",
            ukuran=len(isi),
            sha256=hashlib.sha256(isi).hexdigest(),
            diunggah_oleh=self.dibuat_oleh,
        )
        self.versi_aktif = versi
        self.save(update_fields=["versi_aktif"])


class BuktiEPFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BuktiEP

    dokumen = factory.SubFactory(DokumenFactory)
    elemen_penilaian = factory.SubFactory("apps.standar.tests.factories.ElemenPenilaianFactory")
    jenis_bukti = "R"
    dibuat_oleh = factory.SelfAttribute("dokumen.dibuat_oleh")
