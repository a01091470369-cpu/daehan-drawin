# -*- coding: utf-8 -*-
"""기계설비·정보통신 문서자동화 웹 런처 — 표준 라이브러리만(pip 불필요, 이식성 유지).
왼쪽 고정 사이드바에서 분야(기계설비/정보통신) → 건물 선택 → 7종 문서 실시간 생성.
실행:  python 도면분석기/런처/server.py   →  브라우저 http://127.0.0.1:8766

분야별 정본 진입점(임의 재조립 없이 각 프로젝트의 CLI를 그대로 호출한다):
  기계설비  D:\문서자동화\framework_기계설비_main : run_mech.py --list / run_mech.py <코드>
  정보통신  D:\문서자동화\framework                : menu_helper.py list / build_all_v1.py <코드>
※ 이 런처는 두 프로젝트를 '실행'만 한다. 정보통신 코드·산출물은 읽기 전용으로도 수정하지 않는다.
"""
import os, sys, json, re, subprocess, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))                    # D:\문서자동화\도면분석기\런처
BASE = os.path.dirname(os.path.dirname(HERE))                        # D:\문서자동화
MECH_ROOT = os.path.join(BASE, "framework_기계설비_main")              # 기계설비 정본
IC_ROOT = os.path.join(BASE, "framework")                            # 정보통신 정본
DRAW_ROOT = os.path.join(BASE, "도면분석기")                          # 도면분석기(분야 중립)
PORT = 8766
PYEXE = sys.executable or "python"
CODE_RE = re.compile(r"[A-Za-z0-9_]+")


def _parse_mech_list(out):
    """run_mech.py --list  →  '  <코드>  <건물명>'."""
    rows = []
    for line in out.splitlines():
        m = re.match(r"^\s{2,}([A-Za-z0-9_]+)\s{2,}(.+?)\s*$", line)
        if m:
            rows.append({"code": m.group(1), "name": m.group(2)})
    return rows


def _parse_ic_list(out):
    """menu_helper.py list  →  '   1. <건물명>   (<코드>)'."""
    rows = []
    for line in out.splitlines():
        m = re.match(r"^\s*\d+\.\s+(.+?)\s+\(([A-Za-z0-9_]+)\)\s*$", line)
        if m:
            rows.append({"code": m.group(2), "name": m.group(1)})
    return rows


# ── 분야 정의(사이드바 탭 = 이 순서) ────────────────────────────────────────
# ── 도면분석기: 작업 폴더를 직접 읽는다(전용 --list CLI 가 없다) ──────────────
DRAW_OUTPUTS = [("설비목록", "_설비목록.xlsx", ["export/to_xlsx.py"]),
                ("도면검토보고서", "_도면검토보고서.docx", ["export/to_docx.py"])]


def _draw_work(code):
    return os.path.join(DRAW_ROOT, "작업", code)


def _list_draw():
    """작업\<건물명>\02_판독\reading.json 이 있는 폴더 = 분석 작업 1건."""
    base = os.path.join(DRAW_ROOT, "작업")
    rows = []
    if not os.path.isdir(base):
        return rows
    for n in sorted(os.listdir(base)):
        rd = os.path.join(base, n, "02_판독", "reading.json")
        if not os.path.isdir(os.path.join(base, n)) or not os.path.exists(rd):
            continue
        try:
            with open(rd, encoding="utf-8") as f:
                j = json.load(f)
            n_dw, n_it = len(j.get("도면", [])), len(j.get("설비", []))
            sub = f"도면 {n_dw}장 · 설비 {n_it}건" if n_it else f"도면 {n_dw}장 · 판독 대기"
        except Exception:
            sub = "reading.json 읽기 오류"
        rows.append({"code": n, "name": n, "sub": sub})
    return rows


def _docstatus_draw(code):
    out = os.path.join(_draw_work(code), "03_출력")
    docs = []
    for doc, suffix, _cmd in DRAW_OUTPUTS:
        p2 = os.path.join(out, code + suffix)
        ok = os.path.exists(p2)
        docs.append({"doc": doc, "done": ok, "path": p2 if ok else ""})
    return {"docs": docs}


def _draw_cmd(doc):
    for d, _s, cmd in DRAW_OUTPUTS:
        if d == doc:
            return cmd
    return None


DOMAINS = [
    {
        "key": "mech",
        "label": "기계설비",
        "mark": "기계",
        "title": "기계설비 문서자동화",
        "sub": "㈜대한기계정보통신",
        "root": MECH_ROOT,
        "entry": "run_mech.py",          # 목록·생성 공용 진입점
        "list_args": ["run_mech.py", "--list"],
        "run_args": ["run_mech.py"],
        "register_args": ["build_mechanical_management_register.py", "--open"],  # 경영자료(통합관리대장)
        "only_flag": "--only",           # 개별 생성 지원(카드 클릭)
        "docstatus_flag": "--docstatus", # 카드 완료/미완료·열기 지원
        "parse": _parse_mech_list,
        "docs": ["견적서", "계약서", "대상물현황표", "성능점검계획서",
                 "유지관리계획서", "반기점검표", "성능점검결과보고서",
                 "요약보고서", "완료계", "대금청구서"],
    },
    {
        "key": "ic",
        "label": "정보통신",
        "mark": "정통",
        "title": "정보통신 문서자동화",
        "sub": "㈜대한기계정보통신",
        "root": IC_ROOT,
        "entry": "build_all_v1.py",
        "list_args": ["menu_helper.py", "list"],
        "run_args": ["build_all_v1.py"],
        "register_args": ["build_management_register.py", "--open"],  # 경영자료(통합관리대장)
        "docstatus_flag": "--docstatus",  # 카드 완료/미완료·열기 지원
        "only_flag": "--only",            # 완료계·대금청구서 개별생성(그 외는 7종 일괄)
        "parse": _parse_ic_list,
        "docs": ["대상물현황표", "견적서", "계약서", "유지관리계획서",
                 "성능점검계획서", "반기점검 결과보고서", "성능점검 결과보고서",
                 "요약보고서", "완료계", "대금청구서"],
    },
    {
        "key": "draw",
        "label": "도면분석",
        "mark": "도면",
        "title": "도면분석기",
        "sub": "건축·기계·전기·소방·정보통신",
        "root": DRAW_ROOT,
        "entry": "analyze.py",
        "kind": "analyze",                 # 흐름이 다름: 폴더 분석 → 판독 → 출력
        "run_label": "▶ 출력 2종 생성",
        "list_fn": _list_draw,             # CLI 대신 작업 폴더 스캔
        "docstatus_fn": _docstatus_draw,   # CLI 대신 03_출력 파일 존재 확인
        "only_flag": "-",                  # 카드 개별 생성 지원(실제 명령은 _draw_cmd)
        "docstatus_flag": "-",
        "docs": [d for d, _s, _c in DRAW_OUTPUTS],
    },
]
DOMAIN_BY_KEY = {d["key"]: d for d in DOMAINS}


def _env():
    return dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")


def _available(dom):
    return os.path.exists(os.path.join(dom["root"], dom["entry"]))


def _valid_code(dom, code):
    """도면분석기는 폴더명이 한글이라 정규식 대신 실제 목록(화이트리스트)으로 검증한다."""
    if dom.get("list_fn"):
        return any(r["code"] == code for r in dom["list_fn"]())
    return bool(CODE_RE.fullmatch(code or ""))


def _docstatus(dom, code):
    """분야 CLI(--docstatus)로 건물의 7문서 완료/미완료·경로 JSON을 받아온다."""
    if dom.get("docstatus_fn"):
        return dom["docstatus_fn"](code)
    flag = dom.get("docstatus_flag")
    if not flag:
        return {"docs": []}
    try:
        p = subprocess.run([PYEXE] + dom["run_args"] + [flag, code], cwd=dom["root"],
                           env=_env(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90)
        for line in reversed(p.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
    except Exception as e:
        return {"docs": [], "error": str(e)}
    return {"docs": []}


def list_buildings(dom):
    if not _available(dom):
        return []
    if dom.get("list_fn"):
        return dom["list_fn"]()
    p = subprocess.run([PYEXE] + dom["list_args"], cwd=dom["root"], env=_env(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return dom["parse"](p.stdout)


def _serve_file(h, name, ctype):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        h.send_error(404); return
    with open(p, "rb") as f:
        data = f.read()
    h.send_response(200)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _domain(self, qs):
        return DOMAIN_BY_KEY.get((qs.get("domain") or ["mech"])[0])

    def do_GET(self):
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)
        if path == "/" or path == "/index.html":
            return _serve_file(self, "index.html", "text/html; charset=utf-8")
        if path == "/style.css":
            return _serve_file(self, "style.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return _serve_file(self, "app.js", "application/javascript; charset=utf-8")
        if path == "/api/domains":
            return self._json({"domains": [
                {k: d[k] for k in ("key", "label", "mark", "title", "sub")} |
                {"available": _available(d),
                 "has_register": bool(d.get("register_args")),
                 "supports_only": bool(d.get("only_flag")),
                 "supports_docstatus": bool(d.get("docstatus_flag")),
                 "kind": d.get("kind", "build"),
                 "run_label": d.get("run_label", "▶ 7종 문서 생성")} for d in DOMAINS]})
        if path == "/api/buildings":
            dom = self._domain(qs)
            if not dom:
                self.send_error(400, "bad domain"); return
            if not _available(dom):
                return self._json({"buildings": [], "docs": dom["docs"],
                                   "error": f"{dom['label']} 프로젝트를 찾을 수 없습니다: {dom['root']}"})
            return self._json({"buildings": list_buildings(dom), "docs": dom["docs"]})
        if path == "/api/run":
            dom = self._domain(qs)
            code = (qs.get("code") or [""])[0]
            if not dom or not _available(dom):
                self.send_error(400, "bad domain"); return
            if not _valid_code(dom, code):
                self.send_error(400, "bad code"); return
            return self._stream_run(dom, code)
        if path == "/api/register":
            dom = self._domain(qs)
            if not dom or not _available(dom) or not dom.get("register_args"):
                self.send_error(400, "no register"); return
            return self._stream_cmd(dom, dom["register_args"],
                                    {"code": "register", "domain": dom["key"]})
        if path == "/api/run_one":
            dom = self._domain(qs)
            code = (qs.get("code") or [""])[0]
            doc = (qs.get("doc") or [""])[0]
            if (not dom or not _available(dom) or not dom.get("only_flag")
                    or not _valid_code(dom, code) or doc not in dom.get("docs", [])):
                self.send_error(400, "bad single"); return
            if dom["key"] == "draw":                      # 도면분석기: 출력 스크립트 + 작업폴더
                cmd = _draw_cmd(doc)
                if not cmd:
                    self.send_error(400, "bad doc"); return
                return self._stream_cmd(dom, cmd + [_draw_work(code)],
                                        {"code": code, "doc": doc, "domain": dom["key"]})
            return self._stream_cmd(dom, dom["run_args"] + [dom["only_flag"], doc, code],
                                    {"code": code, "doc": doc, "domain": dom["key"]})
        if path == "/api/docstatus":
            dom = self._domain(qs); code = (qs.get("code") or [""])[0]
            if (not dom or not _available(dom) or not dom.get("docstatus_flag")
                    or not _valid_code(dom, code)):
                return self._json({"docs": []})
            return self._json(_docstatus(dom, code))
        if path == "/api/open":
            dom = self._domain(qs); code = (qs.get("code") or [""])[0]
            doc = (qs.get("doc") or [""])[0]
            if (not dom or not _available(dom) or not dom.get("docstatus_flag")
                    or not _valid_code(dom, code)):
                self.send_error(400); return
            # 서버가 경로를 직접 재도출해 연다(클라이언트 임의경로 차단).
            data = _docstatus(dom, code)
            target = next((x.get("path") for x in data.get("docs", [])
                           if x.get("doc") == doc and x.get("path")), "")
            if target and os.path.exists(target):
                try:
                    os.startfile(target)                       # Windows 기본 앱으로 열기
                    return self._json({"opened": target})
                except Exception as e:
                    return self._json({"error": str(e)})
            self.send_error(404); return
        self.send_error(404)

    def _stream_run(self, dom, code):
        if dom["key"] == "draw":                          # 출력 2종 순차 생성
            work = _draw_work(code)
            return self._stream_cmd(dom, [c for _d, _s, cmd in DRAW_OUTPUTS for c in cmd],
                                    {"code": code, "domain": dom["key"]}, many=[
                                        cmd + [work] for _d, _s, cmd in DRAW_OUTPUTS])
        return self._stream_cmd(dom, dom["run_args"] + [code],
                                {"code": code, "domain": dom["key"]})

    def _stream_cmd(self, dom, args, meta, many=None):
        """분야별 정본 CLI의 실시간 출력을 SSE로 스트리밍. many 가 있으면 순차 실행."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def send(ev, data):
            self.wfile.write(f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()

        try:
            send("start", meta)
            proc = subprocess.Popen([PYEXE] + args, cwd=dom["root"], env=_env(),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1)
            for line in iter(proc.stdout.readline, ""):
                send("line", line.rstrip("\n"))
            proc.stdout.close()
            rc = proc.wait()
            send("done", {"code": meta.get("code"), "returncode": rc})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try: send("line", f"[런처 오류] {type(e).__name__}: {e}")
            except Exception: pass


class LauncherServer(ThreadingHTTPServer):
    # Windows에서 SO_REUSEADDR 는 '이미 쓰는 포트'에도 bind 를 허용해 런처가 중복 기동된다.
    # 두 번째 실행이 확실히 OSError 로 떨어지도록 끈다(중복 방지 → 기존 화면만 다시 열기).
    allow_reuse_address = False


def main():
    ready = [d for d in DOMAINS if _available(d)]
    if not ready:
        print("[오류] 실행 가능한 분야가 없습니다.")
        for d in DOMAINS:
            print(f"  - {d['label']}: {os.path.join(d['root'], d['entry'])} 없음")
        return
    url = f"http://127.0.0.1:{PORT}"
    try:
        srv = LauncherServer(("127.0.0.1", PORT), Handler)
    except OSError:
        # 이미 런처가 떠 있음 — 새로 띄우지 않고 그 화면만 다시 연다.
        print(f"런처가 이미 실행 중입니다 → {url}  (브라우저를 엽니다)")
        webbrowser.open(url)
        return
    print(f"기계설비·정보통신 문서자동화 런처 실행 중 → {url}  (종료: 이 창을 닫거나 Ctrl+C)")
    for d in DOMAINS:
        print(f"  {'[사용가능]' if _available(d) else '[없음]    '} {d['label']}  {d['root']}")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료")


if __name__ == "__main__":
    main()
