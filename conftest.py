import pytest

from apps.akun.peran import Peran
from apps.akun.tests.factories import PokjaFactory, UserFactory


@pytest.fixture
def buat_user(db):
    """buat_user(Peran.KOMITE_MUTU, pokja=[...]) → user dengan grup tersebut."""

    def _buat(*peran: Peran, **kwargs):
        return UserFactory(peran=list(peran), **kwargs)

    return _buat


@pytest.fixture
def pokja(db):
    return PokjaFactory()
