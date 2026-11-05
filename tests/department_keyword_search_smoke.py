"""Shared saved-value keyword filters across six departments and three businesses."""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import fixture,inner
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-department-keyword-review');DEPTS=['realestate','sales','legal','procurement','construction','maintenance']
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[];failed=[];writes=[]
 raw=(ROOT/'index.html').read_text();base=subprocess.check_output(['git','show','be7b828:index.html'],cwd=ROOT,text=True)
 for name in ['batteryCaseSeedData','batteryDepartmentDefinitions']:
  read=lambda text:json.JSONDecoder().raw_decode(inner(text).split('const '+name+'=',1)[1])[0]
  assert read(raw)==read(base)
 injection="""
batteryCaseMap['G-00004'].power.values.brokers=['Shared Broker ABC（検証専用）'];
for(const d of ['realestate','sales','legal','procurement','construction','maintenance'])batteryCaseMap['G-00004'].departments[d].next+=' KeywordOnly-4';
batteryCaseMap['G-00004'].departments.maintenance.inspectionMemo='Inspection-Memo（検証専用）';
projects[0].contract='SOLAR-KEYWORD-CONTRACT';
window.__keywordHistory=()=>JSON.stringify({approval:[...approvalRecords.values()].map(r=>r.history),power:batteryCases.map(c=>c.power.history),department:Object.values(batteryDepartmentStores).map(s=>s.records.map(r=>({changes:r.changes,events:r.events})))});
"""
 with server() as url,sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1550,'height':1350});p.on('pageerror',lambda e:errors.append(str(e)));p.on('requestfailed',lambda r:failed.append(r.url));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);test_url=url+'?keyword-fixture';p.route(test_url,lambda r:r.fulfill(status=200,content_type='text/html',body=fixture(raw,injection)));p.goto(test_url,wait_until='networkidle');f=p.frame_locator('#codex-visualization')
  def done(s):passed.append(s);print('PASS',s,flush=True)
  def mount(d):return f.locator('#'+d+'-workspace')
  def nav(d):f.locator('[data-page='+d+']').click()
  def business(d,name):mount(d).locator('.du-business-tabs').get_by_role('tab',name=name,exact=True).click()
  def tab(d,t):mount(d).locator('.du-work-tabs').get_by_role('tab',name={'summary':'サマリー','bulk':'データ入力','detail':'案件詳細'}[t],exact=True).click()
  def keyword(d):return mount(d).locator('#dept-keyword-'+d)
  def clear(d):mount(d).locator('#dept-clear-'+d).click()
  def ids(d,t):
   w=mount(d)
   if t=='detail':return w.locator('[data-dept-select] option').evaluate_all('(es)=>es.map(e=>e.value)')
   if d=='sales' and w.locator('#sales-search').count():
    return w.locator('#sales-demo-cases tr td:first-child [data-sales-open]').evaluate_all('(es)=>es.map(e=>e.dataset.salesOpen)') if t=='summary' else w.locator('[data-sales-row]').evaluate_all('(es)=>es.map(e=>e.dataset.salesRow)')
   return w.locator('[data-dept-summary-row]' if t=='summary' else '[data-dept-row]').evaluate_all('(es)=>es.map(e=>e.dataset.deptSummaryRow||e.dataset.deptRow)')
  seen=0
  for d in DEPTS:
   nav(d)
   for name in ['蓄電池','太陽光','データセンター']:
    business(d,name)
    for t in ['summary','bulk']+(['detail'] if d=='realestate' else []):
     tab(d,t);w=mount(d);input=keyword(d);assert input.count()==1,(d,name,t);assert ('仲介者' in input.get_attribute('placeholder'))==(name=='蓄電池');initial=len(ids(d,t));labels=input.locator('..').locator('..').locator(':scope>label').evaluate_all('(es)=>es.map(e=>e.firstChild.textContent)');assert labels[-2:]==['並べ替え','キーワードで検索'];assert input.locator('..').evaluate('(e)=>e.nextElementSibling.textContent')=='絞り込みを解除';assert input.bounding_box()['width']>=215;assert 33<=input.bounding_box()['height']<=35
     input.fill('NO-MATCH-XYZ');assert ids(d,t)==[],(d,name,t);assert input.evaluate('(e)=>e===document.activeElement');assert input.input_value()=='NO-MATCH-XYZ';input.fill('   ');assert len(ids(d,t))==initial;clear(d);assert len(ids(d,t))==initial;assert w.locator('#dept-clear-'+d).evaluate('(e)=>e===document.activeElement');seen+=1
  assert seen==39,seen;done('all 39 existing search areas across six departments/three businesses have ordered shared keyword/reset controls, 34px fields, immediate empty/matching lists and preserved focus; empty businesses stay empty')
  for d in DEPTS:
   nav(d);business(d,'蓄電池');tab(d,'summary');w=mount(d);before=w.locator('.du-kpis').inner_text();keyword(d).fill('  sHaReD bRoKeR aBc  ');assert ids(d,'summary')==['G-00004'];assert w.locator('.du-kpis').inner_text()==before
   case=w.locator('[data-dept-filter=search]');case.fill('P-00001');assert ids(d,'summary')==[];case.fill('G-00004');assert ids(d,'summary')==['G-00004'];owner=w.locator('[data-dept-filter=owner]');wanted=next(x for x in owner.locator('option').all_text_contents() if '担当B' in x);owner.select_option(label=wanted);assert ids(d,'summary')==['G-00004'];status_text=w.locator('[data-dept-summary-row] td:nth-child(3)').inner_text();w.locator('[data-dept-filter=status]').select_option(label=status_text);assert ids(d,'summary')==['G-00004'];w.locator('[data-dept-filter=sort]').select_option('due');assert ids(d,'summary')==['G-00004'];tab(d,'bulk');assert keyword(d).input_value()=='  sHaReD bRoKeR aBc  ';assert ids(d,'bulk')==['G-00004'];clear(d);assert len(ids(d,'bulk'))==10 and keyword(d).input_value()=='';assert w.locator('[data-dept-filter=sort]').input_value()=='id'
   tab(d,'summary');keyword(d).fill('keywordonly');assert ids(d,'summary')==['G-00004'];clear(d)
  done('all six departments match shared saved brokers and next-action text case-insensitively with trimming; case/owner/status/keyword combine with AND; sort, tab persistence, clear and existing business-wide KPI semantics remain consistent')
  # Japanese IME and caret selection behave like power: do not replace DOM during composition.
  nav('maintenance');business('maintenance','蓄電池');tab('maintenance','summary');w=mount('maintenance');kw=keyword('maintenance');kw.focus();handle=kw.element_handle();cdp=p.context.new_cdp_session(p);cdp.send('Input.imeSetComposition',{'text':'変換中','selectionStart':3,'selectionEnd':3});assert handle.evaluate('(e)=>e.isConnected') and len(ids('maintenance','summary'))==10;cdp.send('Input.insertText',{'text':'該当しない日本語'});assert ids('maintenance','summary')==[];clear('maintenance');kw=keyword('maintenance');kw.press_sequentially('inspection-memo',delay=10);assert ids('maintenance','summary')==['G-00004'];kw.evaluate('(e)=>e.setSelectionRange(0,2)');kw.press_sequentially('IN');assert kw.input_value()=='INspection-memo' and kw.evaluate('(e)=>e.selectionStart===2&&e.selectionEnd===2');clear('maintenance')
  done('real Chromium Japanese IME retains the composing DOM/rows until commit; partial matches, live caret edits and maintenance memo fields work')
  # A legal broker draft is not searchable in other departments; after save it is shared.
  nav('legal');business('legal','蓄電池');tab('legal','bulk');w=mount('legal');w.locator('[data-dept-group]').select_option('common');broker=w.locator('[data-dept-case="G-00004"][data-dept-field=broker]');broker.fill('UNSAVED-BROKER');tab('legal','summary');keyword('legal').fill('UNSAVED-BROKER');assert ids('legal','summary')==[];keyword('legal').fill('Shared Broker');assert ids('legal','summary')==['G-00004'];tab('legal','bulk');clear('legal');w.locator('[data-dept-action=cancel]').click();assert 'Shared Broker' in broker.input_value();broker.fill('SAVED-SEARCH-BROKER');keyword('legal').fill('NO-MATCH');w.locator('[data-dept-action=save]').click();clear('legal');assert broker.input_value()=='SAVED-SEARCH-BROKER';nav('construction');business('construction','蓄電池');tab('construction','summary');keyword('construction').fill('saved-search-broker');assert ids('construction','summary')==['G-00004'];clear('construction')
  # Business filters are separate; legacy solar sales/legal search their saved contracts.
  for d in ['sales','legal']:
   nav(d);business(d,'太陽光');tab(d,'summary');keyword(d).fill('solar-keyword-contract');assert ids(d,'summary')==['P-00001'];search=mount(d).locator('#sales-search' if d=='sales' else '[data-dept-filter=search]');search.fill('P-00002');search.press('Tab');assert ids(d,'summary')==[];search.fill('P-00001');search.press('Tab');assert ids(d,'summary')==['P-00001'];tab(d,'bulk');assert keyword(d).input_value()=='solar-keyword-contract';assert ids(d,'bulk')==['P-00001'];business(d,'蓄電池');tab(d,'summary');assert keyword(d).input_value()=='';business(d,'太陽光');tab(d,'summary');assert keyword(d).input_value()=='solar-keyword-contract';clear(d)
  nav('sales');business('sales','太陽光');tab('sales','summary');kw=keyword('sales');kw.focus();handle=kw.element_handle();cdp.send('Input.imeSetComposition',{'text':'変換中','selectionStart':3,'selectionEnd':3});assert handle.evaluate('(e)=>e.isConnected') and len(ids('sales','summary'))==3;cdp.send('Input.insertText',{'text':'該当しない日本語'});assert ids('sales','summary')==[];clear('sales')
  done('unsaved broker edits are excluded, hidden drafts can be cancelled/saved and saved brokers immediately match other departments; existing solar contracts are searchable and business filters remain separate')
  # Internal IDs, filenames, histories, case numbers/names are not keyword fields.
  nav('construction');business('construction','蓄電池');tab('construction','summary');before=p.frames[1].evaluate('window.__keywordHistory()');badge=f.locator('#approval-pending-count').inner_text()
  for excluded in ['DEMO-ANDPAD-G-00004','G-00004','デモ第04蓄電所','デモ初期値','DEMO_G-00004_construction_関連資料.pdf']:
   keyword('construction').fill(excluded);assert ids('construction','summary')==[],excluded
  clear('construction');assert p.frames[1].evaluate('window.__keywordHistory()')==before;assert f.locator('#approval-pending-count').inner_text()==badge and not f.locator('.nc-toast').count()
  for d in DEPTS:
   nav(d);business(d,'蓄電池');tab(d,'summary');clear(d);p.screenshot(path=str(OUT/(d+'.png')))
  p.set_viewport_size({'width':390,'height':1300});w=mount('maintenance');w.locator('.du-keyword-filters').scroll_into_view_if_needed();assert w.locator('.du-keyword-filters').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1');assert keyword('maintenance').bounding_box()['width']>=200;assert abs(keyword('maintenance').bounding_box()['width']-w.locator('.du-keyword-filters').bounding_box()['width'])<=2;p.screenshot(path=str(OUT/'mobile.png'));assert not errors,errors;assert not failed,failed;assert not writes,writes;b.close();done('explicit exclusions prevent ID/history/file/draft matches; filters create no history, approvals or notices; desktop/mobile layouts and all six representative screenshots verified; no JS/resource/write errors')
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'areas':seen,'js_errors':errors,'failed_resources':failed,'external_writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
