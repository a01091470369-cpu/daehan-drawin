# -*- coding: utf-8 -*-
"""도면 판독 중립 스키마 (reading.json).

분야(건축·기계설비·전기·소방·정보통신…)를 가리지 않는 단일 형식.
모든 출력(xlsx·docx·분야 초안)은 이 파일 하나에서 파생된다.

원칙: 지어내지 않는다. 항목마다 출처(도면 id·페이지)와 확신도를 남긴다.
"""
import io, json, os, datetime

SCHEMA_VERSION = "1.0"

FIELDS = ("건축", "기계설비", "전기", "소방", "정보통신", "토목", "조경", "기타")
CONF = ("확인", "추정", "미확인")          # 확신도
CONF_MARK = {"확인": "●", "추정": "△", "미확인": "○"}

ITEM_KEYS = ("분야", "분류", "명칭", "규격", "수량", "단위", "위치", "출처", "확신도", "비고")


def new_reading(name, source_folder=""):
    return {
        "schema": SCHEMA_VERSION,
        "건물": {"명칭": name, "주소": "", "연면적": "", "층수": "", "용도": "", "사용승인일": ""},
        "작성": {"생성일": datetime.date.today().isoformat(), "원본폴더": source_folder, "판독자": "Claude"},
        "도면": [],      # {id, 파일, 분야, 도면명, 페이지수, 비고}
        "설비": [],      # ITEM_KEYS
        "계통": [],      # {분야, 계통명, 흐름, 설명, 출처}
        "미확인": [],    # {항목, 사유, 필요자료}
        "메모": [],
    }


def add_item(reading, 분야, 분류, 명칭, 출처, 확신도="추정",
             규격="", 수량="", 단위="", 위치="", 비고=""):
    if 분야 not in FIELDS:
        raise ValueError(f"분야는 {FIELDS} 중 하나: {분야}")
    if 확신도 not in CONF:
        raise ValueError(f"확신도는 {CONF} 중 하나: {확신도}")
    if not 출처:
        raise ValueError("출처(도면 id·페이지)는 비울 수 없다 — 추적 불가 항목 금지")
    reading["설비"].append(dict(zip(ITEM_KEYS,
        [분야, 분류, 명칭, 규격, 수량, 단위, 위치, 출처, 확신도, 비고])))
    return reading


def validate(reading):
    """반환: (오류 list, 경고 list). 오류가 있으면 출력하지 않는다."""
    err, warn = [], []
    if reading.get("schema") != SCHEMA_VERSION:
        warn.append(f"스키마 버전 불일치: {reading.get('schema')} (현재 {SCHEMA_VERSION})")
    if not (reading.get("건물", {}).get("명칭") or "").strip():
        err.append("건물 명칭이 비어 있음")
    ids = {d.get("id") for d in reading.get("도면", [])}
    for i, it in enumerate(reading.get("설비", []), 1):
        for k in ITEM_KEYS:
            if k not in it:
                err.append(f"설비 {i}행: '{k}' 키 없음")
        if it.get("분야") not in FIELDS:
            err.append(f"설비 {i}행: 분야 '{it.get('분야')}' 가 목록에 없음")
        if it.get("확신도") not in CONF:
            err.append(f"설비 {i}행: 확신도 '{it.get('확신도')}' 가 목록에 없음")
        src = (it.get("출처") or "").strip()
        if not src:
            err.append(f"설비 {i}행: 출처 공란 — 어느 도면에서 읽었는지 없는 항목은 둘 수 없음")
        elif ids and not any(d and src.startswith(d) for d in ids):
            warn.append(f"설비 {i}행: 출처 '{src}' 가 도면 목록 id와 맞지 않음")
        if it.get("확신도") == "확인" and not str(it.get("규격") or "").strip():
            warn.append(f"설비 {i}행({it.get('명칭')}): '확인'인데 규격 공란")
    n_est = sum(1 for it in reading.get("설비", []) if it.get("확신도") == "추정")
    if n_est:
        warn.append(f"추정 항목 {n_est}건 — 장비일람표·수량표와 대조 필요")
    return err, warn


def summary(reading):
    by_field, by_conf = {}, {}
    for it in reading.get("설비", []):
        by_field[it.get("분야")] = by_field.get(it.get("분야"), 0) + 1
        by_conf[it.get("확신도")] = by_conf.get(it.get("확신도"), 0) + 1
    return {"도면": len(reading.get("도면", [])), "설비": len(reading.get("설비", [])),
            "계통": len(reading.get("계통", [])), "미확인": len(reading.get("미확인", [])),
            "분야별": by_field, "확신도별": by_conf}


def save(reading, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(reading, f, ensure_ascii=False, indent=2)
    return path


def load(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)
