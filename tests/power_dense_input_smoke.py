"""Dense 10-case power-input browser checks. Run: python3 tests/power_dense_input_smoke.py"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect
from power_mock_smoke import server

OUT=Path('/tmp/ecokaku-power-dense-review')
IDS={'P-00001','P-00002',*(f'G-{i:05d}' for i in range(3,11))}

def run():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'results.json').unlink(missing_ok=True)
    passed,errors,failed,writes=[],[],[],[]
    with server() as url,sync_playwright() as pw:
        b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=b.new_page(viewport={'width':1440,'height':1300},timezone_id='Asia/Tokyo')
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('requestfailed',lambda r:failed.append(r.url+' '+str(r.failure)))
        page.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
        assert page.goto(url,wait_until='networkidle').status==200
        f=page.frame_locator('#codex-visualization');home_before=f.locator('#sales-demo-home').inner_text()
        f.locator('[data-page=power]').click()
        def done(name):passed.append(name);print('PASS',name,flush=True)
        def tab(key):f.locator(f'.pw-primary-tabs [data-power-tab={key}]').click()
        def bulk(stage='connection'):
            tab('bulk');f.locator('#power-bulk-stage').select_option(stage)
        def cell(pid,key):return f.locator(f'[data-power-bulk-row="{pid}"] [data-power-field="{key}"]')
        def row(pid):return f.locator(f'[data-power-bulk-row="{pid}"]')
        def shot(name,target='#power-bulk-scroll'):
            f.locator(target).scroll_into_view_if_needed();page.frames[1].evaluate('document.activeElement?.blur()');page.screenshot(path=str(OUT/name))
        assert f.locator('[data-power-summary-row]').count()==10
        assert f.locator('[data-power-card=""]').get_attribute('data-count')=='10'
        summary_ids=set(f.locator('[data-power-summary-row]').evaluate_all('(els)=>els.map(e=>e.dataset.powerSummaryRow)'))
        assert summary_ids==IDS
        assert sum(int(el.inner_text().replace('件','')) for el in f.locator('[data-power-stage-count]').all())==10
        bulk();rows=f.locator('[data-power-bulk-row]')
        assert rows.count()==10
        assert set(rows.evaluate_all('(els)=>els.map(e=>e.dataset.powerBulkRow)'))==IDS
        assert all(value=='battery' for value in rows.evaluate_all('(els)=>els.map(e=>e.dataset.business)'))
        assert f.locator('.pw-bulk-table small,.pw-bulk-table br,.pw-bulk-table .pw-input-state').count()==0
        assert '入力済み' not in f.locator('.pw-bulk-table').inner_text()
        assert f.locator('.pw-bulk-table thead th').last.inner_text()=='詳細'
        for pid in IDS:
            r=row(pid)
            assert r.locator('td').first.inner_text()==pid
            assert r.locator('.pw-pin-name button').count()==0
            assert r.locator('button').count()==1
            assert r.locator('td').last.locator('button').inner_text()=='詳細'
            assert 51<=r.bounding_box()['height']<=53
            for el in r.locator('input,select').all():assert 32<=el.bounding_box()['height']<=34
            assert cell(pid,'7').get_attribute('title')==cell(pid,'7').input_value()
        done('10 unique battery rows shared with summary; one item per cell; 52px rows, 34px editors, no supplements and rightmost detail column')
        statuses=set()
        for pid in IDS:
            application=cell(pid,'24').input_value();invoice=cell(pid,'25').input_value();due=cell(pid,'connectionDue').input_value()
            if application:
                assert '2026-01-01'<=application<='2026-10-31'
                assert application<=invoice<=due
            else:assert invoice==due==''
            paid=row(pid).locator('.pw-cell-reference').inner_text()
            if paid!='未登録':assert paid<=due
            assert cell(pid,'owner').input_value() in ['申請担当A','申請担当B']
            statuses.add(cell(pid,'commonStatus').input_value())
            if pid not in ['P-00001','P-00002','G-00003']:
                assert '蓄電所' in cell(pid,'7').input_value()
                assert cell(pid,'commonDue').input_value().startswith('2026-11-')
        assert {'対応中','確認待ち','完了'}<=statuses
        done('10 reused battery samples have unique existing-format IDs, varied states and consistent application/invoice/payment dates')
        first=rows.first.get_attribute('data-power-bulk-row')
        cell(first,'24').focus();cell(first,'24').press('Tab')
        assert cell(first,'25').evaluate('(e)=>e===document.activeElement')
        cell(first,'25').press('Shift+Tab')
        assert cell(first,'24').evaluate('(e)=>e===document.activeElement')
        cell(first,'connectionDue').focus();cell(first,'connectionDue').press('Tab')
        assert cell(first,'connectionProof').evaluate('(e)=>e===document.activeElement')
        order=rows.evaluate_all('(els)=>els.map(e=>e.dataset.powerBulkRow)')
        cell(first,'35').focus();cell(first,'35').press('Tab')
        assert cell(order[1],'7').evaluate('(e)=>e===document.activeElement')
        cell(order[1],'7').press('Shift+Tab')
        assert cell(first,'35').evaluate('(e)=>e===document.activeElement')
        done('Tab and Shift+Tab move between complete date cells, skip references and continue across rows')
        for i,pid in enumerate(sorted(IDS)):
            cell(pid,'31').fill('000-DENSE-'+str(i))
            expect(cell(pid,'31')).to_have_class('pw-edit is-dirty')
            assert cell(pid,'31').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(255, 246, 216)'
        f.locator('#power-bulk-stage').click()
        for i,pid in enumerate(sorted(IDS)):expect(cell(pid,'31')).to_have_value('000-DENSE-'+str(i))
        cell(first,'34').fill('1.5')
        f.locator('[data-power-action=saveAll]').click()
        assert '整数' in f.locator('.pw-errors').inner_text()
        assert first in f.locator('.pw-errors').inner_text()
        assert cell(first,'34').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(255, 240, 240)'
        for i,pid in enumerate(sorted(IDS)):expect(cell(pid,'31')).to_have_value('000-DENSE-'+str(i))
        cell(first,'34').fill('3')
        f.locator('[data-power-action=saveAll]').click()
        assert f.locator('.pw-errors').count()==0
        for pid in IDS:assert cell(pid,'31').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(255, 255, 255)'
        expect(f.locator('.pw-draft-count')).to_contain_text('0件')
        done('all 10 cases editable; blur keeps drafts; yellow dirty cells, red errors, atomic save and white saved cells work')
        table=f.locator('#power-bulk-scroll');table.scroll_into_view_if_needed()
        before=f.locator('tbody .pw-pin-id').first.bounding_box();name_before=f.locator('tbody .pw-pin-name').first.bounding_box()
        table.evaluate('(e)=>{e.scrollLeft=e.scrollWidth;e.style.height="200px";e.scrollTop=150}')
        after=f.locator('tbody .pw-pin-id').first.bounding_box();name_after=f.locator('tbody .pw-pin-name').first.bounding_box()
        assert abs(before['x']-after['x'])<2 and abs(name_before['x']-name_after['x'])<2
        assert name_after['x']>=after['x']+after['width']-1
        assert abs(f.locator('.pw-bulk-table th').last.bounding_box()['y']-table.bounding_box()['y'])<3
        assert all(51<=height<=53 for height in rows.evaluate_all('(els)=>els.map(e=>e.getBoundingClientRect().height)'))
        table.evaluate('(e)=>{e.style.removeProperty("height");e.scrollTop=0;e.scrollLeft=0}')
        shot('power-dense-input.png')
        for pid in sorted(IDS):
            bulk();r=row(pid);expected=r.locator('[data-power-open]').get_attribute('data-power-open')
            r.locator('[data-power-open]').click()
            expect(f.locator('#power-detail-case')).to_have_value(expected)
            assert pid in f.locator('.pw-casehead').inner_text()
            expect(f.locator('#power-value-31')).to_have_value('000-DENSE-'+str(sorted(IDS).index(pid)))
        assert f.locator('#power-detail-case option').count()==10
        done('sticky headers/two frozen columns keep constant row heights; all 10 rightmost detail buttons open matching saved data')
        bulk();cell('G-00004','31').fill('HIDDEN-DRAFT-A')
        f.locator('#power-bulk-stage').select_option('main');saved_burden=cell('G-00010','57').input_value();cell('G-00010','57').fill('987654')
        f.locator('#power-search').fill('G-00004');f.locator('#power-search').press('Tab')
        assert rows.count()==1
        f.locator('[data-power-action=cancelAll]').click()
        f.locator('[data-power-action=clearFilters]').click()
        expect(cell('G-00010','57')).to_have_value(saved_burden)
        f.locator('#power-bulk-stage').select_option('connection')
        expect(cell('G-00004','31')).to_have_value('000-DENSE-'+str(sorted(IDS).index('G-00004')))
        cell('G-00004','31').fill('SAVE-FILTERED-A')
        f.locator('#power-bulk-stage').select_option('main');cell('G-00010','57').fill('123456')
        f.locator('#power-search').fill('G-00004');f.locator('#power-search').press('Tab')
        f.locator('[data-power-action=saveAll]').click()
        f.locator('[data-power-action=clearFilters]').click()
        expect(cell('G-00010','57')).to_have_value('123456')
        f.locator('#power-bulk-stage').select_option('connection');expect(cell('G-00004','31')).to_have_value('SAVE-FILTERED-A')
        tab('summary')
        assert f.locator('[data-power-summary-row]').count()==10
        assert f.locator('[data-power-card=""]').get_attribute('data-count')=='10'
        for status in ['answer','payment','proof','overdue']:
            card=f.locator(f'[data-power-card="{status}"]');count=int(card.get_attribute('data-count'));card.click();assert f.locator('[data-power-summary-row]').count()==count
        f.locator('[data-power-card=""]').click()
        shot('power-ten-summary.png','.pw-primary-tabs')
        done('save/cancel include filtered-out rows and hidden stages; summary counts and lists stay consistent with 10-case store')
        f.locator('[data-page=home]').click()
        assert f.locator('#sales-demo-home').inner_text()==home_before
        f.locator('[data-page=sales]').click();f.locator('#sales-workspace .du-business-tabs').get_by_role('tab',name='太陽光',exact=True).click();assert f.locator('#sales-demo-cases tr').count()==3
        f.locator('[data-page=legal]').click();f.locator('#legal-workspace [data-dept-business=solar]').click();assert f.locator('#legal-demo-cases tr').count()==3
        f.locator('[data-page=power]').click();bulk()
        page.set_viewport_size({'width':390,'height':900})
        table=f.locator('#power-bulk-scroll');table.scroll_into_view_if_needed();table.evaluate('(e)=>e.scrollLeft=650')
        assert all(51<=height<=53 for height in rows.evaluate_all('(els)=>els.map(e=>e.getBoundingClientRect().height)'))
        shot('power-dense-mobile.png')
        assert not errors,errors
        assert not failed,failed
        assert not writes,writes
        done('global dashboard and sales/legal keep original shared cases; mobile rows stay single-line; no JS/resource/write errors')
        result={'passed':passed,'page_errors':errors,'failed_requests':failed,'write_requests':writes}
        (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2));b.close()

if __name__=='__main__':run()
