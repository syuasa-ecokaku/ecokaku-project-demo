"""Real-estate development labels, empty development group and aliased shared status filters."""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import fixture,inner
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-realestate-development-review')
STATUS=['すべて','不動産','開発','調査前','調査中','交渉中','取得手続き中','取得済']
ALIAS={'取得手続中':'取得手続き中','取得済み':'取得済'}
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[];writes=[]
 raw=(ROOT/'index.html').read_text();baseline=subprocess.check_output(['git','show','a9fe317:index.html'],cwd=ROOT,text=True)
 parse=lambda s:json.JSONDecoder().raw_decode(inner(s).split('const batteryCaseSeedData=',1)[1])[0]
 assert parse(raw)==parse(baseline)
 expected={s:set() for s in STATUS[1:]}
 for case in parse(raw):expected.get(ALIAS.get(case['departments']['realestate']['status'],case['departments']['realestate']['status']),set()).add(case['id'])
 def done(s):passed.append(s);print('PASS',s,flush=True)
 with server() as url,sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1500,'height':1300});p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');f.locator('[data-page=realestate]').click();m=f.locator('#realestate-workspace')
  assert '不動産開発' in f.locator('[data-page=realestate]').inner_text();assert f.locator('#realestate-demo-main h2').inner_text()=='不動産開発部門';assert f.locator('#realestate-demo-main .s-breadcrumb').inner_text()=='ダッシュボード ／ 不動産開発'
  def tab(t):m.locator('#du-realestate-tab-'+t).click()
  def status(v):m.locator('[data-dept-filter=status]').select_option(v)
  def current_ids(t):
   if t=='summary':return set(m.locator('[data-dept-summary-row]').evaluate_all('(es)=>es.map(e=>e.dataset.deptSummaryRow)'))
   if t=='bulk':return set(m.locator('[data-dept-row]').evaluate_all('(es)=>es.map(e=>e.dataset.deptRow)'))
   return set(m.locator('[data-dept-select] option').evaluate_all('(es)=>es.map(e=>e.value)'))
  for business in ['battery','solar','datacenter']:
   m.locator('[data-dept-business='+business+']').click()
   for t in ['summary','bulk','detail']:
    tab(t);assert m.locator('[data-dept-filter=status] option').all_text_contents()==STATUS
    for value in STATUS[1:]:
     status(value)
     want=expected[value] if business=='battery' else {'R-00004'} if business=='solar' and value=='取得手続き中' else set()
     assert current_ids(t)==want,(business,t,value,current_ids(t),want)
    status('');assert len(current_ids(t))=={'battery':10,'solar':1,'datacenter':0}[business]
   tab('bulk');assert m.locator('[data-dept-group] option').all_text_contents()==['取得状況・対応','土地・取得・契約','開発・許可対応']
   for group in ['common','business','development']:
    m.locator('[data-dept-group]').select_option(group)
    if group=='development':assert '開発・許可対応の入力項目は未設定' in m.inner_text();assert m.locator('[data-dept-field]').count()==0
  done('renamed navigation/title/breadcrumb; all three businesses and tabs share exact ordered status options, legacy aliases and clear; three input groups switch, development is honestly unset')
  m.locator('[data-dept-business=battery]').click();tab('bulk');m.locator('[data-dept-group]').select_option('common');cell=m.locator('[data-dept-case="G-00003"][data-dept-field=owner]');old=cell.input_value();cell.fill('開発画面・保存検証');m.locator('[data-dept-group]').select_option('development');tab('detail');status('開発');assert '条件に一致する案件はありません' in m.inner_text();m.locator('[data-dept-action=cancel]').click();status('');tab('bulk');m.locator('[data-dept-group]').select_option('common');assert cell.input_value()==old
  cell.fill('開発画面・保存検証');m.locator('[data-dept-group]').select_option('development');m.locator('[data-dept-action=save]').click();tab('summary');m.locator('[data-dept-filter=owner]').select_option('開発画面・保存検証');assert current_ids('summary')=={'G-00003'};m.locator('[data-dept-summary-row="G-00003"] [data-dept-open]').first.click();assert m.locator('[data-dept-select]').input_value()=='G-00003';assert m.locator('[data-dept-filter=owner]').input_value()=='開発画面・保存検証';m.locator('[data-dept-filter=owner]').select_option('');tab('summary');m.locator('[data-dept-status="取得済み"]').click();assert m.locator('[data-dept-filter=status]').input_value()=='取得済';assert len(current_ids('summary'))==5
  m.locator('[data-dept-open="G-00007"]').first.click();assert m.locator('[data-dept-select]').input_value()=='G-00007';assert m.locator('[data-dept-filter=status]').input_value()=='';assert '指定案件を開くため' in m.inner_text()
  done('drafts survive group/tab/search changes; cancel and save include hidden fields; filtered detail navigation and legacy status-card clicks select canonical filter labels')
  injection="""
const statuses=['不動産','開発','調査前','調査中','交渉中','取得手続中','取得手続き中','取得済み','取得済','未確認の旧値（検証専用）'];
for(let i=0;i<batteryCases.length;i++)batteryCases[i].departments.realestate.status=statuses[i];
window.__developmentState=()=>batteryCases.map(c=>({id:c.id,status:c.departments.realestate.status}));
"""
  u=url+'?development-fixture';p.route(u,lambda r:r.fulfill(status=200,content_type='text/html',body=fixture(raw,injection)));p.goto(u,wait_until='networkidle');f.locator('[data-page=realestate]').click();initial=p.frames[1].evaluate('window.__developmentState()');before=m.locator('.nc-unread-count').inner_text()
  for label in STATUS[1:]:
   status(label);ids=current_ids('summary');want={x['id'] for x in initial if ALIAS.get(x['status'],x['status'])==label};assert ids==want,(label,ids,want)
   tab('bulk');assert current_ids('bulk')==want;tab('detail');assert current_ids('detail')==want;tab('summary')
  status('');assert len(current_ids('summary'))==10;assert p.frames[1].evaluate('window.__developmentState()')==initial;assert m.locator('.nc-unread-count').inner_text()==before;assert not f.locator('.nc-toast').count()
  done('literal real-estate/development statuses, old/new acquisition spellings and unknown values retain saved data; searches generate no notice or read-state changes')
  p.goto(url,wait_until='networkidle');f.locator('[data-page=realestate]').click();p.screenshot(path=str(OUT/'summary.png'));tab('bulk');m.locator('[data-dept-group]').select_option('development');p.screenshot(path=str(OUT/'development-unset.png'))
  # Unrelated workspaces stay identical except for the department display-name references.
  oldpage=b.new_page(viewport={'width':1500,'height':1300});oldpage.route(url,lambda r:r.fulfill(status=200,content_type='text/html',body=baseline));oldpage.goto(url,wait_until='networkidle');of=oldpage.frame_locator('#codex-visualization')
  def norm(s):return s.replace('不動産開発','不動産').replace('不動産・開発','不動産')
  def state(fr,d,biz,t):
   fr.locator('[data-page='+d+']').click();w=fr.locator('#'+d+'-workspace');w.locator('.du-business-tabs').get_by_role('tab',name=biz,exact=True).click();w.locator('.du-work-tabs').get_by_role('tab',name=t,exact=True).click();return norm(w.inner_html())
  for d in ['power','sales','legal','procurement','construction','maintenance']:
   for biz in ['蓄電池','太陽光','データセンター']:
    for t in ['サマリー','データ入力','案件詳細']:
     if d=='legal' and biz=='蓄電池' and t in ['データ入力','案件詳細']:continue
     assert state(f,d,biz,t)==state(of,d,biz,t),(d,biz,t)
  assert not errors,errors;assert not writes,writes;oldpage.close();b.close();done('52 other department views unchanged apart from department-name references; seed data untouched; no JavaScript errors or external writes')
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'js_errors':errors,'external_writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
