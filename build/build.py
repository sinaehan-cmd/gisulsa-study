import os
import sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb_data import TOPICS
from detail_map import DETAIL
import markdown, os
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
# ---------- 📘 교재 노트 = 링크만 ----------
GH = 'https://github.com/sinaehan-cmd/gisulsa-study/blob/main/build/src/'
SRC_LINKS = {
  'sec_tb.md': ('교재_보안', 'https://docs.google.com/document/d/1e7F9zqf-XnfyBc5v9-iwfr8pJuK1K0yX1cRhhScwl6U/edit'),
  'ds_1112.md': ('디지털서비스 11/12 정리', 'https://drive.google.com/file/d/1-20UzIqYTra0LT5Aa6Dqq-ZpkS83UD72/view'),
  'pet_1115.md': ('PET·동형암호 11/15 정리', 'https://drive.google.com/file/d/19VsI0BRjmnhtXxQSaIwKz7sRFqE8lLvD/view'),
  'net_weekly_0107.md': ('네트워크 주간모의고사 정리', 'https://drive.google.com/file/d/1K9iBtnYr73zsQiAldPvpyLbyhRsJ1qCQ/view'),
}
try:
    SRC_LINKS.update(json.load(open(os.path.join(SRC, 'links.json'), encoding='utf-8')))
except FileNotFoundError:
    pass
def card_links(cid):
    out, seen = [], set()
    for f, _ in DETAIL.get(cid, []):
        if f in seen: continue
        seen.add(f)
        name, url = SRC_LINKS.get(f, (os.path.splitext(f)[0], GH + f))
        out.append([name, url])
    return out
def detail_html(cid):
    return ''

def _level(line):
    m = re.match(r'^(#{1,6}) ', line); return len(m.group(1)) if m else 0
def extract(fname, path):
    lines = open(os.path.join(SRC, fname), encoding='utf-8').read().split('\n')
    lo, hi = 0, len(lines)
    for want in path:
        found = None
        for i in range(lo, hi):
            if lines[i].startswith(want):
                found = i; break
        if found is None: raise SystemExit('heading not found: %s %s' % (fname, want))
        lv = _level(lines[found]); end = hi
        for j in range(found+1, hi):
            l2 = _level(lines[j])
            if l2 and l2 <= lv: end = j; break
        lo, hi = found, end
    return '\n'.join(lines[lo:hi])
EXCLUDE = re.compile(r'대화|오답|틀린|인출|암기송|노래|인수인계|다음 복습|복습|기록|채점|학생|사용자|피드백|진도|확인 수준|평가·오답|❌')
def strip_excluded(md):
    out, skip_lv = [], 0
    for line in md.split('\n'):
        lv = _level(line)
        if lv:
            if skip_lv and lv <= skip_lv: skip_lv = 0
            if not skip_lv and EXCLUDE.search(line): skip_lv = lv; continue
        if not skip_lv: out.append(line)
    return '\n'.join(out)
def detail_html(cid):
    parts = [strip_excluded(extract(f, pth)) for f, pth in DETAIL.get(cid, []) if not any(EXCLUDE.search(h) for h in pth)]
    parts = [x for x in parts if x.strip()]
    if not parts: return ''
    md = '\n\n'.join(parts)
    md = re.sub(r'^#{1,6} ', '#### ', md, flags=re.M)   # 제목 크기 통일
    md = md.replace('\\[', '').replace('\\]', '')
    return markdown.markdown(md, extensions=['tables', 'fenced_code'])


src, out = sys.argv[1], sys.argv[2]
DATA_VER_STR = sys.argv[3] if len(sys.argv) > 3 else 'v19-20261116'
s = open(src, encoding='utf-8').read()

# ---------- 1. 데이터 패치 ----------
m = re.search(r'(<script type="application/json" id="embedded-data">)(.*?)(</script>)', s, re.S)
cards = json.loads(m.group(2))
by_id = {c['id']: c for c in cards}

def short_warn(w):
    segs = [x.strip() for x in re.split(r' · |→ 밤|; ', w or '') if x.strip()]
    w2 = ' · '.join(segs[-2:])
    return w2 if len(w2) <= 90 else w2[:88] + '…'
def patch_for(t):
    t = dict(t); t['warn'] = ''
    p = {'kw': t.get('kw', ''), 'kb': [list(x) for x in t.get('kb', [])], 'mnem': t.get('mnem', ''), 'warn': t.get('warn', ''), 'detail': '', 'links': card_links(t['id']), 'pair': t.get('pair', ''), 'defn': ('' if t.get('new') else t.get('defn', '')), 'fmt': t.get('fmt', 0)}
    return p

PATCH = {}
added, patched = [], []
for t in TOPICS:
    if t.get('new'):
        if t['id'] in by_id:
            raise SystemExit('dup id ' + t['id'])
        c = {"type": "concept", "difficult": False, "reviewStage": 0, "lastReviewDate": None, "diagram": None,
             "freenote": "", "related": [], "itemAName": "", "itemBName": "", "compareRows": [],
             "id": t['id'], "title": t['title'], "en": t.get('en', ''), "def": t.get('defn', ''),
             "features": [], "rows": [], "note": "", "subject": t['subject'],
             "core": {"one": t.get('defn', ''), "mnem": t.get('mnem', ''), "warn": t.get('warn', '')}}
        c['rows'] = [{"div": r[0], "comp": r[1], "desc": (r[2] if len(r) > 2 else "")} for r in t.get('kb', [])]
        c['features'] = [x.strip() for x in re.split(r'[·,]', t.get('kw', '')) if x.strip()][:6]
        cards.append(c); by_id[c['id']] = c; added.append(t['title'])
    else:
        if t['id'] not in by_id:
            raise SystemExit('missing id ' + t['id'])
        patched.append(t['title'])
    PATCH[t['id']] = patch_for(t)


# 패치 적용 (JS와 같은 규칙: 기존 두음 유지, ❌는 덧붙이기)
def apply(c, p):
    core = dict(c.get('core') or {})
    if not core.get('one'):
        core['one'] = c.get('def') or ''
    core['kw'] = p['kw']
    core['kb'] = p['kb']
    if p['mnem'] and not core.get('mnem'):
        core['mnem'] = p['mnem']
    core['warn'] = p.get('baseWarn', '')
    core['kbTag'] = '지난주'
    core['pair'] = p.get('pair', '')
    core['fmt'] = p.get('fmt', 0)
    if p.get('defn'): c['def'] = p['defn']
    c['core'] = core
    c['detailHtml'] = ''
    c['links'] = p.get('links', [])

for cid, p in PATCH.items():
    if 'detailOnly' not in p:
        p['baseWarn'] = '' if (cid.startswith('kb_') or p.get('pair')) else ((by_id[cid].get('core') or {}).get('warn') or '')
for cid, p in PATCH.items():
    apply(by_id[cid], p)
for cid in DETAIL:
    if cid not in PATCH:
        if cid not in by_id: raise SystemExit('detail id missing '+cid)
        by_id[cid]['detailHtml'] = ''
        by_id[cid]['links'] = card_links(cid)
        PATCH[cid] = {'detailOnly': True, 'detail': '', 'links': by_id[cid]['links']}


# ---------- 학원 중요도(최상·상·중·하) ----------
import csv as _csv
IMP_RANK = {'최상': 4, '상': 3, '중': 2, '하': 1}
def _n(x): return re.sub(r'[^0-9a-z가-힣]', '', (x or '').lower())
def _main(x): return _n(re.split(r'[(（]', x or '')[0])
_rows = list(_csv.DictReader(open(os.path.join(SRC, '학원토픽.csv'), encoding='utf-8-sig')))
_imp_topics = [(_n(r['토픽']), _main(r['토픽']), r['중요도']) for r in _rows if r['중요도'] in IMP_RANK]
def find_imp(title, en=''):
    cands = {_n(title), _main(title)}
    if en: cands |= {_main(en)}
    cands = {c for c in cands if len(c) >= 2}
    best = ''
    for full, main, imp in _imp_topics:
        hit = any(c == full or c == main for c in cands)
        if not hit:
            hit = any(len(c) >= 4 and (c in full or (len(main) >= 4 and main in c)) for c in cands)
        if hit and IMP_RANK[imp] > IMP_RANK.get(best, 0):
            best = imp
    return best
IMP_OVERRIDE = {t['id']: t['imp'] for t in TOPICS if t.get('imp')}
for c in cards:
    if c.get('type') == 'problem': continue
    imp = IMP_OVERRIDE.get(c['id']) or find_imp(c.get('title',''), c.get('en',''))
    if imp: c['imp'] = imp
    elif 'imp' in c: del c['imp']
IMP_MAP = {c['id']: c['imp'] for c in cards if c.get('imp')}
data_json = json.dumps(cards, ensure_ascii=False).replace('</', '<\\/')
s = s[:m.start(2)] + data_json + s[m.end(2):]

# ---------- 2. 버전 · 로딩(내가 고친 것 보존 + 패치) ----------
s = s.replace("const DATA_VER = 'v18-20261109';", "const DATA_VER = '" + (sys.argv[3] if len(sys.argv)>3 else 'v19-20261116') + "';")
patch_js = json.dumps(PATCH, ensure_ascii=False).replace('</', '<\\/')
old_load = """    cards = emb.length ? emb : DEFAULT_CARDS.slice();
    let old = (ls && Array.isArray(ls.cards)) ? ls.cards : null;"""
new_load = """    let old = (ls && Array.isArray(ls.cards)) ? ls.cards : null;
    if(old && old.length && emb.length){     // v19: 이전 버전에서 고친 카드는 그대로 두고, 새 카드만 추가 + 키워드판 패치
      const have = {}; old.forEach(o=>{ if(o && o.id) have[o.id]=1; });
      cards = old.concat(emb.filter(c=>!have[c.id]));
      cards.forEach(c=>{ const p = KB_PATCH[c.id]; if(p) applyKbPatch(c, p); if(IMP_MAP[c.id]) c.imp = IMP_MAP[c.id]; });
      old = null;
    } else {
      cards = emb.length ? emb : DEFAULT_CARDS.slice();
    }"""
assert old_load in s
s = s.replace(old_load, new_load)

helpers = """
// ================= v19: 키워드판 =================
const IMP_MAP = """ + json.dumps(IMP_MAP, ensure_ascii=False) + """;
const KB_PATCH = """ + patch_js + """;
function applyKbPatch(c, p){
  c.detailHtml = p.detail || '';
  c.links = p.links || [];
  if(p.detailOnly) return;
  const core = Object.assign({}, c.core||{});
  if(!core.one) core.one = c.def || '';
  core.kw = p.kw; core.kb = p.kb;
  if(p.mnem && !core.mnem) core.mnem = p.mnem;
  core.warn = p.baseWarn || '';
  core.kbTag = '지난주';
  core.pair = p.pair || '';
  core.fmt = p.fmt || 0;
  if(p.defn) c.def = p.defn;
  c.core = core;
}
let readView = 'short';   // mini 초간단(두음만) · short 간단(핵심어+두음, 기본) · full 길게(+키워드 표·❌)
try{ readView = localStorage.getItem('gisulsa_view2') || 'short'; }catch(e){}
const VIEW_NAME = {mini:'초간단', short:'간단', full:'길게'};
function cycleView(){ readView = readView==='mini' ? 'short' : (readView==='short' ? 'full' : 'mini'); try{ localStorage.setItem('gisulsa_view2', readView); }catch(e){} render(); }
let readHide = false;
let revealed = {};
function toggleHide(){ readHide = !readHide; revealed = {}; try{ localStorage.setItem('gisulsa_hide', readHide?'1':'0'); }catch(e){} render(); }
try{ readHide = localStorage.getItem('gisulsa_hide')==='1'; }catch(e){}
function revealCard(id){ revealed[id] = true; const c = cards.find(x=>x.id===id); const el = document.getElementById('rc_'+id); if(el && c) el.outerHTML = rcardHtml(c); }
function kbHtml(core){
  if(!core.kb || !core.kb.length) return '';
  const three = core.kb.some(r=>r[2]);
  return `<table class="kb-tbl">${core.kb.map(r=>`<tr><th>${esc(r[0])}</th><td><b>${esc(r[1])}</b>${three && r[2] ? `<div class="kb-desc">${esc(r[2])}</div>` : ''}</td></tr>`).join('')}</table>`;
}
"""
anchor = "// ---------- 평가 ----------"
assert anchor in s
s = s.replace(anchor, helpers + anchor, 1)

# getCore: 기본값 위에 저장된 core를 덮어써서 kw·kb가 사라지지 않게
old_gc = "  if(c.core && (c.core.one || c.core.mnem)) return c.core;"
assert old_gc in s
s = s.replace(old_gc, "  if(c.core && (c.core.one || c.core.mnem)) return c.core;\n  if(c.core && (c.core.kw || (c.core.kb||[]).length)) return Object.assign({one: c.def||''}, c.core);")

# ---------- 3. 읽기 카드: 핵심어 · 키워드판 표 · 가리기 ----------
old_mid = """    ${core.one ? `<div class="r-one">${esc(core.one)}</div>` : ''}
    ${core.mnem ? `<div class="r-mnem">🎵 ${esc(core.mnem)}</div>` : ''}
    ${core.warn ? `<div class="r-warn">⚠ ${esc(core.warn)}</div>` : ''}"""
assert old_mid in s
new_mid = """    ${hidden ? `<button class="reveal-btn" onclick="revealCard('${c.id}')">👀 말로 먼저 해보고 → 펼치기</button>` : `
    ${readView!=='mini' ? (core.kw ? `<div class="r-kw">🔑 ${esc(core.kw)}</div>` : (core.one ? `<div class="r-one">${esc(core.one)}</div>` : '')) : ''}
    ${core.mnem ? `<div class="r-mnem">🎵 ${esc(core.mnem)}</div>` : (readView==='mini' && core.one ? `<div class="r-one">${esc(core.one)}</div>` : '')}
    ${readView==='full' ? kbHtml(core) : ''}
    ${core.warn ? (readView==='full' ? `<div class="r-warn">❌ ${esc(core.warn)}</div>` : `<span class="warn-chip">❌ 헷갈림·틀린 것 있음 — 자세히</span>`) : ''}`}"""
s = s.replace(old_mid, new_mid)
old_open = "  const open = !!openDetail[c.id];\n  let detail = '';"
assert old_open in s
s = s.replace(old_open, "  const open = !!openDetail[c.id];\n  const hidden = readHide && !revealed[c.id] && !todayR;\n  let detail = '';")
# 정의 한 줄은 자세히 안에서 보이게 (핵심어가 대신 위에 나옴)
s = s.replace("      if(c.def) detail += `<div class=\"lbl\">정의</div><div>${esc(c.def)}</div>`;",
              "      if(c.def) detail += `<div class=\"lbl\">정의</div><div>${esc(c.def)}</div>`;\n      else if(core.one) detail += `<div class=\"lbl\">정의</div><div>${esc(core.one)}</div>`;")

# 필터: 📌 키워드판 + 가리기 버튼
old_f = "${f('all','전체')}${f('weak','🌱🌿 약한 것')}${f('new','안 본 것')}${f('warn','⚠ 고질병')}"
assert old_f in s
s = s.replace(old_f, "${f('kb','📌 키워드판')}${f('all','전체')}${f('weak','🌱🌿 약한 것')}${f('new','안 본 것')}${f('warn','⚠ 고질병')}<button class=\"${readHide?'on':''}\" onclick=\"toggleHide()\">${readHide?'🙈 가리기 켬':'🙈 가리기'}</button><button onclick=\"cycleView()\">👁 ${VIEW_NAME[readView]}</button>")
old_rp = "    if(readFilter==='warn') return !!getCore(c).warn;"
assert old_rp in s
s = s.replace(old_rp, old_rp + "\n    if(readFilter==='kb') return !!(c.core && c.core.kbTag);")
# 키워드판 필터는 과목 상관없이 보고 싶을 때가 많으니 goRead와 같은 처리
s = s.replace(".read-filter { display: flex; gap: 6px; margin-top: 8px; }",
              ".read-filter { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }")

# 홈에 키워드판 바로가기 퀘스트
old_q = "    {ico:'⚔️', title:'⚠ 고질병 카드 3장 \"알아\"'"
assert old_q in s
kbq = """    (()=>{ const kbc = cards.filter(c=>c.core && c.core.kbTag); const n = kbc.filter(c=>log.rated[c.id]).length; return {ico:'📌', title:'키워드판 한 바퀴 (가리고 말해보기)', sub:'지난주 공부한 '+kbc.length+'토픽', cur:n, target:kbc.length, done: kbc.length>0 && n>=kbc.length, go:"readHide=true;revealed={};goRead(null,'kb')"}; })(),
"""
s = s.replace(old_q, kbq + old_q, 1)

# 자세히 열면 정리 노트(detailHtml) 보이기
old_note = "    if(c.note) detail += `<div class=\"lbl\">특기사항</div>"
assert old_note in s
s = s.replace(old_note, "    if(c.detailHtml) detail += `<details class=\"md-wrap\"><summary>📚 교재 노트 펼치기</summary><div class=\"md-detail\">${c.detailHtml}</div></details>`;\n" + old_note, 1)

# 편집 저장 시 kw·kb 유지
for fid in ('f', 'cf'):
    o = "core: {one: document.getElementById('%s_one').value.trim(), mnem: document.getElementById('%s_mnem').value.trim(), warn: document.getElementById('%s_warn').value.trim()}" % (fid, fid, fid)
    assert o in s, fid
    s = s.replace(o, "core: Object.assign({}, (editing!==null && cards[editing] && cards[editing].core)||{}, {one: document.getElementById('%s_one').value.trim(), mnem: document.getElementById('%s_mnem').value.trim(), warn: document.getElementById('%s_warn').value.trim()})" % (fid, fid, fid))

# CSS
css = """
.r-kw { font-size: 14.5px; color: #2c2c2a; line-height: 1.55; margin-top: 7px; font-weight: 600; }
.kb-tbl { width: 100%; border-collapse: collapse; margin-top: 7px; font-size: 13px; line-height: 1.45; }
.kb-tbl th { text-align: left; white-space: nowrap; vertical-align: top; color: #5f5e5a; font-weight: 700; padding: 4px 8px 4px 0; width: 1%; }
.kb-tbl td { color: #2c2c2a; padding: 4px 0; border-bottom: 1px dashed #eeece2; word-break: keep-all; overflow-wrap: anywhere; }
.md-detail { font-size: 13.5px; line-height: 1.6; color: #2c2c2a; }
.md-detail h4 { font-size: 14px; margin: 12px 0 4px; color: #444441; }
.md-detail table { width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 12.5px; }
.md-detail th, .md-detail td { border: 1px solid #e3e1d8; padding: 4px 6px; text-align: left; vertical-align: top; word-break: keep-all; overflow-wrap: anywhere; }
.md-detail th { background: #f5f4ef; }
.md-detail pre { background: #f5f4ef; border-radius: 8px; padding: 8px; overflow-x: auto; font-size: 12px; line-height: 1.4; }
.md-detail ul { padding-left: 18px; margin: 4px 0; }
.md-detail blockquote { margin: 6px 0; padding: 6px 10px; background: #faf9f5; border-left: 3px solid #d3d1c7; }
.md-wrap { margin-top: 10px; } .md-wrap summary { cursor: pointer; font-weight: 700; color: #5f5e5a; font-size: 13px; padding: 6px 0; }
.kb-desc { font-weight: 400; color: #6b6a64; font-size: 12.5px; margin-top: 2px; }
.kb-tbl td b { font-weight: 700; }
.pair { font-size: 13px; line-height: 1.55; background: #f3f1fa; border-radius: 8px; padding: 7px 10px; color: #3b3560; }
.reveal-btn { display: block; width: 100%; margin-top: 10px; border: 1px dashed #b4b2a9; background: #faf9f5; color: #444441; border-radius: 10px; padding: 12px; font-size: 14px; font-weight: 700; font-family: inherit; }
"""
s = s.replace("</style>", css + "</style>", 1)
s = s.replace('v18', 'v19', 0)


# ---------- 중요도 배지 · ⭐ 필터 · 오늘 결과 복사 ----------
old_head = "<span class=\"r-title\">${c.type==='compare'?'🔀 ':''}${esc(c.title)}</span>"
assert old_head in s, 'head'
s = s.replace(old_head, old_head + "${c.imp ? `<span class=\"imp imp${IMP_RANK_JS[c.imp]}\">${c.imp}</span>` : ''}", 1)
s = s.replace("${f('kb','📌 키워드판')}", "${f('kb','📌 키워드판')}${f('top','⭐ 최상·상')}", 1)
s = s.replace("    if(readFilter==='kb') return !!(c.core && c.core.kbTag);",
              "    if(readFilter==='kb') return !!(c.core && c.core.kbTag);\n    if(readFilter==='top') return c.imp==='최상' || c.imp==='상';", 1)
ob = '<button onclick="cycleView()">👁 ${VIEW_NAME[readView]}</button>'
assert ob in s, 'viewbtn'
s = s.replace(ob, ob + '<button onclick="copyToday()">📋 오늘 결과 복사</button>', 1)
s = s.replace("let readHide = false;", """const IMP_RANK_JS = {'최상':4,'상':3,'중':2,'하':1};
function copyToday(){
  const t = localDate(); const log = prog.log[t] || {rated:{}};
  const by = {1:[],2:[],3:[]};
  Object.keys(log.rated).forEach(id=>{ const c = cards.find(x=>x.id===id); if(c) by[log.rated[id]].push(c.title + (c.imp?'('+c.imp+')':'')); });
  const n = by[1].length + by[2].length + by[3].length;
  const txt = `[암기노트 ${t}] ${n}장 · 알아 ${by[3].length} · 애매 ${by[2].length} · 몰라 ${by[1].length}\\n몰라: ${by[1].join(', ')||'-'}\\n애매: ${by[2].join(', ')||'-'}\\n알아: ${by[3].join(', ')||'-'}`;
  const done = ()=> showToast('📋 복사했어요 — Claude나 GPT 채팅에 붙여넣기');
  try{ navigator.clipboard.writeText(txt).then(done, ()=>prompt('이 글을 복사해 주세요', txt)); }catch(e){ prompt('이 글을 복사해 주세요', txt); }
}
let readHide = false;""", 1)
s = s.replace(".reveal-btn {", """.imp { display: inline-block; margin-left: 6px; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 1px 6px; vertical-align: 2px; }
.imp4 { background: #b5442a; color: #fff; } .imp3 { background: #e48ab0; color: #fff; } .imp2 { background: #eeece2; color: #5f5e5a; } .imp1 { background: #f5f4ef; color: #9a988f; }
.reveal-btn {""", 1)

# ---------- 자세히: 기출 문항 원문 · 교재 링크 ----------
TEXTBOOK = {'sec_tb.md': ('교재_보안', 'https://docs.google.com/document/d/1e7F9zqf-XnfyBc5v9-iwfr8pJuK1K0yX1cRhhScwl6U/edit'),
            'ds_1112.md': ('교재_DS', 'https://docs.google.com/document/d/16ifPWsEtq7SEwIhKu5-8moU5lRYILHZ3KTmvkc6PyiE/edit')}
TB_MAP = {}
for cid, lst in DETAIL.items():
    for f, _ in lst:
        if f in TEXTBOOK: TB_MAP[cid] = TEXTBOOK[f]
old_g = "    if(c.gichul && c.gichul.n) detail += `<div class=\"lbl\">기출</div><div>${c.gichul.n}회 출제 ${gcBadge(c,true)}</div>`;"
assert old_g in s, 'gichul'
new_g = """    if(c.gichul && c.gichul.n){
      detail += `<div class="lbl">📝 기출 ${c.gichul.n}회 ${gcBadge(c,true)} — 이 문제들에 다 답할 수 있나?</div><ol class="gc-list">${(c.gichul.list||[]).map(q=>`<li><b>${q[0]}회 ${esc(q[1]||'')} ${q[2]}교시</b> ${esc(q[3]||'')}${(q[3]||'').length>=80?'…':''}</li>`).join('')}</ol>`;
    }
    if(core.pair) detail += `<div class="lbl">🔀 헷갈리는 짝</div><div class="pair">${esc(core.pair)}</div>`;
    if((c.links||[]).length) detail += `<div class="lbl">📘 교재 노트</div>${c.links.map(l=>`<a class="tb-link" href="${l[1]}" target="_blank">${esc(l[0])} 열기</a>`).join(' ')}`;"""
s = s.replace(old_g, new_g, 1)
s = s.replace("let readHide = false;", "const TB_MAP = " + json.dumps(TB_MAP, ensure_ascii=False) + ";\nlet readHide = false;", 1)
s = s.replace(".reveal-btn {", """.gc-list { margin: 4px 0 0; padding-left: 20px; font-size: 12.5px; line-height: 1.5; color: #444441; }
.gc-list li { margin-bottom: 4px; }
.tb-link { display: inline-block; margin-top: 4px; background: #eef4fb; color: #1d4f91; border-radius: 8px; padding: 6px 10px; font-size: 13px; font-weight: 700; text-decoration: none; }
.reveal-btn {""", 1)

# ---------- 🔄 새 내용 받기: 앱이 깃에서 update.json을 가져와 합침 ----------
UPDATE_URL = 'https://raw.githubusercontent.com/sinaehan-cmd/gisulsa-study/main/app/update.json'
_new_ids = [t['id'] for t in TOPICS if t.get('new')]
_upd = {'ver': DATA_VER_STR, 'cards': [by_id[i] for i in _new_ids], 'patch': PATCH, 'imp': IMP_MAP, 'tb': TB_MAP}
open(os.path.join(os.path.dirname(os.path.abspath(out)), 'update.json'), 'w', encoding='utf-8').write(json.dumps(_upd, ensure_ascii=False))
pull_js = """
const UPDATE_URL = '""" + UPDATE_URL + """';
function pullUpdate(manual){
  if(!manual){ try{ if(localStorage.getItem('gisulsa_upd_day')===localDate()) return; }catch(e){} }
  if(manual) showToast('🔄 새 내용 확인 중…');
  fetch(UPDATE_URL + '?t=' + Date.now()).then(r=>{ if(!r.ok) throw new Error(r.status); return r.json(); }).then(u=>{
    try{ localStorage.setItem('gisulsa_upd_day', localDate()); }catch(e){}
    const have = {}; cards.forEach(c=>have[c.id]=c);
    let added = 0, touched = 0;
    (u.cards||[]).forEach(c=>{ if(!have[c.id]){ cards.push(normalizeCard(c)); have[c.id]=cards[cards.length-1]; added++; } });
    Object.keys(u.patch||{}).forEach(id=>{ const c = have[id]; if(!c) return; const before = JSON.stringify([c.core, c.detailHtml]); applyKbPatch(c, u.patch[id]); if(JSON.stringify([c.core, c.detailHtml])!==before) touched++; });
    Object.keys(u.imp||{}).forEach(id=>{ if(have[id]) have[id].imp = u.imp[id]; });
    Object.assign(TB_MAP, u.tb||{});
    saveCards();
    if(added || touched){ render(); showToast('✅ 새 카드 '+added+'장 · 보강 '+touched+'장 받았어요'); }
    else if(manual) showToast('이미 최신이에요 👍');
  }).catch(e=>{ if(manual) showToast('인터넷 연결을 확인해 주세요'); });
}
"""
s = s.replace("let readHide = false;", pull_js + "let readHide = false;", 1)
# 버튼: 읽기 화면 · 홈 모드 바
mb = "return `<div class=\"mode-bar\">${b('home','🏠 오늘')}${b('read','📖 읽기')}${b('cards','🗂 카드')}</div>`;"
assert mb in s, 'modebar'
s = s.replace(mb, "return `<div class=\"mode-bar\">${b('home','🏠 오늘')}${b('read','📖 읽기')}${b('cards','🗂 카드')}<button class=\"mode-btn upd-btn\" onclick=\"pullUpdate(true)\" title=\"새 내용 받기\">🔄</button></div>`;", 1)
# 앱 열 때 하루 한 번 자동 확인
s = s.replace("\nloadCards();\n</script>", "\nloadCards();\nsetTimeout(()=>pullUpdate(false), 800);\n</script>", 1)
assert "pullUpdate(false)" in s, 'autoload'
s = s.replace(".reveal-btn {", ".upd-btn { flex: 0 0 auto !important; width: 52px; }\n.reveal-btn {", 1)

# ---------- 자세히 맨 위: 키워드 표 · 내가 틀린 것 ----------
old_det = "  if(open){\n    if(c.type==='compare'){"
assert old_det in s, 'det'
s = s.replace(old_det, "  if(open){\n    if(readView!=='full' && (core.kb||[]).length) detail += `<div class=\"lbl\">📌 키워드 설명</div>${kbHtml(core)}`;\n    if(readView!=='full' && core.warn) detail += `<div class=\"lbl\">❌ 헷갈림 · 내가 틀린 것</div><div class=\"r-warn\" style=\"margin-top:2px\">${esc(core.warn)}</div>`;\n    if(c.type==='compare'){", 1)
s = s.replace(".reveal-btn {", ".warn-chip { display: inline-block; margin-top: 7px; background: #fdeceb; color: #8f2a22; border-radius: 8px; padding: 3px 8px; font-size: 12px; font-weight: 700; }\n.reveal-btn {", 1)

# ---------- 읽기 자세히: 새 카드는 📌 키워드 설명 표가 곧 구성요소라 중복 표시 안 함 ----------
of = "      if((c.features||[]).length) detail += `<div class=\"lbl\">특징</div>"
assert of in s, 'feat'
s = s.replace(of, "      const kbNew = c.id.indexOf('kb_')===0;\n      if(!kbNew && (c.features||[]).length) detail += `<div class=\"lbl\">특징</div>", 1)
orow = "      if((c.rows||[]).length) detail += `<div class=\"lbl\">구성요소</div>"
assert orow in s, 'rows'
s = s.replace(orow, "      if(!kbNew && (c.rows||[]).length) detail += `<div class=\"lbl\">구성요소</div>", 1)

# ---------- 300장 자동 변환: kb 없는 카드는 구성요소 표·특징으로 새 화면 ----------
oc = "function rcardHtml(c){\n  const core = getCore(c);"
assert oc in s, 'core'
s = s.replace(oc, "function rcardHtml(c){\n  const core = withAuto(c, getCore(c));", 1)
s = s.replace("let readHide = false;", """function withAuto(c, core){
  if((core.kb||[]).length || !(c.rows||[]).length) return core;
  const kb = c.rows.filter(r=>r && (r.comp||r.div)).map(r=>[r.div||'', r.comp||'', r.desc||'']);
  const kw = core.kw || [].concat(c.features||[], c.rows.map(r=>r.comp).filter(Boolean)).join(' · ');
  return Object.assign({}, core, {kb: kb, kw: kw, _auto: true});
}
let readHide = false;""", 1)
ok = "      const kbNew = c.id.indexOf('kb_')===0;"
assert ok in s, 'kbnew'
s = s.replace(ok, "      const kbNew = c.id.indexOf('kb_')===0 || !!core._auto;", 1)

# 11/17: v18 warn은 '헷갈리는 짝'으로만 (오답 표시·앞면 칩 제거)
w1 = "    if(readView!=='full' && core.warn) detail += `<div class=\"lbl\">❌ 헷갈림 · 내가 틀린 것</div><div class=\"r-warn\" style=\"margin-top:2px\">${esc(core.warn)}</div>`;"
assert w1 in s, 'w1'
s = s.replace(w1, "", 1)
w2 = "    if(core.pair) detail += `<div class=\"lbl\">🔀 헷갈리는 짝</div><div class=\"pair\">${esc(core.pair)}</div>`;"
assert w2 in s, 'w2'
s = s.replace(w2, "    { const pr = [core.pair, core.warn].filter(Boolean).join(' / '); if(pr) detail += `<div class=\"lbl\">🔀 헷갈리는 짝</div><div class=\"pair\">${esc(pr)}</div>`; }", 1)
w3 = "    ${core.warn ? (readView==='full' ? `<div class=\"r-warn\">❌ ${esc(core.warn)}</div>` : `<span class=\"warn-chip\">❌ 헷갈림·틀린 것 있음 — 자세히</span>`) : ''}"
assert w3 in s, 'w3'
s = s.replace(w3, "", 1)

# 11/17: fmt=3 정식 카드는 옛 표·특징·비교표·특기사항 숨김
f1 = "      const kbNew = c.id.indexOf('kb_')===0 || !!core._auto;"
assert f1 in s, 'f1'
s = s.replace(f1, "      const kbNew = c.id.indexOf('kb_')===0 || !!core._auto || core.fmt===3;", 1)
f2 = "    if(c.type==='compare'){"
assert f2 in s, 'f2'
s = s.replace(f2, "    if(c.type==='compare' && core.fmt!==3){", 1)
f3 = "    if(c.note) detail += `<div class=\"lbl\">특기사항</div>"
assert f3 in s, 'f3'
s = s.replace(f3, "    if(c.note && core.fmt!==3) detail += `<div class=\"lbl\">특기사항</div>", 1)
open(out, 'w', encoding='utf-8').write(s)
print('patched', len(patched), 'added', len(added))
print('added:', ', '.join(added))
