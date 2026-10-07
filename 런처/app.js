let DOMAINS = [], domain = null, BUILDINGS = [], DOCS = [],
    sel = null, running = false, es = null;
const CACHE = {};   // domain.key → {buildings, docs, sel}

const runLabel = () => (domain && domain.run_label) || "▶ 7종 문서 생성";

const $ = s => document.querySelector(s);
const listEl = $("#building-list"), searchEl = $("#search"), tabsEl = $("#domain-tabs"),
      cardsEl = $("#cards"), consoleEl = $("#console"), statusEl = $("#status"),
      runBtn = $("#run-all"), regBtn = $("#run-register"),
      selName = $("#sel-name"), selCode = $("#sel-code"), countEl = $("#count"),
      brandMark = $("#brand-mark"), brandTitle = $("#brand-title"), brandSub = $("#brand-sub");

async function init() {
  try {
    const d = await (await fetch("/api/domains")).json();
    DOMAINS = d.domains || [];
  } catch (e) {
    listEl.innerHTML = `<div class="loading">분야 로드 실패: ${esc(e)}</div>`;
    return;
  }
  renderTabs();
  const first = DOMAINS.find(d => d.available) || DOMAINS[0];
  if (first) selectDomain(first.key);
}

/* ── 분야 전환 ────────────────────────────────────────────── */
function renderTabs() {
  tabsEl.innerHTML = "";
  DOMAINS.forEach(d => {
    const b = document.createElement("button");
    b.className = "dtab" + (domain && domain.key === d.key ? " active" : "");
    b.textContent = d.label;
    if (!d.available) { b.classList.add("off"); b.title = "프로젝트 폴더를 찾을 수 없습니다"; }
    b.onclick = () => selectDomain(d.key);
    tabsEl.appendChild(b);
  });
}

async function selectDomain(key) {
  if (running) return;
  const d = DOMAINS.find(x => x.key === key);
  if (!d || (domain && domain.key === key)) return;
  domain = d;
  brandMark.textContent = d.mark;
  brandTitle.textContent = d.title;
  brandSub.textContent = d.sub;
  runBtn.textContent = runLabel();                       // 분야별 실행 버튼 문구
  regBtn.style.display = d.has_register ? "" : "none";   // 경영자료 버튼(해당 분야만)
  regBtn.disabled = running;
  renderTabs();

  const c = CACHE[key];
  sel = c ? c.sel : null;
  searchEl.value = "";
  showSelection();

  if (c) {
    BUILDINGS = c.buildings; DOCS = c.docs;
    countEl.textContent = BUILDINGS.length;
    renderList(filtered());
    return;
  }
  BUILDINGS = []; DOCS = [];
  countEl.textContent = "—";
  listEl.innerHTML = `<div class="loading">${esc(d.label)} 건물 목록 불러오는 중…</div>`;
  try {
    const r = await (await fetch(`/api/buildings?domain=${encodeURIComponent(key)}`)).json();
    if (domain.key !== key) return;                    // 로딩 중 다른 분야로 전환됨
    if (r.error) { listEl.innerHTML = `<div class="loading">${esc(r.error)}</div>`; return; }
    BUILDINGS = r.buildings || []; DOCS = r.docs || [];
    CACHE[key] = { buildings: BUILDINGS, docs: DOCS, sel: null };
    countEl.textContent = BUILDINGS.length;
    renderList(BUILDINGS);
  } catch (e) {
    listEl.innerHTML = `<div class="loading">목록 로드 실패: ${esc(e)}</div>`;
  }
}

/* ── 건물 목록 ────────────────────────────────────────────── */
function renderList(rows) {
  if (!rows.length) { listEl.innerHTML = `<div class="loading">건물 없음</div>`; return; }
  listEl.innerHTML = "";
  rows.forEach(b => {
    const el = document.createElement("div");
    el.className = "b-item" + (sel && sel.code === b.code ? " active" : "");
    el.innerHTML = `<span class="bn">${esc(b.name)}</span><span class="bc">${esc(b.sub || b.code)}</span>`;
    el.onclick = () => select(b);
    listEl.appendChild(el);
  });
}

function select(b) {
  if (running) return;
  sel = b;
  if (CACHE[domain.key]) CACHE[domain.key].sel = b;
  showSelection();
  renderList(filtered());
}

function showSelection() {
  selName.textContent = sel ? sel.name : "건물을 선택하세요";
  selCode.textContent = sel ? `${domain.label} · ${sel.code}` : "";
  runBtn.disabled = !sel;
  cardsEl.innerHTML = "";
  if (!sel) return;
  const cards = {};
  DOCS.forEach((name, i) => {
    const c = document.createElement("div");
    c.className = "card";
    c.innerHTML = `<div class="num">${i + 1}</div><div class="cn">${esc(name)}</div>` +
      `<div class="cs" data-cs>확인 중…</div>`;
    cardsEl.appendChild(c);
    cards[name] = c;
  });
  if (domain && domain.supports_docstatus) loadDocStatus(sel.code, cards);
  else applyCardMode(cards, {});          // 상태조회 미지원 분야
}

/* 카드에 완료/미완료·열기·생성 부착 */
function applyCardMode(cards, byName) {
  const canOne = domain && domain.supports_only;
  DOCS.forEach(name => {
    const c = cards[name]; if (!c) return;
    const cs = c.querySelector("[data-cs]");
    const st = byName[name];
    c.onclick = null; c.style.cursor = "default"; c.style.borderLeft = "";
    if (st && st.done) {                  // 작성완료 → 클릭하면 열기
      c.style.borderLeft = "4px solid #2e9e5b";
      cs.innerHTML = "✅ 작성완료 · <b>클릭하여 열기</b>";
      c.style.cursor = "pointer";
      c.onclick = () => openDoc(name);
    } else if (canOne) {                  // 미작성 → 클릭하면 생성
      c.style.borderLeft = "4px solid #cfd4dc";
      cs.textContent = "⬜ 미작성 · 클릭하여 생성";
      c.style.cursor = "pointer";
      c.onclick = () => runOne(name, c);
    } else {
      c.style.borderLeft = "4px solid #cfd4dc";
      cs.textContent = "⬜ 미작성";
    }
  });
}

async function loadDocStatus(code, cards) {
  let docs = [];
  try {
    const r = await (await fetch(`/api/docstatus?domain=${encodeURIComponent(domain.key)}&code=${encodeURIComponent(code)}`)).json();
    docs = r.docs || [];
  } catch (e) {}
  if (!sel || sel.code !== code) return;   // 그새 다른 건물 선택됨
  const byName = {}; docs.forEach(d => byName[d.doc] = d);
  applyCardMode(cards, byName);
}

function openDoc(name) {
  if (!sel) return;
  log(`📂 ${name} 여는 중…\n`, "warn");
  fetch(`/api/open?domain=${encodeURIComponent(domain.key)}&code=${encodeURIComponent(sel.code)}&doc=${encodeURIComponent(name)}`)
    .then(r => r.ok ? r.json() : Promise.reject())
    .then(j => log(j.opened ? `✅ 열었습니다 — ${name}\n` : `⚠ ${name} 열기 실패\n`, j.opened ? "ok" : "err"))
    .catch(() => log(`⚠ ${name} 파일을 찾을 수 없습니다\n`, "err"));
}

/* ── 개별 문서 생성(카드 클릭) ──────────────────────────────── */
function runOne(doc, cardEl) {
  if (!sel || running) return;
  running = true;
  runBtn.disabled = true; regBtn.disabled = true;
  cardEl && (cardEl.style.opacity = "0.55");
  setStatus("run", "실행 중");
  consoleEl.innerHTML = "";
  es = new EventSource(`/api/run_one?domain=${encodeURIComponent(domain.key)}&code=${encodeURIComponent(sel.code)}&doc=${encodeURIComponent(doc)}`);
  es.addEventListener("start", e => log(`▶ [${domain.label}] ${sel.name} · ${doc} 개별 생성 시작\n`, "warn"));
  es.addEventListener("line", onLine);
  es.addEventListener("done", e => finishOne(JSON.parse(e.data).returncode === 0, cardEl, doc));
  es.onerror = () => { if (running) finishOne(false, cardEl, doc); };
}

function finishOne(ok, cardEl, doc) {
  running = false;
  es && es.close(); es = null;
  cardEl && (cardEl.style.opacity = "");
  runBtn.disabled = !sel; regBtn.disabled = false;
  setStatus(ok ? "ok" : "err", ok ? "완료" : "종료(오류)");
  log(ok ? `\n✅ ${doc} 생성 완료 — 저장 폴더를 확인하세요.\n`
        : `\n⚠ ${doc} 생성 오류 — 로그를 확인하세요.\n`, ok ? "ok" : "err");
  if (ok && sel) refreshCards();          // 방금 만든 문서 → 작성완료로 갱신
}

function refreshCards() {
  // 콘솔은 두고 카드 상태만 다시 조회
  const cards = {};
  [...cardsEl.children].forEach(c => {
    const cn = c.querySelector(".cn"); if (cn) cards[cn.textContent] = c;
  });
  if (domain && domain.supports_docstatus && sel) loadDocStatus(sel.code, cards);
}

function filtered() {
  const q = searchEl.value.trim().toLowerCase();
  return !q ? BUILDINGS : BUILDINGS.filter(b =>
    b.name.toLowerCase().includes(q) || b.code.toLowerCase().includes(q));
}
searchEl.oninput = () => renderList(filtered());

/* ── 실행 ─────────────────────────────────────────────────── */
runBtn.onclick = () => {
  if (!sel || running) return;
  running = true;
  runBtn.classList.add("running");
  runBtn.textContent = "⏳ 생성 중…";
  setStatus("run", "실행 중");
  consoleEl.innerHTML = "";
  es = new EventSource(`/api/run?domain=${encodeURIComponent(domain.key)}&code=${encodeURIComponent(sel.code)}`);
  es.addEventListener("start", e => log(`▶ [${domain.label}] ${sel.name} (${sel.code}) 7종 문서 생성 시작\n`, "warn"));
  es.addEventListener("line", onLine);
  es.addEventListener("done", e => finish(JSON.parse(e.data).returncode === 0));
  es.onerror = () => { if (running) finish(false); };
};

function onLine(e) {
  const t = JSON.parse(e.data);
  log(t + "\n", /\[OK\]|SUCCESS|완료|성공/.test(t) ? "ok"
    : /\[FAIL\]|FAIL|오류|실패|Error|Traceback/.test(t) ? "err"
    : /SKIP|건너뜀/.test(t) ? "warn" : "");
}

/* ── 경영자료(통합관리대장) ─────────────────────────────────── */
regBtn.onclick = () => {
  if (running || !domain || !domain.has_register) return;
  running = true;
  regBtn.classList.add("running");
  regBtn.textContent = "⏳ 여는 중…";
  runBtn.disabled = true;
  setStatus("run", "실행 중");
  consoleEl.innerHTML = "";
  es = new EventSource(`/api/register?domain=${encodeURIComponent(domain.key)}`);
  es.addEventListener("start", e => log(`▶ [${domain.label}] 경영자료(통합관리대장) 생성·열기\n`, "warn"));
  es.addEventListener("line", onLine);
  es.addEventListener("done", e => finishReg(JSON.parse(e.data).returncode === 0));
  es.onerror = () => { if (running) finishReg(false); };
};

function finishReg(ok) {
  running = false;
  es && es.close(); es = null;
  regBtn.classList.remove("running");
  regBtn.textContent = "📊 경영자료(관리대장)";
  regBtn.disabled = false;
  runBtn.disabled = !sel;
  setStatus(ok ? "ok" : "err", ok ? "완료" : "종료(오류)");
  log(ok ? "\n✅ 통합관리대장을 열었습니다.\n" : "\n⚠ 오류로 종료됨 — 로그를 확인하세요.\n", ok ? "ok" : "err");
}

function finish(ok) {
  running = false;
  es && es.close(); es = null;
  runBtn.classList.remove("running");
  runBtn.textContent = runLabel();
  runBtn.disabled = !sel;
  setStatus(ok ? "ok" : "err", ok ? "완료" : "종료(오류)");
  log(ok ? "\n✅ 생성 완료 — 저장 폴더를 확인하세요.\n" : "\n⚠ 오류로 종료됨 — 로그를 확인하세요.\n", ok ? "ok" : "err");
  if (sel) refreshCards();                 // 7종 생성 후 카드 완료상태 갱신
}

function setStatus(cls, txt) { statusEl.className = "status " + cls; statusEl.textContent = txt; }
function log(t, cls) {
  const span = document.createElement("span");
  if (cls) span.className = cls;
  span.textContent = t;
  consoleEl.appendChild(span);
  consoleEl.scrollTop = consoleEl.scrollHeight;
}
function esc(s) { return String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }

init();
