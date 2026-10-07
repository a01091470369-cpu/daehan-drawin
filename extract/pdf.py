# -*- coding: utf-8 -*-
"""PDF 도면 → 페이지 텍스트 + 페이지 PNG(Claude 직접 판독용)."""
import os

DPI = 160          # 도면 글자가 읽히는 최소선. 너무 키우면 파일이 커져 판독이 느려진다.
MAX_PAGES = 40


def extract(path, out_dir, dpi=DPI, max_pages=MAX_PAGES):
    """반환: {'pages': n, 'texts': [str], 'images': [png경로], 'note': str}"""
    try:
        import fitz
    except ImportError:
        return {"pages": 0, "texts": [], "images": [], "note": "PyMuPDF(fitz) 없음 — PDF 처리 불가"}
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    texts, images, note = [], [], ""
    with fitz.open(path) as doc:
        n = doc.page_count
        if n > max_pages:
            note = f"{n}쪽 중 앞 {max_pages}쪽만 이미지 생성(텍스트는 전체)"
        for i, page in enumerate(doc):
            texts.append(page.get_text() or "")
            if i < max_pages:
                pm = page.get_pixmap(dpi=dpi)
                p = os.path.join(out_dir, f"{base}_p{i+1:02d}.png")
                pm.save(p)
                images.append(p)
    chars = sum(len(t.strip()) for t in texts)
    if chars < 30:
        note = (note + " / " if note else "") + "텍스트 거의 없음 — 스캔본일 수 있음(이미지 판독 필요)"
    return {"pages": n, "texts": texts, "images": images, "note": note}
