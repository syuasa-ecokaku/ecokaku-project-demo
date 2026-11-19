"""Verify the published workbook samples and preserve browsers with an older saved catalogue."""
from pathlib import Path
import subprocess

from playwright.sync_api import expect, sync_playwright

from department_notices_smoke import fixture
from power_mock_smoke import server
from verified_cdn import verified_cdn

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '707152832e353d77529a41e7b864193074382d1f'
TEST_API = """
window.__samplesTest = {
 snapshot: lifecycleSnapshot,
 save: () => lifecycleTransaction(() => {
  powerRecord(batteryCaseMap['P-00001']).values.withdrawalReason = '保存済みの検証用メモ';
 })
};
"""


def run():
    latest = (ROOT / 'index.html').read_text()
    prior = subprocess.check_output(['git', 'show', f'{BASELINE}:index.html'], cwd=ROOT, text=True)
    with server() as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        verified_cdn(page)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        served = [fixture(latest, TEST_API)]
        page.route(url, lambda route: route.fulfill(body=served[0], content_type='text/html'))
        page.goto(url, wait_until='networkidle')
        frame = page.frame_locator('#codex-visualization')
        workspace = frame.locator('#power-workspace')

        def open_input():
            frame.locator('[data-page=power]').click()
            workspace.locator('[data-power-tab=bulk]').click()

        def stage(value):
            workspace.locator('#power-bulk-stage').select_option(value)

        def row(case_id):
            return workspace.locator(f'[data-power-bulk-row="{case_id}"]')

        def field(case_id, key):
            return row(case_id).locator(f'[data-power-field="{key}"]')

        open_input()
        stage('basic')
        expect(workspace.locator('[data-power-bulk-row]')).to_have_count(10)
        sample_numbers = workspace.locator('[data-power-workbook-number]')
        expected_samples = [f'Excel {n}' for n in range(1, 11)]
        expect(sample_numbers).to_have_text(expected_samples)
        expect(row('P-00001').locator('.pw-pin-id')).to_contain_text('P-00001')
        expect(field('P-00001', '7')).to_have_value('サンプル蓄電所 01')
        expect(row('P-00001').locator('[data-power-case-field=address]')).to_have_value('架空県デモ市サンプル町 1番')
        expect(row('P-00002').locator('[data-pin-field=batteryCapacityKwh]')).to_have_value('')
        expect(row('G-00009').locator('[data-pin-field=acCapacityKw]')).to_have_value('')
        stage('consultation')
        expect(field('P-00001', 'preconsultationAppliedAt')).to_have_value('対象外')
        assert field('G-00005', 'preconsultationAppliedAt').input_value()
        assert field('P-00001', 'consultationOwner').input_value() == ''
        stage('connection')
        owner = field('P-00001', 'owner').input_value()
        expect(field('P-00001', 'durationDescription')).to_have_value('入金後6ヵ月（受給申込後14ヵ月）')
        expect(field('P-00001', '31')).to_have_value('00090001')
        expect(field('P-00001', '33')).to_have_value('34950000')
        stage('main')
        expect(workspace.get_by_role('columnheader', name='本回答予定日', exact=True)).to_be_visible()
        expect(sample_numbers).to_have_text(expected_samples)
        dates = ['2025-07-08', '対象外', '2026-09-01', '2026-09-29', '2026-06-01',
                 '2026-05-27', '2026-03-27', '2025-10-14', '対象外', '']
        assert workspace.locator('tbody [data-power-field="47"]').evaluate_all(
            '(fields) => fields.map(field => field.value)') == dates
        order = workspace.locator('[data-power-filter=sort]')
        expect(order).to_have_value('number')
        order.select_option('progress')
        assert sample_numbers.all_text_contents() != expected_samples
        order.select_option('number')
        expect(sample_numbers).to_have_text(expected_samples)
        assert field('P-00001', 'mainOwner').input_value() != owner
        expect(field('G-00005', 'mainSupplyCondition')).to_have_value('入金後12ヵ月')
        expect(field('G-00008', 'burdenPaidAt')).to_have_value('')
        expect(field('G-00010', '42')).to_have_value('')
        stage('grid')
        assert field('P-00001', 'gridEquipment').input_value()
        stage('operation')
        expect(field('P-00001', '100')).to_have_value('')
        stage('withdrawal')
        assert field('G-00010', 'withdrawalDate').input_value()
        expect(field('G-00010', 'withdrawalReason')).to_contain_text('デモ用記述')
        print('PASS: 10 workbook samples appear across stages with fictional values and preserved cell types')

        field('G-00010', 'withdrawalOwner').select_option('申請担当A')
        workspace.locator('[data-power-action=saveAll]').click()
        expect(frame.locator('.lc-busy')).to_be_hidden()
        page.reload(wait_until='networkidle')
        open_input()
        stage('withdrawal')
        expect(field('G-00010', 'withdrawalOwner')).to_have_value('申請担当A')
        stage('connection')
        expect(field('P-00001', 'owner')).to_have_value(owner)

        old = browser.new_page()
        verified_cdn(old)
        old_source = [fixture(prior, TEST_API)]
        old.route(url, lambda route: route.fulfill(body=old_source[0], content_type='text/html'))
        old.goto(url, wait_until='networkidle')
        old.frames[1].evaluate('() => __samplesTest.save()')
        before = old.frames[1].evaluate('() => __samplesTest.snapshot()')
        old_source[0] = fixture(latest, TEST_API)
        old.reload(wait_until='networkidle')
        assert old.frames[1].evaluate('() => __samplesTest.snapshot()') == before
        old_frame = old.frame_locator('#codex-visualization')
        old_frame.locator('[data-page=power]').click()
        old_frame.locator('#power-workspace [data-power-tab=bulk]').click()
        expect(old_frame.locator('[data-power-workbook-number]')).to_have_count(0)
        expect(old_frame.locator('[data-power-workbook-note]')).to_contain_text('シークレットウィンドウ')
        assert errors == [], errors
        print('PASS: stage-specific editing survives reload and an existing saved catalogue hydrates unchanged')
        browser.close()


if __name__ == '__main__':
    run()
