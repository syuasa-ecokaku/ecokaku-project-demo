"""Receiving examples: additive upgrade, visible history, ledger consistency and reload.
Run: python tests/procurement_receiving_examples_smoke.py
"""
from pathlib import Path
import json
import subprocess
from playwright.sync_api import sync_playwright, expect
from power_mock_smoke import server
from department_notices_smoke import fixture

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('/tmp/ecokaku-procurement-receiving-examples')
INJECT = """window.__rx={data:()=>pcData,stock:pcStock,remaining:pcRemaining,total:pcTotal,snapshot:lifecycleSnapshot,validate:pcValidate};"""

def run():
    OUT.mkdir(exist_ok=True)
    old = subprocess.check_output(['git', 'show', 'c908633:index.html'], cwd=ROOT, text=True)
    current_body = [fixture(old, INJECT)]
    errors, passed = [], []
    with server() as url, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        p = browser.new_page(viewport={'width':1540,'height':1150}, timezone_id='Asia/Tokyo')
        p.on('pageerror', lambda e: errors.append(str(e)))
        p.route(url, lambda route: route.fulfill(body=current_body[0], content_type='text/html'))
        p.goto(url, wait_until='networkidle')
        f = p.frame_locator('#codex-visualization')
        m = f.locator('#procurement-workspace')
        dlg = f.locator('#pc-dialog')
        def api(code): return p.frames[1].evaluate(code)
        def data(): return api('()=>__rx.data()')
        def wait(): expect(f.locator('.lc-busy')).to_be_hidden()
        def button(action, ident=None):
            selector = '[data-pcu-action="'+action+'"]'
            if ident: selector += '[data-pcu-id="'+ident+'"]'
            return m.locator(selector)
        def open_receiving(biz):
            f.locator('[data-page=procurement]').click()
            m.locator('[data-dept-business='+biz+']').click()
            m.locator('[data-pcu-tab=bulk]').click()
            m.locator('#pcu-section').select_option('receipt')
            button('receipt-examples').click()
        def done(name):
            passed.append(name)
            print('PASS', name, flush=True)
        # Start with an actual saved prior-version browser, including a user edit.
        f.locator('[data-page=procurement]').click()
        m.locator('[data-pcu-tab=bulk]').click()
        m.locator('#pcu-section').select_option('prep')
        m.locator('[data-pcu-col=orders][data-pcu-row=po-battery-1][data-pcu-key=owner]').fill('保存済みの購買担当')
        button('save').click()
        wait()
        original = data()
        original_cases = api('()=>__rx.snapshot().cases')
        original_stock = api('()=>__rx.stock("battery","pile","架空第一倉庫")')
        current_body[0] = fixture((ROOT/'index.html').read_text(), INJECT)
        p.reload(wait_until='networkidle')
        upgraded = data()
        for col in ['orders','lines','receipts','allocations','issues','transfers','invoices','payments','usagePlans']:
            by_id = {row['id']:row for row in upgraded[col]}
            for row in original[col]:
                assert by_id[row['id']] == row, (col, row['id'])
        assert api('()=>__rx.snapshot().cases') == original_cases
        assert api('()=>__rx.stock("battery","pile","架空第一倉庫")') == original_stock
        assert upgraded['receiptExamplesVersion'] == 1
        done('saved previous-version data and case IDs survive the additive example upgrade unchanged')

        for biz in ['battery','solar','datacenter']:
            open_receiving(biz)
            oid = 'po-receipt-example-'+biz+'-v1'
            d = data()
            order = next(o for o in d['orders'] if o['id']==oid)
            lines = [l for l in d['lines'] if l['orderId']==oid]
            def line(key): return next(l for l in lines if l['id'].endswith('-line-'+key))
            def received(l): return sum(x['qty'] for x in d['receipts'] if x['lineId']==l['id'])
            partial, complete, pending = line('partial'), line('complete'), line('pending')
            assert (partial['qty'], received(partial), partial['qty']-received(partial)) == (6,3,3)
            assert received(complete)==complete['qty']==4
            assert received(pending)==0 and pending['qty']==10
            rows = [r for r in d['receipts'] if r['lineId'] in [l['id'] for l in lines]]
            assert all(r['receiver'] and r['inspection'] and r['date'] for r in rows)
            stock = api('()=>__rx.stock('+json.dumps(biz)+',"monitor","架空納品サンプル倉庫")')
            assert stock=={'real':3,'unusable':1,'allocated':0,'available':2,'pending':3}
            assert '分納中' in m.inner_text() and '納品完了' in m.inner_text() and '未納' in m.inner_text()
            assert '1台に外装破損あり' in m.inner_text()
            assert m.locator('#pcu-filters [name=caseId]').input_value()==''
            assert order['number'] in m.inner_text()
            payments = [x for x in d['payments'] if x['orderId']==oid]
            assert len(payments)==1 and payments[0]['amount']==api('()=>__rx.total(__rx.data().orders.find(o=>o.id==='+json.dumps(oid)+'))')
            direct = [l for l in lines if l['route']=='direct']
            if biz=='datacenter':
                assert not direct and order['purpose']=='stock' and all(not l['caseId'] for l in lines)
            else:
                assert len(direct)==1 and received(direct[0])==1
                assert api('()=>__rx.stock('+json.dumps(biz)+',"pcs","架空納品サンプル倉庫").real')==0
            assert api('()=>__rx.stock('+json.dumps(biz)+',"freight","架空納品サンプル倉庫").real')==0
            api('()=>__rx.validate()')
        m.screenshot(path=str(OUT/'datacenter-receiving.png'))
        done('all three businesses show populated partial/full/pending and expense examples; direct deliveries, unusable stock and amounts stay consistent')

        # Execute an additional receipt on the example; preparation alone must have no stock effect.
        open_receiving('battery')
        oid = 'po-receipt-example-battery-v1'
        button('aux-receipt',oid+'-line-partial').click()
        dlg.locator('[name=qty]').fill('1')
        dlg.locator('[name=actualReceiver]').fill('追加荷受サンプル担当')
        dlg.locator('[name=inspection]').fill('追加受領分に異常なし')
        dlg.locator('#pc-save').click()
        button('save').click()
        wait()
        work = data()['workItems'][-1]
        assert api('()=>__rx.stock("battery","monitor","架空納品サンプル倉庫").real')==3
        button('execute',work['id']).click()
        dlg.locator('#pc-save').click()
        wait()
        assert api('()=>__rx.stock("battery","monitor","架空納品サンプル倉庫").real')==4
        assert api('()=>__rx.remaining(__rx.data().lines.find(l=>l.id==="po-receipt-example-battery-v1-line-partial"))')==2
        assert api('()=>__rx.stock("battery","pile","架空第一倉庫")')==original_stock
        m.screenshot(path=str(OUT/'battery-receiving.png'))
        saved = data()
        p.reload(wait_until='networkidle')
        assert data()==saved
        assert len({o['id'] for o in data()['orders']})==len(data()['orders'])
        assert len({r['id'] for r in data()['receipts']})==len(data()['receipts'])
        assert not errors, errors
        done('example accepts another partial receipt once, restores actual saved records on reload, and never duplicates the migration')
        browser.close()
    (OUT/'results.json').write_text(json.dumps({'passed':passed,'errors':errors}, ensure_ascii=False, indent=2))
    print('Results:',OUT)

if __name__=='__main__':
    run()
