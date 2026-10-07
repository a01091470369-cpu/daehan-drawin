# -*- coding: utf-8 -*-
"""이미지 도면·스캔 PDF OCR(보조). Claude 직접 판독이 주(主)이고, OCR 글자는 찾아보기용이다.

엔진 순서:
  1) EasyOCR (한국어+영어, 이 PC 에 모델 설치됨 — 인터넷 불필요). 도면 글자에 Tesseract 보다 낫다.
  2) Tesseract (설치돼 있으면)
둘 다 없으면 조용히 건너뛴다.

결과는 위→아래, 왼→오 순서의 줄 단위 텍스트. 각 줄 끝에 [x,y] 픽셀 위치를 붙여
페이지 이미지에서 해당 글자를 바로 찾아볼 수 있게 한다.
"""
import os, shutil

MAX_SIDE = 4000        # 이보다 큰 이미지는 줄여서 읽는다(CPU 시간·메모리)
MIN_CONF = 0.25        # EasyOCR 신뢰도 하한 — 이보다 낮은 건 잡음으로 버린다

_reader = None


def _easyocr_ready():
    try:
        import easyocr                           # noqa: F401
    except ImportError:
        return False
    d = os.path.join(os.path.expanduser("~"), ".EasyOCR", "model")
    need = ("craft_mlt_25k.pth", "korean_g2.pth")
    return all(os.path.exists(os.path.join(d, n)) for n in need)


def _tesseract_ready():
    try:
        import pytesseract                       # noqa: F401
    except ImportError:
        return False
    return bool(shutil.which("tesseract"))


def engine():
    if _easyocr_ready():
        return "easyocr"
    if _tesseract_ready():
        return "tesseract"
    return None


def available():
    return engine() is not None


def _get_reader():
    global _reader
    if _reader is None:
        import warnings
        warnings.filterwarnings("ignore", message=".*pin_memory.*")   # GPU 없음 경고(무해)
        import easyocr
        # download_enabled=False: 설치된 모델만 쓴다(몰래 내려받지 않음)
        _reader = easyocr.Reader(["ko", "en"], gpu=False, verbose=False, download_enabled=False)
    return _reader


def _load(path):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    scale = 1.0
    if max(im.size) > MAX_SIDE:
        scale = MAX_SIDE / max(im.size)
        im = im.resize((int(im.width * scale), int(im.height * scale)))
    return im, scale


def _lines(items, row_tol):
    """[(x, y, 글자)] → 같은 줄끼리 묶어 위→아래, 왼→오 순서 문자열."""
    items = sorted(items, key=lambda t: (t[1], t[0]))
    rows = []
    for x, y, s in items:
        if rows and abs(rows[-1][0] - y) <= row_tol:
            rows[-1][1].append((x, y, s))
        else:
            rows.append([y, [(x, y, s)]])
    out = []
    for _y, row in rows:
        row.sort()
        x0, y0 = row[0][0], row[0][1]
        out.append("   ".join(s for _x, _y2, s in row) + f"   [{int(x0)},{int(y0)}]")
    return "\n".join(out)


def extract(path, lang="kor+eng"):
    """반환: {'text': str, 'note': str, 'engine': str}"""
    eng = engine()
    if not eng:
        return {"text": "", "engine": "",
                "note": "OCR 엔진 없음(EasyOCR 모델·Tesseract) — 이미지 직접 판독으로 대체"}
    try:
        im, scale = _load(path)
        if eng == "easyocr":
            import numpy as np
            res = _get_reader().readtext(np.asarray(im), detail=1, paragraph=False)
            items, hs = [], []
            for box, s, conf in res:
                s = (s or "").strip()
                if not s or conf < MIN_CONF:
                    continue
                xs = [p[0] for p in box]; ys = [p[1] for p in box]
                items.append((min(xs) / scale, min(ys) / scale, s))
                hs.append((max(ys) - min(ys)) / scale)
            tol = (sorted(hs)[len(hs) // 2] * 0.6) if hs else 10
            return {"text": _lines(items, tol), "note": "", "engine": eng}
        import pytesseract
        return {"text": pytesseract.image_to_string(im, lang=lang) or "", "note": "", "engine": eng}
    except Exception as e:
        return {"text": "", "engine": eng, "note": f"OCR 실패: {e}"}
