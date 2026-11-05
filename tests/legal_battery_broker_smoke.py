"""Battery legal broker shared binding, direct editing and unset rights-transfer group."""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from notice_snapshot import snapshot_html
from department_notices_smoke import fixture,inner
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-legal-broker-review')
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[];writes=[]
 raw=(ROOT/'index.html').read_text();baseline=subprocess.check_output(['git','show','152a528:index.html'],cwd=ROOT,text=True)
 for name in ['batteryCaseSeedData','batteryDepartmentDefinitions']:
  read=lambda text:json.JSONDecoder().raw_decode(inner(text).split('const '+name+'=',1)[1])[0]
  assert read(raw)==read(baseline)
 def done(text):passed.append(text);print('PASS',text,flush=True)
 with server() as url,sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1500,'height':1300});p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');f.locator('[data-page=legal]').click();m=f.locator('#legal-workspace')
  def tab(t):m.locator('#du-legal-tab-'+t).click()
  def group(g):m.locator('[data-dept-group]').select_option(g)
  def cell(id,key):return m.locator('[data-dept-case="'+id+'"][data-dept-field='+key+']')
  def action(a):m.locator('[data-dept-action='+a+']').click()
  tab('bulk');assert m.locator('[data-dept-group] option').all_text_contents()==['契約対応','設備販売契約（契約単位）','土地売買契約（非課税のデモ）','保守契約（契約単位）','権利譲渡契約'];assert m.locator('thead th').all_text_contents()==['案件番号','案件名（共通参照）','担当者','仲介','進捗ステータス','対応期限','次の対応','詳細'];assert m.locator('[data-dept-row]').count()==10
  assert all(50<=r.bounding_box()['height']<=54 for r in m.locator('[data-dept-row]').all());assert m.locator('[data-dept-field=broker]').count()==10;assert all(x.input_value()=='' for x in m.locator('[data-dept-field=broker]').all())
  owner=cell('G-00003','owner');broker=cell('G-00003','broker');owner.focus();owner.press('Tab');expect(broker).to_be_focused();broker.press('Tab');expect(cell('G-00003','due')).to_be_focused();cell('G-00003','due').press('Shift+Tab');expect(broker).to_be_focused()
  for g in ['sale','land','maintenance','rightsTransfer']:group(g)
  assert '権利譲渡契約の入力項目は未設定' in m.inner_text();assert m.locator('[data-dept-field]').count()==0;assert m.locator('thead th').all_text_contents()==['案件番号','案件名（共通参照）','詳細'];group('common');p.screenshot(path=str(OUT/'broker-column.png'))
  done('five ordered groups, unchanged existing contract columns, honest unset rights-transfer view; exact common column order, ten editable broker cells, Tab/Shift-Tab and 52px rows')
  broker.fill('架空仲介会社A（検証専用）');assert 'du-dirty' in broker.get_attribute('class');group('rightsTransfer');tab('summary');f.locator('[data-page=power]').click();w=f.locator('#power-workspace');assert w.locator('#power-summary-broker option').all_text_contents()==['すべて','未登録'];f.locator('[data-page=legal]').click();tab('bulk');group('common');assert broker.input_value()=='架空仲介会社A（検証専用）'
  m.locator('[data-dept-filter=search]').fill('P-00001');m.locator('[data-dept-filter=search]').press('Tab');group('rightsTransfer');action('cancel');m.locator('[data-dept-filter=search]').fill('');m.locator('[data-dept-filter=search]').press('Tab');group('common');assert broker.input_value()==''
  broker.fill('架空仲介会社A（検証専用）、架空仲介者B（検証専用）');cell('G-00004','broker').fill('別案件の架空仲介（検証専用）');group('rightsTransfer');action('save');group('common');assert 'du-dirty' not in (broker.get_attribute('class') or '');assert broker.input_value()=='架空仲介会社A（検証専用）、架空仲介者B（検証専用）';assert cell('G-00004','broker').input_value()=='別案件の架空仲介（検証専用）'
  m.locator('[data-dept-row="G-00003"] [data-dept-open]').last.click();assert cell('G-00003','broker').input_value()=='架空仲介会社A（検証専用）、架空仲介者B（検証専用）';m.locator('[data-dept-section=changes]>summary').click();assert '仲介' in m.locator('[data-dept-section=changes]').inner_text();f.locator('[data-page=power]').click();w.locator('#power-summary-broker').select_option(label='架空仲介者B（検証専用）');assert w.locator('[data-power-summary-row]').count()==1;assert w.locator('[data-power-summary-row]').get_attribute('data-power-summary-row')=='G-00003';assert not f.locator('.nc-toast').count()
  done('drafts stay local until saved; group/tab/department changes preserve drafts; hidden-row/group cancel and multi-case save work; shared power broker choices and per-case detail/history reflect saved legal edits without notices')
  injection=r"""
batteryCaseMap['G-00003'].power.values.brokers=['保存済み仲介A（検証専用）','保存済み、仲介B（検証専用）','保存済み\\仲介C（検証専用）'];
window.__brokerState=()=>batteryCases.map(c=>({id:c.id,brokers:c.power.values.brokers,contracts:c.contracts}));
window.__externalBrokerEdit=()=>batteryCaseMap['G-00003'].power.values.brokers=['別画面更新（検証専用）'];
"""
  u=url+'?legal-broker-fixture';p.route(u,lambda r:r.fulfill(status=200,content_type='text/html',body=fixture(raw,injection)));p.goto(u,wait_until='networkidle');f.locator('[data-page=legal]').click();tab('bulk');original=p.frames[1].evaluate('window.__brokerState()');oldvalue=broker.input_value();assert '保存済み仲介A' in oldvalue and '仲介B' in oldvalue;assert oldvalue.count('、')==3
  cell('G-00003','owner').fill('担当者のみ編集（検証専用）');action('save');assert p.frames[1].evaluate('window.__brokerState()')==original
  broker.fill(oldvalue+'、追加の仲介（検証専用）');action('save');saved=p.frames[1].evaluate('window.__brokerState()');assert next(x for x in saved if x['id']=='G-00003')['brokers']==next(x for x in original if x['id']=='G-00003')['brokers']+['追加の仲介（検証専用）'];assert all(x['contracts']==y['contracts'] for x,y in zip(saved,original))
  broker.fill('古い画面の下書き（検証専用）');p.frames[1].evaluate('window.__externalBrokerEdit()');action('save');assert '他部門・他画面' in m.locator('[data-dept-errors]').inner_text();assert broker.input_value()=='古い画面の下書き（検証専用）';action('cancel');assert broker.input_value()=='別画面更新（検証専用）';broker.fill('');action('save');assert next(x for x in p.frames[1].evaluate('window.__brokerState()') if x['id']=='G-00003')['brokers']==[]
  done('existing multiple brokers, punctuation/backslashes and unrelated saves preserve shared values/contracts; concurrent-update conflict preserves drafts; blank clears the shared broker list')
  p.goto(url,wait_until='networkidle');f.locator('[data-page=legal]').click();tab('bulk');group('rightsTransfer');p.screenshot(path=str(OUT/'rights-transfer-unset.png'));p.set_viewport_size({'width':800,'height':1100});group('common');assert m.locator('.du-bulk-table [data-dept-field=broker]').count()==10;p.screenshot(path=str(OUT/'narrow.png'));p.set_viewport_size({'width':1500,'height':1300})
  old=b.new_page(viewport={'width':1500,'height':1300});old.route(url,lambda r:r.fulfill(status=200,content_type='text/html',body=baseline));old.goto(url,wait_until='networkidle');of=old.frame_locator('#codex-visualization')
  def state(fr,d,biz,t):
   fr.locator('[data-page='+d+']').click();w=fr.locator('#'+d+'-workspace');w.locator('.du-business-tabs').get_by_role('tab',name=biz,exact=True).click();w.locator('.du-work-tabs').get_by_role('tab',name=t,exact=True).click();return snapshot_html(w)
  for d in ['realestate','power','sales','legal','procurement','construction','maintenance']:
   for biz in ['蓄電池','太陽光','データセンター']:
    for t in ['サマリー','データ入力','案件詳細']:
     if d=='legal' and biz=='蓄電池' and t in ['データ入力','案件詳細']:continue
     assert state(f,d,biz,t)==state(of,d,biz,t),(d,biz,t)
  assert not errors,errors;assert not writes,writes;old.close();b.close();done('all other 61 views unchanged, including solar/datacenter legal, power summary KPIs and existing prior changes; reload resets edits; no JavaScript errors or external writes')
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'js_errors':errors,'external_writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
