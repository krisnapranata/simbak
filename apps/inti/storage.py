from django.core.files.storage import FileSystemStorage


class StoragePrivat(FileSystemStorage):
    """Storage file bukti di luar folder publik. Tidak pernah punya URL langsung;
    file hanya boleh dikirim lewat view yang mengecek izin."""

    def url(self, name):
        raise NotImplementedError("File privat tidak punya URL publik; gunakan view unduh.")


def storage_privat():
    """Callable untuk `FileField(storage=...)`, dievaluasi saat runtime."""
    from django.core.files.storage import storages

    return storages["privat"]
