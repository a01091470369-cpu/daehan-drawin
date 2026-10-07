# -*- coding: utf-8 -*-
"""도면분석기 진입점 — 자료폴더 전처리.

  python analyze.py "<자료폴더>" [--name 건물명] [--no-copy]

하는 일(①단계, 자동):
  자료폴더 스캔 → 분야 추정 → 00_원본 복사 → 01_추출(페이지 PNG·텍스트·DXF 덤프)
  → 02_판독\reading.json 뼈대 생성

하지 않는 일: 판독(②단계). 설비·계통은 비워 둔 채로 둔다.
01_추출 의 텍스트와 페이지 PNG 를 Claude 가 직접 보고 reading.json 을 채운다.
"""
import os, io, sys, shutil, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import schema as S
from extract import pdf as X_PDF, dwg as X_DWG, ocr as X_OCR

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

WORK = os.path.join(HERE, "작업")
DRAWING_EXT = (".pdf", ".dwg", ".dxf", ".png", ".jpg", ".jpeg", ".tif", ".tiff")

# 파일명 → 분야 추정(앞에서부터 먼저 맞는 것). 확정이 아니라 초기값이다.
FIELD_HINT = [
    ("소방",     ["소방", "스프링클러", "소화", "자탐", "자동화재", "제연", "fire", "fp-", "f-"]),
    ("전기",     ["전기", "동력", "조명", "간선", "수변전", "분전반", "단선결선", "elec", "e-"]),
    ("기계설비", ["기계", "공조", "덕트", "위생", "급배수", "냉난방", "hvac", "m-"]),
    ("정보통신", ["통신", "약전", "cctv", "방송", "네트워크", "tel", "ict"]),
    ("건축",     ["건축", "평면", "입면", "단면", "배치", "arch", "a-"]),
]


def guess_field(fname):
    low = fname.lower()
    for fld, keys in FIELD_HINT:
        if any(k in low for k in keys):
            return fld
    return "기타"


def scan(folder):
    rows = []
    for root, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if f.startswith("~$"):
                continue
            if f.lower().endswith(DRAWING_EXT):
                rows.append(os.path.join(root, f))
    return rows


def run(folder, name=None, copy=True, render=True, ocr=True):
    if not os.path.isdir(folder):
        print(f"[오류] 폴더가 없습니다: {folder}"); return 1
    name = name or os.path.basename(os.path.normpath(folder))
    work = os.path.join(WORK, name)
    d_src = os.path.join(work, "00_원본")
    d_ext = os.path.join(work, "01_추출")
    d_rd = os.path.join(work, "02_판독")
    d_out = os.path.join(work, "03_출력")
    for d in (d_src, d_ext, d_rd, d_out):
        os.makedirs(d, exist_ok=True)

    files = scan(folder)
    if not files:
        print(f"[오류] 도면 파일이 없습니다({', '.join(DRAWING_EXT)}): {folder}"); return 1

    print("=" * 64)
    print(f"  도면분석기 — 전처리   건물: {name}")
    print("=" * 64)
    print(f"  자료폴더: {folder}")
    print(f"  작업폴더: {work}")
    print(f"  도면파일: {len(files)}개\n")

    reading = S.new_reading(name, folder)
    for i, src in enumerate(files, 1):
        fn = os.path.basename(src)
        fld = guess_field(fn)
        did = f"D{i:02d}"
        ext = os.path.splitext(fn)[1].lower()
        if copy:
            try:
                shutil.copy2(src, os.path.join(d_src, fn))
            except Exception as e:
                print(f"  [{did}] 원본 복사 실패: {e}")
        pages, note, imgs = "", "", []
        sub = os.path.join(d_ext, f"{did}_{os.path.splitext(fn)[0]}")

        if ext == ".pdf":
            r = X_PDF.extract(src, sub)
            pages, note, imgs = r["pages"], r["note"], r["images"]
            texts = list(r["texts"])
            # 글자가 거의 없는 쪽(스캔본)은 페이지 이미지를 OCR 한다
            scanned = [i for i, t in enumerate(texts) if len(t.strip()) < 30 and i < len(imgs)]
            if scanned and ocr and X_OCR.available():
                print(f"  [{did}] {fn} — 스캔 {len(scanned)}쪽 OCR 중(쪽당 수십 초)…", flush=True)
                for i in scanned:
                    o = X_OCR.extract(imgs[i])
                    if o["text"].strip():
                        texts[i] = f"[OCR·{o['engine']}] 글자 뒤 [x,y]는 페이지 이미지 픽셀 위치\n" + o["text"]
                    elif o["note"]:
                        texts[i] = f"[OCR] {o['note']}"
                note = (note + " / " if note else "") + f"스캔 {len(scanned)}쪽 OCR 처리"
            with io.open(sub + ".txt", "w", encoding="utf-8", newline="\n") as f:
                for pi, t in enumerate(texts, 1):
                    f.write(f"\n===== p{pi} =====\n{t}")
        elif ext in (".dwg", ".dxf"):
            print(f"  [{did}] {fn} — 변환·이미지 생성 중(큰 도면은 수 분 걸림)…", flush=True)
            if ext == ".dwg":
                r = X_DWG.extract(src, sub, render=render)
            else:
                r = X_DWG.read_dxf(src, img_dir=sub if render else None); r["dxf"] = src
            note, imgs, sheets = r.get("note", ""), r.get("images", []), r.get("sheets", [])
            with io.open(sub + ".txt", "w", encoding="utf-8", newline="\n") as f:
                if sheets:
                    f.write("===== 시트 목록 =====\n")
                    for sh in sheets:
                        f.write(f"{sh['id']}  {sh['구분']:4s} {sh['도면번호'] or '-':8s} "
                                f"{os.path.basename(sh['png']) or '(이미지 실패)'}\n")
                    f.write("\n")
                f.write("===== 레이어 =====\n" + "\n".join(r.get("layers", [])))
                f.write("\n\n===== 블록(심볼) 개수 — 전체 =====\n")
                for k, v in sorted(r.get("blocks", {}).items(), key=lambda x: -x[1]):
                    f.write(f"{v:6d}  {k}\n")
                for sh in sheets:
                    if not (sh["texts"] or sh["blocks"]):
                        continue
                    f.write(f"\n===== {sh['id']} {sh['도면번호']} — 블록 =====\n")
                    for k, v in sorted(sh["blocks"].items(), key=lambda x: -x[1]):
                        f.write(f"{v:6d}  {k}\n")
                    f.write(f"----- {sh['id']} 텍스트 -----\n" + "\n".join(sh["texts"]) + "\n")
                f.write("\n===== 도면 텍스트 — 전체 =====\n" + "\n".join(r.get("texts", [])))
            pages = len(sheets) or len(r.get("texts", []))
        else:                                   # 이미지
            os.makedirs(sub, exist_ok=True)
            dst = os.path.join(sub, fn)
            try:
                shutil.copy2(src, dst); imgs = [dst]
            except Exception:
                pass
            if ocr:
                print(f"  [{did}] {fn} — OCR 중…", flush=True)
                r = X_OCR.extract(src)
            else:
                r = {"text": "", "note": "OCR 생략(--no-ocr)", "engine": ""}
            note = r["note"]
            if r["text"].strip():
                with io.open(sub + ".txt", "w", encoding="utf-8", newline="\n") as f:
                    f.write(f"[OCR·{r['engine']}] 글자 뒤 [x,y]는 이미지 픽셀 위치\n" + r["text"])
            pages = 1

        reading["도면"].append({"id": did, "파일": fn, "분야": fld, "도면명": "",
                                "페이지수": pages, "비고": note})
        print(f"  [{did}] {fld:5s} {fn}" + (f"   ({pages}쪽)" if pages else ""))
        if note:
            print(f"        ※ {note}")
        if imgs:
            print(f"        판독용 이미지 {len(imgs)}개 → {os.path.relpath(os.path.dirname(imgs[0]), work)}")

    rd_path = os.path.join(d_rd, "reading.json")
    if os.path.exists(rd_path):
        prev = S.load(rd_path)
        if prev.get("설비") or prev.get("계통"):
            bak = rd_path + ".bak"
            S.save(prev, bak)
            print(f"\n  ※ 기존 판독 결과가 있어 백업했습니다 → {os.path.basename(bak)}")
            prev["도면"] = reading["도면"]
            reading = prev
    S.save(reading, rd_path)

    by = {}
    for d in reading["도면"]:
        by[d["분야"]] = by.get(d["분야"], 0) + 1
    print("\n" + "-" * 64)
    print("  분야별 도면: " + " · ".join(f"{k} {v}" for k, v in sorted(by.items())))
    print(f"  판독 파일  : {rd_path}")
    print("-" * 64)
    print("  다음 단계(②판독): 01_추출 의 텍스트와 페이지 PNG 를 보고 reading.json 의")
    print("                    '설비'·'계통'·'건물' 을 채운다. 출처·확신도 필수.")
    print("  그 다음(③출력) : python export/to_xlsx.py \"%s\"" % work)
    print("                    python export/to_docx.py \"%s\"" % work)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="도면이 든 자료 폴더")
    ap.add_argument("--name", default=None, help="건물명(생략하면 폴더명)")
    ap.add_argument("--no-copy", action="store_true", help="00_원본 복사 생략")
    ap.add_argument("--no-render", action="store_true", help="DWG/DXF 시트 이미지 생성 생략")
    ap.add_argument("--no-ocr", action="store_true", help="스캔 PDF·이미지 OCR 생략")
    a = ap.parse_args()
    sys.exit(run(a.folder, a.name, copy=not a.no_copy, render=not a.no_render, ocr=not a.no_ocr))
