# -*- coding: utf-8 -*-
"""reading.json → 설비목록 xlsx (설비 · 계통 · 미확인 · 도면 4시트)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import setup
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

NAVY = "1F3864"; LIGHT = "EAF0F7"
THIN = Side(style="thin", color="BFC7D2")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _sheet(wb, title, headers, rows, widths):
    ws = wb.create_sheet(title)
    for ci, h in enumerate(headers, 1):
        c = ws.cell(1, ci, h)
        c.font = Font(bold=True, color="FFFFFF", name="맑은 고딕", size=10)
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = BORDER
        ws.column_dimensions[c.column_letter].width = widths[ci - 1]
    for ri, row in enumerate(rows, 2):
        for ci, v in enumerate(row, 1):
            c = ws.cell(ri, ci, v)
            c.font = Font(name="맑은 고딕", size=9.5)
            c.alignment = Alignment(vertical="center", wrap_text=(widths[ci - 1] > 25))
            c.border = BORDER
    ws.freeze_panes = "A2"
    return ws


def build(work=None):
    reading, work, out = setup(work)
    name = reading["건물"]["명칭"]
    wb = Workbook(); wb.remove(wb.active)

    # 건물 개요
    ws = wb.create_sheet("건물")
    ws.column_dimensions["A"].width = 14; ws.column_dimensions["B"].width = 60
    for ri, (k, v) in enumerate(reading["건물"].items(), 1):
        a = ws.cell(ri, 1, k); a.font = Font(bold=True, name="맑은 고딕", size=10)
        a.fill = PatternFill("solid", fgColor=LIGHT); a.border = BORDER
        b = ws.cell(ri, 2, v or ""); b.font = Font(name="맑은 고딕", size=10); b.border = BORDER

    _sheet(wb, "설비",
           ["분야", "분류", "명칭", "규격", "수량", "단위", "위치", "출처", "확신도", "비고"],
           [[it.get(k, "") for k in ("분야", "분류", "명칭", "규격", "수량", "단위", "위치", "출처", "확신도", "비고")]
            for it in reading["설비"]],
           [10, 14, 24, 26, 7, 6, 18, 12, 8, 24])

    _sheet(wb, "계통", ["분야", "계통명", "흐름", "설명", "출처"],
           [[c.get(k, "") for k in ("분야", "계통명", "흐름", "설명", "출처")] for c in reading["계통"]],
           [10, 18, 38, 46, 12])

    _sheet(wb, "미확인", ["항목", "사유", "필요자료"],
           [[u.get(k, "") for k in ("항목", "사유", "필요자료")] for u in reading["미확인"]],
           [28, 36, 30])

    _sheet(wb, "도면", ["id", "파일", "분야", "도면명", "페이지수", "비고"],
           [[d.get(k, "") for k in ("id", "파일", "분야", "도면명", "페이지수", "비고")] for d in reading["도면"]],
           [7, 40, 10, 22, 9, 36])

    p = os.path.join(out, f"{name}_설비목록.xlsx")
    wb.save(p)
    print("생성:", p)
    return p


if __name__ == "__main__":
    build()
