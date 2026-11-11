"""Real Chromium purchasing workflow checks; local server, no production writes.
Run: python tests/procurement_workflow_smoke.py
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect
from power_mock_smoke import server
from department_notices_smoke import fixture
ROOT=Path(__file__).resolve().parents[1]
OUT=Path('/tmp/ecokaku-procurement-review')
INJECT="""
window.__pc={data:()=>pcData,stock:pcStock,total:pcTotal,amounts:pcAmounts,remaining:pcRemaining,status:pcStatus,complete:pcCompleteTransfer,snapshot:lifecycleSnapshot,cases:pcCases,open:pcHandle,render:pcRender,commit:pcCommit,generate:pcGenerate,filters:pcF,ui:pcUI};
"""
def run():
 OUT.mkdir(exist_ok=True);errors=[];passed=[];writes=[]
 body=fixture((ROOT/'index.html').read_text(),INJECT)
 with server() as url,sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1540,'height':1100},timezone_id='Asia/Tokyo')
  page.route(url,lambda r:r.fulfill(body=body,content_type='text/html'))
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
  page.goto(url,wait_until='networkidle');f=page.frame_locator('#codex-visualization');m=f.locator('#procurement-workspace');dlg=f.locator('#pc-dialog')
  def api(code):return page.frames[1].evaluate(code)
  def data():return api('()=>__pc.data()')
  def done(t):passed.append(t);print('PASS',t,flush=True)
  def click(action,id=None,scope=None):
   el=(scope or m).locator('[data-pc-action="'+action+'"]'+('[data-pc-id="'+id+'"]' if id else ''));el.first.click()
  def submit():dlg.locator('#pc-save').click();expect(f.locator('.lc-busy')).to_be_hidden();page.frames[1].wait_for_function('()=>!__pc.ui.busy')
  def fill(name,value):dlg.locator('[name="'+name+'"]').fill(str(value))
  def select(name,value):dlg.locator('[name="'+name+'"]').select_option(value)
  def open_action(action,id):api('()=>__pc.open('+json.dumps(action)+','+json.dumps(id)+')')
  def close():click('close',scope=dlg)
  f.locator('[data-page=procurement]').click();expect(m.locator('[data-pc-tab]')).to_have_count(5)
  page.screenshot(path=str(OUT/'summary.png'),full_page=True)
  click('metric','overdue');expect(m.locator('#pc-tab-orders')).to_have_attribute('aria-selected','true');assert 'DEMO-BATTERY-001' in m.inner_text();click('clear')
  before=data();baseline_other=api('()=>{const s=__pc.snapshot();delete s.procurement;return s;}')
  # Create one project order, then add a stocked item and freight through the staged UI.
  click('new-order');fill('number','DEMO-TEST-001');submit();expect(dlg.locator('[name=productId]')).to_be_visible()
  case=api('()=>__pc.cases("battery")[0].internalId');select('caseId',case);fill('qty',3);fill('price',1001);fill('due','2026-11-30')
  assert '3,303' in dlg.locator('#pc-line-preview').inner_text();submit()
  d=data();o=next(x for x in d['orders'] if x['number']=='DEMO-TEST-001');oid=o['id'];l=next(x for x in d['lines'] if x['orderId']==oid)
  click('new-line',oid);select('productId','freight');select('caseId',case);fill('price',500);submit()
  assert api('()=>__pc.total(__pc.data().orders.find(o=>o.id==='+json.dumps(oid)+'))')==3853
  done('staged project order with multiple lines, automatic expense type and line tax rounding')
  # Split delivery; freight role completion cannot increase stock.
  open_action('receipt',l['id']);fill('qty',1);submit();assert api('()=>__pc.remaining(__pc.data().lines.find(l=>l.id==='+json.dumps(l['id'])+'))')==2
  open_action('receipt',l['id']);fill('qty',1);submit()
  d=data();fee=next(x for x in d['lines'] if x['orderId']==oid and x['kind']=='expense');stock_before=api('()=>__pc.stock("battery","panel","架空第一倉庫")')
  open_action('receipt',fee['id']);submit();assert api('()=>__pc.stock("battery","panel","架空第一倉庫")')==stock_before
  open_action('cancel-line',l['id']);submit();d=data();ll=next(x for x in d['lines'] if x['id']==l['id']);assert ll['qty']==3 and ll['cancelled']==1;assert sum(x['qty'] for x in d['receipts'] if x['lineId']==l['id'])==2
  done('split delivery reduces outstanding quantity, expenses never add stock and cancellation preserves received history')
  f.locator('[data-pc-tab=inventory]').click();s=api('()=>__pc.stock("battery","pile","架空第一倉庫")');assert s=={'real':16,'unusable':2,'allocated':6,'available':8,'pending':10}
  click('allocate','pile|架空第一倉庫');fill('qty',9);submit();assert '超える' in dlg.locator('#pc-error').inner_text();fill('qty',5);submit()
  alloc=data()['allocations'][-1];click('issue',alloc['id']);fill('qty',2);submit();s=api('()=>__pc.stock("battery","pile","架空第一倉庫")');assert s['real']==14 and s['allocated']==9 and s['available']==3
  click('release',alloc['id']);fill('qty',1);submit();s=api('()=>__pc.stock("battery","pile","架空第一倉庫")');assert s['real']==14 and s['allocated']==8 and s['available']==4
  direct=next(x for x in data()['lines'] if x['orderId']=='po-battery-1' and x['route']=='direct');open_action('receipt',direct['id']);fill('qty',1);submit();assert api('()=>__pc.stock("battery","pcs","架空第一倉庫").real')==0
  done('warehouse ledger, unusable exclusion, allocation limits, partial issue/release, direct shipment exclusion')
  f.locator('[data-pc-tab=transfers]').click();pay_count=len(data()['payments']);t=next(x for x in data()['transfers'] if x['id']=='transfer-battery-case');click('confirm-transfer',t['id']);submit();click('complete-transfer',t['id']);submit();assert next(x for x in data()['transfers'] if x['id']==t['id'])['status']=='完了'
  assert api('()=>__pc.stock("battery","pile","架空第一倉庫").real')==14
  result=api('()=>{try{__pc.complete(__pc.data().transfers.find(t=>t.id==="transfer-battery-case"),"2026-11-11");return false}catch(e){return e.message}}');assert '二重' in result
  t=next(x for x in data()['transfers'] if x['id']=='transfer-battery-warehouse');click('complete-transfer',t['id']);submit();assert api('()=>__pc.stock("battery","monitor","架空第一倉庫").real')==3;assert api('()=>__pc.stock("battery","monitor","架空第二倉庫").real')==1;assert len(data()['payments'])==pay_count
  click('new-transfer');select('productId','monitor');fill('qty',100);fill('reason','倉庫移動');submit();assert '不足' in dlg.locator('#pc-error').inner_text();close()
  page.screenshot(path=str(OUT/'transfers.png'),full_page=True)
  done('case and warehouse transfer completion, stock conservation, no duplicate reflection or payable creation, over-capacity rejection')
  f.locator('[data-pc-tab=payments]').click();d=data()
  for oid2 in ['po-battery-1','po-battery-2']:
   payments=[p for p in d['payments'] if p['orderId']==oid2];order=next(o for o in d['orders'] if o['id']==oid2);assert len(payments)==2;assert sum(p['amount'] for p in payments)==api('()=>__pc.total(__pc.data().orders.find(o=>o.id==='+json.dumps(oid2)+'))')
  p=next(p for p in d['payments'] if p['orderId']=='po-battery-1');n=len(d['payments']);amounts=sum(p['amount'] or 0 for p in d['payments']);open_action('edit-payment',p['id']);select('invoiceId','invoice-demo-1');submit();assert len(data()['payments'])==n and sum(p['amount'] or 0 for p in data()['payments'])==amounts
  open_action('generate','po-battery-1');submit();open_action('generate','po-battery-1');submit();assert len(data()['payments'])==n
  # Register a real staged invoice; its three dates stay distinct and file contents never persist.
  open_action('new-invoice','po-battery-1');fill('number','DEMO-INV-TEST');fill('invoiceDate','2026-11-01');fill('receivedDate','2026-11-03');fill('confirmedDate','2026-11-05');fill('amount',10000);select('status','確認済');dlg.locator('[name=files]').set_input_files({'name':'架空請求.pdf','mimeType':'application/pdf','buffer':b'demo'});submit();new_invoice=data()['invoices'][-1];assert new_invoice['invoiceDate']=='2026-11-01' and new_invoice['receivedDate']=='2026-11-03' and new_invoice['confirmedDate']=='2026-11-05' and new_invoice['files']==['架空請求.pdf']
  open_action('edit-payment',p['id']);select('invoiceId',new_invoice['id']);select('basis','請求書確認');submit();assert len(data()['payments'])==n
  # Leave unknown dates/amounts explicit, then ensure reload preservation.
  open_action('new-payment','po-battery-1');fill('memo','未確定の例');submit();assert data()['payments'][-1]['amount'] is None and not data()['payments'][-1]['date'];assert '未確定' in m.inner_text()
  assert next(p for p in data()['payments'] if p['orderId']=='po-battery-2' and p['kind']=='残金')['date']=='2026-12-31'
  done('50/50 and 30/70 totals, calendar dates, unknown values, invoice linking and repeated generation without double counting')
  # New valid transfer plus detail and completion (not just seeded records).
  f.locator('[data-pc-tab=transfers]').click();click('new-transfer');select('productId','monitor');fill('qty',1);fill('reason','架空倉庫の再配置');submit();new_transfer=data()['transfers'][-1];click('transfer-detail',new_transfer['id']);assert '架空倉庫の再配置' in dlg.inner_text();close();click('confirm-transfer',new_transfer['id']);submit();click('complete-transfer',new_transfer['id']);submit();assert api('()=>__pc.stock("battery","monitor","架空第一倉庫").real')==2 and api('()=>__pc.stock("battery","monitor","架空第二倉庫").real')==2
  done('invoice registration with distinct dates and filename-only storage; new transfer registration/details/completion')
  f.locator('[data-pc-tab=payments]').click()
  # Failed storage must roll back model and allow retry on same form with same entity references.
  target=next(p for p in data()['payments'] if p['orderId']=='po-battery-1');open_action('edit-payment',target['id']);fill('amount',123)
  page.evaluate("()=>{window.__set=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k.includes('case-lifecycle'))throw new DOMException('quota','QuotaExceededError');return window.__set.call(this,k,v)}}")
  submit();assert '保存容量' in dlg.locator('#pc-error').inner_text();assert next(p for p in data()['payments'] if p['id']==target['id'])['amount']==target['amount'];page.evaluate('()=>{Storage.prototype.setItem=window.__set}');submit();assert next(p for p in data()['payments'] if p['id']==target['id'])['amount']==123
  saved=data();page.reload(wait_until='networkidle');assert data()==saved;f.locator('[data-page=procurement]').click()
  done('atomic rollback on quota failure, same-form retry, full procurement persistence after reload')
  for b in ['solar','datacenter','battery']:
   m.locator('[data-dept-business='+b+']').click();assert m.locator('[data-dept-business='+b+']').get_attribute('aria-selected')=='true'
   api('()=>{__pc.ui.tab="orders";__pc.render()}');text=m.inner_text();assert all(('DEMO-'+other.upper()+'-001') not in text for other in ['battery','solar','datacenter'] if other!=b)
  now_other=api('()=>{const s=__pc.snapshot();delete s.procurement;return s;}');assert now_other==baseline_other
  for dept in ['sales','legal','power','realestate','construction','maintenance','home']:
   f.locator('[data-page='+dept+']').click();assert f.locator('#sales-demo-home' if dept=='home' else '#'+dept+'-demo-main').is_visible()
  f.locator('[data-page=procurement]').click();open_action('case',case);expect(dlg).to_be_visible();click('case-sales',case,dlg);assert f.locator('#sales-demo-main').is_visible()
  f.locator('[data-page=procurement]').click();page.set_viewport_size({'width':390,'height':844});click('new-order');expect(dlg.locator('#pc-save')).to_be_visible();page.screenshot(path=str(OUT/'mobile-order.png'));close()
  # Reset only purchasing; the same review samples and invoice links are restored.
  page.set_viewport_size({'width':1540,'height':1100});other_before_reset=api('()=>{const s=__pc.snapshot();delete s.procurement;return s;}');click('reset');submit();assert data()['orders']==before['orders'] and data()['receipts']==before['receipts'] and data()['invoices']==before['invoices'];assert api('()=>{const s=__pc.snapshot();delete s.procurement;return s;}')==other_before_reset
  assert not errors,errors;assert not writes,writes;done('business isolation, unchanged other-department state, navigation and case links, usable mobile form, no JavaScript errors')
  browser.close()
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'errors':errors,'writes':writes},ensure_ascii=False,indent=2));print('Results:',OUT)
if __name__=='__main__':run()
