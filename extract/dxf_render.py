# -*- coding: utf-8 -*-
"""DXF 도면 → 시트별 PNG(Claude 직접 판독용) + 시트별 텍스트·블록.

국내 CAD 도면은 한 파일의 모델공간에 여러 장(도곽)이 나란히 그려진 경우가 대부분이다.
그래서 모델공간 전체를 한 장으로 찍으면 글자가 안 보인다. 순서:

  1) 도곽 찾기  — A 시리즈 비율(√2)의 큰 블록(INSERT)·사각 폴리라인을 모아,
                 다른 도곽을 여럿 품은 외곽선과 도곽 안쪽 상자를 걸러 낸다.
  2) 한 번 그리기 — ezdxf 드로잉 애드온으로 모델공간을 한 번만 기록한다.
  3) 도곽별 자르기 — 기록을 도곽 영역으로 잘라 PNG 로 찍는다(빠름).

도곽을 못 찾으면 전체 개요 1장 + 2×2 분할 4장으로 대신한다.
종이공간(배치) 탭에 내용이 있으면 탭마다 1장씩 추가로 찍는다.

한글: 도면 글꼴(SHX·미설치 TTF)은 한글이 □ 로 깨지므로 전부 맑은 고딕으로 대체한다.
글자 폭이 원본과 조금 다를 수 있으나 판독에는 지장 없다.
"""
import os, re, math, contextlib

DPI = 200            # A3 기준 약 3300px — 도면 글자가 읽히는 선
MAX_SHEETS = 80
KO_FONT = "malgun.ttf"
A_RATIO = (1.36, 1.47)   # √2 = 1.414 (A 시리즈 도곽)
DWG_NO = re.compile(r"\b([A-Z]{1,3})\s*-\s*(\d{2,4})\b")


# ── 글꼴 ────────────────────────────────────────────────────────
@contextlib.contextmanager
def _korean_font():
    """렌더링하는 동안만 모든 글꼴을 맑은 고딕으로 바꾼다."""
    from ezdxf.fonts import fonts as F
    orig = F.make_font

    def make_font(font_name, cap_height, width_factor=1.0):
        try:
            return F.TrueTypeFont(KO_FONT, cap_height, width_factor)
        except Exception:
            return orig(font_name, cap_height, width_factor)

    F.make_font = make_font
    try:
        yield
    finally:
        F.make_font = orig


# ── 도곽 찾기 ───────────────────────────────────────────────────
def _rect(x0, y0, x1, y1):
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _w(r):
    return r[2] - r[0]


def _h(r):
    return r[3] - r[1]


def _inside(inner, outer, tol=0.01):
    t = tol * max(_w(outer), _h(outer))
    return (inner[0] >= outer[0] - t and inner[1] >= outer[1] - t and
            inner[2] <= outer[2] + t and inner[3] <= outer[3] + t)


def _same(a, b, tol=0.02):
    t = tol * max(_w(a), _h(a))
    return all(abs(a[i] - b[i]) <= t for i in range(4))


def _a_ratio(r):
    w, h = _w(r), _h(r)
    if min(w, h) <= 0:
        return False
    return A_RATIO[0] <= max(w, h) / min(w, h) <= A_RATIO[1]


def find_frames(doc):
    """모델공간 도곽 후보 → [(x0,y0,x1,y1), ...] (위→아래, 왼→오 순)."""
    from ezdxf import bbox
    msp = doc.modelspace()
    blk_ext, cands = {}, []

    for e in msp.query("INSERT"):
        name = e.dxf.name
        if name not in blk_ext:
            try:
                b = bbox.extents(doc.blocks[name], fast=True)
                blk_ext[name] = (b.extmin, b.extmax) if b.has_data else None
            except Exception:
                blk_ext[name] = None
        ext = blk_ext[name]
        if ext is None:
            continue
        try:
            m = e.matrix44()
        except Exception:
            continue
        (x0, y0, _), (x1, y1, _) = ext
        pts = list(m.transform_vertices([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]))
        xs, ys = [p.x for p in pts], [p.y for p in pts]
        r = _rect(min(xs), min(ys), max(xs), max(ys))
        if _a_ratio(r):
            cands.append(r)

    for e in msp.query("LWPOLYLINE"):
        n = len(e)
        if n not in (4, 5) or (n == 4 and not e.closed):
            continue
        pts = [(p[0], p[1]) for p in e.get_points("xy")]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        r = _rect(min(xs), min(ys), max(xs), max(ys))
        # 축에 나란한 사각형만
        if all(min(abs(x - r[0]), abs(x - r[2])) < 1e-6 * _w(r) + 1e-9 for x in xs) and _a_ratio(r):
            cands.append(r)

    if not cands:
        return []
    # 같은 자리 중복 제거
    uniq = []
    for r in sorted(cands, key=lambda r: -_w(r) * _h(r)):
        if not any(_same(r, u) for u in uniq):
            uniq.append(r)
    # 도곽 크기의 후보를 2개 이상 품은 외곽선 제거(도면 묶음 테두리).
    # 도곽 안의 작은 심볼 블록(비율이 우연히 √2)은 세지 않는다.
    def _holds_sheets(r):
        big = 0.08 * max(_w(r), _h(r))
        return sum(1 for o in uniq if o is not r and _inside(o, r)
                   and max(_w(o), _h(o)) >= big) >= 2
    uniq = [r for r in uniq if not _holds_sheets(r)]
    # 남은 것 중 큰 것부터, 이미 고른 도곽 안에 든 것(범례·표 상자)은 버림
    frames = []
    for r in uniq:
        if not any(_inside(r, f) for f in frames):
            frames.append(r)
    # 너무 작은 것(가장 큰 도곽 긴 변의 25% 미만) 제거
    big = max(max(_w(f), _h(f)) for f in frames)
    frames = [f for f in frames if max(_w(f), _h(f)) >= 0.25 * big]
    return _reading_order(frames)


def _reading_order(frames):
    """위 줄부터, 줄 안에서는 왼쪽부터."""
    frames = sorted(frames, key=lambda f: -f[3])
    rows = []
    for f in frames:
        cy = (f[1] + f[3]) / 2
        for row in rows:
            if abs(row[0] - cy) < 0.5 * _h(f):
                row[1].append(f)
                break
        else:
            rows.append([cy, [f]])
    out = []
    for _cy, fs in rows:
        out.extend(sorted(fs, key=lambda f: f[0]))
    return out


def _robust_extents(doc):
    """동떨어진 점(원점 근처 찌꺼기 등) 때문에 범위가 터지지 않게 1~99% 구간을 쓴다."""
    xs, ys = [], []
    for e in doc.modelspace():
        t = e.dxftype()
        try:
            if t == "LINE":
                p = e.dxf.start
            elif t in ("TEXT", "MTEXT", "INSERT"):
                p = e.dxf.insert
            elif t in ("CIRCLE", "ARC"):
                p = e.dxf.center
            else:
                continue
        except Exception:
            continue
        xs.append(p[0]); ys.append(p[1])
    if len(xs) < 2:
        return None
    xs.sort(); ys.sort()
    k = len(xs)
    lo, hi = int(k * 0.01), max(int(k * 0.99) - 1, 0)
    r = (xs[lo], ys[lo], xs[hi], ys[hi])
    pad = 0.02 * max(_w(r), _h(r), 1)
    return (r[0] - pad, r[1] - pad, r[2] + pad, r[3] + pad)


def _grid(r, cols=2, rows=2, overlap=0.05):
    w, h = _w(r) / cols, _h(r) / rows
    ox, oy = w * overlap, h * overlap
    out = []
    for j in range(rows):              # 위 줄부터
        for i in range(cols):
            x0 = r[0] + i * w
            y1 = r[3] - j * h
            out.append(_rect(x0 - ox, y1 - h - oy, x0 + w + ox, y1 + oy))
    return out


# ── 시트별 텍스트·블록 ─────────────────────────────────────────
def _texts_and_blocks(doc):
    """[(x, y, 글자)], [(x, y, 블록명)] — 블록 속성(ATTRIB) 글자도 포함."""
    texts, inserts = [], []
    for e in doc.modelspace():
        t = e.dxftype()
        try:
            if t == "TEXT":
                s = (e.dxf.text or "").strip()
                if s:
                    p = e.dxf.insert; texts.append((p[0], p[1], s))
            elif t == "MTEXT":
                s = (e.plain_text() or "").strip()
                if s:
                    p = e.dxf.insert; texts.append((p[0], p[1], s.replace("\n", " ")))
            elif t == "INSERT":
                p = e.dxf.insert
                inserts.append((p[0], p[1], e.dxf.name))
                for a in e.attribs:
                    s = (a.dxf.text or "").strip()
                    if s:
                        q = a.dxf.insert; texts.append((q[0], q[1], s))
        except Exception:
            continue
    return texts, inserts


def _in(x, y, r):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def _sheet_no(texts):
    """도곽 오른쪽 아래(표제란)에 가까운 도면번호(M-001 등)를 고른다."""
    best = None
    for x, y, s in texts:
        m = DWG_NO.search(s)
        if m:
            key = (-x + y)             # 오른쪽·아래일수록 작다
            if best is None or key < best[0]:
                best = (key, f"{m.group(1)}-{m.group(2)}")
    return best[1] if best else ""


# ── 렌더링 ─────────────────────────────────────────────────────
def _page_for(r):
    return (420, 297) if _w(r) >= _h(r) else (297, 420)


def _batched_backend_cls():
    """선마다 PDF 마감(finish)을 하면 도면 1장에 수 분이 걸린다.
    같은 색·선굵기·레이어로 이어지는 선은 모아서 한 번에 마감한다."""
    from ezdxf.addons.drawing import pymupdf

    class Batched(pymupdf.PyMuPdfRenderBackend):
        _pending = None

        def _queue(self, props):
            key = props[:3]
            if self._pending is not None and self._pending[:3] != key:
                self._flush()
            self._pending = props

        def _flush(self):
            if self._pending is not None:
                self.finish_line(self.content_shape, self._pending, close=False)
                self._pending = None

        def draw_point(self, pos, properties):
            self._queue(properties)
            v = pymupdf.Vec2(pos)
            self.content_shape.draw_line(v, v)

        def draw_line(self, start, end, properties):
            self._queue(properties)
            self.content_shape.draw_line(pymupdf.Vec2(start), pymupdf.Vec2(end))

        def draw_solid_lines(self, lines, properties):
            self._queue(properties)
            for a, b in lines:
                self.content_shape.draw_line(a, b)

        def draw_path(self, path, properties):
            if len(path) == 0:
                return
            self._queue(properties)
            pymupdf.add_path_to_shape(self.content_shape, path, close=False)

        def draw_filled_paths(self, paths, properties):
            self._flush(); super().draw_filled_paths(paths, properties)

        def draw_filled_polygon(self, points, properties):
            self._flush(); super().draw_filled_polygon(points, properties)

        def draw_image(self, image_data, properties):
            self._flush(); super().draw_image(image_data, properties)

        def finalize(self):
            self._flush(); super().finalize()

    class Backend(pymupdf.PyMuPdfBackend):
        @staticmethod
        def make_backend(page, settings):
            return Batched(page, settings)

    return Backend


class _Index:
    """기록(선·글자 등)마다 범위를 한 번만 계산해 두고, 도곽마다 겹치는 것만 골라 자른다."""

    def __init__(self, master):
        import numpy as np
        self.master = master
        self.records = master.records
        box = np.full((len(self.records), 4), np.nan)
        for i, rec in enumerate(self.records):
            try:
                b = rec.bbox()
                if b.has_data:
                    box[i] = (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y)
            except Exception:
                pass
        self.box = box
        self.cls = _batched_backend_cls()

    def subset(self, r):
        import numpy as np
        b = self.box
        with np.errstate(invalid="ignore"):
            hit = (b[:, 0] <= r[2]) & (b[:, 2] >= r[0]) & (b[:, 1] <= r[3]) & (b[:, 3] >= r[1])
        return [self.records[i] for i in np.nonzero(hit)[0]]


def _png(index, r, out_path, dpi):
    from ezdxf.math import BoundingBox2d
    from ezdxf.addons.drawing import layout
    from ezdxf.addons.drawing.recorder import crop_records_rect
    m = index.master
    crop = BoundingBox2d([(r[0], r[1]), (r[2], r[3])])
    sub = index.cls()
    sub.config, sub.background, sub.properties = m.config, m.background, m.properties
    sub.records = crop_records_rect(index.subset(r), crop, max(_w(r), _h(r)) / 20000)
    w, h = _page_for(r)
    data = sub.get_pixmap_bytes(layout.Page(w, h), dpi=dpi, render_box=crop,
                                settings=layout.Settings(output_layers=False))
    with open(out_path, "wb") as f:
        f.write(data)


def _readable(color):
    """흰 바탕에서 안 보이는 밝은 색을 진하게. 색상(계통 구분)은 유지한다.
    흰색·연회색 → 검정, 노랑·하늘색 등 밝은 색 → 같은 색조로 어둡게."""
    try:
        h = color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return color
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if lum <= 140:
        return color
    if max(r, g, b) - min(r, g, b) < 40:          # 무채색(흰·회색)
        return "#000000" + h[6:]
    k = 120 / lum
    return "#%02x%02x%02x" % (int(r * k), int(g * k), int(b * k)) + h[6:]


def _draw(doc, layout_obj):
    from ezdxf.addons.drawing import Frontend, RenderContext, pymupdf, config
    be = pymupdf.PyMuPdfBackend()
    cfg = config.Configuration(
        background_policy=config.BackgroundPolicy.WHITE,
        color_policy=config.ColorPolicy.COLOR,          # 색은 유지(계통 구분용)
    )
    Frontend(RenderContext(doc), be, config=cfg).draw_layout(layout_obj, finalize=True)
    be.properties = {k: p._replace(color=_readable(p.color)) for k, p in be.properties.items()}
    return be


def render(doc, out_dir, base, dpi=DPI, max_sheets=MAX_SHEETS):
    """반환: {'images': [png], 'sheets': [{'id','png','도면번호','범위','texts','blocks'}], 'note': str}"""
    os.makedirs(out_dir, exist_ok=True)
    notes, sheets = [], []
    texts, inserts = _texts_and_blocks(doc)

    with _korean_font():
        # 1) 모델공간
        frames = find_frames(doc)
        kind = "도곽"
        if not frames:
            ext = _robust_extents(doc)
            if ext:
                frames = [ext] + _grid(ext)
                kind = "분할"
                notes.append("도곽을 찾지 못해 전체 개요 1장 + 2×2 분할 4장으로 대신함")
        if len(frames) > max_sheets:
            notes.append(f"도곽 {len(frames)}개 중 앞 {max_sheets}개만 이미지 생성")
            frames = frames[:max_sheets]

        if frames:
            index = _Index(_draw(doc, doc.modelspace()))
            for i, r in enumerate(frames, 1):
                sid = f"S{i:02d}"
                st = [(x, y, s) for x, y, s in texts if _in(x, y, r)]
                sb = {}
                for x, y, n in inserts:
                    if _in(x, y, r):
                        sb[n] = sb.get(n, 0) + 1
                no = _sheet_no(st) if kind == "도곽" else ""
                tag = "개요" if (kind == "분할" and i == 1) else no
                png = os.path.join(out_dir, f"{base}_{sid}" + (f"_{tag}" if tag else "") + ".png")
                try:
                    _png(index, r, png, dpi)
                except Exception as e:
                    notes.append(f"{sid} 이미지 실패: {e}")
                    png = ""
                # 위→아래, 왼→오 순으로 글자 정렬
                st.sort(key=lambda t: (-round(t[1] / max(_h(r) / 200, 1e-9)), t[0]))
                sheets.append({"id": sid, "png": png, "도면번호": no, "구분": kind,
                               "범위": [round(v, 1) for v in r],
                               "texts": [s for _x, _y, s in st], "blocks": sb})
            del index

        # 2) 종이공간(배치 탭) — 내용 있는 탭만
        for lay in doc.layouts:
            if lay.name == "Model" or len(lay) < 5:
                continue
            try:
                be = _draw(doc, lay)
                bb = be.player().bbox()
                if not bb.has_data:
                    continue
                r = _rect(bb.extmin.x, bb.extmin.y, bb.extmax.x, bb.extmax.y)
                sid = f"L{len([s for s in sheets if s['id'].startswith('L')]) + 1:02d}"
                safe = re.sub(r'[\\/:*?"<>|]', "_", lay.name)
                png = os.path.join(out_dir, f"{base}_{sid}_{safe}.png")
                _png(_Index(be), r, png, dpi)
                sheets.append({"id": sid, "png": png, "도면번호": "", "구분": f"배치:{lay.name}",
                               "범위": [round(v, 1) for v in r], "texts": [], "blocks": {}})
            except Exception as e:
                notes.append(f"배치 '{lay.name}' 이미지 실패: {e}")

    return {"images": [s["png"] for s in sheets if s["png"]], "sheets": sheets,
            "note": " / ".join(notes)}
