import os
import sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb_data import TOPICS
from detail_map import DETAIL
import markdown, os
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
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
def detail_html(cid):
    parts = [extract(f, pth) for f, pth in DETAIL.get(cid, [])]
    if not parts: return ''
    md = '\n\n'.join(parts)
    md = re.sub(r'^#{1,6} ', '#### ', md, flags=re.M)   # 제목 크기 통일
    md = md.replace('\\[', '').replace('\\]', '')
    return markdown.markdown(md, extensions=['tables', 'fenced_code'])


src, out = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()

# ---------- 1. 데이터 패치 ----------
m = re.search(r'(<script type="application/json" id="embedded-data">)(.*?)(</script>)', s, re.S)
cards = json.loads(m.group(2))
by_id = {c['id']: c for c in cards}

def patch_for(t):
    p = {'kw': t.get('kw', ''), 'kb': [list(x) for x in t.get('kb', [])], 'mnem': t.get('mnem', ''), 'warn': t.get('warn', ''), 'detail': detail_html(t['id'])}
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
    if p['warn'] and p['warn'] not in (core.get('warn') or ''):
        core['warn'] = (core['warn'] + ' · ' + p['warn']) if core.get('warn') else p['warn']
    core['kbTag'] = '지난주'
    c['core'] = core
    if p.get('detail'): c['detailHtml'] = p['detail']

for cid, p in PATCH.items():
    apply(by_id[cid], p)
for cid in DETAIL:
    if cid not in PATCH:
        if cid not in by_id: raise SystemExit('detail id missing '+cid)
        by_id[cid]['detailHtml'] = detail_html(cid)
        PATCH[cid] = {'detailOnly': True, 'detail': by_id[cid]['detailHtml']}

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
      cards.forEach(c=>{ const p = KB_PATCH[c.id]; if(p) applyKbPatch(c, p); });
      old = null;
    } else {
      cards = emb.length ? emb : DEFAULT_CARDS.slice();
    }"""
assert old_load in s
s = s.replace(old_load, new_load)

helpers = """
// ================= v19: 키워드판 =================
const KB_PATCH = """ + patch_js + """;
function applyKbPatch(c, p){
  if(p.detail) c.detailHtml = p.detail;
  if(p.detailOnly) return;
  const core = Object.assign({}, c.core||{});
  if(!core.one) core.one = c.def || '';
  core.kw = p.kw; core.kb = p.kb;
  if(p.mnem && !core.mnem) core.mnem = p.mnem;
  if(p.warn && (core.warn||'').indexOf(p.warn) < 0) core.warn = core.warn ? core.warn + ' · ' + p.warn : p.warn;
  core.kbTag = '지난주';
  c.core = core;
}
let readView = 'full';   // mini 초간단(두음만) · short 간단(핵심어+두음+❌) · full 길게(+키워드 표)
try{ readView = localStorage.getItem('gisulsa_view') || 'full'; }catch(e){}
const VIEW_NAME = {mini:'초간단', short:'간단', full:'길게'};
function cycleView(){ readView = readView==='mini' ? 'short' : (readView==='short' ? 'full' : 'mini'); try{ localStorage.setItem('gisulsa_view', readView); }catch(e){} render(); }
let readHide = false;
let revealed = {};
function toggleHide(){ readHide = !readHide; revealed = {}; try{ localStorage.setItem('gisulsa_hide', readHide?'1':'0'); }catch(e){} render(); }
try{ readHide = localStorage.getItem('gisulsa_hide')==='1'; }catch(e){}
function revealCard(id){ revealed[id] = true; const c = cards.find(x=>x.id===id); const el = document.getElementById('rc_'+id); if(el && c) el.outerHTML = rcardHtml(c); }
function kbHtml(core){
  if(!core.kb || !core.kb.length) return '';
  return `<table class="kb-tbl">${core.kb.map(r=>`<tr><th>${esc(r[0])}</th><td>${esc(r[1])}</td></tr>`).join('')}</table>`;
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
    ${readView!=='mini' && core.warn ? `<div class="r-warn">❌ ${esc(core.warn)}</div>` : ''}`}"""
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
s = s.replace(old_note, "    if(c.detailHtml) detail += `<div class=\"lbl\">📚 자세히 정리</div><div class=\"md-detail\">${c.detailHtml}</div>`;\n" + old_note, 1)

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
.kb-tbl td { color: #2c2c2a; padding: 4px 0; border-bottom: 1px dashed #eeece2; }
.md-detail { font-size: 13.5px; line-height: 1.6; color: #2c2c2a; }
.md-detail h4 { font-size: 14px; margin: 12px 0 4px; color: #444441; }
.md-detail table { width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 12.5px; }
.md-detail th, .md-detail td { border: 1px solid #e3e1d8; padding: 4px 6px; text-align: left; vertical-align: top; }
.md-detail th { background: #f5f4ef; }
.md-detail pre { background: #f5f4ef; border-radius: 8px; padding: 8px; overflow-x: auto; font-size: 12px; line-height: 1.4; }
.md-detail ul { padding-left: 18px; margin: 4px 0; }
.md-detail blockquote { margin: 6px 0; padding: 6px 10px; background: #faf9f5; border-left: 3px solid #d3d1c7; }
.reveal-btn { display: block; width: 100%; margin-top: 10px; border: 1px dashed #b4b2a9; background: #faf9f5; color: #444441; border-radius: 10px; padding: 12px; font-size: 14px; font-weight: 700; font-family: inherit; }
"""
s = s.replace("</style>", css + "</style>", 1)
s = s.replace('v18', 'v19', 0)

open(out, 'w', encoding='utf-8').write(s)
print('patched', len(patched), 'added', len(added))
print('added:', ', '.join(added))
