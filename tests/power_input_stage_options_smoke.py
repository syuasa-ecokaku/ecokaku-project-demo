"""Battery input-stage labels, withdrawal empty state and saved-value stage filters."""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import fixture
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-power-input-stages-review')
STAGES=['すべて','基本情報','接続検討','本申込','名義・設備変更','連系準備','受電・送電','商業運転','市場参入']
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[]
 raw=(ROOT/'index.html').read_text();baseline=subprocess.check_output(['git','show','36dd6e0:index.html'],cwd=ROOT,text=True)
 with server() as url,sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1500,'height':1300});p.on('pageerror',lambda e:errors.append(str(e)));p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');f.locator('[data-page=power]').click();m=f.locator('#power-workspace');m.locator('[data-power-tab=bulk]').click()
  def done(s):passed.append(s);print('PASS',s,flush=True)
  def ids():return m.locator('[data-power-bulk-row]').evaluate_all('(es)=>es.map(e=>e.dataset.powerBulkRow)')
  def cell(id,key):return m.locator('[data-power-bulk-row="'+id+'"] [data-power-field="'+key+'"]')
  expected=['接続検討','本申込・支払','名義・設備変更','連系準備・受電','商用運転・市場参入','取下']
  assert m.locator('#power-bulk-stage option').all_text_contents()==expected
  assert m.locator('#power-input-current-stage option').all_text_contents()==STAGES
  for key,label in zip(['connection','main','aggregator','grid','operation','withdrawal'],expected):
   m.locator('#power-bulk-stage').select_option(key);assert m.locator('#power-bulk-heading').inner_text()==label;assert len(ids())==10
  assert '取下関連の入力項目は現在未定義' in m.inner_text();assert m.locator('thead th').all_text_contents()==['案件番号','申請案件名','担当者','対応状態（共通）','対応期限（共通）','詳細']
  cell('G-00003','commonStatus').select_option('保留');m.locator('#power-bulk-stage').select_option('aggregator');assert cell('G-00003','commonStatus').input_value()=='保留';assert cell('G-00003','69').count()==1
  m.locator('[data-power-action=cancelAll]').click();assert cell('G-00003','commonStatus').input_value()=='未着手'
  before=cell('G-00003','69').input_value();cell('G-00003','69').fill('2026-11-05');m.locator('[data-power-action=saveAll]').click();m.locator('#power-input-current-stage').select_option('changes');assert 'G-00003' in ids()
  m.locator('[data-power-action=clearFilters]').click();assert len(ids())==10 and m.locator('#power-input-current-stage').input_value()==''
  m.locator('#power-bulk-stage').select_option('aggregator');assert cell('G-00003','69').input_value()=='2026-11-05';cell('G-00003','69').fill(before);m.locator('[data-power-action=saveAll]').click()
  done('both lists have the specified labels/order; all six groups render; withdrawal reuses common fields without inventing a workflow; No.69 binding, save/cancel and clear work')
  injection="""
const stageKeys=[null,'24','42','69','80','89','100','102',null,null];
for(let i=0;i<batteryCases.length;i++){const d=batteryCases[i].power;d.values={kind:'蓄電池',owner:'申請担当A','7':batteryCases[i].name};d.na={};if(stageKeys[i])d.values[stageKeys[i]]='2026-11-05';}
"""
  u=url+'?stage-fixture';p.route(u,lambda r:r.fulfill(status=200,content_type='text/html',body=fixture(raw,injection)));p.goto(u,wait_until='networkidle');f.locator('[data-page=power]').click();m.locator('[data-power-tab=bulk]').click();m.locator('#power-bulk-stage').select_option('aggregator')
  caseids=['P-00001','P-00002']+['G-'+str(i).zfill(5) for i in range(3,11)]
  for i,key in enumerate(['basic','connection','main','changes','preparation','receipt','commercial','market']):
   m.locator('#power-input-current-stage').select_option(key);assert set(ids())==set([caseids[i]]+(caseids[8:] if key=='basic' else [])),(key,ids())
  m.locator('#power-input-current-stage').select_option('changes');m.locator('#power-search').fill('P-00001');m.locator('#power-search').press('Tab');assert ids()==[];m.locator('[data-power-action=clearFilters]').click();assert len(ids())==10
  m.locator('#power-input-current-stage').select_option('changes');m.locator('#power-bulk-stage').select_option('withdrawal');assert ids()==['G-00004'];m.locator('[data-power-tab=detail]').click();m.locator('[data-power-tab=bulk]').click();assert m.locator('#power-input-current-stage').input_value()=='changes';m.locator('[data-power-action=clearFilters]').click()
  done('all eight saved-date stage mappings filter correctly, including name/equipment changes, commercial/market separation, AND search, zero results and view persistence; withdrawal is not a filter stage')
  # Only the battery bulk view changes; all other 62 views remain byte-identical in the DOM.
  p.goto(url,wait_until='networkidle');f.locator('[data-page=power]').click();m.locator('[data-power-tab=bulk]').click()
  for stage,name in [('aggregator','name-equipment-changes.png'),('withdrawal','withdrawal.png')]:
   m.locator('#power-bulk-stage').select_option(stage);m.locator('.pw-toolbar').scroll_into_view_if_needed();p.screenshot(path=str(OUT/name))
  old=b.new_page(viewport={'width':1500,'height':1300});old.route(url,lambda r:r.fulfill(status=200,content_type='text/html',body=baseline));old.goto(url,wait_until='networkidle');of=old.frame_locator('#codex-visualization')
  def state(fr,d,business,t):
   fr.locator('[data-page='+d+']').click();w=fr.locator('#'+d+'-workspace');w.locator('.du-business-tabs').get_by_role('tab',name=business,exact=True).click();w.locator('.du-work-tabs').get_by_role('tab',name=t,exact=True).click();return w.inner_html()
  for d in ['realestate','power','sales','legal','procurement','construction','maintenance']:
   for business in ['蓄電池','太陽光','データセンター']:
    for t in ['サマリー','データ入力','案件詳細']:
     if (d,business,t)==('power','蓄電池','データ入力'):continue
     assert state(f,d,business,t)==state(of,d,business,t),(d,business,t)
  assert not errors,errors;old.close();b.close();done('all other 62 views unchanged, including summary stage counts and other businesses; no JavaScript errors')
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'js_errors':errors},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
