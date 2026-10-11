#!/usr/bin/env python3
"""TrustFolio reference-layout renderer V8.
Uses the existing infographic payload; no fabricated product data.
Canvas follows the approved tall 1024x1536 composition.
"""
import io, json, re, sys, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = Path.home() / "new_scraper"
ADS = BASE / "ads"
DEFAULT_INPUT = ADS / "trustfolio_infographic_payload_v1.json"
OUT = ADS / "generated_creatives" / "feed"
W, H = 1024, 1536
NAVY=(4,20,56); BLUE=(0,91,220); CYAN=(24,211,255); PURPLE=(91,24,238)
YELLOW=(255,218,25); WHITE=(255,255,255); INK=(8,21,48); PALE=(225,244,255)

def font(size, bold=False, italic=False):
    candidates = []
    if italic: candidates += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"]
    candidates += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                   "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    for p in candidates:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def text_fit(d, s, maxw, size, minsize=12, bold=True):
    for n in range(size,minsize-1,-1):
        f=font(n,bold)
        if d.textbbox((0,0),str(s),font=f)[2] <= maxw: return f
    return font(minsize,bold)

def wrap(d, s, maxw, size=20, minsize=12, maxlines=2, bold=True):
    words=str(s or "").split()
    for n in range(size,minsize-1,-1):
        f=font(n,bold); lines=[]; cur=""
        for word in words:
            test=(cur+" "+word).strip()
            if d.textbbox((0,0),test,font=f)[2] <= maxw: cur=test
            else:
                if cur: lines.append(cur)
                cur=word
        if cur: lines.append(cur)
        if len(lines)<=maxlines: return lines,f
    f=font(minsize,bold); lines=[]; cur=""
    for word in words:
        test=(cur+" "+word).strip()
        if d.textbbox((0,0),test,font=f)[2] <= maxw: cur=test
        else:
            if cur: lines.append(cur)
            cur=word
    if cur: lines.append(cur)
    lines=lines[:maxlines]
    if len(lines)==maxlines and lines:
        while lines[-1] and d.textbbox((0,0),lines[-1]+"…",font=f)[2]>maxw: lines[-1]=lines[-1][:-1]
        lines[-1]=lines[-1].rstrip()+"…"
    return lines,f

def get_image(url, size):
    if not url: return None
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 TrustFolioCreative/8"})
    with urllib.request.urlopen(req,timeout=20) as r: raw=r.read()
    im=Image.open(io.BytesIO(raw)).convert("RGBA")
    im.thumbnail(size,Image.Resampling.LANCZOS)
    return im

def glow(im, box, color, blur=50):
    lay=Image.new("RGBA",im.size,(0,0,0,0)); ImageDraw.Draw(lay).ellipse(box,fill=color)
    im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(blur)))

def gradient_bg():
    im=Image.new("RGBA",(W,H))
    px=im.load()
    top=(248,253,255); bottom=(189,226,255)
    for y in range(H):
        t=y/(H-1)
        c=tuple(int(top[i]*(1-t)+bottom[i]*t) for i in range(3))
        for x in range(W): px[x,y]=(*c,255)
    # luminous central wash and electric side glows
    glow(im,(-150,130,440,790),(35,139,255,110),80)
    glow(im,(680,80,1180,720),(119,53,255,100),85)
    glow(im,(170,590,900,1350),(255,255,255,205),100)
    glow(im,(-180,1150,350,1560),(45,208,255,90),60)
    d=ImageDraw.Draw(im)
    # diagonal light beams
    d.polygon([(0,260),(0,80),(360,0),(235,0)],fill=(255,255,255,95))
    d.polygon([(1024,190),(1024,0),(840,0),(760,330)],fill=(255,255,255,100))
    d.polygon([(0,860),(0,700),(190,950),(260,1180)],fill=(32,105,255,45))
    d.polygon([(1024,620),(930,720),(1024,850)],fill=(94,38,242,45))
    # subtle sparkles
    for x,y,r in [(42,436,4),(987,710,4),(71,870,3),(949,920,3),(890,75,3),(325,405,3)]:
        d.ellipse((x-r,y-r,x+r,y+r),fill=(255,255,255,240))
    return im

def load_logo():
    try: return get_image("https://www.trustfolio.in/logo.png",(108,108))
    except Exception: return None

def product_image(im, url, box, contain=True):
    x1,y1,x2,y2=box
    try: p=get_image(url,(x2-x1,y2-y1))
    except Exception: p=None
    if p:
        im.alpha_composite(p,(x1+(x2-x1-p.width)//2,y1+(y2-y1-p.height)//2))
    return p is not None

def price_pill(d, box, value):
    x1,y1,x2,y2=box
    d.rounded_rectangle(box,radius=12,fill=YELLOW,outline=(255,246,143),width=2)
    s=str(value or "")
    f=text_fit(d,s,x2-x1-14,32,19,True)
    d.text(((x1+x2)//2,(y1+y2)//2),s,font=f,fill=INK,anchor="mm",stroke_width=0)

def money(v):
    try: return "₹"+format(float(v),",.0f")
    except Exception: return str(v or "")

def product_name(p): return str(p.get("name") or p.get("full_title") or p.get("title") or "Product")

def specs_for(p, limit=3):
    raw=p.get("raw_specifications") or p.get("specifications") or {}
    if isinstance(raw,dict):
        vals=[]
        priority=("display","screen","battery","ram","storage","connectivity","resolution","capacity","power","bluetooth","calling","sp02","heart")
        pairs=list(raw.items())
        pairs.sort(key=lambda kv: next((i for i,k in enumerate(priority) if k in str(kv[0]).lower()),999))
        for k,v in pairs:
            if v not in (None,"","N/A","Unknown"):
                val=f"{k}: {v}".strip()
                if len(val)<44: vals.append(val)
            if len(vals)>=limit: break
        return vals
    if isinstance(raw,list): return [str(x) for x in raw[:limit]]
    ks=p.get("key_specs") or []
    return [str(x) for x in ks[:limit]] if isinstance(ks,list) else []

def draw_rank(d,cx,cy,n,best=False):
    r=42 if best else 25
    fill=YELLOW if best else (247,250,255)
    outline=(255,255,255) if best else (135,143,165)
    d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=fill,outline=outline,width=4)
    d.text((cx,cy-2),("#1" if best else str(n)),font=font(32 if best else 26,True),fill=INK,anchor="mm")
    if best: d.text((cx,cy+22),"Best Value",font=font(12,True),fill=INK,anchor="mm")

def top_product(im,p,rank,box,featured=False):
    d=ImageDraw.Draw(im); x1,y1,x2,y2=box
    # podium gradient body and glossy oval top
    base_y=y2-4
    d.rounded_rectangle((x1,base_y-85,x2,base_y+3),radius=20,fill=(4,45,117,255),outline=(82,206,255,255),width=3)
    podium_top = 164 if featured else 104
    d.rounded_rectangle((x1,base_y-podium_top+20,x2,base_y+3),radius=20,fill=(4,45,117,255),outline=(82,206,255,255),width=3)
    d.ellipse((x1,base_y-podium_top,x2,base_y-podium_top+52),fill=(28,142,247,255),outline=(188,246,255,255),width=4)
    d.ellipse((x1+12,base_y-podium_top+7,x2-12,base_y-podium_top+36),fill=(65,190,255,255),outline=(255,255,255,200),width=2)
    if featured:
        draw_rank(d,(x1+x2)//2,y1+30,rank,True)
        product_image(im,p.get("image_url",""),(x1+15,y1+58,x2-15,y2-176))
        d=ImageDraw.Draw(im)
        name=product_name(p)
        lines,f=wrap(d,name,x2-x1-26,25,16,2,True)
        yy=y2-184
        for line in lines:
            d.text(((x1+x2)//2,yy),line,font=f,fill=WHITE,anchor="mt",stroke_width=1,stroke_fill=(0,30,75)); yy+=f.size+1
        specs=specs_for(p,2)
        if specs:
            d.text(((x1+x2)//2,y2-119)," • ".join(specs)[:64],font=text_fit(d," • ".join(specs)[:64],x2-x1-24,13,10,False),fill=(231,244,255),anchor="mt")
        price_pill(d,(x1+45,y2-74,x2-45,y2-24),p.get("price_display") or money(p.get("price_inr",p.get("price"))))
        retailer=str(p.get("retailer") or p.get("platform") or "").strip()
        if retailer: d.text(((x1+x2)//2,y2-15),retailer,font=font(21,True),fill=WHITE,anchor="mb")
    else:
        draw_rank(d,x1+27,y1+22,rank,False)
        product_image(im,p.get("image_url",""),(x1+10,y1+48,x2-10,y2-150))
        d=ImageDraw.Draw(im)
        lines,f=wrap(d,product_name(p),x2-x1-20,20,13,2,True)
        yy=y2-139
        for line in lines:
            d.text(((x1+x2)//2,yy),line,font=f,fill=WHITE,anchor="mt",stroke_width=1,stroke_fill=(0,25,70)); yy+=f.size
        price_pill(d,(x1+18,y2-70,x2-18,y2-29),p.get("price_display") or money(p.get("price_inr",p.get("price"))))
        retailer=str(p.get("retailer") or p.get("platform") or "").strip()
        if retailer: d.text(((x1+x2)//2,y2-16),retailer,font=font(17,True),fill=WHITE,anchor="mb")

def draw_benefits(d):
    rows=[("◆","Compare Prices","Across Top Websites",BLUE),("✓","Latest Models","& Real Prices",(0,180,155)),("★","Top Rated Picks","Based on reviews",PURPLE),("ϟ","Best Deals","in Your Budget",(0,117,238))]
    y=161
    for ico,a,b,c in rows:
        d.rounded_rectangle((770,y,1000,y+59),radius=30,fill=(255,255,255,232),outline=(255,255,255,255),width=2)
        d.ellipse((778,y+5,827,y+54),fill=c)
        d.text((802,y+29),ico,font=font(24,True),fill=WHITE,anchor="mm")
        d.text((839,y+14),a,font=text_fit(d,a,150,16,12,True),fill=INK)
        d.text((839,y+36),b,font=text_fit(d,b,150,13,10,False),fill=(65,76,99))

def headline_parts(title, category):
    title=str(title or "").strip()
    m=re.match(r"^(.*?)\s+Under\s+(₹\s*[\d,]+)\s*$",title,re.I)
    if m: return m.group(1).strip(),m.group(2).replace(" ","")
    cat=str(category or "Products").replace("-"," ").title()
    return "Best "+cat, None

def render(ad):
    OUT.mkdir(parents=True,exist_ok=True)
    im=gradient_bg(); d=ImageDraw.Draw(im)
    # fixed TrustFolio header
    logo=load_logo()
    if logo: im.alpha_composite(logo,(42,24))
    else:
        d.rounded_rectangle((44,26,149,130),radius=26,fill=PURPLE)
        d.text((96,77),"T",font=font(70,True),fill=WHITE,anchor="mm")
    d.text((163,36),"TrustFolio",font=font(47,True),fill=INK)
    d.text((166,91),"Compare • Save • Shop Smart",font=font(20),fill=INK)
    d.text((1004,25),"Smart",font=font(24,True,True),fill=NAVY,anchor="ra")
    d.text((1004,53),"Shopping",font=font(23,True,True),fill=NAVY,anchor="ra")
    d.text((1004,81),"Smarter You",font=font(21,True,True),fill=NAVY,anchor="ra")
    d.line((879,126,990,101),fill=(0,83,220),width=5)
    # colorful decorative shards around headline
    for pts,col in [([(88,161),(123,174),(98,188)],PURPLE),([(141,150),(166,181),(148,188)],(255,182,25)), ([(550,45),(582,51),(566,86)],YELLOW), ([(660,44),(711,45),(675,81)],PURPLE), ([(749,95),(774,80),(767,111)],YELLOW)]:
        d.polygon(pts,fill=col)
    left,budget=headline_parts((ad.get("metadata") or {}).get("campaign_title"),(ad.get("metadata") or {}).get("campaign_category"))
    # title ribbon with layered shadow, angled ends
    d.polygon([(86,192),(708,83),(758,109),(750,228),(112,335),(79,300)],fill=(53,17,131))
    d.polygon([(91,177),(703,78),(754,104),(744,211),(108,315),(78,286)],fill=PURPLE,outline=(159,112,255))
    lines,f=wrap(d,left,600,60,31,2,True)
    yy=126 if len(lines)==1 else 105
    for line in lines:
        d.text((115,yy),line,font=f,fill=WHITE,stroke_width=4,stroke_fill=(41,16,91)); yy+=f.size+2
    if budget:
        budget_text="Under "+budget
    else:
        budget_text="Top 5 Picks"
    bf=text_fit(d,budget_text,620,68,35,True)
    d.text((110,260),budget_text,font=bf,fill=YELLOW,stroke_width=4,stroke_fill=(94,49,0))
    # yellow brush-stroke subtitle
    d.polygon([(181,352),(707,287),(739,315),(716,354),(189,414),(168,396)],fill=YELLOW)
    subtitle=str((ad.get("metadata") or {}).get("subtitle") or "Top 5 Picks for Style, Fitness & Value")
    sf=text_fit(d,subtitle,520,28,17,True)
    d.text((207,350),subtitle,font=sf,fill=INK,stroke_width=0)
    draw_benefits(d)
    # products: preserve the legacy payload order mapping [left,right,bottom-left,bottom-right,featured]
    products=ad.get("products") or []
    if len(products)<5: raise ValueError(f"{ad.get('source_ad_id')}: requires 5 products, got {len(products)}")
    leftp,rightp,bottomleft,bottomright,featured=products[:5]
    # Top three large podiums
    top_product(im,leftp,2,(57,431,355,824),False)
    top_product(im,featured,1,(332,407,704,920),True)
    top_product(im,rightp,3,(668,431,966,824),False)
    # Lower two products: photo left/right and dynamic copy blocks
    d=ImageDraw.Draw(im)
    draw_rank(d,58,971,4,False)
    product_image(im,bottomleft.get("image_url",""),(35,986,258,1250))
    d=ImageDraw.Draw(im)
    lines,f=wrap(d,product_name(bottomleft),335,20,14,2,True)
    yy=1055
    for line in lines: d.text((260,yy),line,font=f,fill=NAVY); yy+=f.size+2
    d.text((260,yy+3),str(bottomleft.get("retailer") or ""),font=font(17,True),fill=(0,97,225))
    price_pill(d,(260,yy+26,407,yy+70),bottomleft.get("price_display") or money(bottomleft.get("price_inr",bottomleft.get("price"))))
    spec=specs_for(bottomleft,3)
    for i,s in enumerate(spec):
        d.text((260,yy+80+i*25),"▪ "+s[:34],font=text_fit(d,"▪ "+s[:34],350,14,11,False),fill=INK)
    draw_rank(d,958,971,5,False)
    product_image(im,bottomright.get("image_url",""),(677,986,862,1250))
    d=ImageDraw.Draw(im)
    lines,f=wrap(d,product_name(bottomright),155,18,12,3,True)
    yy=1024
    for line in lines: d.text((869,yy),line,font=f,fill=NAVY); yy+=f.size+1
    price_pill(d,(871,yy+5,1000,yy+49),bottomright.get("price_display") or money(bottomright.get("price_inr",bottomright.get("price"))))
    d.text((935,yy+56),str(bottomright.get("retailer") or ""),font=font(16,True),fill=INK,anchor="mt")
    for i,s in enumerate(specs_for(bottomright,3)):
        d.text((871,yy+82+i*27),"▪ "+s[:22],font=text_fit(d,"▪ "+s[:22],132,12,9,False),fill=INK)
    # footer trust strip
    d.rounded_rectangle((15,1316,1009,1405),radius=38,fill=NAVY)
    foot=[("₹","Compare Prices","Across Top Websites",(242,65,177)),("⬟","Find the Best Deals","in Your Budget",YELLOW),("✓","Latest Products","Always Updated",(0,218,196)),("★","No Login","No Ads • No Data Collection",(140,69,250))]
    xs=[55,302,547,793]
    for (ico,a,b,c),x in zip(foot,xs):
        d.ellipse((x,1337,x+48,1385),fill=c)
        d.text((x+24,1361),ico,font=font(23,True),fill=INK if c==YELLOW else WHITE,anchor="mm")
        d.text((x+59,1343),a,font=text_fit(d,a,160,15,11,True),fill=WHITE)
        d.text((x+59,1366),b,font=text_fit(d,b,160,12,9,False),fill=(222,234,255))
    # CTA bar + pointer/click rays
    d.rounded_rectangle((41,1414,603,1490),radius=38,fill=YELLOW,outline=(255,245,143),width=3)
    d.ellipse((61,1433,99,1471),outline=INK,width=5); d.line((92,1465,107,1480),fill=INK,width=5)
    d.text((122,1452),"Compare Now on TrustFolio  →",font=text_fit(d,"Compare Now on TrustFolio  →",455,27,18,True),fill=INK,anchor="lm")
    d.text((986,1424),"🌐  trustfolio.in",font=font(26,True),fill=NAVY,anchor="ra")
    d.text((986,1467),"Smart Shopping for a Smarter You",font=font(13),fill=(72,92,126),anchor="ra")
    # pointer at CTA edge
    d.polygon([(574,1458),(615,1495),(606,1494),(610,1512),(598,1516),(592,1499),(584,1507)],fill=WHITE,outline=INK)
    d.line((612,1443,624,1431),fill=YELLOW,width=5); d.line((619,1452,635,1450),fill=YELLOW,width=5)
    # Export large and high quality: 2x upscale from fixed composition
    rgb=Image.new("RGB",im.size,WHITE); rgb.paste(im,mask=im.getchannel("A"))
    adid=ad.get("source_ad_id") or "trustfolio"
    path=OUT/f"{adid}_reference_v8_1024x1536.png"
    rgb.save(path,format="PNG",optimize=True)
    print("TRUSTFOLIO REFERENCE RENDERER V8")
    print("AD ID   :",adid)
    print("CATEGORY:",(ad.get("metadata") or {}).get("campaign_category"))
    print("OUTPUT  :",path)
    print("QUALITY : native 1024x1536 PNG; inspect one ad before batch publishing")
    return path

def main():
    path=Path(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_INPUT
    adid=sys.argv[2] if len(sys.argv)>2 else "tf-aa5900f0c166"
    data=json.loads(path.read_text(encoding="utf-8"))
    ads=data.get("ads") or []
    ad=next((x for x in ads if x.get("source_ad_id")==adid),None)
    if ad is None: raise SystemExit(f"Ad ID not found: {adid}")
    render(ad)

if __name__=="__main__": main()
