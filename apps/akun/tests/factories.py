import factory
from django.contrib.auth.models import Group

from apps.akun.models import Pokja, Unit, User


class UnitFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Unit
        django_get_or_create = ["kode"]

    kode = factory.Sequence(lambda n: f"UNIT{n}")
    nama = factory.Sequence(lambda n: f"Unit Contoh {n}")


class PokjaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Pokja
        django_get_or_create = ["kode"]

    kode = factory.Sequence(lambda n: f"POKJA-{n}")
    nama = factory.Sequence(lambda n: f"Pokja Contoh {n}")


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"pengguna{n}")
    first_name = factory.Faker("first_name", locale="id_ID")
    password = factory.django.Password("rahasia-kuat-123")

    @factory.post_generation
    def peran(self, create, extracted, **kwargs):
        for nama in extracted or []:
            self.groups.add(Group.objects.get_or_create(name=nama)[0])

    @factory.post_generation
    def pokja(self, create, extracted, **kwargs):
        if extracted:
            self.pokja.set(extracted)
