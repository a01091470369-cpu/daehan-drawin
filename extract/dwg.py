# -*- coding: utf-8 -*-
"""DWG 도면 → (ODA File Converter) DXF → 텍스트·레이어·블록 덤프.

그림 자체는 해석하지 않는다. 도면에 적힌 글자와 블록(심볼) 이름·개수만 뽑아
Claude 판독의 보조 자료로 쓴다.
"""
import os, glob, shutil, subprocess, tempfile

ODA_GLOB = r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe"


def oda_path():
    hits = sorted(glob.glob(ODA_GLOB))
    return hits[-1] if hits else None


def dwg_to_dxf(dwg_path, out_dir, timeout=180):
    """DWG → DXF. ODA 가 없으면 None."""
    exe = oda_path()
    if not exe:
        return None
    os.makedirs(out_dir, exist_ok=True)
    src = tempfile.mkdtemp(prefix="dwgin_")
    try:
        shutil.copy2(dwg_path, src)
        # ODAFileConverter <입력> <출력> <버전> <형식ACAD> <재귀0/1> <감사0/1>
        subprocess.run([exe, src, out_dir, "ACAD2018", "DXF", "0", "1"],
                       timeout=timeout, capture_output=True)
    except Exception:
        return None
    finally:
        shutil.rmtree(src, ignore_errors=True)
    base = os.path.splitext(os.path.basename(dwg_path))[0]
    hit = os.path.join(out_dir, base + ".dxf")
    return hit if os.path.exists(hit) else None


def read_dxf(dxf_path, max_texts=4000):
    """DXF → {'texts': [...], 'layers': [...], 'blocks': {이름: 개수}}"""
    try:
        import ezdxf
    except ImportError:
        return {"texts": [], "layers": [], "blocks": {}, "note": "ezdxf 없음"}
    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception as e:
        return {"texts": [], "layers": [], "blocks": {}, "note": f"DXF 읽기 실패: {e}"}
    msp = doc.modelspace()
    texts, blocks = [], {}
    for e in msp:
        t = e.dxftype()
        if t == "TEXT":
            s = (e.dxf.text or "").strip()
            if s:
                texts.append(s)
        elif t == "MTEXT":
            s = (e.text or "").strip()
            if s:
                texts.append(s)
        elif t == "INSERT":
            nm = e.dxf.name
            blocks[nm] = blocks.get(nm, 0) + 1
        if len(texts) >= max_texts:
            break
    layers = sorted(l.dxf.name for l in doc.layers)
    return {"texts": texts, "layers": layers, "blocks": blocks, "note": ""}


def extract(path, out_dir):
    """반환: {'dxf': 경로|None, 'texts': [...], 'layers': [...], 'blocks': {...}, 'note': str}"""
    dxf = dwg_to_dxf(path, out_dir)
    if not dxf:
        return {"dxf": None, "texts": [], "layers": [], "blocks": {},
                "note": "ODA File Converter 없음 또는 변환 실패 — PDF로 출력해 주시면 직접 판독 가능"}
    r = read_dxf(dxf)
    r["dxf"] = dxf
    return r
