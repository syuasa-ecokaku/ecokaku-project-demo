"""Browser regression checks. Run: python3 tests/power_mock_smoke.py
Requires Python Playwright and system Chromium; starts its own local HTTP server.
Screenshots/results are written outside the checkout under /tmp/ecokaku-power-review.
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
OUTPUT = Path(os.environ.get('ECOKAKU_REVIEW_DIR', '/tmp/ecokaku-power-review'))

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
    passed, errors, failed_requests, external_http = [], [], [], []
    with server() as url, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 1100}, timezone_id='Asia/Tokyo')
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.on('requestfailed', lambda req: failed_requests.append({'url': req.url, 'error': req.failure}))
        page.on('response', lambda r: external_http.append({'url': r.url, 'status': r.status}) if r.url.startswith('https:') and r.status >= 400 else None)
        assert page.goto(url, wait_until='networkidle').status == 200
        frame = page.frame_locator('#codex-visualization')
        app_frame = page.frames[1]
        def done(name):
            passed.append(name)
            print('PASS', name, flush=True)
        def tab(name):
            frame.locator(f'button[role=tab][data-power-tab="{name}"]').click()
            expect(frame.locator(f'#power-tab-{name}')).to_have_attribute('aria-selected', 'true')
        def case(i):
            frame.locator(f'[data-power-case="{i}"]').click()
        def value(key, value):
            el = frame.locator(f'[data-power-field="{key}"]')
            if el.evaluate('(e)=>e.tagName') == 'SELECT':
                el.select_option(value)
            else:
                el.fill(value)
                el.dispatch_event('change')
        def text():
            return frame.locator('#power-demo-panel').inner_text()
        def shot(name):
            page.evaluate('window.scrollTo(0, 0)')
            page.locator('#codex-visualization').evaluate('(e)=>e.style.removeProperty("height")')
            app_frame.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
            app_frame.locator('#power-demo-main .s-detailhead').evaluate('(e)=>window.scrollTo(0,e.getBoundingClientRect().top+window.scrollY-8)')
            app_frame.evaluate('() => new Promise(resolve => requestAnimationFrame(resolve))')
            page.screenshot(path=str(OUTPUT / name), full_page=False)
        frame.locator('[data-page="power"]').click()
        for name in ['overview', 'connection', 'main', 'coordination', 'operation', 'tasks']:
            tab(name)
        done('six tabs switch without JavaScript errors')
        case(2)
        tab('connection')
        assert frame.locator('[data-power-status=answer]').get_attribute('data-count') == '1'
        frame.locator('[data-power-na="29"]').check()
        assert frame.locator('#power-value-29').is_disabled()
        assert frame.locator('[data-power-status=answer]').get_attribute('data-count') == '0'
        frame.locator('[data-power-na="29"]').uncheck()
        assert frame.locator('[data-power-status=answer]').get_attribute('data-count') == '1'
        case(0)
        done('out-of-scope dates stay separate from missing inputs and do not trigger answer alerts')
        tab('overview')
        value('7', '独立保存する申請名')
        value('追加1', '独立保存する申請住所')
        frame.locator('#power-demo-save').click()
        expect(frame.locator('#power-demo-message')).to_contain_text('画面内で保存')
        case(1)
        assert frame.locator('#power-value-7').input_value() != '独立保存する申請名'
        case(0)
        expect(frame.locator('#power-value-7')).to_have_value('独立保存する申請名')
        expect(frame.locator('#power-value-追加1')).to_have_value('独立保存する申請住所')
        done('application name/address save independently by project')
        integer = frame.locator('#power-value-18')
        integer.fill('1.5')
        integer.dispatch_event('change')
        assert not integer.evaluate('(e)=>e.checkValidity()')
        integer.fill('5')
        integer.dispatch_event('change')
        value('20', '6')
        assert frame.locator('#power-value-14').evaluate('(e)=>e.closest(".s-formgrid") === document.getElementById("power-value-15").closest(".s-formgrid")')
        expect(frame.locator('#power-value-18')).to_have_value('5')
        for key in ['17', '19']:
            assert not frame.locator(f'#power-value-{key}').evaluate('(e)=>e.multiple')
        value('13', 'アグリゲーターB（サンプル）')
        value('17', 'PCS-B（サンプル）')
        frame.locator('#power-qb-add').click()
        frame.locator('#power-qb-maker-1').select_option('メーカーB（サンプル）')
        frame.locator('#power-qb-spec-1').select_option('QB-B（サンプル）')
        tab('tasks')
        assert 'アグリゲーターA（サンプル） → アグリゲーターB（サンプル）' in text()
        tab('overview')
        expect(frame.locator('#power-qb-spec-1')).to_have_value('QB-B（サンプル）')
        done('integer validation, single-select models, aggregator history, multi-row cubicles')
        # End-of-month predictions use both bases and the later date.
        tab('main')
        value('42', '2028-01-31')
        value('burdenPlanned', '2028-01-31')
        value('57', '9876543')
        value('55', '14000000')
        expect(frame.locator('#power-value-57')).to_have_value('9876543')
        assert frame.locator('[data-power-field="45"]').count() == 0
        assert frame.locator('[data-power-field="58"]').count() == 0
        assert frame.locator('#power-value-54').get_attribute('type') == 'date'
        tab('connection')
        value('34', '1')
        value('35', '1')
        value('forecastPhase', 'connection')
        value('burdenBase', 'planned')
        expect(frame.locator('#power-forecast-result')).to_contain_text('2028-02-29')
        value('35', '2')
        expect(frame.locator('#power-forecast-result')).to_contain_text('2028-03-31')
        tab('main')
        value('42', '2027-01-31')
        value('burdenPlanned', '2027-01-31')
        tab('connection')
        value('35', '1')
        expect(frame.locator('#power-forecast-result')).to_contain_text('2027-02-28')
        tab('main')
        value('42', '')
        expect(frame.locator('#power-forecast-result')).to_contain_text('算出に必要な日付が未登録')
        value('forecastPhase', 'main')
        value('54', '2027-06-30')
        expect(frame.locator('#power-forecast-result')).to_contain_text('2027-06-30')
        frame.locator('[data-power-na="54"]').check()
        expect(frame.locator('#power-forecast-result')).to_contain_text('算出に必要な日付が未登録')
        frame.locator('[data-power-na="54"]').uncheck()
        expect(frame.locator('#power-value-54')).to_have_value('2027-06-30')
        tab('coordination')
        value('agreedForecast', '2027-07-15')
        value('forecastPhase', 'coordination')
        expect(frame.locator('#power-forecast-result')).to_contain_text('2027-07-15')
        value('forecastPhase', 'connection')
        value('burdenBase', 'actual')
        expect(frame.locator('#power-forecast-result')).to_contain_text('実績')
        assert '連系見込の更新履歴（0件）' not in text()
        done('forecast stages, missing base, planned/actual, leap/non-leap month-end, history')
        tab('connection')
        assert '220,000円' in text()
        assert '支払済み・証憑未送付' in text()
        assert frame.locator('[data-power-field="26"]').count() == 0
        assert frame.locator('[data-power-status=proof]').get_attribute('data-count') == '2'
        value('connectionProof', '2026-07-11')
        # Counts are projects, not invoices: this project still has burden proof pending.
        assert frame.locator('[data-power-status=proof]').get_attribute('data-count') == '2'
        tab('main')
        value('burdenProof', '2026-10-16')
        assert frame.locator('[data-power-status=proof]').get_attribute('data-count') == '1'
        tab('connection')
        assert '支払済み・証憑送付済み' in text()
        value('28', '2027-01-15')
        tab('tasks')
        assert '接続検討 回答予定日：' in text()
        done('220,000 fee, accounting references, proof state, answer date history')
        tab('coordination')
        assert '番号照合：一致' in text()
        value('追加3', '0000000000000000000001')
        assert '番号照合：不一致' in text()
        value('追加3', '')
        assert '番号照合：未入力' in text()
        value('追加3', '0012345678901234567890')
        value('77', '00000042')
        value('79', 'EXCEPTION-123')
        expect(frame.locator('#power-value-79')).to_have_value('EXCEPTION-123')
        assert '供給地点番号' not in text()
        done('point number match/mismatch/missing and leading zeros; unrestricted grid code')
        value('91', '2026-11-01')
        value('92', '2026-11-02')
        assert '未完了（両側の完了日が必要）' in text()
        value('generationDone', '2026-11-03')
        value('supplyDone', '2026-11-04')
        assert '2026-11-04' in text()
        value('utility', '東京電力')
        assert frame.locator('#power-value-87').is_disabled()
        assert not frame.locator('#power-value-90').is_disabled()
        value('90', '2026-11-06')
        assert '疎通試験完了日が未登録' in text()
        frame.locator('#power-demo-group').select_option('facilities')
        value('64', '2026-11-01')
        expect(frame.locator('#power-value-internetTest')).to_have_value('')
        value('internetTest', '2026-11-07')
        frame.locator('#power-demo-group').select_option('grid')
        assert '疎通試験完了前の日付' in text()
        value('90', '2026-11-08')
        assert '疎通試験完了後の提出を確認' in text()
        value('utility', '中部電力')
        assert not frame.locator('#power-value-87').is_disabled()
        value('82', '自由入力支社')
        value('83', '担当変更サンプル')
        value('84', 'contact@example.com')
        for key in ['supplyDesired', 'supplyStart']:
            assert frame.locator(f'#power-value-{key}').get_attribute('type') == 'date'
        done('two-sided completion, utility conditions, independent internet test, editable branch/contact, new dates')
        for key, filename in [('settings', '整定値一覧サンプル.pdf'), ('plantId', '発電所IDサンプル.pdf')]:
            frame.locator(f'#power-file-{key}').set_input_files({'name': filename, 'mimeType': 'application/pdf', 'buffer': b'mock name only'})
            expect(frame.locator(f'[data-power-filename="{key}"]')).to_have_text(filename)
        shot('power-coordination.png')
        tab('operation')
        assert frame.locator('#power-value-101').is_disabled()
        for no in ['94', '96', '97', '98']:
            assert frame.locator(f'#power-value-{no}').count() == 0
        labels = frame.locator('#power-demo-panel label').all_text_contents()
        assert labels.index('EPRX参入日') > labels.index('参入資料提出日（需給調整市場・アグリ）')
        assert labels[-1] == 'EPRX参入日' or labels[-1].startswith('対象外')
        for no in ['95', '99', '100', '102', '103']:
            assert frame.locator(f'#power-value-{no}').get_attribute('type') == 'date'
        frame.locator('#power-file-circular').set_input_files({'name': '最新版回覧板.xlsx', 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'buffer': b'name only'})
        shot('power-operation.png')
        case(2)
        assert not frame.locator('#power-value-101').is_disabled()
        assert '最新版回覧板.xlsx' not in text()
        case(0)
        tab('tasks')
        assert '最新版回覧板.xlsx' in text() and '整定値一覧サンプル.pdf' in text()
        frame.locator('#power-task-text').fill('追加タスク検証')
        frame.locator('#power-task-due').fill('2026-11-30')
        frame.locator('#power-task-add').click()
        task = frame.locator('.pw-task').filter(has_text='追加タスク検証')
        expect(task).to_contain_text('未完了')
        task.locator('input[type=checkbox]').check()
        expect(frame.locator('.pw-task').filter(has_text='追加タスク検証')).to_contain_text('完了')
        shot('power-tasks.png')
        case(1)
        assert '追加タスク検証' not in text() and '最新版回覧板.xlsx' not in text()
        case(0)
        done('attachments keep only per-project names, task addition/deadline/completion, operation removal/order and solar applicability')
        tab('connection')
        frame.locator('#power-file-connectionAnswer').set_input_files({'name': '旧回答.pdf', 'mimeType': 'application/pdf', 'buffer': b'name only'})
        frame.locator('#power-reconnect').click()
        expect(frame.locator('[role=alertdialog]')).to_be_visible()
        frame.locator('#power-reconnect-cancel').click()
        expect(frame.locator('#power-demo-id')).to_contain_text('申請回 1')
        frame.locator('#power-reconnect').click()
        frame.locator('#power-reconnect-confirm').click()
        expect(frame.locator('#power-demo-id')).to_contain_text('申請回 2')
        expect(frame.locator('#power-value-24')).to_have_value('')
        expect(frame.locator('#power-forecast-result')).to_contain_text('算出に必要な日付が未登録')
        tab('tasks')
        assert '旧回答.pdf' in text() and '接続検討 回答予定日：' in text() and '追加タスク検証' in text()
        tab('overview')
        expect(frame.locator('#power-value-7')).to_have_value('独立保存する申請名')
        expect(frame.locator('#power-qb-spec-1')).to_have_value('QB-B（サンプル）')
        tab('main')
        expect(frame.locator('#power-value-57')).to_have_value('9876543')
        tab('coordination')
        expect(frame.locator('#power-value-77')).to_have_value('00000042')
        done('reconnection cancel/confirm, archive, and preservation of common/equipment/later-stage data')
        frame.locator('#power-sort').click()
        rows = frame.locator('[data-power-row]').all()
        assert rows[0].get_attribute('data-power-row') == 'P-00002'
        stage_names = ['基本情報','接続検討','本申込','連系準備','受電・送電','商用運転・市場参入']
        for i, name in enumerate(stage_names):
            count = sum(name == row.locator('td').nth(2).locator('strong').inner_text() for row in rows)
            assert frame.locator(f'[data-power-stage-count="{i}"]').get_attribute('data-count') == str(count)
        assert sum(int(frame.locator(f'[data-power-stage-count="{i}"]').get_attribute('data-count')) for i in range(6)) == 3
        done('progress sort and dashboard stage counts equal list data')
        # Reference master editing uses the existing settings screen.
        frame.locator('[data-page="settings"]').click()
        frame.locator('[data-setting="masters"]').click()
        frame.locator('#settings-master-kind').select_option('PCS型式')
        frame.locator('#settings-master-name').fill('PCS-追加サンプル')
        frame.locator('#settings-master-add').click()
        frame.locator('[data-page="power"]').click()
        tab('overview')
        value('17', 'PCS-追加サンプル')
        expect(frame.locator('#power-value-17')).to_have_value('PCS-追加サンプル')
        shot('power-overview.png')
        frame.locator('[data-page="sales"]').click()
        frame.locator('[data-section="contract"]').click()
        frame.locator('#sales-demo-date').fill('2026-10-05')
        frame.locator('#sales-demo-save').click()
        expect(frame.locator('#sales-demo-date')).to_have_value('2026-10-05')
        frame.locator('[data-page="legal"]').click()
        frame.locator('[data-legal-tab="contract"]').click()
        frame.locator('#legal-demo-number').fill('SC-SMOKE-001')
        frame.locator('#legal-demo-save').click()
        frame.locator('[data-page="sales"]').click()
        assert 'SC-SMOKE-001' in frame.locator('#sales-demo-panel').inner_text()
        frame.locator('[data-page="settings"]').click()
        frame.locator('[data-setting="users"]').click()
        frame.locator('#settings-user-name').fill('検証ユーザー')
        frame.locator('#settings-user-email').fill('smoke@example.com')
        frame.locator('#settings-user-save').click()
        assert 'smoke@example.com' in frame.locator('#settings-demo-detail').inner_text()
        done('settings master feeds power selections; sales/legal shared edits and settings user creation remain functional')
        frame.locator('[data-page="power"]').click()
        tab('overview')
        page.set_viewport_size({'width': 390, 'height': 844})
        shot('power-mobile.png')
        done('desktop and mobile screenshots captured')
        page.reload(wait_until='networkidle')
        frame.locator('[data-page="power"]').click()
        expect(frame.locator('#power-value-7')).not_to_have_value('独立保存する申請名')
        tab('tasks')
        assert '追加タスク検証' not in text() and '最新版回覧板.xlsx' not in text()
        done('reload resets in-memory changes as stated in UI')
        assert not errors, errors
        done('no uncaught browser JavaScript errors')
        result = {'passed': passed, 'page_errors': errors, 'failed_requests': failed_requests, 'external_http_errors': external_http}
        (OUTPUT / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        browser.close()

if __name__ == '__main__':
    run()
