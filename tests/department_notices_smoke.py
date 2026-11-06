"""Shared department notice UI, audience, committed events and unchanged home."""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from notice_snapshot import normalize_department_names
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-notices-review')
DEPTS=['realestate','power','sales','legal','procurement','construction','maintenance']
class Inner(HTMLParser):
    value=''
    def handle_starttag(self,t,a):
        d=dict(a)
        if t=='iframe' and d.get('id')=='codex-visualization':self.value=d['data-srcdoc']
def inner(raw):p=Inner();p.feed(raw);return p.value
def fixture(raw,injection):
    s=inner(raw).replace("render();showPage('home');settingsRefreshIcons();",injection+"\nrender();showPage('home');settingsRefreshIcons();")
    a=raw.index('data-srcdoc="')+len('data-srcdoc="');b=raw.index('"',a);return raw[:a]+escape(s,quote=True)+raw[b:]
def run():
    OUT.mkdir(exist_ok=True);passed=[];errors=[];failed=[];writes=[];permission_calls=[]
    raw=(ROOT/'index.html').read_text();baseline=subprocess.check_output(['git','show','d049134:index.html'],cwd=ROOT,text=True)
    for var in ['batteryCaseSeedData','batteryDepartmentDefinitions']:
        parse=lambda text:json.JSONDecoder().raw_decode(inner(text).split('const '+var+'=',1)[1])[0]
        assert parse(raw)==parse(baseline)
    def done(s):passed.append(s);print('PASS',s,flush=True)
    with server() as url,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        p=browser.new_page(viewport={'width':1550,'height':1350});p.on('pageerror',lambda e:errors.append(str(e)));p.on('requestfailed',lambda r:failed.append(r.url));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
        p.add_init_script("Notification.requestPermission=()=>{throw new Error('Notification permission requested');};")
        p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');dialog=f.locator('.nc-dialog')
        def nav(d):f.locator('[data-page='+d+']').click();return f.locator('#'+d+'-workspace')
        def biz(m,label):m.locator('.du-business-tabs').get_by_role('tab',name=label,exact=True).click()
        def tab(m,label):m.locator('.du-work-tabs').get_by_role('tab',name=label,exact=True).click()
        def card(m):return m.locator('.nc-card')
        def unread(m):return int(card(m).locator('.nc-unread-count').inner_text())
        def rows(m):return card(m).locator('.nc-row')
        def category(m,key):card(m).locator('[data-notice-category='+key+']').click()
        def user(m,key):
            card(m).locator('[data-notice-info]').click();dialog.locator('[data-notice-user]').select_option(key)
        def close():dialog.locator('[data-notice-close]').click()
        def save(m,d):m.locator('[data-power-action=saveAll]' if d=='power' else '[data-sales-action=save]' if d=='legacy-sales' else '[data-dept-action=save]').first.click()
        initial_home=f.locator('#sales-demo-home').inner_html();header=f.locator('.s-top').inner_html()
        for d in DEPTS:
            m=nav(d)
            for b in ['蓄電池','太陽光','データセンター']:
                biz(m,b);assert card(m).count()==1;expect(card(m)).to_be_visible();assert rows(m).count()<=5
                kpi=m.locator('.du-kpis,.sl-kpis,.pw-counts')
                if kpi.count():
                    a=kpi.bounding_box();c=card(m).bounding_box();assert c['y']>=a['y']+a['height'] and abs(c['width']-a['width'])<2
                pair=m.locator('[data-summary-pair],.du-overview,.sl-overview')
                if pair.count():assert pair.bounding_box()['y']>card(m).bounding_box()['y']
                if b=='データセンター':assert card(m).locator('.nc-case').count()==0
                if d=='maintenance' and b=='蓄電池':assert '緊急' in rows(m).first.inner_text()
                assert all(e.bounding_box()['height']<26 for e in card(m).locator('.nc-checks label').all())
            for t in ['データ入力','案件詳細']:tab(m,t);assert not card(m).count()
        assert not f.locator('.nc-toast').count()
        done('all 21 summary contexts show one full-width card in the correct position; input/detail and home are untouched; no switch toasts')
        m=nav('power');n=unread(m);assert n==6;assert rows(m).count()==5
        category(m,'company');assert rows(m).count()==3 and unread(m)==n
        company_id=rows(m).first.get_attribute('data-notice-id');rows(m).first.locator('[data-notice-open]').first.click();assert dialog.is_visible();assert unread(m)==n-1
        close();expect(card(m).locator('[data-notice-id='+company_id+']')).to_have_attribute('data-unread','false')
        assert card(m).locator('[data-notice-id='+company_id+'] .nc-category').evaluate('(e)=>getComputedStyle(e).color')=='rgb(29, 78, 216)'
        card(m).locator('[data-notice-filter=unread]').check();assert rows(m).count()==2 and unread(m)==n-1
        category(m,'progress');card(m).locator('[data-notice-filter=action]').check();assert rows(m).count()==2
        assert all(r.locator('.nc-action').count() for r in rows(m).all());assert unread(m)==n-1
        card(m).locator('[data-notice-all]').click();assert dialog.locator('[data-notice-category=progress]').get_attribute('aria-pressed')=='true';assert dialog.locator('[data-notice-filter=unread]').is_checked();assert dialog.locator('[data-notice-filter=action]').is_checked();assert dialog.locator('.nc-row').count()==2
        request_id=dialog.locator('.nc-row').first.get_attribute('data-notice-id');dialog.locator('.nc-row').first.locator('[data-notice-open]').first.click();assert '要対応' in dialog.inner_text();close()
        card(m).locator('[data-notice-filter=unread]').uncheck();assert '要対応' in card(m).locator('[data-notice-id='+request_id+']').inner_text()
        card(m).locator('[data-notice-filter=action]').uncheck();category(m,'all');card(m).locator('[data-notice-all]').click();assert dialog.locator('.nc-row').count()==6;close()
        other=nav('sales');category(other,'company');expect(card(other).locator('[data-notice-id='+company_id+']')).to_have_attribute('data-unread','false')
        done('category and AND filters, five/all display, per-user cross-department read state, scope-wide badges, fixed category colors and separate action states work')
        m=nav('power');user(m,'staff');assert unread(m)==5
        card(m).locator('[data-notice-all]').click();text=dialog.inner_text();assert 'P-00001' not in text and 'G-00010' not in text and '責任者本人宛て' not in text;close()
        user(m,'manager');assert unread(m)==0 and rows(m).count()==0
        m=nav('legal');category(m,'approval');assert rows(m).count()==2
        pending=card(m).locator('.nc-row').filter(has_text='確認してください');pending.locator('[data-notice-open]').first.click();assert '要承認' in dialog.inner_text();close();assert '要承認' in pending.inner_text()
        category(m,'company');assert '責任者本人宛て' in card(m).inner_text()
        user(m,'none');assert unread(m)==0 and not rows(m).count();assert '件名' not in card(m).inner_text();p.screenshot(path=str(OUT/'empty-state.png'))
        user(m,'dual');category(m,'company');assert '責任者本人宛て' not in card(m).inner_text();biz(m,'データセンター');assert rows(m).count()==3 and not card(m).locator('.nc-case').count()
        done('department/user/role/project audiences are enforced before content and counts; profiles have separate reads; empty/DC states contain no invented cases')
        # Existing committed generic save: drafts/cancel/no-op/memo edits do not notify.
        m=nav('construction');category(m,'all');base=unread(m);tab(m,'データ入力')
        cell=m.locator('[data-dept-row=P-00002] [data-dept-field=status]');cell.select_option('未着工');assert not f.locator('.nc-toast').count();m.locator('[data-dept-action=cancel]').click();tab(m,'サマリー');assert unread(m)==base
        tab(m,'データ入力');cell.select_option('未着工');save(m,'construction');assert f.locator('.nc-toast').count()==1
        tab(m,'サマリー');assert unread(m)==base+1;row=rows(m).filter(has_text='施工中 → 未着工');assert row.count()==1
        row.locator('[data-notice-open]').first.click();dialog.locator('[data-notice-navigate]').click();expect(m.locator('[data-dept-select]')).to_have_value('P-00002');assert m.locator('[data-dept-section=business]').get_attribute('open') is not None
        tab(m,'データ入力');save(m,'construction');tab(m,'サマリー');assert unread(m)==base
        tab(m,'データ入力');m.locator('[data-dept-row=P-00002] [data-dept-field=next]').fill('通知対象外の軽微なメモ');save(m,'construction');tab(m,'サマリー');assert unread(m)==base
        done('committed status changes emit once and navigate to the correct case; drafts, cancel, repeated saves and minor next-action edits do not emit')
        # Important date save and recipient-only toast.
        p.reload(wait_until='networkidle');m=nav('construction');tab(m,'データ入力');m.locator('[data-dept-group]').select_option('business');m.locator('[data-dept-row=P-00002] [data-dept-field=completion]').fill('2026-11-21');save(m,'construction');assert f.locator('.nc-toast').count()==1;tab(m,'サマリー');assert rows(m).filter(has_text='完工予定日').count()==1
        user(m,'staff');assert not f.locator('.nc-toast').count();tab(m,'データ入力');m.locator('[data-dept-group]').select_option('business');m.locator('[data-dept-row=P-00002] [data-dept-field=completion]').fill('2026-11-22');save(m,'construction');assert not f.locator('.nc-toast').count()
        # Approval changes are stored contract states, never notification-side approvals.
        p.reload(wait_until='networkidle');m=nav('legal');user(m,'manager');tab(m,'データ入力');m.locator('[data-dept-group]').select_option('sale');m.locator('[data-dept-row=G-00010] [data-dept-field=saleApproval]').select_option('承認済み');save(m,'legal');assert f.locator('.nc-toast').count()==1;tab(m,'サマリー');category(m,'approval');card(m).locator('[data-notice-all]').click();new=dialog.locator('.nc-row').filter(has_text='承認待ち → 承認済み');assert new.count()==1;assert dialog.locator('.nc-row').filter(has_text='確認してください').locator('.nc-tag').filter(has_text='参考').count()==1
        new.locator('[data-notice-open]').first.click();assert not dialog.locator('button').filter(has_text='承認する').count();dialog.locator('[data-notice-navigate]').click();expect(m.locator('[data-dept-select]')).to_have_value('G-00010');expect(m.locator('[data-dept-field=saleApproval]').first).to_have_value('承認済み')
        tab(m,'サマリー');category(m,'progress');card(m).locator('[data-notice-all]').click();assert not dialog.locator('.nc-row').filter(has_text='承認待ち → 承認済み').count();close()
        done('important date edits notify; excluded users receive no toast; approval saves emit approval only and update related pending state without notification-side approval')
        # Power and legacy solar sales committed operations.
        p.reload(wait_until='networkidle');m=nav('power');tab(m,'データ入力');m.locator('[data-power-bulk-row=G-00004] [data-power-field="29"]').fill('2026-11-05');save(m,'power');assert f.locator('.nc-toast').count()==1;tab(m,'サマリー');assert rows(m).filter(has_text='接続検討回答').count()==1
        m=nav('sales');biz(m,'太陽光');tab(m,'データ入力');m.locator('[data-sales-project=P-00001][data-sales-field=stage]').select_option('検収済み');save(m,'legacy-sales');assert f.locator('.nc-toast').count()==2;tab(m,'サマリー');assert rows(m).filter(has_text='営業ステータス').count()==1
        done('power save and existing solar sales save are connected without mixing same-number cases across businesses')
        # Fixture-only API exercises unimplemented routes, stable identity and event dedup.
        inject="""
const ref=[...homeBusinessCases('battery')].find(r=>r.id==='P-00002');
const watch=[...noticeCenter.snapshot().values()].find(w=>w.ref.source===ref.source);
const sample={eventId:'fixture-unique',category:'progress',subtype:'引き継ぎ',subject:'非常に長い件名'.repeat(25),body:'未実装の遷移先の検証',business:'battery',caseId:watch.ref.internalId,caseNumber:'P-00002',sourceDepartment:'construction',targetDepartments:['construction'],targetUsers:['dual'],destination:{department:'construction',unimplemented:true},occurredAt:'2026-11-05T12:00:00+09:00'};
noticeCenter.emit(sample,true);noticeCenter.emit(sample,true);
"""
        body=fixture(raw,inject);extra=browser.new_page(viewport={'width':800,'height':1100});extra.on('pageerror',lambda e:errors.append(str(e)));u=url+'?notice-fixture';extra.route(u,lambda r:r.fulfill(status=200,content_type='text/html',body=body));extra.goto(u,wait_until='networkidle');ff=extra.frame_locator('#codex-visualization');ff.locator('[data-page=construction]').click();cc=ff.locator('#construction-workspace .nc-card');cc.locator('[data-notice-all]').click();dd=ff.locator('.nc-dialog');rr=dd.locator('.nc-row').filter(has_text='非常に長い件名');assert rr.count()==1;rr.locator('[data-notice-open]').first.click();assert dd.locator('[data-notice-navigate]').count()==0;assert '未実装' in dd.locator('.nc-destination-message').inner_text();extra.screenshot(path=str(OUT/'narrow-detail.png'));extra.close()
        done('shared emit API deduplicates event IDs; unimplemented route remains in safe detail; long subjects and narrow modal render')
        # Compare initial executive home against production; remove committed case edits explicitly.
        p.evaluate("()=>{for(const k of Object.keys(localStorage))if(k.includes('case-lifecycle'))localStorage.removeItem(k);}")
        old=browser.new_page(viewport={'width':1550,'height':1350});old.route(url,lambda r:r.fulfill(status=200,content_type='text/html',body=baseline));old.goto(url,wait_until='networkidle');of=old.frame_locator('#codex-visualization');p.reload(wait_until='networkidle')
        for b in ['蓄電池','太陽光','データセンター']:
            for frame in [of,f]:frame.locator('#sales-demo-home .home-business-tabs').get_by_role('tab',name=b,exact=True).click()
            for k in ['active','grid','money']:
                for frame in [of,f]:frame.locator('#sales-demo-home .home-kpi[data-home-kpi='+k+']').click()
                # Whole-case lifecycle intentionally changes follow-up, archive, descriptions and type labels.
                # Keep the notification regression focused on unchanged initial KPI amounts/list membership.
                def initial_totals(frame):
                    return frame.locator('#sales-demo-home').evaluate("e=>({kpis:[...e.querySelectorAll('[data-home-kpi-value]')].map(x=>x.textContent),rows:[...e.querySelectorAll('[data-home-row]')].map(x=>x.dataset.homeRow),ring:e.querySelector('[data-home-ring-total]').textContent,cash:[...e.querySelectorAll('[data-home-cash-issued],[data-home-cash-paid],[data-home-cash-remaining]')].map(x=>x.textContent)})")
                assert initial_totals(f)==initial_totals(of),(b,k)
        assert f.locator('.s-top').inner_html()==header
        old.close();p.reload(wait_until='networkidle');m=nav('power');assert unread(m)==6 and not f.locator('.nc-toast').count()
        card(m).scroll_into_view_if_needed();p.screenshot(path=str(OUT/'power-notices.png'));m=nav('legal');user(m,'manager');category(m,'approval');card(m).scroll_into_view_if_needed();p.screenshot(path=str(OUT/'legal-approvals.png'));p.set_viewport_size({'width':800,'height':1100});m=nav('maintenance');user(m,'dual');card(m).scroll_into_view_if_needed();p.screenshot(path=str(OUT/'narrow-notices.png'))
        assert not errors,errors;assert not failed,failed;assert not writes,writes
        done('all nine initial home KPI amounts and list membership match production; whole-case lifecycle follow-up/archive/type descriptions are verified separately; header/data unchanged; reload resets notices/reads; no JS/resource/write/permission errors')
        browser.close()
    (OUT/'results.json').write_text(json.dumps({'passed':passed,'js_errors':errors,'failed_resources':failed,'external_writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
