"""Chromium checks for sales business/work tabs and shared project drafts."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect
from power_mock_smoke import server

OUTPUT=Path('/tmp/ecokaku-sales-review')

def run():
    OUTPUT.mkdir(exist_ok=True)
    passed, errors, writes = [], [], []
    with server() as url, sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1200})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
        page.goto(url,wait_until='networkidle')
        f=page.frame_locator('#codex-visualization')
        def done(name): passed.append(name);print('PASS',name,flush=True)
        def tab(key): f.locator('.sl-work-tabs [data-sales-tab='+key+']').click()
        def business(key): f.locator('[data-sales-business='+key+']').click()
        def cell(pid,key): return f.locator('[data-sales-project="'+pid+'"][data-sales-field="'+key+'"]')
        def shot(name,target='.sl-business-tabs'):
            f.locator(target).scroll_into_view_if_needed(); page.screenshot(path=str(OUTPUT/name))
        f.locator('[data-page=sales]').click()
        expect(f.locator('[data-sales-business=battery]')).to_have_attribute('aria-selected','true')
        expect(f.locator('#sales-tab-summary')).to_have_attribute('aria-selected','true')
        assert f.locator('.sl-business-tabs button').all_text_contents()==['蓄電池','太陽光','データセンター']
        assert f.locator('.sl-work-tabs button').all_text_contents()==['サマリー','データ入力','案件詳細']
        assert '未登録' in f.locator('#sales-view').inner_text()
        for key,icon in [('battery','battery'),('solar','solar-panel'),('datacenter','server')]:
            svg=f.locator('[data-sales-business='+key+'] svg');expect(svg).to_have_attribute('data-lucide',icon)
            assert 18<=svg.bounding_box()['width']<=20
            business(key)
            for t in ['summary','bulk','detail']:
                tab(t);expect(f.locator('#sales-tab-'+t)).to_have_attribute('aria-selected','true')
            business('battery');expect(f.locator('#sales-tab-detail')).to_have_attribute('aria-selected','true')
        business('solar');tab('summary')
        assert f.locator('#sales-demo-cases tr').count()==3
        assert f.locator('.sl-kpi strong').all_text_contents()==['3','—','—','—','—']
        assert f.locator('#sales-status option').all_text_contents()==['すべて','契約締結','検収済み','契約準備']
        assert f.locator('.sl-schedules').inner_text().count('未設定')==4
        shot('sales-summary.png')
        done('independent business tabs, SVG icons, default battery summary, solar originals and honest unknown KPIs')
        f.locator('#sales-search').fill('足利');assert f.locator('#sales-demo-cases tr').count()==1
        f.locator('[data-sales-open=P-00002]').first.click()
        expect(f.locator('#sales-demo-title')).to_have_text('足利第二 太陽光発電所')
        f.locator('#sales-view [data-sales-tab=summary]').click()
        expect(f.locator('#sales-search')).to_have_value('足利')
        f.locator('#sales-search').fill('');f.locator('#sales-status').select_option('契約準備')
        assert f.locator('#sales-demo-cases tr').count()==1
        f.locator('#sales-status').select_option('');f.locator('#sales-sort').select_option('name')
        done('search, existing status filters, sorting and list-detail return state')
        tab('bulk')
        assert f.locator('[data-sales-row]').count()==3
        assert all(50<=r.bounding_box()['height']<=54 for r in f.locator('[data-sales-row]').all())
        assert all(32<=e.bounding_box()['height']<=34 for e in f.locator('.sl-bulk-table input').all())
        assert not f.locator('.sl-bulk-table br').count()
        for row in f.locator('[data-sales-row]').all():assert row.locator('td').last.locator('[data-sales-open]').count()==1
        cell('P-00001','customer').fill('連続入力テスト株式会社')
        cell('P-00001','customer').press('Tab')
        expect(cell('P-00001','stage')).to_be_focused()
        cell('P-00001','stage').press('Shift+Tab');expect(cell('P-00001','customer')).to_be_focused()
        cell('P-00002','name').fill('足利第二 太陽光発電所（確認）')
        expect(cell('P-00002','name')).to_have_class('sl-dirty')
        shot('sales-data-input.png','#sales-bulk-scroll')
        f.locator('#sales-input-group').select_option('contract')
        cell('P-00001','equipment').fill('123.5')
        f.locator('[data-sales-action=save]').click()
        assert 'P-00001' in f.locator('#sales-errors').inner_text() and '整数' in f.locator('#sales-errors').inner_text()
        assert 'sl-invalid' in cell('P-00001','equipment').get_attribute('class')
        cell('P-00001','equipment').fill('35000000')
        cell('P-00001','date').fill('2026-10-05')
        business('datacenter');tab('summary');business('solar');tab('bulk')
        expect(cell('P-00001','date')).to_have_value('2026-10-05')
        f.locator('#sales-search').fill('G-00003')
        f.locator('[data-sales-action=save]').click()
        assert '保存しました' in f.locator('#sales-feedback').inner_text()
        f.locator('#sales-search').fill('');f.locator('#sales-input-group').select_option('basic')
        expect(cell('P-00001','customer')).to_have_value('連続入力テスト株式会社')
        expect(cell('P-00002','name')).to_have_value('足利第二 太陽光発電所（確認）')
        assert not f.locator('.sl-dirty').count()
        done('52px rows, 34px editors, Tab/Shift-Tab, multi-case drafts, errors and saving hidden drafts')
        cell('P-00001','name').fill('取り消す名前')
        f.locator('#sales-search').fill('G-00003')
        f.locator('[data-sales-action=cancel]').click();f.locator('#sales-search').fill('')
        expect(cell('P-00001','name')).to_have_value('佐野第一 太陽光発電所')
        f.locator('#sales-input-group').select_option('contract')
        sc=f.locator('#sales-bulk-scroll');f.locator('.sl-bulk-table').scroll_into_view_if_needed()
        before=f.locator('td.sl-pin-id').first.bounding_box()['x']
        sc.evaluate('(e)=>e.scrollLeft=600')
        assert abs(f.locator('td.sl-pin-id').first.bounding_box()['x']-before)<1
        assert f.locator('td.sl-pin-name').first.bounding_box()['x']>=before+109
        tab('summary');f.locator('[data-sales-open=P-00001]').first.click()
        expect(f.locator('#sales-demo-date')).to_have_value('2026-10-05')
        assert '35,000,000' in f.locator('#sales-demo-panel').inner_text()
        shot('sales-case-detail.png')
        f.locator('[data-section=invoice]').click();f.locator('#sales-demo-request').click();f.locator('#sales-demo-confirm').click()
        assert '依頼済み' in f.locator('#sales-demo-panel').inner_text()
        f.locator('[data-section=receipt]').click();assert '経理確認済み入金額' in f.locator('#sales-demo-panel').inner_text()
        f.locator('[data-section=handover]').click();assert '検収予定日' in f.locator('#sales-demo-panel').inner_text()
        f.locator('[data-section=contract]').click();f.locator('#sales-demo-date').fill('2026-10-06');f.locator('#sales-demo-save').click()
        expect(f.locator('#sales-demo-date')).to_have_value('2026-10-06')
        done('cancel includes hidden drafts; pinned columns; original contract/invoice/receipt/handover functions retained')
        f.locator('[data-page=legal]').click();f.locator('#legal-workspace [data-dept-business=solar]').click();f.locator('#legal-workspace [data-dept-open=P-00001]').first.click();f.locator('[data-legal-tab=contract]').click()
        expect(f.locator('#legal-demo-date')).to_have_value('2026-10-06')
        expect(f.locator('#legal-demo-amount')).to_have_value('35000000')
        f.locator('#legal-demo-number').fill('SC-SALES-REVIEW');f.locator('#legal-demo-save').click()
        f.locator('[data-open-sales=contract]').click()
        assert 'SC-SALES-REVIEW' in f.locator('#sales-demo-panel').inner_text()
        f.locator('#sales-demo-date').fill('2026-10-08')
        f.locator('[data-page=legal]').click();f.locator('#legal-workspace [data-dept-business=solar]').click();f.locator('#legal-workspace [data-dept-open=P-00001]').first.click();f.locator('#legal-demo-date').fill('2026-10-07');f.locator('#legal-demo-save').click()
        f.locator('[data-open-sales=contract]').click();f.locator('#sales-demo-save').click()
        assert '他画面で更新' in f.locator('#sales-errors').inner_text()
        expect(f.locator('#sales-demo-date')).to_have_value('2026-10-08')
        f.locator('[data-sales-action=cancel]').click();expect(f.locator('#sales-demo-date')).to_have_value('2026-10-07')
        f.locator('[data-page=power]').click()
        assert f.locator('[data-power-summary-row]').count()==10
        expect(f.locator('#power-tab-summary')).to_have_attribute('aria-selected','true')
        f.locator('[data-page=settings]').click();f.locator('[data-setting=users]').click()
        assert f.locator('#settings-user-name').is_visible()
        done('shared legal edits, conflict protection, unchanged power 10 samples and settings')
        page.reload(wait_until='networkidle');f.locator('[data-page=sales]').click();business('solar');tab('bulk')
        expect(cell('P-00001','customer')).to_have_value('サンプルエナジー株式会社')
        page.set_viewport_size({'width':800,'height':1050})
        assert f.locator('.sl-business-tabs').is_visible()
        shot('sales-narrow-input.png','#sales-bulk-scroll')
        assert errors==[],errors
        assert writes==[],writes
        done('reload resets mock data; narrow layout; no JavaScript errors or external writes')
        browser.close()
    (OUTPUT/'results.json').write_text(json.dumps({'passed':passed,'js_errors':errors,'external_writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
