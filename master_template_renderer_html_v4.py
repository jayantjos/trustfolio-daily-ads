#!/usr/bin/env python3
import json, re, sys, html, importlib.util, base64
from pathlib import Path
from urllib.parse import quote
from PIL import Image
from ads_qa.spec_sanity import is_sane_spec
from ads_qa.category_copy_v1 import category_tagline
from playwright.sync_api import sync_playwright

ADS = Path(__file__).resolve().parent
OUT = ADS/'generated_creatives/feed'
MASTER = ADS/'assets/trustfolio_master_universal_v12.png'
HELPER_PATH = ADS/'renderer_v12_helper.py'
CACHE = ADS/'.html_v3_cache'

spec=importlib.util.spec_from_file_location('tfh', HELPER_PATH)
h=importlib.util.module_from_spec(spec); spec.loader.exec_module(h)

SLOTS={
1: dict(img=(396,416,675,769), name=(360,776,662,831), price=(389,840,635,895), merchant=(405,902,620,936), specs=(354,951,672,1040), top=True),
2: dict(img=(77,448,323,694), name=(77,719,321,754), price=(97,762,299,807), merchant=(105,808,291,835), specs=(70,856,320,941), top=True),
3: dict(img=(700,452,950,694), name=(708,719,947,754), price=(726,762,925,807), merchant=(733,808,917,835), specs=(705,856,955,941), top=True),
4: dict(img=(46,969,250,1242), name=(260,1082,470,1130), price=(260,1134,401,1177), merchant=(260,1180,405,1210), specs=(260,1217,490,1302), top=False),
5: dict(img=(666,990,857,1263), name=(876,1031,1015,1080), price=(881,1086,1006,1128), merchant=(877,1131,1014,1169), specs=(867,1189,1020,1285), top=False),
}

def esc(x): return html.escape(str(x or ''))
def ell(x,n=42):
    x=re.sub(r'\s+',' ',str(x or '')).strip()
    return x if len(x)<=n else x[:n-1].rstrip()+'…'
def tagline(p,rank):
    for k in ('tagline','short_tagline','short_description','subtitle'):
        if p.get(k): return str(p[k]).strip()
    return ''
def retail_class(name):
    n=(name or '').lower()
    if 'amazon' in n: return 'amazon'
    if 'flipkart' in n: return 'flipkart'
    if 'croma' in n: return 'croma'
    return 'generic'
def symbol(v):
    c=h.spec_code(v)
    return {'DISP':'▣','BAT':'▰','BT':'☎','IP':'◆','HLT':'♥','CPU':'C','RAM':'R','SSD':'S','CAM':'◉','STAR':'★','W':'⚡','CAP':'C','RPM':'↻','RO':'R','AUD':'♪','4K':'4K'}.get(c,'✓')
def prep_image(product, rank):
    CACHE.mkdir(exist_ok=True)
    # Retail image CDNs occasionally reset live connections. Retry the exact
    # source image before failing; never substitute another product or fake art.
    import time
    raw=None
    for attempt in range(3):
        raw=h.v5.load_product_image(product.get('image_url') or '', (720,720))
        if raw is not None:
            break
        if attempt < 2:
            time.sleep(0.6 * (attempt + 1))
    if raw is None: raise ValueError(f'Missing product image for rank {rank} after three attempts')
    raw=h.cutout_and_crop(raw)
    if not raw.width or not raw.height: return ''
    import io
    buf=io.BytesIO(); raw.save(buf, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
def clean_body_uri():
    # Remove only obsolete medallions in the legacy clean layer. All other
    # source pixels remain unchanged; canonical badges are separate fixed art.
    import cv2, numpy as np, io
    raw=np.array(Image.open(ADS/'assets/trustfolio_clean_master_v3.png').convert('RGB'))
    mask=np.zeros(raw.shape[:2],dtype=np.uint8)
    for x,y in [(57,986),(961,985)]: cv2.circle(mask,(x,y),38,255,-1)
    clean=cv2.inpaint(raw,mask,5,cv2.INPAINT_TELEA)
    buf=io.BytesIO();Image.fromarray(clean).save(buf,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii')

def readable_specs(product, profile, count):
    explicit=product.get('key_specs') or []
    category=profile.get('label') or profile.get('category') or ''
    if explicit:
        return [str(v) for v in explicit if is_sane_spec(category,'',v)][:count]
    raw=product.get('raw_specifications') or {}
    if not raw:
        return [v for v in h.choose_specs(product,profile,count) if is_sane_spec(category,'',v)][:count]
    values=[]
    for key,value in raw.items():
        if not value or not isinstance(value,(str,int,float)): continue
        key=str(key).lower();value=str(value).strip()
        if not is_sane_spec(category,key,value): continue
        if 'noise' in key:
            if 'environment' in value.lower() or 'enc' in value.lower(): value='ENC Calling'
            elif 'active' in value.lower() or 'anc' in value.lower(): value='Active Noise Cancellation'
        elif 'battery' in key and 'battery' not in value.lower(): value+=' Battery'
        elif 'display' in key and 'display' not in value.lower(): value+=' Display'
        elif 'driver' in key and 'driver' not in value.lower(): value+=' Driver'
        elif 'water' in key and 'resist' not in value.lower(): value+=' Resistant'
        elif 'form factor' in key: value=value.replace('In Ear','In-ear')
        values.append(value)
    priorities=profile.get('priority') or []
    def score(v):
        return next((i for i,k in enumerate(priorities) if k.lower() in v.lower()),999)
    return sorted(dict.fromkeys(values),key=score)[:count]

def display_label(product, rank):
    # Derive a compact model label from supplied data; retain full name in metadata.
    label=product.get('display_name') or product.get('short_name') or h.v5.display_name(product)
    label=re.split(r',|\s+with\s+|\s+\|\s+',str(label),maxsplit=1,flags=re.I)[0]
    words=label.split()
    max_chars=38 if rank==4 else 29 if rank==5 else 48
    kept=[]
    for word in words:
        if kept and len(' '.join(kept+[word]))>max_chars: break
        kept.append(word)
    while len(kept)>1 and kept[-1].lower() in {'in','for','with','and','the','&'}: kept.pop()
    return ' '.join(kept)

def pxbox(t):
    x1,y1,x2,y2=t; return f'left:{x1}px;top:{y1}px;width:{x2-x1}px;height:{y2-y1}px;'

def build(ad):
    key,profile=h.detect_category(ad); budget=h.detect_budget(ad)
    products=ad.get('products') or []
    ranks=[int(p.get('rank', 0)) for p in products]
    if sorted(ranks) != [1,2,3,4,5]: raise ValueError('Payload must contain exactly five unique explicit ranks 1..5')
    ranked={int(p['rank']):p for p in products}
    miss=[r for r in range(1,6) if r not in ranked]
    if miss: raise ValueError(f'missing ranks {miss}')
    title=f'Best {profile["label"]}'
    budget_text=f'Under ₹{h.indian_commas(budget)}' if budget else 'Top 5 Best Picks'
    master_uri='data:image/png;base64,' + base64.b64encode(MASTER.read_bytes()).decode('ascii')
    clean_uri=clean_body_uri()
    approved_uri='data:image/jpeg;base64,' + base64.b64encode((ADS/'assets/trustfolio_approved_reference.jpg').read_bytes()).decode('ascii')
    benefits=[('Compare Prices','Across Top Websites'),('Latest Models','& Real Prices'),('Top Rated Picks',''),('Best Deals','in Your Budget')]
    rank_art=''.join(f'<div class="rank-art rank-{r}" style="left:{x}px;top:{y}px;width:{w}px;height:{w}px;background-image:url({approved_uri});background-position:-{x}px -{y}px"></div>' for r,x,y,w in [(1,381,386,100),(2,119,417,59),(3,868,431,60),(4,28,941,66),(5,928,942,69)])
    prod_html=[]
    for r in (1,2,3,4,5):
        p=ranked[r]; s=SLOTS[r]; uri=prep_image(p,r); specs=readable_specs(p, profile, 4 if r == 1 else 3)
        name=esc(display_label(p,r)); price=esc(h.v5.product_price(p)); retailer=str(h.v5.retailer(p) or '')
        specs_html=''.join(f'<div class="spec"><span class="ico">{esc(symbol(v))}</span><span class="stxt">{esc(v)}</span></div>' for v in specs[:4])
        prod_html.append(f'''<section class="prod p{r}" data-rank="{r}" data-name="{esc(p.get('name'))}">
          <div class="pimg" style="{pxbox(s['img'])}">{f'<img src="{uri}">' if uri else ''}</div>
          <div class="namebox" style="{pxbox(s['name'])}"><div class="pname">{name}</div><div class="tag">{esc(tagline(p,r))}</div></div>
          <div class="price" style="{pxbox(s['price'])}">{price}</div>
          <div class="merchant {retail_class(retailer)}" style="{pxbox(s['merchant'])}">{esc(retailer)}</div>
          <div class="specs {'top' if s['top'] else 'bottom'}" style="{pxbox(s['specs'])}">{specs_html}</div>
        </section>''')
    benefits_html=''.join(f'<div class="benefit b{i+1}"><b>{a}</b><span>{b}</span></div>' for i,(a,b) in enumerate(benefits))
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}html,body{{margin:0;width:1024px;height:1536px;overflow:hidden;background:#fff}}body{{position:relative;font-family:"DejaVu Sans",Arial,sans-serif;color:#071939}}.bg{{position:absolute;inset:0;width:1024px;height:1536px;z-index:0}}.overlay{{position:absolute;inset:0;z-index:2}}
.hero{{position:absolute;text-align:center;font-family:"DejaVu Sans Condensed",Arial,sans-serif;font-weight:900;white-space:nowrap;text-rendering:geometricPrecision}}.hero1{{left:88px;top:122px;width:665px;height:76px;font-size:58px;line-height:76px;color:#fff;text-shadow:0 5px 0 #19005f,0 8px 12px #340071}}.hero2{{left:86px;top:198px;width:675px;height:110px;font-size:73px;line-height:106px;color:#ffd51b;text-shadow:0 5px 0 #7b4200,0 8px 10px #4d1d00}}.sub{{left:168px;top:322px;width:580px;height:54px;font-size:25px;line-height:54px;color:#071939;text-shadow:none}}
.benefit{{position:absolute;left:842px;width:143px;height:58px;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;padding-left:0}}.benefit b{{font-size:15px;line-height:18px}}.benefit span{{font-size:10.5px;line-height:14px}}.b1{{top:160px}}.b2{{top:228px}}.b3{{top:296px}}.b4{{top:364px}}
.prod{{position:absolute;inset:0}}.pimg{{position:absolute;display:flex;align-items:center;justify-content:center;z-index:6}}.pimg img{{width:100%;height:100%;object-fit:contain;filter:drop-shadow(0 7px 8px rgba(0,20,80,.25))}}.namebox,.price,.merchant,.specs{{position:absolute;z-index:8}}.namebox{{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:2px 6px;color:#fff}}.pname{{font-family:"DejaVu Sans",Arial,sans-serif;font-weight:800;font-size:20px;line-height:21px;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.tag{{font-size:11.5px;line-height:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%;opacity:.98}}.p1 .pname{{font-size:22px}}.p1 .tag{{font-size:12.5px}}.p4 .namebox,.p5 .namebox{{color:#071939;align-items:flex-start;text-align:left;padding-left:0}}.p4 .pname,.p5 .pname{{font-size:15px}}.p4 .tag,.p5 .tag{{font-size:11px}}
.price{{display:flex;align-items:center;justify-content:center;font-family:"DejaVu Sans",Arial,sans-serif;font-weight:900;font-size:31px;line-height:1;color:#071939;text-shadow:0 1px 0 rgba(255,255,255,.55)}}.p1 .price{{font-size:37px}}.p4 .price,.p5 .price{{font-size:23px}}
.merchant{{display:flex;align-items:center;justify-content:center;font-weight:800;font-size:15px;color:#fff;text-transform:none}}.p1 .merchant{{font-size:17px}}.p4 .merchant,.p5 .merchant{{color:#071939;font-size:12px;justify-content:flex-start;padding-left:8px}}.merchant.amazon::after{{content:"";position:absolute;width:42px;height:9px;border-bottom:3px solid #ff9900;border-radius:50%;left:50%;bottom:-1px;transform:translateX(-50%) rotate(-3deg)}}.p4 .merchant.amazon::after,.p5 .merchant.amazon::after{{left:36px}}
.specs{{display:flex;align-items:flex-start;justify-content:space-around;padding-top:0}}.spec{{display:flex;flex-direction:column;align-items:center;text-align:center;color:#fff;width:24%}}.ico{{width:42px;height:42px;border:2px solid currentColor;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:16px;line-height:1}}.stxt{{margin-top:4px;font-size:10px;line-height:11px;width:62px;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}}.p1 .stxt{{font-size:10.5px;width:72px}}.specs.bottom{{color:#071939;padding-top:0}}.specs.bottom .spec{{color:#071939}}.specs.bottom .ico{{width:34px;height:34px;font-size:13px;border-width:2px}}.specs.bottom .stxt{{font-size:9px;line-height:10px;width:46px}}

.clean-body{{position:absolute;left:0;top:375px;width:1024px;height:940px;overflow:hidden;z-index:1}}
.clean-body img{{position:absolute;left:0;top:-395.68px;width:1024px;height:1611.6px}}
/* Reference geometry: fixed artwork crops contain no product data. */
.fixed-footer,.fixed-benefits{{position:absolute;inset:0;width:1024px;height:1536px;z-index:1;pointer-events:none}}
.fixed-footer{{clip-path:inset(1315px 0 0 0)}}
.fixed-benefits{{clip-path:inset(150px 0 1108px 770px)}}
.benefit{{display:none}}
.hero1{{left:105px;top:150px;width:640px;height:82px;font-size:72px;line-height:82px;transform:rotate(-9deg);font-stretch:condensed;letter-spacing:-3px}}
.hero2{{left:103px;top:225px;width:647px;height:115px;font-size:101px;line-height:115px;transform:rotate(-9deg);letter-spacing:-4px}}
.sub{{left:206px;top:324px;width:510px;height:46px;font-size:27px;line-height:46px;transform:rotate(-7deg);letter-spacing:-1px}}
.pname{{font-family:'Liberation Sans Narrow','Arial Narrow',Arial,sans-serif;font-size:22px;line-height:24px;letter-spacing:-.5px}}
.tag{{font-size:15px;line-height:19px}}.p1 .tag{{font-size:17px;line-height:21px}}
.price{{background:linear-gradient(#fff95a,#ffe222);border-radius:9px;box-shadow:0 0 12px #ffee4477;font-size:38px;color:#080b11;letter-spacing:-1px}}
.p1 .price{{font-size:48px}}.p4 .price,.p5 .price{{font-size:33px}}
.merchant{{font-size:24px}}.p1 .merchant{{font-size:28px}}.p4 .merchant,.p5 .merchant{{font-size:23px;padding-left:0}}
.spec{{flex:1}}.stxt{{font-size:14px;line-height:17px;width:78px;-webkit-line-clamp:3}}.p1 .stxt{{font-size:14px;width:76px}}
.specs.bottom{{flex-direction:column;justify-content:flex-start;gap:6px}}
.specs.bottom .spec{{width:100%;flex:none;flex-direction:row;text-align:left;gap:7px}}
.specs.bottom .ico{{width:25px;height:25px;border:0;border-radius:4px;background:#081326;color:white;flex-shrink:0}}
.specs.bottom .stxt{{font-size:14px;line-height:18px;width:auto;margin:0;display:block}}
.p4 .pname,.p5 .pname{{font-size:18px;line-height:20px}}.p4 .tag,.p5 .tag{{font-size:14px;line-height:18px}}

.clean-body{{mask-image:linear-gradient(to bottom,transparent,black 35px,black)}}
.pname{{white-space:normal;overflow:visible;text-overflow:clip;line-height:1.05}}
.tag{{white-space:normal;overflow:visible;text-overflow:clip;line-height:1.1}}
.stxt{{display:block;overflow:visible;line-height:1.12;overflow-wrap:anywhere}}
.p4 .namebox,.p5 .namebox{{justify-content:flex-start}}
.specs.top{{padding-top:0}}.p2 .specs,.p3 .specs{{top:844px!important;height:92px!important}}
.specs.top .ico{{width:42px;height:42px;flex-shrink:0}}
.p1 .stxt{{font-size:13px}}.p2 .stxt,.p3 .stxt{{font-size:13px}}


.rank-art{{position:absolute;z-index:10;border-radius:50%;background-size:1024px 1536px;background-repeat:no-repeat}}
</style></head><body><img class="bg" src="{master_uri}"><div class="clean-body"><img src="{clean_uri}"></div><img class="fixed-footer" src="{approved_uri}"><img class="fixed-benefits" src="{approved_uri}"><div class="overlay"><div class="hero hero1">{esc(title)}</div><div class="hero hero2">{esc(budget_text)}</div><div class="hero sub">{esc(category_tagline(key, ad_type=ad.get('source_ad_type') or ''))}</div>{benefits_html}{''.join(prod_html)}{rank_art}</div></body></html>''',key,profile

def render(ad):
    html_text,key,profile=build(ad); OUT.mkdir(parents=True,exist_ok=True); CACHE.mkdir(exist_ok=True)
    pagefile=CACHE/'render.html'; pagefile.write_text(html_text,encoding='utf-8')
    adid=ad.get('source_ad_id') or 'trustfolio'; dest=OUT/f'{adid}_final_html_v3_1024x1536.png'
    with sync_playwright() as p:
        kwargs=dict(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        for candidate in ('/usr/bin/chromium','/usr/bin/google-chrome'):
            if Path(candidate).exists():
                kwargs['executable_path']=candidate
                break
        browser=p.chromium.launch(**kwargs)
        page=browser.new_page(viewport={'width':1024,'height':1536}, device_scale_factor=1)
        page.set_content(html_text, wait_until='load')
        page.evaluate('''() => document.fonts.ready''')
        # fit long hero/category text without tiny fonts
        page.evaluate('''() => { for (const el of document.querySelectorAll('.hero1,.hero2')) { let s=parseFloat(getComputedStyle(el).fontSize); while (el.scrollWidth>el.clientWidth && s>42){s-=1;el.style.fontSize=s+'px';} } }''')
        page.evaluate("""() => {
          for (const el of document.querySelectorAll('.pname,.tag')) {
            const limit=el.classList.contains('pname')?14:11;
            let size=parseFloat(getComputedStyle(el).fontSize);
            while ((el.scrollWidth>el.clientWidth+1 || el.parentElement.scrollHeight>el.parentElement.clientHeight+1) && size>limit) {
              size-=.5;el.style.fontSize=size+'px';
            }
          }
          for (const el of document.querySelectorAll('.stxt')) {
            let size=parseFloat(getComputedStyle(el).fontSize);
            const parent=el.closest('.specs');
            while (el.getBoundingClientRect().bottom>parent.getBoundingClientRect().bottom+1 && size>11) {
              size-=.5;el.style.fontSize=size+'px';
            }
          }
        }""")
        geometry=page.evaluate("""() => {
          const box=e=>{const r=e.getBoundingClientRect();return [r.x,r.y,r.right,r.bottom]};
          const errors=[];
          const dynamic=[...document.querySelectorAll('.hero,.pimg,.namebox,.price,.merchant,.specs')].map(box);
          const slots=[...document.querySelectorAll('.prod')].map(p=>{
            const fields={};for(const cls of ['pimg','namebox','price','merchant','specs']) fields[cls]=box(p.querySelector('.'+cls));
            const im=p.querySelector('.pimg img');if(!im || !im.complete || !im.naturalWidth) errors.push('missing image '+p.dataset.rank);
            for(const e of p.querySelectorAll('.pname,.tag')) if(e.scrollWidth>e.clientWidth+2 || e.parentElement.scrollHeight>e.parentElement.clientHeight+2) errors.push('overflow rank '+p.dataset.rank+' '+e.className);
            for(const e of p.querySelectorAll('.stxt')) {const a=box(e),b=box(e.closest('.specs'));if(a[0]<b[0]-2||a[2]>b[2]+2||a[3]>b[3]+2)errors.push('spec overflow rank '+p.dataset.rank);}
            return {rank:Number(p.dataset.rank),name:p.dataset.name,fields};
          });return {dynamic,slots,errors};
        }""")
        geometry['category']=key
        geometry['source_ad_id']=adid
        dest.with_suffix('.json').write_text(json.dumps(geometry,indent=2))
        page.screenshot(path=str(dest),full_page=False)
        browser.close()
    print('HTML V3 QA IMAGE:',dest); print('CATEGORY:',key,'| LABEL:',profile['label'],'| BUDGET:',h.detect_budget(ad)); print('LAYOUT: CLEAN MASTER + CSS LOCKED | DATA: DYNAMIC | NOT PUBLISHED')
    return dest

if __name__=='__main__':
    payload=Path(sys.argv[1]) if len(sys.argv)>1 else ADS/'trustfolio_infographic_payload_v1.json'; adid=sys.argv[2] if len(sys.argv)>2 else 'tf-aa5900f0c166'
    data=json.loads(payload.read_text(encoding='utf-8')); ad=next((x for x in data.get('ads',[]) if x.get('source_ad_id')==adid),None)
    if ad is None: raise SystemExit(f'Ad not found: {adid}')
    render(ad)

