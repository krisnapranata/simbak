def notifikasi(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    return {"jumlah_notifikasi": user.notifikasi.filter(dibaca_pada__isnull=True).count()}
