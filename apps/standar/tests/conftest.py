import pytest
from openpyxl import Workbook

from apps.standar.services import KOLOM_BAB, KOLOM_EP

BAB_CONTOH = [["KMRS", "Kelompok Contoh", "TKRS", "Bab Contoh TKRS", "POKJA-TKRS", 1]]
EP_CONTOH = [
    ["TKRS", "TKRS 1", "Uraian standar contoh 1", "", "a", "Uraian EP contoh a", "R", 1],
    ["TKRS", "TKRS 1", "", "", "b", "Uraian EP contoh b", "D,W", 2],
    ["TKRS", "TKRS 2", "Uraian standar contoh 2", "", "a", "Uraian EP contoh c", "R, O", 1],
]


@pytest.fixture
def buat_excel(tmp_path):
    """buat_excel(ep=[...], bab=[...]) → path file .xlsx di tmp_path."""
    hitung = {"n": 0}

    def _buat(ep=None, bab=BAB_CONTOH, header_ep=KOLOM_EP, header_bab=KOLOM_BAB):
        hitung["n"] += 1
        wb = Workbook()
        ws = wb.active
        ws.title = "EP"
        ws.append(header_ep)
        for row in EP_CONTOH if ep is None else ep:
            ws.append(row)
        if bab is not None:
            ws_bab = wb.create_sheet("Bab")
            ws_bab.append(header_bab)
            for row in bab:
                ws_bab.append(row)
        path = tmp_path / f"standar_{hitung['n']}.xlsx"
        wb.save(path)
        return path

    return _buat
