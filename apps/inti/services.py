from django.utils import timezone


def hapus_lunak(*, obj):
    """Tandai objek sebagai dihapus tanpa menghapus barisnya."""
    if obj.dihapus_pada is None:
        obj.dihapus_pada = timezone.now()
        obj.save(update_fields=["dihapus_pada", "diubah_pada"])
    return obj


def pulihkan(*, obj):
    if obj.dihapus_pada is not None:
        obj.dihapus_pada = None
        obj.save(update_fields=["dihapus_pada", "diubah_pada"])
    return obj
