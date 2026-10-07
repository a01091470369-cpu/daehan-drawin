# -*- coding: utf-8 -*-
"""이미지 도면 OCR(보조). Tesseract 없으면 조용히 건너뛴다 — Claude 직접 판독이 주(主)다."""
import os, shutil


def available():
    try:
        import pytesseract                       # noqa: F401
    except ImportError:
        return False
    return bool(shutil.which("tesseract"))


def extract(path, lang="kor+eng"):
    """반환: {'text': str, 'note': str}"""
    if not available():
        return {"text": "", "note": "Tesseract 미설치 — OCR 건너뜀(이미지 직접 판독으로 대체)"}
    try:
        import pytesseract
        from PIL import Image
        with Image.open(path) as im:
            return {"text": pytesseract.image_to_string(im, lang=lang) or "", "note": ""}
    except Exception as e:
        return {"text": "", "note": f"OCR 실패: {e}"}
