# -*- coding: utf-8 -*-
"""DWG 도면 → (ODA File Converter) DXF → 텍스트·레이어·블록 덤프 + 시트별 PNG.

글자·블록 덤프는 보조 자료다. 그림 판독은 dxf_render 가 도곽별로 찍은 PNG 를
Claude 가 직접 보고 한다.
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


MAX_RENDER_MB = 400   # 이보다 큰 DXF 는 메모리 때문에 이미지를 만들지 않는다


def read_dxf(dxf_path, max_texts=4000, img_dir=None, base=None):
    """DXF → {'texts': [...], 'layers': [...], 'blocks': {이름: 개수}, 'images': [...], 'sheets': [...]}

    img_dir 를 주면 시트별 PNG 도 만든다(dxf_render).
    """
    empty = {"texts": [], "layers": [], "blocks": {}, "images": [], "sheets": []}
    try:
        import ezdxf
    except ImportError:
        return dict(empty, note="ezdxf 없음")
    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception as e:
        return dict(empty, note=f"DXF 읽기 실패: {e}")
    msp = doc.modelspace()
    texts, blocks = [], {}
    for e in msp:
        t = e.dxftype()
        if t == "INSERT":              # 블록 개수는 끝까지 센다(수량 대조용)
            nm = e.dxf.name
            blocks[nm] = blocks.get(nm, 0) + 1
        elif len(texts) >= max_texts:
            continue
        elif t == "TEXT":
            s = (e.dxf.text or "").strip()
            if s:
                texts.append(s)
        elif t == "MTEXT":
            s = (e.text or "").strip()
            if s:
                texts.append(s)
    layers = sorted(l.dxf.name for l in doc.layers)
    out = dict(empty, texts=texts, layers=layers, blocks=blocks, note="")
    if img_dir:
        mb = os.path.getsize(dxf_path) / 1e6
        if mb > MAX_RENDER_MB:
            out["note"] = (f"DXF {mb:.0f}MB — 너무 커서 이미지 생략(한도 {MAX_RENDER_MB}MB). "
                           "CAD 에서 PDF 로 출력해 주시면 직접 판독 가능")
        else:
            from . import dxf_render
            try:
                r = dxf_render.render(doc, img_dir, base or os.path.splitext(os.path.basename(dxf_path))[0])
                out.update(images=r["images"], sheets=r["sheets"], note=r["note"])
            except Exception as e:
                out["note"] = f"이미지 생성 실패: {e}"
    return out


def extract(path, out_dir, render=True):
    """반환: {'dxf': 경로|None, 'texts', 'layers', 'blocks', 'images', 'sheets', 'note'}"""
    dxf = dwg_to_dxf(path, out_dir)
    if not dxf:
        return {"dxf": None, "texts": [], "layers": [], "blocks": {}, "images": [], "sheets": [],
                "note": "ODA File Converter 없음 또는 변환 실패 — PDF로 출력해 주시면 직접 판독 가능"}
    r = read_dxf(dxf, img_dir=out_dir if render else None)
    r["dxf"] = dxf
    return r
