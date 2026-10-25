import factory

from apps.standar.models import Bab, ElemenPenilaian, KelompokStandar, Standar


class KelompokStandarFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = KelompokStandar
        django_get_or_create = ["kode"]

    kode = factory.Sequence(lambda n: f"KEL{n}")
    nama = factory.Sequence(lambda n: f"Kelompok Contoh {n}")


class BabFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Bab
        django_get_or_create = ["kode"]

    kelompok = factory.SubFactory(KelompokStandarFactory)
    kode = factory.Sequence(lambda n: f"BAB{n}")
    nama = factory.Sequence(lambda n: f"Bab Contoh {n}")


class StandarFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Standar

    bab = factory.SubFactory(BabFactory)
    kode = factory.Sequence(lambda n: f"STD {n}")
    uraian = "Uraian standar contoh"


class ElemenPenilaianFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ElemenPenilaian

    standar = factory.SubFactory(StandarFactory)
    kode = factory.Sequence(lambda n: f"ep{n}")
    uraian = "Uraian EP contoh"
    jenis_bukti = factory.LazyFunction(lambda: ["R", "D"])
