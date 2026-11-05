"""Business-scoped executive dashboard: KPI/list/chart integrity and unchanged departments."""
from pathlib import Path
from html.parser import HTMLParser
from html import escape
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from notice_snapshot import content_text

ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-executive-dashboard-review')
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
    OUT.mkdir(exist_ok=True);passed=[];errors=[];failed=[];writes=[]
    raw=(ROOT/'index.html').read_text();baseline=subprocess.check_output(['git','show','49ed427:index.html'],cwd=ROOT,text=True)
    for var in ['batteryCaseSeedData','batteryDepartmentDefinitions']:
        parse=lambda text:json.JSONDecoder().raw_decode(inner(text).split('const '+var+'=',1)[1])[0]
        assert parse(raw)==parse(baseline)
    def done(name):passed.append(name);print('PASS',name,flush=True)
    with server() as url,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1500,'height':1300});page.on('pageerror',lambda e:errors.append(str(e)));page.on('requestfailed',lambda r:failed.append(r.url));page.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
        page.goto(url,wait_until='networkidle');f=page.frame_locator('#codex-visualization');h=f.locator('#sales-demo-home');header=f.locator('.s-top').inner_html()
        def business(label):h.locator('.home-business-tabs').get_by_role('tab',name=label,exact=True).click()
        def kpi(key):h.locator('.home-kpi[data-home-kpi='+key+']').click()
        def navhome():f.locator('[data-page=home]').click()
        def rowids():return h.locator('[data-home-row]').evaluate_all('(es)=>es.map(e=>e.dataset.homeRow)')
        def shot(name,target='#home-kpis'):
            h.locator(target).first.scroll_into_view_if_needed();page.screenshot(path=str(OUT/name))
        expect(h.locator('#home-business-battery')).to_have_attribute('aria-selected','true')
        assert h.locator('.home-business-tabs button').all_text_contents()==['蓄電池','太陽光','データセンター']
        assert h.locator('.home-kpi').count()==3
        assert h.locator('[data-home-kpi-value]').all_text_contents()==['10件','1件','未設定']
        expect(h.locator('.home-kpi[data-home-kpi=active]')).to_have_attribute('aria-pressed','true')
        boxes=[e.bounding_box() for e in h.locator('.home-kpi').all()];assert max(b['width'] for b in boxes)-min(b['width'] for b in boxes)<=1
        assert h.locator('.home-kpi-arrow svg').count()==3
        assert h.locator('[data-home-row]').count()==5
        assert h.locator('#home-kpi-list').get_attribute('data-total-count')=='10'
        assert h.locator('table').count()==1 and h.locator('#dash-projects,#dash-todos,#dash-todo-progress,#dash-kpis').count()==0
        assert '自分の今日のタスク' not in h.inner_text() and '今日の自分のタスク' not in h.inner_text()
        shot('battery-active.png')
        h.locator('[data-home-action=expand]').click();assert len(set(rowids()))==10
        h.locator('[data-home-action=expand]').click();assert len(rowids())==5
        assert sum(int(x.get_attribute('data-home-phase-count')) for x in h.locator('[data-home-phase-count]').all())==10
        assert h.locator('[data-home-department-count]').count()==7
        assert h.locator('[data-home-ring-total]').inner_text()=='10'
        done('battery defaults; three equal clickable KPIs; five/all/collapse list; ring totals; seven departments; old list and personal tasks removed')
        # Native keyboard behavior and grid drill-through.
        h.locator('.home-kpi[data-home-kpi=grid]').focus();h.locator('.home-kpi[data-home-kpi=grid]').press('Enter')
        expect(h.locator('#home-kpi-list')).to_have_attribute('data-home-mode','grid')
        assert rowids()==['P-00002']
        assert '2026-11-27' in h.locator('[data-home-row=P-00002]').inner_text()
        h.locator('[data-home-row=P-00002] td').nth(1).locator('button').click()
        expect(f.locator('[data-page=power]')).to_have_class('s-on')
        expect(f.locator('#power-detail-case')).to_have_value('1');expect(f.locator('#power-section-receipt')).to_have_attribute('open','')
        navhome();kpi('active');h.locator('[data-home-row=P-00001] td').first.locator('button').click()
        expect(f.locator('#maintenance-workspace [data-dept-select]')).to_have_value('P-00001')
        navhome();kpi('money');assert rowids()==[]
        assert h.locator('[data-home-total=remaining]').inner_text()=='未設定'
        assert '売上請求データは未登録' in h.inner_text()
        assert h.locator('.home-kpi[data-home-kpi=money] [data-home-kpi-value]').inner_text()=='未設定'
        shot('battery-money-empty.png')
        done('keyboard KPI selection; grid and active lists open correct battery department/case; missing battery invoices stay unset')
        # Saved power forecasts update home; other department state is not edited by the dashboard.
        kpi('grid');h.locator('[data-home-row=P-00002] td').nth(1).locator('button').click()
        basic=f.locator('#power-section-basic')
        if basic.get_attribute('open') is None:basic.locator('summary').click()
        prep=f.locator('#power-section-preparation')
        if prep.get_attribute('open') is None:prep.locator('summary').click()
        f.locator('[data-power-field=agreedForecast]').fill('2026-12-03');f.locator('[data-power-action=saveCase]').first.click();navhome()
        assert h.locator('.home-kpi[data-home-kpi=grid] [data-home-kpi-value]').inner_text()=='0件'
        kpi('grid');assert not rowids()
        page.reload(wait_until='networkidle');assert h.locator('.home-kpi[data-home-kpi=grid] [data-home-kpi-value]').inner_text()=='1件'
        done('grid uses saved power-company forecast and excludes energized cases; edits refresh on return; reload preserves existing mock scope')
        business('太陽光');expect(h.locator('.home-kpi[data-home-kpi=active]')).to_have_attribute('aria-pressed','true')
        assert h.locator('[data-home-kpi-value]').all_text_contents()==['6件','0件','¥9,166,667']
        assert sum(int(e.inner_text().split()[-1].replace('%','')) for e in h.locator('.home-ring-item strong').all())==100
        kpi('money');assert rowids()==['P-00001','P-00002']
        totals={k:int(h.locator('[data-home-total='+k+']').get_attribute('data-amount')) for k in ['issued','paid','remaining']}
        assert totals=={'issued':27500000,'paid':18333333,'remaining':9166667}
        assert sum(int(e.get_attribute('data-home-case-remaining')) for e in h.locator('[data-home-case-remaining]').all())==totals['remaining']
        assert int(h.locator('[data-home-cash-remaining]').get_attribute('data-home-cash-remaining'))==totals['remaining']
        assert h.locator('.home-kpi[data-home-kpi=money] [data-home-kpi-value]').inner_text()=='¥9,166,667'
        assert all('未設定' in row.locator('td').last.inner_text() for row in h.locator('[data-home-row]').all())
        shot('solar-invoices.png')
        h.locator('[data-home-row=P-00002] td').nth(1).locator('button').click()
        expect(f.locator('#sales-demo-title')).to_have_text('足利第二 太陽光発電所');assert '経理確認済み入金額' in f.locator('#sales-demo-panel').inner_text()
        navhome();h.locator('.d-panelhead [data-home-kpi=money]').click();expect(h.locator('#home-kpi-list')).to_have_attribute('data-home-mode','money')
        kpi('active');h.locator('[data-home-action=expand]').click();h.locator('[data-home-row=P-00005] td').nth(1).locator('button').click()
        assert '鹿沼第五 太陽光発電所' in h.locator('#home-case-detail').inner_text()
        assert '部門別詳細は未登録' in h.locator('#home-case-detail').inner_text()
        h.locator('[data-home-action=closeDetail]').click()
        done('solar issued-only invoices reconcile KPI/list/footer/graph; incoming dates not fabricated; finance and top-only case navigation work')
        business('データセンター');assert h.locator('[data-home-kpi-value]').all_text_contents()==['0件','0件','未設定']
        assert not rowids();assert h.locator('[data-home-ring-total]').inner_text()=='0'
        assert all(e.inner_text()=='0件' for e in h.locator('[data-home-department-count]').all())
        for key in ['grid','money']:kpi(key);assert not rowids()
        shot('datacenter-empty.png')
        h.locator('#home-business-datacenter').focus();h.locator('#home-business-datacenter').press('ArrowRight');expect(h.locator('#home-business-battery')).to_have_attribute('aria-selected','true');expect(h.locator('.home-kpi[data-home-kpi=active]')).to_have_attribute('aria-pressed','true')
        for button in h.locator('[data-home-week]').all():
            button.click();assert h.locator('[data-home-week-detail]').is_visible()
        assert '自分' not in h.inner_text()
        shot('battery-charts.png','.home-chart-row')
        done('business switching resets active KPI and all graphs/lists; datacenter is empty; tab keyboard and weekly schedule drill-through work')
        # Source edge cases are injected only into local fixture responses.
        def fixture_page(body,suffix):
            p=browser.new_page(viewport={'width':1500,'height':1200});u=url+'?fixture='+suffix;p.route(u,lambda route:route.fulfill(status=200,content_type='text/html',body=body));p.goto(u,wait_until='networkidle');return p,p.frame_locator('#codex-visualization')
        body=fixture(raw,"const realRows=rows;rows=p=>{const r=realRows(p);return [...r,...r.filter(x=>x.state==='発行済み'),{key:'void',state:'取消済み',amount:999999999,paid:0},{key:'voidflag',state:'発行済み',cancelled:true,amount:999999999,paid:0},{key:'planned',state:'未依頼',amount:999999999,paid:0}];};")
        p,ff=fixture_page(body,'invoice-dedup');hh=ff.locator('#sales-demo-home');hh.locator('[data-home-business-tab=solar]').click();hh.locator('.home-kpi[data-home-kpi=money]').click();assert hh.locator('[data-home-total=remaining]').get_attribute('data-amount')=='9166667';p.close()
        body=fixture(raw,"batteryCases[0].lifecycleStatus='完了';batteryCases[1].lifecycleStatus='中止';batteryCases[2].lifecycleStatus='廃止';")
        p,ff=fixture_page(body,'closed');hh=ff.locator('#sales-demo-home');assert hh.locator('.home-kpi[data-home-kpi=active] [data-home-kpi-value]').inner_text()=='7件';assert hh.locator('[data-home-ring-total]').inner_text()=='7';assert hh.locator('.home-kpi[data-home-kpi=grid] [data-home-kpi-value]').inner_text()=='0件';p.close()
        done('invoice duplicates/cancellations/unissued entries excluded; explicit completed/cancelled/abolished projects excluded from active and grid totals')
        # More than five financial rows: totals cover all rows while display is folded.
        injection="const project=homeProjection;homeProjection=()=>{const d=project();if(executiveHome.business==='solar'){const a=d.all.map((record,i)=>({record,issued:(i+1)*1000,paid:i*100,remaining:(i+1)*1000-i*100,expected:''})).sort((a,b)=>b.remaining-a.remaining);d.money={available:true,rows:a,issued:a.reduce((n,r)=>n+r.issued,0),paid:a.reduce((n,r)=>n+r.paid,0),remaining:a.reduce((n,r)=>n+r.remaining,0)};}return d;};"
        p,ff=fixture_page(fixture(raw,injection),'invoice-fold');hh=ff.locator('#sales-demo-home');hh.locator('[data-home-business-tab=solar]').click();hh.locator('.home-kpi[data-home-kpi=money]').click();assert hh.locator('[data-home-row]').count()==5
        assert hh.locator('[data-home-total=remaining]').get_attribute('data-amount')=='19500';assert hh.locator('.home-kpi[data-home-kpi=money] [data-home-kpi-value]').inner_text()=='¥19,500'
        hh.locator('[data-home-action=expand]').click();assert hh.locator('[data-home-row]').count()==6;assert hh.locator('[data-home-total=remaining]').get_attribute('data-amount')=='19500';p.close()
        done('financial total remains the full six-case total when the list is folded to five')
        # Every department/business/tab remains exactly as it was at the start of this task.
        old=browser.new_page(viewport={'width':1500,'height':1300});old.route(url,lambda route:route.fulfill(status=200,content_type='text/html',body=baseline));old.goto(url,wait_until='networkidle');of=old.frame_locator('#codex-visualization');page.reload(wait_until='networkidle')
        def state(frame,d,b,t):
            frame.locator('[data-page='+d+']').click();m=frame.locator('#'+d+'-workspace');m.locator('.du-business-tabs').get_by_role('tab',name=b,exact=True).click();m.locator('.du-work-tabs').get_by_role('tab',name=t,exact=True).click()
            if d=='power' and b=='蓄電池' and t=='サマリー':return {'kpis':m.locator('.pw-counts').inner_text(),'stages':m.locator('[data-summary-pair]').inner_text(),'cases':m.locator('.pw-summary-scroll').inner_text()}
            return {'text':content_text(m),'controls':m.locator('input:not([type=file]),select,textarea').evaluate_all('(es)=>es.filter(e=>!e.closest(".nc-card")).map(e=>[e.tagName,e.type,e.value,e.disabled,e.readOnly])')}
        for d in DEPTS:
            for b in ['蓄電池','太陽光','データセンター']:
                for t in ['サマリー','データ入力','案件詳細']:assert state(f,d,b,t)==state(of,d,b,t),(d,b,t)
        old.close();assert f.locator('.s-top').inner_html()==header
        done('all 63 department/business/tab snapshots match the starting branch; common data and header remain unchanged')
        navhome();business('蓄電池');page.set_viewport_size({'width':800,'height':1050})
        boxes=[x.bounding_box() for x in h.locator('.home-kpi').all()];assert boxes[1]['y']>boxes[0]['y']
        shot('narrow-dashboard.png');assert h.locator('[data-home-row]').count()==5
        assert not errors,errors
        assert not failed,failed
        assert not writes,writes
        done('narrow layout and table scroll; no JavaScript/resource/write errors')
        browser.close()
    (OUT/'results.json').write_text(json.dumps({'passed':passed,'js_errors':errors,'failed_resources':failed,'external_writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
