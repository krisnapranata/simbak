from django import template

from .. import permissions
from ..models import MIME_PRATINJAU

register = template.Library()

WARNA_STATUS = {
    "draft": "bg-secondary-subtle text-secondary-emphasis",
    "diajukan": "bg-info-subtle text-info-emphasis",
    "diverifikasi_komite": "bg-primary-subtle text-primary-emphasis",
    "disetujui": "bg-success-subtle text-success-emphasis",
    "dikembalikan": "bg-warning-subtle text-warning-emphasis",
    "kedaluwarsa": "bg-danger-subtle text-danger-emphasis",
    "dicabut": "bg-dark-subtle text-dark-emphasis dicabut",
}


@register.inclusion_tag("dokumen/partials/status.html")
def status_dokumen(dokumen):
    return {"label": dokumen.get_status_display(), "warna": WARNA_STATUS.get(dokumen.status, "")}


@register.filter
def ukuran_file(byte):
    for satuan in ("B", "KB", "MB", "GB"):
        if byte < 1024 or satuan == "GB":
            return f"{byte:.0f} {satuan}" if satuan == "B" else f"{byte:.1f} {satuan}"
        byte /= 1024


@register.filter
def bisa_lepas_bukti(user, bukti):
    return permissions.bisa_lepas_bukti(user, bukti)


@register.filter
def bisa_buat_dokumen(user):
    return permissions.bisa_buat_dokumen(user)


@register.filter
def bisa_dipratinjau(versi):
    return versi.mime in MIME_PRATINJAU
