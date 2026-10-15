#!/usr/bin/env python3
"""TrustFolio V3: clean fixed artwork + data-driven five-product rendering."""
import io, json, re, sys, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

BASE=Path.home()/"new_scraper"
ADS=BASE/"ads"
ASSET=ADS/"assets"/"trustfolio_clean_master_v5.png"
DEFAULT_INPUT=ADS/"trustfolio_infographic_payload_v1.json"
OUT=ADS/"generated_creatives"/"feed"
W,H=1024,1536
NAVY=(4,20,56); INK=(8,21,48); WHITE=(255,255,255); YELLOW=(255,218,25); CYAN=(24,211,255)

def font(size,bold=False,italic=False):
    paths=[]
    if italic: paths.append('/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf')
    paths += ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf']
    for p in paths:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def fit(d,s,maxw,size,minsize=10,bold=True):
    s=str(s or '')
    for n in range(size,minsize-1,-1):
        f=font(n,bold)
        if d.textbbox((0,0),s,font=f)[2] <= maxw: return f
    return font(minsize,bold)

def wrap(d,s,maxw,size=18,minsize=10,maxlines=2,bold=True):
    words=str(s or '').split()
    for n in range(size,minsize-1,-1):
        f=font(n,bold); lines=[]; line=''
        for word in words:
            test=(line+' '+word).strip()
            if d.textbbox((0,0),test,font=f)[2] <= maxw: line=test
            else:
                if line: lines.append(line)
                line=word
        if line: lines.append(line)
        if len(lines)<=maxlines: return lines,f
    f=font(minsize,bold); lines=[]; line=''
    for word in words:
        test=(line+' '+word).strip()
        if d.textbbox((0,0),test,font=f)[2] <= maxw: line=test
        else:
            if line: lines.append(line)
            line=word
    if line: lines.append(line)
    lines=lines[:maxlines]
    if lines and len(lines)==maxlines:
        last=lines[-1]
        while last and d.textbbox((0,0),last+'…',font=f)[2]>maxw: last=last[:-1]
        lines[-1]=last.rstrip()+'…'
    return lines,f

def product_name(p):
    return str(p.get('name') or p.get('full_title') or p.get('title') or 'Product').strip()

def display_name(p):
    """Short display label only; the full source title remains in the payload."""
    value = str(p.get('display_name') or product_name(p)).strip()
    # Keep the model/series part, dropping long marketplace feature copy.
    value = re.split(r'\s*(?:\||,|;\s*|\s+with\s+|\s+for\s+(?:men|women|man|woman)\b)', value, maxsplit=1, flags=re.I)[0]
    value = re.sub(r'\s+\d+(?:\.\d+)?\s*["″]?\s*(?:inch|inches|display|tft|amoled|hd|curved).*$', '', value, flags=re.I)
    value = re.sub(r'\s+(?:smart\s*watch|smartwatch|bluetooth calling|fitness tracker)$', '', value, flags=re.I)
    value = re.sub(r'\s+', ' ', value).strip(" -,:|")
    return value or product_name(p)
def product_price(p):
    v=p.get('price_display')
    if v: return str(v)
    v=p.get('price_inr',p.get('price'))
    if v in (None,''): return 'Price unavailable'
    try: return '₹'+format(float(v),',.0f')
    except (ValueError,TypeError): return str(v)
def retailer(p): return str(p.get('retailer') or p.get('platform') or '').strip()

def product_specs(p,limit=3):
    raw=p.get('raw_specifications') or p.get('specifications') or {}
    if isinstance(raw,dict):
        preferred=('display','screen','battery','bluetooth','calling','sp02','heart','sports','water','resolution','connectivity','capacity','power')
        pairs=list(raw.items()); pairs.sort(key=lambda kv: next((i for i,k in enumerate(preferred) if k in str(kv[0]).lower()),999))
        out=[]
        for k,v in pairs:
            if v not in (None,'','N/A','Unknown','unknown'):
                item=f'{str(k).strip()}: {str(v).strip()}'
                if len(item)<=50: out.append(item)
            if len(out)>=limit: break
        if out: return out
    raw=p.get('key_specs') or []
    return [str(x) for x in raw if str(x).strip()][:limit] if isinstance(raw,list) else []
def short_specs(p,limit=2):
    # A short tagline is shown only when the source provides one. Do not repeat
    # the same specifications both in this line and again in the feature row.
    t=p.get('tagline')
    return str(t).strip() if t else ''

def compact_spec(value):
    # UI-only compact formatting; values and facts are preserved.
    s=str(value).strip()
    rules = [
        (r'^Display:\s*(.+)$', r'\1 Display'),
        (r'^Battery Life:\s*(.+)$', r'\1 Battery'),
        (r'^Connectivity:\s*(.+)$', r'\1'),
        (r'^Water Resistance:\s*(.+)$', r'\1 Water Resistance'),
        (r'^Sports Modes:\s*(.+)$', r'\1 Sports Modes'),
        (r'^Heart Rate Monitor:?\s*(.*)$', r'Heart Rate Monitor \1'),
    ]
    for pattern, repl in rules:
        if re.match(pattern,s,re.I):
            s=re.sub(pattern,repl,s,flags=re.I)
            break
    s=re.sub(r'\s+',' ',s).strip()
    return s

def load_product_image(url,box):
    if not url: return None
    try:
        if str(url).startswith(('http://','https://')):
            req=urllib.request.Request(str(url),headers={'User-Agent':'Mozilla/5.0 TrustFolioCreative/3'})
            with urllib.request.urlopen(req,timeout=20) as r: data=r.read()
            im=Image.open(io.BytesIO(data)).convert('RGBA')
        else: im=Image.open(str(url)).convert('RGBA')
        # Remove only edge-connected near-white studio background. This avoids
        # punching holes in white watch faces, text, reflections, or pale straps.
        from collections import deque
        rgba = im.convert("RGBA")
        px = rgba.load()
        w, h = rgba.size
        seen = bytearray(w * h)
        q = deque()

        def is_background(x, y):
            r, g, b, a = px[x, y]
            return a > 0 and min(r, g, b) >= 246 and (max(r, g, b) - min(r, g, b)) <= 10

        # Seed from all four edges; only connected white backdrop is made transparent.
        for x in range(w):
            if is_background(x, 0): q.append((x, 0))
            if h > 1 and is_background(x, h - 1): q.append((x, h - 1))
        for y in range(1, h - 1):
            if is_background(0, y): q.append((0, y))
            if w > 1 and is_background(w - 1, y): q.append((w - 1, y))

        while q:
            x, y = q.popleft()
            idx = y * w + x
            if seen[idx]: continue
            seen[idx] = 1
            if not is_background(x, y): continue
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, 0)
            if x > 0 and not seen[idx - 1]: q.append((x - 1, y))
            if x + 1 < w and not seen[idx + 1]: q.append((x + 1, y))
            if y > 0 and not seen[idx - w]: q.append((x, y - 1))
            if y + 1 < h and not seen[idx + w]: q.append((x, y + 1))

        # Trim transparent margins after background removal to scale products consistently.
        alpha = rgba.getchannel("A")
        bbox = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
        if bbox:
            rgba = rgba.crop(bbox)
        return ImageOps.contain(rgba, box, method=Image.Resampling.LANCZOS)
    except Exception as e:
        print(f'WARNING image load failed: {str(url)[:55]} ({e})')
        return None

def paste_product(im,p,box):
    x1,y1,x2,y2=box; pic=load_product_image(p.get('image_url') or '',(x2-x1,y2-y1))
    if pic: im.alpha_composite(pic,(x1+(x2-x1-pic.width)//2,y1+(y2-y1-pic.height)//2))
    else: print(f'WARNING missing product image for: {product_name(p)[:55]}')

def draw_center(d,text,x,y,maxw,size=18,color=WHITE,bold=True):
    f=fit(d,text,maxw,size,10,bold); d.text((x,y),str(text),font=f,fill=color,anchor='mt')

def draw_rotated_text(im, text, xy, maxw, size, color, stroke_width=0, stroke_fill=INK):
    """Draw headline text angled to follow the purple ribbon."""
    probe=ImageDraw.Draw(im)
    f=fit(probe,text,maxw,size,max(26,size-24),True)
    bbox=probe.textbbox((0,0),str(text),font=f,stroke_width=stroke_width)
    tw=maxw+24
    th=max(100,bbox[3]-bbox[1]+36)
    layer=Image.new('RGBA',(tw,th),(0,0,0,0))
    ld=ImageDraw.Draw(layer)
    ld.text((8,8-bbox[1]),str(text),font=f,fill=color,stroke_width=stroke_width,stroke_fill=stroke_fill)
    layer=layer.rotate(8, resample=Image.Resampling.BICUBIC, expand=True)
    im.alpha_composite(layer,(int(xy[0]),int(xy[1])))

def price_pill(d,box,text,size=29):
    d.rounded_rectangle(box,radius=12,fill=YELLOW,outline=(255,246,150),width=2)
    d.text(((box[0]+box[2])//2,(box[1]+box[3])//2),str(text),font=fit(d,text,box[2]-box[0]-12,size,15,True),fill=INK,anchor='mm')

def retailer_text(d,value,cx,y,maxw):
    if value: d.text((cx,y),value,font=fit(d,value,maxw,19,11,True),fill=WHITE,anchor='mt')

def draw_top_product(im,p,kind):
    d=ImageDraw.Draw(im)
    if kind=='left':
        paste_product(im,p,(68,425,340,708)); cx=205; name_y=721; maxw=260; pricebox=(91,787,320,832); ry=836; spec_y=866; specw=260
    elif kind=='right':
        paste_product(im,p,(687,425,959,708)); cx=832; name_y=721; maxw=252; pricebox=(731,787,946,832); ry=836; spec_y=866; specw=248
    else:
        paste_product(im,p,(348,402,682,757)); cx=517; name_y=782; maxw=326; pricebox=(391,858,652,905); ry=909; spec_y=944; specw=305
    d=ImageDraw.Draw(im)
    lines,f=wrap(d,display_name(p),maxw,22 if kind!='center' else 24,14,2,True)
    yy=name_y
    for line in lines:
        d.text((cx,yy),line,font=f,fill=WHITE,anchor='mt',stroke_width=1,stroke_fill=(0,24,69)); yy+=f.size+1
    hi=short_specs(p,2)
    if hi: draw_center(d,hi,cx,yy+2,maxw,14,(231,244,255),False)
    price_pill(d,pricebox,product_price(p),34 if kind=='center' else 30)
    retailer_text(d,retailer(p),cx,ry,maxw)
    items=product_specs(p,4 if kind=='center' else 3)
    if items:
        if kind=='center':
            gap=5; cw=(specw-gap*(len(items)-1))/len(items); x0=cx-specw/2
            for i,item in enumerate(items):
                xx=x0+i*(cw+gap); d.ellipse((xx+cw/2-13,spec_y,xx+cw/2+13,spec_y+26),outline=(228,248,255),width=2)
                d.text((xx+cw/2,spec_y+13),['▣','♥','✓','↗'][i%4],font=font(12,True),fill=WHITE,anchor='mm')
                lines,sf=wrap(d,compact_spec(item),cw,11,9,2,False)
                for j,line in enumerate(lines): d.text((xx+cw/2,spec_y+28+j*11),line,font=sf,fill=WHITE,anchor='mt')
        else:
            gap=3; cw=(specw-gap*(len(items)-1))/len(items); x0=cx-specw/2
            for i,item in enumerate(items):
                xx=x0+i*(cw+gap); d.ellipse((xx+cw/2-12,spec_y,xx+cw/2+12,spec_y+24),outline=(228,248,255),width=2)
                d.text((xx+cw/2,spec_y+12),['▣','♥','✓'][i%3],font=font(11,True),fill=WHITE,anchor='mm')
                lines,sf=wrap(d,compact_spec(item),cw,11,9,2,False)
                for j,line in enumerate(lines): d.text((xx+cw/2,spec_y+25+j*10),line,font=sf,fill=WHITE,anchor='mt')

def draw_bottom_card_panels(im):
    d=ImageDraw.Draw(im,'RGBA')
    # Two compact white cards, matching the approved reference layout.
    d.rounded_rectangle((32,1043,495,1290),radius=28,fill=(250,253,255,238),outline=(100,210,255,255),width=2)
    d.rounded_rectangle((547,1043,995,1290),radius=28,fill=(250,253,255,238),outline=(100,210,255,255),width=2)

def draw_bottom_product(im,p,side):
    d=ImageDraw.Draw(im)
    if side=='left':
        paste_product(im,p,(40,1015,255,1278)); tx=271; tw=208; pricebox=(272,1109,475,1153); retailer_y=1156; specs_y=1190
    else:
        paste_product(im,p,(567,1015,790,1278)); tx=800; tw=179; pricebox=(800,1109,979,1153); retailer_y=1156; specs_y=1190
    d=ImageDraw.Draw(im)
    lines,f=wrap(d,display_name(p),tw,19,12,2,True); yy=1054
    for line in lines: d.text((tx,yy),line,font=f,fill=NAVY,anchor='lt'); yy+=f.size+1
    hi=short_specs(p,1)
    if hi:
        lines,hf=wrap(d,hi,tw,13,10,1,False); d.text((tx,yy+1),lines[0],font=hf,fill=(31,69,120));
    price_pill(d,pricebox,product_price(p),27)
    if retailer(p): d.text((tx+tw/2,retailer_y),retailer(p),font=fit(d,retailer(p),tw,17,10,True),fill=(0,88,214),anchor='mt')
    yy=specs_y
    for item in product_specs(p,3):
        d.rounded_rectangle((tx,yy+2,tx+13,yy+15),radius=3,fill=NAVY)
        lines,sf=wrap(d,compact_spec(item),tw-19,12,9,1,False); d.text((tx+18,yy),lines[0],font=sf,fill=INK); yy+=24

def parse_title(meta):
    title=str(meta.get('campaign_title') or '').strip(); category=str(meta.get('campaign_category') or '').strip()
    m=re.match(r'^(.*?)\s+Under\s+(₹\s*[\d,]+)\s*$',title,re.I)
    if not m: m=re.match(r'^(.*?)\s+(?:below|within)\s+(₹\s*[\d,]+)\s*$',title,re.I)
    if m: return m.group(1).strip(), 'Under '+m.group(2).replace(' ','')
    return ('Best '+category.title() if category else title),''

def render(ad):
    if not ASSET.exists(): raise FileNotFoundError(f'Clean master template missing: {ASSET}')
    im=Image.open(ASSET).convert('RGBA')
    if im.size!=(W,H): im=im.resize((W,H),Image.Resampling.LANCZOS)
    meta=ad.get('metadata') or {}; headline,budget=parse_title(meta); products=ad.get('products') or []
    if len(products)<5: raise ValueError(f"Expected five products; got {len(products)}")
    # Place products by rank, independent of payload list ordering.
    ranked = {}
    for index, product in enumerate(products[:5], 1):
        try:
            rank = int(product.get('rank') or index)
        except (TypeError, ValueError):
            rank = index
        if 1 <= rank <= 5 and rank not in ranked:
            ranked[rank] = product
    if len(ranked) < 5:
        raise ValueError("Could not map five unique product ranks.")
    featured = ranked[1]
    leftp = ranked[2]
    rightp = ranked[3]
    bottomleft = ranked[4]
    bottomright = ranked[5]
    # Headline lives only inside the blank purple banner. No old title is baked in.
    d=ImageDraw.Draw(im)
    # Follow the same rising diagonal as the approved purple/yellow headline ribbons.
    draw_rotated_text(im,headline,(88,102),690,66,WHITE,4,(39,7,89))
    if budget: draw_rotated_text(im,budget,(105,169),650,74,YELLOW,4,(91,42,0))
    # Product photos float naturally over the three glossy podiums.
    draw_top_product(im,leftp,'left'); draw_top_product(im,featured,'center'); draw_top_product(im,rightp,'right')
    # Approved reference has no white backing cards behind products #4 and #5.
    # Keep the original background/reflections visible and draw products directly over it.
    draw_bottom_product(im,bottomleft,'left'); draw_bottom_product(im,bottomright,'right')
    # Repaint the existing master badge last so it sits in front of the featured product.
    d=ImageDraw.Draw(im)
    d.ellipse((378,386,478,486),fill=(255,211,18),outline=(255,255,255),width=4)
    d.ellipse((384,392,472,480),outline=(255,238,135),width=2)
    d.text((428,423),'#1',font=font(34,True),fill=INK,anchor='mm')
    d.text((428,449),'Best Value',font=font(12,True),fill=INK,anchor='mm')
    OUT.mkdir(parents=True,exist_ok=True)
    adid=str(ad.get('source_ad_id') or 'trustfolio')
    out=OUT/f'{adid}_final_v5_1024x1536.png'
    rgb=Image.new('RGB',(W,H),WHITE); rgb.paste(im,mask=im.getchannel('A')); rgb.save(out,'PNG',optimize=True)
    print('TRUSTFOLIO FINAL MASTER RENDERER (NO BOTTOM WHITE CARDS)')
    print('AD ID   :',adid); print('CATEGORY:',meta.get('campaign_category')); print('HEADLINE:',meta.get('campaign_title'))
    print('PRODUCTS:',len(products[:5])); print('OUTPUT  :',out); print('QA ONLY : do not batch publish yet')
    return out

def main():
    inp=Path(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_INPUT
    adid=sys.argv[2] if len(sys.argv)>2 else 'tf-aa5900f0c166'
    payload=json.loads(inp.read_text(encoding='utf-8'))
    ad=next((x for x in payload.get('ads',[]) if x.get('source_ad_id')==adid),None)
    if ad is None: raise SystemExit(f'Ad ID not found: {adid}')
    render(ad)
if __name__=='__main__': main()
