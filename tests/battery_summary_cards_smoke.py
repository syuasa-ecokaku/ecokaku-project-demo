"""Shared battery summary cards: layout, unchanged data, filters, links and other-business isolation."""
from pathlib import Path
from html.parser import HTMLParser
from html import escape
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from notice_snapshot import content_text

ROOT=Path(__file__).resolve().parents[1]
OUT=Path('/tmp/ecokaku-summary-cards-review')
DEPTS=['realestate','power','sales','legal','procurement','construction','maintenance']
class Inner(HTMLParser):
    value=''
    def handle_starttag(self,t,a):
        d=dict(a)
        if t=='iframe' and d.get('id')=='codex-visualization':self.value=d['data-srcdoc']
def inner(raw):p=Inner();p.feed(raw);return p.value
def fixture(raw,fn):
    s=fn(inner(raw));a=raw.index('data-srcdoc="')+len('data-srcdoc="');b=raw.index('"',a)
    return raw[:a]+escape(s,quote=True)+raw[b:]

def run():
    OUT.mkdir(exist_ok=True);passed=[];errors=[];writes=[];failed=[]
    old_html=subprocess.check_output(['git','show','6dd6154:index.html'],cwd=ROOT,text=True)
    current=(ROOT/'index.html').read_text()
    for name in ['batteryCaseSeedData','batteryDepartmentDefinitions']:
        get=lambda raw:json.JSONDecoder().raw_decode(inner(raw).split('const '+name+'=',1)[1])[0]
        assert get(old_html)==get(current),name
    def done(s):passed.append(s);print('PASS',s,flush=True)
    done('shared case data and department status/schedule definitions exactly unchanged')
    with server() as url,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1550,'height':1250})
        page.on('pageerror',lambda e:errors.append(str(e)));page.on('requestfailed',lambda r:failed.append(r.url))
        page.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
        page.goto(url,wait_until='networkidle');f=page.frame_locator('#codex-visualization')
        old=browser.new_page(viewport={'width':1550,'height':1250});old.route(url,lambda r:r.fulfill(status=200,content_type='text/html',body=old_html));old.goto(url,wait_until='networkidle');of=old.frame_locator('#codex-visualization')
        seed=json.JSONDecoder().raw_decode(inner(current).split('const batteryCaseSeedData=',1)[1])[0]
        def nav(frame,d):frame.locator('[data-page='+d+']').click();return frame.locator('#'+d+'-workspace')
        def clear(m,d):
            if d=='power':m.locator('[data-power-action=clearFilters]').click()
            else:m.locator('[data-dept-filter=status]').select_option('')
        def baseline(d):
            m=nav(of,d)
            if d=='power':
                counts=m.locator('.pw-stage-count').evaluate_all('(es)=>es.map(e=>({label:e.querySelector("span").textContent,count:Number(e.querySelector("strong").textContent.replace("件",""))}))')
                rows=m.locator('.pw-schedule').evaluate_all('(es)=>es.map(e=>({date:e.querySelector("time").textContent,index:Number(e.querySelector("button").dataset.powerOpen),text:e.querySelector("button").textContent}))')
                plans=[{'date':r['date'],'id':seed[r['index']]['id'],'name':r['text'].rsplit(' ／ ',1)[0],'label':r['text'].rsplit(' ／ ',1)[1]} for r in rows]
            else:
                counts=[]
                for s in m.locator('.du-overview section').first.locator('[data-dept-status]').all():
                    counts.append({'label':s.get_attribute('data-dept-status'),'count':int(s.inner_text().rsplit(' ',1)[1].replace('件',''))})
                rows=m.locator('.du-overview section').nth(1).locator('.du-padded>p').evaluate_all('(es)=>es.map(e=>({date:e.textContent.slice(0,10),id:e.querySelector("button").dataset.deptOpen,label:e.textContent.split(" ／ ").at(-1)}))')
                plans=[{**r,'name':next(c['name'] for c in seed if c['id']==r['id'])} for r in rows]
            return counts,plans
        for d in DEPTS:
            counts,plans=baseline(d);m=nav(f,d);clear(m,d);pair=m.locator('[data-summary-pair]')
            expect(pair.locator('[data-summary-card]')).to_have_count(2)
            assert pair.locator('h3').all_text_contents()==['工程・ステータス別件数','直近の予定・期限']
            assert pair.locator('.s-boxhead,.s-btn').count()==0
            cards=pair.locator('[data-summary-card]');boxes=[c.bounding_box() for c in cards.all()]
            assert abs(boxes[0]['width']-boxes[1]['width'])<=1 and abs(boxes[0]['y']-boxes[1]['y'])<=1
            for c in cards.all():
                assert c.evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(255, 255, 255)'
                assert c.locator('h3').evaluate('(e)=>Number(getComputedStyle(e).fontWeight)')>=600
            actual=pair.locator('.dept-status-row').evaluate_all('(es)=>es.map(e=>({label:e.querySelector("[data-status-label]").textContent,count:Number(e.querySelector("strong").textContent.replace("件",""))}))')
            lookup={x['label']:x['count'] for x in actual}
            assert all(lookup[x['label']]==x['count'] for x in counts)
            assert sum(lookup.values())==10
            for row in pair.locator('.dept-status-row').all():
                assert abs(row.bounding_box()['height']-46)<=1
                assert row.locator('button').count()==1
                assert row.locator('button').evaluate('(e)=>getComputedStyle(e).textAlign')=='right'
                assert row.locator('strong').evaluate('(e)=>getComputedStyle(e).color')=='rgb(20, 106, 184)'
            if d=='power':assert [x['label'] for x in actual]==[x['label'] for x in counts]
            else:
                defs=json.JSONDecoder().raw_decode(inner(current).split('const batteryDepartmentDefinitions=',1)[1])[0]
                assert set(defs[d]['groups']['common']['fields']['status']['options'])<=set(lookup)
            observed=pair.locator('[data-summary-schedule]').evaluate_all('(es)=>es.map(e=>({date:e.querySelector("time").textContent,id:e.dataset.caseId,name:e.querySelector("button").textContent,label:e.querySelector(".dept-schedule-label").textContent.replace(/^／ /,"")}))')
            assert observed==plans,(d,observed,plans)
            assert [r['date'] for r in observed]==sorted(r['date'] for r in observed)
            for row in pair.locator('[data-summary-schedule]').all():
                assert row.locator(':scope>*').evaluate_all('(es)=>es.map(e=>e.tagName)')==['TIME','BUTTON','SPAN']
                assert row.locator('button').get_attribute('title')==row.locator('button').inner_text()
                assert abs(row.bounding_box()['height']-46)<=1
            pair.scroll_into_view_if_needed();page.screenshot(path=str(OUT/(d+'-cards.png')))
            # Every configured status including zero can filter, without changing the record data.
            for entry in actual:
                clear(m,d)
                target=m.locator('[data-summary-status="'+entry['label']+'"]')
                target.locator('button').click()
                assert m.locator('[data-power-summary-row]' if d=='power' else '[data-dept-summary-row]').count()==entry['count'],(d,entry)
                if d!='power':expect(m.locator('[data-dept-filter=status]')).to_have_value(entry['label'])
            clear(m,d)
            if plans:
                row=m.locator('[data-summary-schedule]').first;pid=row.get_attribute('data-case-id');row.locator('button').click()
                if d=='power':
                    assert pid in m.locator('.pw-casehead').inner_text();expect(m.locator('#power-section-receipt')).to_have_attribute('open','')
                else:expect(m.locator('[data-dept-select]')).to_have_value(pid)
            done(d+': equal cards, unchanged counts/dates, configured zero rows, right alignment, filter counts, name tooltip and correct detail navigation')
        # An unregistered name must fall back to the existing case ID. Long names must ellipsize.
        for kind,name in [('missing',''),('long','デモの非常に長い蓄電池案件名'*15)]:
            html=fixture(current,lambda s:s.replace('"name":"デモ第02蓄電所"','"name":'+json.dumps(name,ensure_ascii=False),1))
            assert html!=current
            p=browser.new_page(viewport={'width':1280,'height':1100});route_url=url+'?'+kind;p.route(route_url,lambda r:r.fulfill(status=200,content_type='text/html',body=html));p.goto(route_url,wait_until='networkidle');ff=p.frame_locator('#codex-visualization');m=nav(ff,'sales');el=m.locator('[data-summary-schedule][data-case-id=P-00002] button')
            expect(el).to_have_text(name or 'P-00002');expect(el).to_have_attribute('title',name or 'P-00002')
            if name:
                assert el.evaluate('(e)=>e.scrollWidth>e.clientWidth')
                assert el.evaluate('(e)=>getComputedStyle(e).textOverflow')=='ellipsis'
            p.close()
        done('missing case name falls back to ID; long name is truncated with full title tooltip')
        # Empty dates fixture modifies only this browser response, with no production hooks or data changes.
        html=fixture(current,lambda s:s.replace("render();showPage('home');settingsRefreshIcons();", "for(const c of Object.values(batteryDepartmentDefinitions))c.schedule=[];for(const c of batteryCases)for(const k of ['88','supplyDesired','89','supplyStart'])c.power.values[k]='';render();showPage('home');settingsRefreshIcons();"))
        p=browser.new_page();route_url=url+'?empty';p.route(route_url,lambda r:r.fulfill(status=200,content_type='text/html',body=html));p.goto(route_url,wait_until='networkidle');ff=p.frame_locator('#codex-visualization')
        for d in DEPTS:
            m=nav(ff,d);expect(m.locator('.dept-summary-empty')).to_have_text('直近の予定はありません');assert m.locator('[data-summary-schedule]').count()==0
        p.close();done('all seven empty schedule cards use the specified message')
        # Solar/DC text, values and styles continue using their old markup.
        def snapshot(frame,d,business):
            m=nav(frame,d);m.locator('.du-business-tabs').get_by_role('tab',name=business,exact=True).click()
            return {'text':content_text(m),'controls':m.locator('input:not([type=file]),select').evaluate_all('(es)=>es.filter(e=>!e.closest(".nc-card")).map(e=>[e.type,e.value,e.disabled])'),'legacy_cards':m.locator('.du-overview,.sl-overview').inner_html() if m.locator('.du-overview,.sl-overview').count() else ''}
        for d in DEPTS:
            for business in ['太陽光','データセンター']:assert snapshot(f,d,business)==snapshot(of,d,business),(d,business)
        done('all 14 non-battery summaries retain their text, input values and legacy card markup')
        page.set_viewport_size({'width':800,'height':1050});m=nav(f,'realestate');pair=m.locator('[data-summary-pair]');boxes=[x.bounding_box() for x in pair.locator('[data-summary-card]').all()]
        assert boxes[1]['y']>=boxes[0]['y']+boxes[0]['height']
        pair.scroll_into_view_if_needed();page.screenshot(path=str(OUT/'narrow-cards.png'))
        assert not errors,errors
        assert not failed,failed
        assert not writes,writes
        done('narrow layout stacks cleanly; no JavaScript errors, failed resources or external writes')
        old.close();browser.close()
    (OUT/'results.json').write_text(json.dumps({'passed':passed,'js_errors':errors,'failed_resources':failed,'external_writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
