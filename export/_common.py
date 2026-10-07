# -*- coding: utf-8 -*-
import os, sys

def setup(path_arg=None):
    """작업폴더 경로를 받아 (reading, 작업폴더, 출력폴더) 반환. 검증 실패 시 종료."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, here)
    import schema as S
    work = path_arg or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not work:
        print("사용: python export/to_xxx.py \"<작업폴더>\""); sys.exit(1)
    rd = os.path.join(work, "02_판독", "reading.json")
    if not os.path.exists(rd):
        print(f"[오류] 판독 파일이 없습니다: {rd}"); sys.exit(1)
    reading = S.load(rd)
    err, warn = S.validate(reading)
    for w in warn:
        print(f"  [경고] {w}")
    if err:
        for e in err:
            print(f"  [오류] {e}")
        print("\n판독 파일을 고친 뒤 다시 실행하세요. (오류가 있으면 출력하지 않습니다)")
        sys.exit(2)
    out = os.path.join(work, "03_출력")
    os.makedirs(out, exist_ok=True)
    return reading, work, out
