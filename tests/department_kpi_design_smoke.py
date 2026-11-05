"""Six-department KPI presentation: stable metrics, semantics, input behavior and exclusions."""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-kpi-design-review')
DEPTS=['realestate','power','sales','legal','procurement','construction']
CARDS='.du-kpis>.du-kpi,.sl-kpis>.sl-kpi,.pw-counts>.pw-count'
EXTRA='.sl-finance .d-kpis>.d-kpi,.du-finance .d-kpis>.d-kpi'
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
    OUT.mkdir(exist_ok=True);passed=[];errors=[];failed=[];writes=[];inventory=[]
    raw=(ROOT/'index.html').read_text();baseline=subprocess.check_output(['git','show','f816545:index.html'],cwd=ROOT,text=True)
    for var in ['batteryCaseSeedData','batteryDepartmentDefinitions']:
        parse=lambda text:json.JSONDecoder().raw_decode(inner(text).split('const '+var+'=',1)[1])[0]
        assert parse(raw)==parse(baseline)
    def done(s):passed.append(s);print('PASS',s,flush=True)
    with server() as url,sync_playwright() as pw:
        b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1550,'height':1250});old=b.new_page(viewport={'width':1550,'height':1250});old.route(url,lambda r:r.fulfill(status=200,content_type='text/html',body=baseline));old.goto(url,wait_until='networkidle')
        p.on('pageerror',lambda e:errors.append(str(e)));p.on('requestfailed',lambda r:failed.append(r.url));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');of=old.frame_locator('#codex-visualization')
        def nav(fr,d):fr.locator('[data-page='+d+']').click();return fr.locator('#'+d+'-workspace')
        def biz(m,name):m.locator('.du-business-tabs').get_by_role('tab',name=name,exact=True).click()
        def tab(m,name):m.locator('.du-work-tabs').get_by_role('tab',name=name,exact=True).click()
        def values(m,selector=CARDS):return m.locator(selector).evaluate_all('''es=>es.map(e=>({label:(e.querySelector('.dk-label')||e.querySelector(':scope>span')||e.querySelector('.d-kpihead>span')).textContent,value:(e.querySelector('strong')||e.querySelector('.d-kpivalue')).textContent,note:((e.querySelector(':scope>small')||e.querySelector(':scope>.d-kpi-note'))?.textContent||''),disabled:Boolean(e.disabled)}))''')
        def list_state(m):return {'ids':m.locator('[data-power-summary-row],[data-dept-summary-row],#sales-demo-cases tr').evaluate_all('(es)=>es.map(e=>e.dataset.powerSummaryRow||e.dataset.deptSummaryRow||e.querySelector("button").dataset.salesOpen)'),'selected':m.locator(CARDS).evaluate_all('(es)=>es.map(e=>[e.getAttribute("aria-pressed"),e.classList.contains("is-selected")])')}
        def notice(m):return m.locator('.nc-card').evaluate('e=>({ids:[...e.querySelectorAll(".nc-row")].map(x=>[x.dataset.noticeId,x.dataset.unread]),unread:e.querySelector(".nc-unread-count").textContent,category:e.querySelector("[data-notice-category][aria-pressed=true]").dataset.noticeCategory,filters:[...e.querySelectorAll("[data-notice-filter]")].map(x=>[x.dataset.noticeFilter,x.checked])})')
        def shot(name,m):m.locator(CARDS).first.scroll_into_view_if_needed();p.screenshot(path=str(OUT/(name+'.png')))
        colors={'blue':('rgb(29, 78, 216)','rgb(239, 246, 255)'),'purple':('rgb(126, 34, 206)','rgb(250, 245, 255)'),'green':('rgb(21, 128, 61)','rgb(240, 253, 244)'),'orange':('rgb(194, 65, 12)','rgb(255, 247, 237)'),'red':('rgb(185, 28, 28)','rgb(254, 242, 242)'),'muted':('rgb(100, 116, 139)','rgb(241, 245, 249)')}
        for d in DEPTS:
            m=nav(f,d);om=nav(of,d)
            for business in ['蓄電池','太陽光','データセンター']:
                biz(m,business);biz(om,business);a=values(m);assert a==values(om),(d,business,a,values(om));assert notice(m)==notice(om),(d,business,'notice changed')
                if not a:
                    assert d=='power' and business!='蓄電池';assert m.locator('[data-power-placeholder]').count()==1;assert not m.locator('.dk-row').count();continue
                extras=values(m,EXTRA);assert extras==values(om,EXTRA);all_values=a+extras
                for panel in [m,om]:panel.locator('details.sl-finance,details.du-finance').evaluate_all('es=>es.forEach(e=>e.open=true)')
                assert m.locator('.dk-card').count()==len(all_values)
                row_heights={}
                for index,c in enumerate(m.locator(CARDS+','+EXTRA).all()):
                    meta=c.evaluate('''e=>{const s=getComputedStyle(e),v=e.querySelector('strong')||e.querySelector('.d-kpivalue'),i=e.querySelector('.dk-icon'),l=e.querySelector('.dk-label'),svg=i.querySelector('svg');return {actionable:e.matches('button:not(:disabled)'),key:e.dataset.kpiKey,semantic:e.dataset.kpiSemantic,tone:e.dataset.kpiTone,bg:s.backgroundColor,line:s.borderTopColor,color:getComputedStyle(v).color,iconColor:getComputedStyle(i).color,soft:getComputedStyle(i).backgroundColor,diameter:i.getBoundingClientRect().width,svgWidth:svg.getBoundingClientRect().width,hidden:i.getAttribute('aria-hidden'),font:parseFloat(getComputedStyle(v).fontSize),labelFont:parseFloat(getComputedStyle(l).fontSize),cursor:s.cursor,box:e.getBoundingClientRect().toJSON()};}''')
                    expected_color,soft=colors[meta['tone']];assert meta['bg']=='rgb(255, 255, 255)';assert meta['line']==meta['color']==meta['iconColor']==expected_color
                    assert meta['soft']==soft and 48<=meta['diameter']<=56 and 24<=meta['svgWidth']<=30;assert meta['hidden']=='true' and 32<=meta['font']<=36 and 14<=meta['labelFont']<=16
                    assert meta['key'] and meta['semantic'];assert meta['cursor']==('pointer' if meta['actionable'] else 'default')
                    row_heights.setdefault(round(meta['box']['y']),[]).append(meta['box']['height'])
                    inventory.append({'department':d,'business':business,**all_values[index],**{k:meta[k] for k in ['key','semantic','tone']}})
                for heights in row_heights.values():assert max(heights)-min(heights)<1
                if business=='蓄電池':shot(d,m)
                if extras:m.locator(EXTRA).first.scroll_into_view_if_needed();p.screenshot(path=str(OUT/(d+'-legacy-kpis.png')))
                # Click the icon itself, compare with the old card's actual filter action.
                for index in range(len(a)):
                    c=m.locator(CARDS).nth(index);oc=om.locator(CARDS).nth(index)
                    if c.is_disabled():continue
                    c.locator('.dk-icon>svg').click();oc.click();assert list_state(m)==list_state(om),(d,business,index)
                    c=m.locator(CARDS).nth(index);c.press('Tab');c.focus();assert c.evaluate('(e)=>getComputedStyle(e).outlineStyle')!='none';c.press('Enter');oc.press('Enter');assert list_state(m)==list_state(om)
                # Existing search and clear behavior are identical.
                search=m.locator('[data-dept-filter=search],[data-power-filter=search],#sales-search');old_search=om.locator('[data-dept-filter=search],[data-power-filter=search],#sales-search')
                if search.count():search.fill('P-00002');search.dispatch_event('change');old_search.fill('P-00002');old_search.dispatch_event('change');assert list_state(m)==list_state(om);search.fill('');search.dispatch_event('change');old_search.fill('');old_search.dispatch_event('change')
            done(d+': all three businesses retain card counts/labels/values/notes and actions; icon/color/layout and unchanged notices verified')
        assert len(inventory)==76,len(inventory)
        # A filtered zero warning stays clickable and goes back to red for the full sample.
        m=nav(f,'power');search=m.locator('[data-power-filter=search]');search.fill('P-00001');search.dispatch_event('change');warning=m.locator('[data-kpi-key=overdue]');expect(warning).to_have_attribute('data-kpi-tone','muted');assert not warning.is_disabled();warning.locator('.dk-icon').click();assert not m.locator('[data-power-summary-row]').count()
        search.fill('');search.dispatch_event('change');expect(warning).to_have_attribute('data-kpi-tone','red');assert warning.locator('strong').inner_text()=='1件'
        m=nav(f,'sales');biz(m,'太陽光');assert values(m)==[{'label':x['label'],'value':x['value'],'note':x['note'],'disabled':x['disabled']} for x in inventory if x['department']=='sales' and x['business']=='太陽光' and x['key'] in ['all','negotiation','planned','overdue','month']];assert m.locator('[data-kpi-key=overdue] .dk-unit').count()==0
        done('zero warnings use gray and remain clickable; real nonzero overdue stays red; unavailable values remain dashes without a count unit')
        # Excluded maintenance screens must be byte-for-byte unchanged for every business/tab.
        for business in ['蓄電池','太陽光','データセンター']:
            m=nav(f,'maintenance');om=nav(of,'maintenance');biz(m,business);biz(om,business)
            for t in ['サマリー','データ入力','案件詳細']:
                tab(m,t);tab(om,t);assert m.evaluate('(e)=>{const c=e.cloneNode(true);c.querySelectorAll(".nc-card").forEach(n=>n.remove());return c.innerHTML;}')==om.evaluate('(e)=>{const c=e.cloneNode(true);c.querySelectorAll(".nc-card").forEach(n=>n.remove());return c.innerHTML;}'),(business,t);assert not m.locator('.dk-card,.dk-row').count()
        for business in ['蓄電池','太陽光','データセンター']:
            for fr in [of,f]:fr.locator('[data-page=home]').click();fr.locator('#sales-demo-home .home-business-tabs').get_by_role('tab',name=business,exact=True).click()
            for key in ['active','grid','money']:
                for fr in [of,f]:fr.locator('#sales-demo-home .home-kpi[data-home-kpi='+key+']').click()
                assert f.locator('#sales-demo-home').inner_html()==of.locator('#sales-demo-home').inner_html()
        done('all nine maintenance screens and nine executive-home states exactly match the starting branch')
        # Fixture-only exceptional presentation; no production sample or labels are changed.
        injection="""
const kpiBefore=departmentKpis;departmentKpis=d=>kpiBefore(d).map((k,i)=>d==='sales'&&departmentState(d).business==='battery'?{...k,label:i===0?'長い項目名の表示確認'.repeat(5):k.label,value:i===0?'123,456,789,012':i===1?'未設定':i===2?'対象外':k.value}:k);
"""
        body=fixture(raw,injection);n=b.new_page(viewport={'width':800,'height':1150});n.on('pageerror',lambda e:errors.append(str(e)));u=url+'?kpi-long';n.route(u,lambda r:r.fulfill(status=200,content_type='text/html',body=body));n.goto(u,wait_until='networkidle');nf=n.frame_locator('#codex-visualization');nf.locator('[data-page=sales]').click();nm=nf.locator('#sales-workspace');assert nm.locator('.dk-value').all_text_contents()[:3]==['123,456,789,012','未設定','対象外']
        assert nm.locator('.dk-card').evaluate_all('es=>es.every(e=>e.scrollWidth<=e.clientWidth+1)');assert nm.locator('.dk-card').count()==5
        nm.locator('.dk-row').scroll_into_view_if_needed();n.screenshot(path=str(OUT/'long-and-unset.png'));n.close()
        p.set_viewport_size({'width':800,'height':1150});m=nav(f,'sales');boxes=[c.bounding_box() for c in m.locator(CARDS).all()];assert len(set(round(x['y']) for x in boxes))>1
        assert m.locator('.dk-card').evaluate_all('es=>es.every(e=>e.scrollWidth<=e.clientWidth+1)');shot('narrow-sales',m)
        assert not errors,errors;assert not failed,failed;assert not writes,writes
        done('long labels, huge counts, unset/out-of-scope values and narrow wrapping stay readable; no JS/resource/write errors')
        b.close()
    (OUT/'results.json').write_text(json.dumps({'passed':passed,'inventory':inventory,'js_errors':errors,'failed_resources':failed,'external_writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
