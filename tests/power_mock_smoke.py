"""Real Chromium regression checks for the power three-tab mock.
Run: python3 tests/power_mock_smoke.py
Requires Python Playwright and /usr/bin/chromium; starts its own local server.
Results/screenshots: /tmp/ecokaku-power-three-review (ECOKAKU_REVIEW_DIR overrides).
"""
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import threading
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(os.environ.get('ECOKAKU_REVIEW_DIR', '/tmp/ecokaku-power-three-review'))

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

@contextmanager
def server():
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}/'
    finally:
        httpd.shutdown()
        httpd.server_close()


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'results.json').unlink(missing_ok=True)
    passed, errors, failed_requests, external_http, writes = [], [], [], [], []
    with server() as url, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 1300}, timezone_id='Asia/Tokyo')
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.on('requestfailed', lambda req: failed_requests.append({'url': req.url, 'error': req.failure}))
        page.on('request', lambda req: writes.append({'url': req.url, 'method': req.method}) if req.method not in ['GET', 'HEAD', 'OPTIONS'] else None)
        page.on('response', lambda r: external_http.append({'url': r.url, 'status': r.status}) if r.url.startswith('https:') and r.status >= 400 else None)
        assert page.goto(url, wait_until='networkidle').status == 200
        f = page.frame_locator('#codex-visualization')
        inner = page.frames[1]
        def done(name):
            passed.append(name)
            print('PASS', name, flush=True)
        def tab(name):
            f.locator(f'.pw-primary-tabs [data-power-tab="{name}"]').click()
            expect(f.locator(f'#power-tab-{name}')).to_have_attribute('aria-selected', 'true')
        def case(i):
            f.locator('#power-detail-case').select_option(str(i))
        def section(name):
            loc = f.locator(f'#power-section-{name}')
            if loc.get_attribute('open') is None:
                loc.locator(':scope > summary').click()
            return loc
        def detail(i=0, name='basic'):
            tab('detail')
            case(i)
            section(name)
        def field(key):
            loc = f.locator(f'#power-value-{key}')
            owner = loc.locator('xpath=ancestor::details[contains(@class,"pw-section")]')
            if owner.get_attribute('open') is None:
                owner.locator(':scope > summary').click()
            return loc
        def set_value(loc, value):
            if loc.evaluate('(e)=>e.tagName') == 'SELECT':
                loc.select_option(value)
            else:
                loc.fill(value)
                loc.dispatch_event('input')
        def value(key, value):
            set_value(field(key), value)
        def cell(pid, key):
            return f.locator(f'[data-power-bulk-row="{pid}"] [data-power-field="{key}"]')
        def save_case():
            f.locator('[data-power-action=saveCase]').first.click()
            assert f.locator('.pw-errors').count() == 0
        def save_all():
            f.locator('[data-power-action=saveAll]').click()
        def bulk(stage='connection'):
            tab('bulk')
            f.locator('#power-bulk-stage').select_option(stage)
        def clear_filters():
            f.locator('[data-power-action=clearFilters]').click()
        def screenshot(name, target='.pw-primary-tabs'):
            page.evaluate('window.scrollTo(0,0)')
            inner.locator(target).scroll_into_view_if_needed()
            page.wait_for_timeout(150)
            page.screenshot(path=str(OUTPUT/name))
        f.locator('[data-page=power]').click()
        f.locator('[data-power-business=battery]').click()
        expect(f.locator('#power-tab-summary')).to_have_attribute('aria-selected', 'true')
        assert f.locator('.pw-primary-tabs [role=tab]').all_text_contents() == ['サマリー','データ入力','案件詳細']
        assert '2026-11-04' in f.locator('.pw-demo-note').inner_text()
        done('initial summary, exactly three primary tabs, explicit demo date')
        for status in ['', 'answer', 'payment', 'proof', 'overdue']:
            card = f.locator(f'[data-power-card="{status}"]')
            count = int(card.get_attribute('data-count'))
            card.click()
            assert f.locator('[data-power-summary-row]').count() == count
            expect(f.locator('#power-list-count')).to_have_text(f'{count}件')
        f.locator('[data-power-card=""]').click()
        assert f.locator('[data-power-summary-row]').first.get_attribute('data-power-summary-row') == 'P-00001'
        done('all count cards match filtered list and progress ordering')
        f.locator('[data-power-filter=owner]').select_option('申請担当A')
        f.locator('#power-summary-equipment').select_option('missing')
        f.locator('[data-power-filter=sort]').select_option('deadline')
        f.locator('#power-search').fill('G-00003')
        f.locator('#power-search').press('Tab')
        assert f.locator('[data-power-summary-row]').count() == 1
        f.locator('[data-power-summary-row="G-00003"] [data-power-section=basic]').first.click()
        expect(f.locator('#power-detail-case')).to_have_value('2')
        expect(f.locator('#power-section-basic')).to_have_attribute('open', '')
        f.locator('[data-power-tab=summary]').last.click()
        expect(f.locator('[data-power-filter=owner]')).to_have_value('申請担当A')
        expect(f.locator('#power-summary-equipment')).to_have_value('missing')
        expect(f.locator('[data-power-filter=sort]')).to_have_value('deadline')
        assert f.locator('[data-power-summary-row]').count() == 1
        clear_filters()
        f.locator('[data-power-summary-row="G-00005"] [data-power-focus=connectionProof]').click()
        expect(f.locator('#power-detail-case')).to_have_value('4')
        expect(f.locator('#power-section-connection')).to_have_attribute('open', '')
        assert f.locator('#power-section-connection [data-power-field=connectionProof]').evaluate('(e)=>e===document.activeElement')
        section('basic')
        case(0);section('connection');section('basic')
        assert f.locator('.pw-section[open]').count() >= 2
        case(1)
        section('receipt')
        case(0)
        assert f.locator('#power-section-connection').get_attribute('open') == ''
        done('filters persist on return; names/warnings open correct project and section; multiple sections persist by project')
        bulk('connection')
        assert cell('P-00001','24').count() == 1
        assert cell('P-00001','42').count() == 0
        table = f.locator('#power-bulk-scroll')
        before = f.locator('tbody .pw-pin-id').first.bounding_box()
        name_before = f.locator('tbody .pw-pin-name').first.bounding_box()
        table.evaluate('(e)=>e.scrollLeft=900')
        after = f.locator('tbody .pw-pin-id').first.bounding_box()
        name_after = f.locator('tbody .pw-pin-name').first.bounding_box()
        assert abs(before['x']-after['x']) < 2 and abs(name_before['x']-name_after['x']) < 2
        assert name_after['x'] >= after['x']+after['width']-1
        assert table.evaluate('(e)=>e.scrollWidth>e.clientWidth')
        table.evaluate('(e)=>{e.style.height="150px";e.scrollTop=100}')
        head=f.locator('.pw-bulk-table th').first.bounding_box()
        box=table.bounding_box()
        assert abs(head['y']-box['y'])<3
        table.evaluate('(e)=>{e.style.removeProperty("height");e.scrollTop=0;e.scrollLeft=0}')
        f.locator('#power-bulk-stage').select_option('main')
        assert cell('P-00001','42').count()==1 and cell('P-00001','24').count()==0
        assert f.locator('[data-power-field="45"]').count()==0 and '経理参照' in f.locator('.pw-cell-reference').first.get_attribute('title')
        done('five-stage columns, read-only accounting, sticky IDs/names and non-overlapping sticky headers')
        bulk('connection')
        set_value(cell('P-00001','28'),'2027-02-01')
        set_value(cell('P-00002','28'),'2027-02-02')
        set_value(cell('P-00001','7'),'一括下書き案件A')
        assert '3件' in f.locator('.pw-draft-count').inner_text()
        expect(cell('P-00001','28')).to_have_class('pw-edit is-dirty')
        cell('P-00001','31').focus()
        cell('P-00001','31').press('Tab')
        assert cell('P-00001','28').evaluate('(e)=>e===document.activeElement')
        f.locator('#power-bulk-stage').select_option('operation')
        f.locator('#power-bulk-stage').select_option('connection')
        expect(cell('P-00001','28')).to_have_value('2027-02-01')
        tab('summary')
        assert '一括下書き案件A' not in f.locator('.pw-summary-table').inner_text()
        f.locator('#power-search').fill('P-00001')
        f.locator('#power-search').press('Tab')
        assert f.locator('[data-power-summary-row]').count()==1
        clear_filters()
        detail(0,'connection')
        expect(field('28')).to_have_value('2027-02-01')
        expect(field('7')).to_have_value('一括下書き案件A')
        value('28','2027-02-10')
        bulk('connection')
        expect(cell('P-00001','28')).to_have_value('2027-02-10')
        set_value(cell('P-00001','31'),'000-受付番号')
        detail(0,'connection')
        expect(field('31')).to_have_value('000-受付番号')
        bulk('connection')
        set_value(cell('P-00001','34'),'1.5')
        set_value(cell('P-00002','33'),'-1')
        save_all()
        assert 'P-00001' in f.locator('.pw-errors').inner_text() and '整数' in f.locator('.pw-errors').inner_text()
        assert 'P-00002' in f.locator('.pw-errors').inner_text() and '0以上' in f.locator('.pw-errors').inner_text()
        expect(cell('P-00002','28')).to_have_value('2027-02-02')
        expect(cell('P-00001','34')).to_have_value('1.5')
        set_value(cell('P-00001','34'),'1')
        set_value(cell('P-00002','33'),'12000000')
        save_all()
        assert f.locator('.pw-errors').count()==0
        expect(f.locator('.pw-draft-count')).to_contain_text('0件')
        tab('summary')
        assert '一括下書き案件A' in f.locator('.pw-summary-table').inner_text()
        detail(0,'connection')
        expect(field('28')).to_have_value('2027-02-10')
        section('records')
        assert '接続検討 回答予定日：' in f.locator('#power-section-records').inner_text()
        done('multi-case drafts, Tab input, preserved navigation/search, shared cross-view edits, atomic validation and save')
        bulk('connection')
        set_value(cell('P-00001','28'),'2030-01-01')
        bulk('operation')
        set_value(cell('P-00002','99'),'2030-01-02')
        f.locator('[data-power-filter=owner]').select_option('申請担当A')
        f.locator('[data-power-action=cancelAll]').click()
        expect(f.locator('.pw-draft-count')).to_contain_text('0件')
        clear_filters()
        expect(cell('P-00002','99')).to_have_value('')
        bulk('connection')
        expect(cell('P-00001','28')).to_have_value('2027-02-10')
        done('cancel removes drafts across hidden stages and filtered-out projects without changing saved values')
        tab('summary')
        baseline_answer=int(f.locator('[data-power-card=answer]').get_attribute('data-count'))
        baseline_payment=int(f.locator('[data-power-card=payment]').get_attribute('data-count'))
        detail(3,'connection')
        f.locator('[data-power-na="29"]').check()
        save_case()
        tab('summary')
        assert int(f.locator('[data-power-card=answer]').get_attribute('data-count'))==baseline_answer-1
        bulk('connection')
        assert cell('G-00004','29').is_disabled()
        expect(cell('G-00004','29')).to_have_value('対象外')
        detail(3,'connection')
        f.locator('[data-power-na="29"]').uncheck()
        save_case()
        tab('summary')
        assert int(f.locator('[data-power-card=answer]').get_attribute('data-count'))==baseline_answer
        detail(3,'connection')
        f.locator('[data-power-scope=connection]').check()
        save_case()
        tab('summary')
        assert int(f.locator('[data-power-card=answer]').get_attribute('data-count'))==baseline_answer-1
        assert int(f.locator('[data-power-card=payment]').get_attribute('data-count'))==baseline_payment-1
        detail(3,'connection')
        f.locator('[data-power-scope=connection]').uncheck()
        save_case()
        detail(0,'basic')
        value('18','1.5')
        value('追加1','独立した申請住所')
        f.locator('[data-power-action=saveCase]').first.click()
        assert 'PCS台数' in f.locator('.pw-errors').inner_text()
        expect(field('追加1')).to_have_value('独立した申請住所')
        value('18','5')
        value('20','6')
        value('17','PCS-B（サンプル）')
        value('19','BAT-B（サンプル）')
        value('13','アグリゲーターB（サンプル）')
        f.locator('[data-power-action=qbAdd]').click()
        f.locator('[data-power-qb="1"][data-qb-key=maker]').select_option('メーカーB（サンプル）')
        f.locator('[data-power-qb="1"][data-qb-key=spec]').select_option('QB-B（サンプル）')
        save_case()
        expect(field('18')).to_have_value('5')
        assert not field('17').evaluate('(e)=>e.multiple') and not field('19').evaluate('(e)=>e.multiple')
        assert 'アグリゲーターA（サンプル） → アグリゲーターB（サンプル）' in f.locator('#power-section-records').inner_text()
        done('out-of-scope exclusion, integer equipment counts, single models, multi-line cubicles and aggregator history')
        value('42','2028-01-31')
        value('burdenPlanned','2028-01-31')
        value('34','1')
        value('35','1')
        value('forecastPhase','connection')
        value('burdenBase','planned')
        expect(f.locator('#power-forecast-result')).to_contain_text('2028-02-29')
        value('35','2')
        expect(f.locator('#power-forecast-result')).to_contain_text('2028-03-31')
        value('42','2027-01-31')
        value('burdenPlanned','2027-01-31')
        value('35','1')
        expect(f.locator('#power-forecast-result')).to_contain_text('2027-02-28')
        value('42','')
        expect(f.locator('#power-forecast-result')).to_contain_text('算出に必要な日付が未登録')
        value('forecastPhase','main')
        value('54','2027-06-30')
        expect(f.locator('#power-forecast-result')).to_contain_text('2027-06-30')
        value('forecastPhase','coordination')
        value('agreedForecast','2027-07-15')
        expect(f.locator('#power-forecast-result')).to_contain_text('2027-07-15')
        value('57','9876543')
        value('55','14000000')
        expect(field('57')).to_have_value('9876543')
        value('88','2027-08-31')
        expect(f.locator('#power-preparation-target')).to_contain_text('2027-02-28')
        save_case()
        assert '連系見込を更新' in f.locator('#power-section-records').inner_text()
        assert '220,000円' in f.locator('#power-section-connection').inner_text()
        done('retained forecast stages/missing bases/leap month end, six-month preparation target, invoice amounts not overwritten')
        value('74','0012345678901234567890');value('追加3','0012345678901234567890')
        expect(f.locator('#power-point-match')).to_contain_text('一致')
        value('追加3','0000000000000000000001')
        expect(f.locator('#power-point-match')).to_contain_text('不一致')
        value('追加3','')
        expect(f.locator('#power-point-match')).to_contain_text('未入力')
        value('追加3','0012345678901234567890')
        value('77','00000042')
        value('79','EXCEPTION-123')
        save_case()
        bulk('grid')
        expect(cell('P-00001','77')).to_have_value('00000042')
        expect(cell('P-00001','79')).to_have_value('EXCEPTION-123')
        assert cell('P-00001','87').count()==0
        detail(0,'preparation')
        value('utility','東京電力');value('internetTest','')
        assert field('87').is_disabled()
        assert not field('90').is_disabled()
        value('90','2026-11-06')
        expect(f.locator('#power-pcs-check')).to_contain_text('疎通試験完了日が未登録')
        value('64','2026-11-01')
        expect(field('internetTest')).to_have_value('')
        value('internetTest','2026-11-07')
        expect(f.locator('#power-pcs-check')).to_contain_text('疎通試験完了前の提出')
        value('90','2026-11-08')
        expect(f.locator('#power-pcs-check')).to_contain_text('疎通試験完了後')
        value('utility','中部電力')
        assert not field('87').is_disabled()
        value('82','自由入力支社')
        save_case()
        assert '並行' in f.locator('.pw-parallel').inner_text() or '主工程' in f.locator('.pw-parallel').inner_text()
        assert f.locator('.pw-parallel [data-power-focus="61"]').count()==1
        done('leading-zero IDs, point comparisons, utility applicability, independent communication test and visible parallel work')
        section('records')
        for key,name in [('settings','整定値一覧.pdf'),('plantId','発電所ID.pdf')]:
            f.locator(f'#power-file-{key}').set_input_files({'name':name,'mimeType':'application/pdf','buffer':b'name only'})
            section('records')
            expect(f.locator(f'[data-power-filename="{key}"]')).to_have_text(name)
        f.locator('#power-task-text').fill('追加タスク検証')
        f.locator('#power-task-due').fill('2026-11-30')
        f.locator('[data-power-action=taskAdd]').click()
        section('records')
        task=f.locator('.pw-task').filter(has_text='追加タスク検証')
        task.locator('input[type=checkbox]').check()
        save_case()
        section('operation')
        f.locator('#power-file-circular').set_input_files({'name':'最新版回覧板.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':b'name only'})
        save_case()
        value('kind','太陽光');section('operation')
        assert field('101').is_disabled()
        for key in ['94','96','97','98']:
            assert f.locator(f'#power-value-{key}').count()==0
        labels=f.locator('#power-section-operation .s-field > label[for]').all_text_contents()
        assert labels[-1]=='EPRX参入日' and labels.index('EPRX参入日')>labels.index('参入資料提出日（需給調整市場・アグリ）')
        case(2)
        section('operation')
        assert not field('101').is_disabled()
        section('records')
        assert '追加タスク検証' not in f.locator('#power-section-records').inner_text()
        assert '発電所ID.pdf' not in f.locator('#power-section-records').inner_text()
        case(0)
        section('records')
        assert '追加タスク検証' in f.locator('#power-section-records').inner_text()
        assert '最新版回覧板.xlsx' in f.locator('#power-section-records').inner_text()
        done('per-case attachments/tasks/history, solar JEPX exclusion, removed items and EPRX ordering')
        section('connection')
        value('31','000-PENDING')
        f.locator('[data-power-action=reconnect]').click()
        assert f.locator('[role=alertdialog]').count()==0
        expect(f.locator('#power-message')).to_contain_text('下書き')
        save_case()
        f.locator('[data-power-action=reconnect]').click()
        f.locator('[data-power-action=reconnectCancel]').click()
        assert '申請回 1' in f.locator('.pw-casehead').inner_text()
        f.locator('[data-power-action=reconnect]').click()
        f.locator('[data-power-action=reconnectConfirm]').click()
        assert '申請回 2' in f.locator('.pw-casehead').inner_text()
        expect(field('24')).to_have_value('')
        expect(field('57')).to_have_value('9876543')
        expect(field('77')).to_have_value('00000042')
        expect(field('追加1')).to_have_value('独立した申請住所')
        assert '000-PENDING' in f.locator('#power-section-records').inner_text()
        done('reconnection protects drafts, supports cancellation, archives old application and retains other stages')
        # Existing department workflows remain independently usable.
        f.locator('[data-page=sales]').click()
        f.locator('#sales-workspace .du-business-tabs').get_by_role('tab',name='太陽光',exact=True).click()
        f.locator('[data-sales-open=P-00001]').first.click()
        f.locator('[data-section=contract]').click()
        f.locator('#sales-demo-date').fill('2026-10-05')
        f.locator('#sales-demo-save').click()
        expect(f.locator('#sales-demo-date')).to_have_value('2026-10-05')
        f.locator('[data-page=legal]').click();f.locator('#legal-workspace [data-dept-business=solar]').click();f.locator('#legal-workspace [data-dept-open=P-00001]').first.click()
        f.locator('[data-legal-tab=contract]').click()
        f.locator('#legal-demo-number').fill('SC-THREE-001')
        f.locator('#legal-demo-save').click()
        f.locator('[data-page=sales]').click()
        f.locator('#sales-workspace .du-business-tabs').get_by_role('tab',name='太陽光',exact=True).click()
        f.locator('[data-sales-open=P-00001]').first.click()
        assert 'SC-THREE-001' in f.locator('#sales-demo-panel').inner_text()
        f.locator('[data-page=settings]').click()
        f.locator('[data-setting=masters]').click()
        f.locator('#settings-master-kind').select_option('PCS型式')
        f.locator('#settings-master-name').fill('PCS-追加サンプル')
        f.locator('#settings-master-add').click()
        f.locator('[data-setting=users]').click()
        f.locator('#settings-user-name').fill('検証ユーザー')
        f.locator('#settings-user-email').fill('three@example.com')
        f.locator('#settings-user-save').click()
        assert 'three@example.com' in f.locator('#settings-demo-detail').inner_text()
        f.locator('[data-page=power]').click()
        f.locator('[data-power-business=battery]').click()
        detail(0,'basic')
        value('17','PCS-追加サンプル')
        save_case()
        done('sales/legal shared contract edits, settings users and equipment master linkage preserved')
        # Reload preserves saved cases; unsaved UI state resets for review screenshots.
        page.reload(wait_until='networkidle')
        inner=page.frames[1]
        f.locator('[data-page=power]').click()
        f.locator('[data-power-business=battery]').click()
        assert '一括下書き案件A' in f.locator('.pw-summary-table').inner_text()
        expect(f.locator('#power-tab-summary')).to_have_attribute('aria-selected','true')
        screenshot('power-summary.png')
        bulk('connection')
        screenshot('power-bulk.png')
        detail(0,'basic')
        for name in ['connection','main','aggregator','preparation','receipt','operation','records']:
            loc=f.locator('#power-section-'+name)
            if loc.get_attribute('open') is not None:
                loc.locator(':scope > summary').click()
        screenshot('power-detail.png')
        page.set_viewport_size({'width':390,'height':900})
        bulk('connection')
        scroller=f.locator('#power-bulk-scroll')
        scroller.evaluate('(e)=>e.scrollLeft=650')
        width=scroller.evaluate('(e)=>e.clientWidth')
        pins=f.locator('tbody .pw-pin-name').first.bounding_box()
        ids=f.locator('tbody .pw-pin-id').first.bounding_box()
        assert width > pins['width']+ids['width']+100
        screenshot('power-bulk-mobile.png','#power-bulk-scroll')
        expect(f.locator('.pw-primary-tabs')).to_be_visible()
        done('reload restores saved cases and resets view state; screenshots of all three tabs and usable mobile sticky columns')
        assert not errors, errors
        assert not failed_requests, failed_requests
        assert not external_http, external_http
        assert not writes, writes
        done('no uncaught JavaScript errors, failed resources or write/upload requests')
        result={'passed':passed,'page_errors':errors,'failed_requests':failed_requests,'external_http_errors':external_http,'write_requests':writes}
        (OUTPUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps(result,ensure_ascii=False,indent=2))
        browser.close()

if __name__=='__main__':
    run()
