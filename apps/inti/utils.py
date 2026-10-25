import calendar
import datetime


def tambah_bulan(tanggal: datetime.date, bulan: int) -> datetime.date:
    """Tambah sejumlah bulan; tanggal disesuaikan ke akhir bulan (31 Jan + 1 → 28/29 Feb)."""
    indeks = tanggal.month - 1 + bulan
    tahun, bulan_baru = tanggal.year + indeks // 12, indeks % 12 + 1
    hari = min(tanggal.day, calendar.monthrange(tahun, bulan_baru)[1])
    return tanggal.replace(year=tahun, month=bulan_baru, day=hari)


def ip_klien(request) -> str | None:
    """IP klien. Di produksi di belakang Nginx, pastikan X-Real-IP di-set oleh proxy."""
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR")
