#!/usr/bin/env python3
"""TrustFolio master-template renderer V2: fixed artwork + dynamic product fields."""
import io, json, re, sys, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

BASE = Path.home() / "new_scraper"
ADS = BASE / "ads"
ASSET = ADS / "assets" / "trustfolio_reference_master_v1.jpg"
DEFAULT_INPUT = ADS / "trustfolio_infographic_payload_v1.json"
OUT = ADS / "generated_creatives" / "feed"
W, H = 1024, 1536
NAVY=(4,20,56); DEEP=(3,25,76); CYAN=(24,211,255); PURPLE=(83,20,220)
YELLOW=(255,218,25); WHITE=(255,255,255); INK=(8,21,48)

def font(size, bold=False, italic=False):
    candidates=[]
    if italic: candidates.append("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf")
    candidates += [
      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
      "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    for p in candidates:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def fit(d, value, maxw, size, minsize=10, bold=True):
    value=str(value or "")
    for n in range(size,minsize-1,-1):
        f=font(n,bold)
        if d.textbbox((0,0),value,font=f)[2] <= maxw: return f
    return font(minsize,bold)

def wrap(d, value, maxw, size=18, minsize=11, maxlines=2, bold=True):
    words=str(value or "").split()
    for n in range(size,minsize-1,-1):
        f=font(n,bold); lines=[]; line=""
        for word in words:
            test=(line+" "+word).strip()
            if d.textbbox((0,0),test,font=f)[2] <= maxw: line=test
            else:
                if line: lines.append(line)
                line=word
        if line: lines.append(line)
        if len(lines)<=maxlines: return lines,f
    f=font(minsize,bold); lines=[]; line=""
    for word in words:
        test=(line+" "+word).strip()
        if d.textbbox((0,0),test,font=f)[2] <= maxw: line=test
        else:
            if line: lines.append(line)
            line=word
    if line: lines.append(line)
    lines=lines[:maxlines]
    if lines and len(lines)==maxlines:
        last=lines[-1]
        while last and d.textbbox((0,0),last+"…",font=f)[2]>maxw: last=last[:-1]
        lines[-1]=last.rstrip()+"…"
    return lines,f

def fetch_image(source, size):
    if not source: return None
    try:
        if str(source).startswith(("http://","https://")):
            req=urllib.request.Request(str(source),headers={"User-Agent":"Mozilla/5.0 TrustFolioCreative/2"})
            with urllib.request.urlopen(req,timeout=18) as r: data=r.read()
            img=Image.open(io.BytesIO(data)).convert("RGBA")
        else:
            img=Image.open(str(source)).convert("RGBA")
        # Product feeds often contain a plain white studio background. Remove only
        # near-pure white pixels so straps and pale product details remain visible.
        px=img.load()
        for yy in range(img.height):
            for xx in range(img.width):
                rr,gg,bb,aa=px[xx,yy]
                if rr >= 249 and gg >= 249 and bb >= 249 and max(rr,gg,bb)-min(rr,gg,bb) <= 7:
                    px[xx,yy]=(rr,gg,bb,0)
        return ImageOps.contain(img,size,method=Image.Resampling.LANCZOS)
    except Exception as exc:
        print(f"WARNING: image unavailable ({str(source)[:70]}): {exc}")
        return None

def gradient_panel(im, box, top=(7,71,158), bottom=(2,15,53), radius=18, outline=CYAN, width=3):
    x1,y1,x2,y2=box; h=y2-y1
    grad=Image.new("RGBA",(x2-x1,h)); px=grad.load()
    for y in range(h):
        t=y/max(1,h-1); c=tuple(round(top[i]*(1-t)+bottom[i]*t) for i in range(3))
        for x in range(x2-x1): px[x,y]=(*c,255)
    mask=Image.new("L",grad.size,0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,grad.width-1,grad.height-1),radius=radius,fill=255)
    im.paste(grad,(x1,y1),mask)
    ImageDraw.Draw(im).rounded_rectangle(box,radius=radius,outline=outline,width=width)

def gradient_polygon(im, points, top=(94,25,235), bottom=(37,8,93)):
    mask=Image.new("L",(W,H),0); ImageDraw.Draw(mask).polygon(points,fill=255)
    grad=Image.new("RGBA",(W,H)); px=grad.load()
    ymin=max(0,min(p[1] for p in points)); ymax=min(H-1,max(p[1] for p in points))
    for y in range(ymin,ymax+1):
        t=(y-ymin)/max(1,ymax-ymin); c=tuple(round(top[i]*(1-t)+bottom[i]*t) for i in range(3))
        for x in range(W): px[x,y]=(*c,255)
    im.paste(grad,(0,0),mask)
    ImageDraw.Draw(im).line(points+[points[0]],fill=(171,94,255),width=3,joint="curve")

def name(p): return str(p.get("name") or p.get("full_title") or p.get("title") or "Product").strip()

def price(p):
    value=p.get("price_display")
    if value: return str(value)
    value=p.get("price_inr",p.get("price"))
    if value in (None,""): return ""
    try: return "₹"+format(float(value),",.0f")
    except (TypeError,ValueError): return str(value)

def specs(p, limit=3):
    raw=p.get("raw_specifications") or p.get("specifications") or {}
    if isinstance(raw,dict) and raw:
        priority=("display","screen","battery","bluetooth","calling","sp02","heart","sports","water","storage","ram","resolution","connectivity","capacity","power")
        pairs=list(raw.items())
        pairs.sort(key=lambda kv: next((i for i,k in enumerate(priority) if k in str(kv[0]).lower()),999))
        result=[]
        for k,v in pairs:
            if v not in (None,"","N/A","Unknown","unknown"):
                item=f"{str(k).strip()}: {str(v).strip()}"
                if len(item)<=48: result.append(item)
            if len(result)>=limit: break
        if result: return result
    raw=p.get("key_specs") or []
    if isinstance(raw,list): return [str(x) for x in raw if str(x).strip()][:limit]
    return []

def tagline(p):
    value=str(p.get("tagline") or "").strip()
    if value: return value
    return " • ".join(specs(p,2))

def image_slot(im, url, box):
    x1,y1,x2,y2=box
    img=fetch_image(url,(x2-x1,y2-y1))
    if img:
        im.alpha_composite(img,(x1+(x2-x1-img.width)//2,y1+(y2-y1-img.height)//2))
    else:
        ImageDraw.Draw(im).text(((x1+x2)//2,(y1+y2)//2),"Image unavailable",font=font(12),fill=(80,92,115),anchor="mm")

def price_badge(d, box, value, size=31):
    d.rounded_rectangle(box,radius=12,fill=YELLOW,outline=(255,246,143),width=2)
    value=value or "Price unavailable"
    d.text(((box[0]+box[2])//2,(box[1]+box[3])//2),value,font=fit(d,value,box[2]-box[0]-12,size,16,True),fill=INK,anchor="mm")

def retailer_pill(d, box, value):
    value=str(value or "").strip()
    if not value: return
    d.rounded_rectangle(box,radius=(box[3]-box[1])//2,fill=(219,243,255),outline=WHITE,width=1)
    d.text(((box[0]+box[2])//2,(box[1]+box[3])//2),value,font=fit(d,value,box[2]-box[0]-12,16,10,True),fill=(0,49,103),anchor="mm")

def draw_specs(d, items, box, small=False):
    x1,y1,x2,y2=box; items=items[:4 if not small else 3]
    if not items: return
    gap=5; cw=(x2-x1-gap*(len(items)-1))/len(items)
    for i,item in enumerate(items):
        x=x1+i*(cw+gap)
        if small:
            d.rounded_rectangle((x,y1+2,x+14,y1+17),radius=4,fill=NAVY)
            lines,f=wrap(d,item,cw-19,12,9,1,False); yy=y1
            for line in lines: d.text((x+19,yy+1),line,font=f,fill=INK); yy+=f.size
        else:
            cx=x+cw/2
            d.ellipse((cx-15,y1,cx+15,y1+30),outline=(229,248,255),width=2)
            d.text((cx,y1+15),["▣","♥","✓","↗"][i%4],font=font(14,True),fill=WHITE,anchor="mm")
            lines,f=wrap(d,item,cw,11,8,2,False); yy=y1+33
            for line in lines: d.text((cx,yy),line,font=f,fill=WHITE,anchor="mt"); yy+=f.size+1

def top_card(im,p,kind):
    if kind=="left":
        imgbox=(92,488,315,708); panel=(61,720,349,954); ty=728
        pb=(88,795,321,843); rb=(130,846,280,877); sb=(77,884,334,949)
    elif kind=="right":
        imgbox=(728,488,941,708); panel=(694,720,969,954); ty=728
        pb=(728,795,946,843); rb=(765,846,902,877); sb=(707,884,956,949)
    else:
        imgbox=(400,445,640,723); panel=(342,742,700,1024); ty=751
        pb=(391,831,652,880); rb=(443,884,600,914); sb=(369,921,675,1017)
    image_slot(im,p.get("image_url") or "",imgbox)
    gradient_panel(im,panel)
    d=ImageDraw.Draw(im); lines,f=wrap(d,name(p),panel[2]-panel[0]-24,22 if kind!="center" else 24,14,2,True)
    y=ty
    for line in lines: d.text(((panel[0]+panel[2])//2,y),line,font=f,fill=WHITE,anchor="mt",stroke_width=1,stroke_fill=(0,20,60)); y+=f.size+1
    high=tagline(p)
    if high: d.text(((panel[0]+panel[2])//2,y+1),high,font=fit(d,high,panel[2]-panel[0]-22,15 if kind=="center" else 14,10,False),fill=(233,244,255),anchor="mt")
    price_badge(d,pb,price(p),36 if kind=="center" else 32)
    retailer_pill(d,rb,p.get("retailer") or p.get("platform") or "")
    draw_specs(d,specs(p,4 if kind=="center" else 3),sb,False)

def bottom_card(im,p,side):
    if side=="left":
        card=(30,1042,495,1287); ib=(46,1054,260,1276); tx=274; tw=204
        pb=(273,1111,476,1153); rb=(305,1157,452,1183); sy=1191
    else:
        card=(547,1042,997,1287); ib=(562,1054,779,1276); tx=794; tw=188
        pb=(792,1111,980,1153); rb=(819,1157,957,1183); sy=1191
    d=ImageDraw.Draw(im); d.rounded_rectangle(card,radius=25,fill=(248,253,255),outline=(111,207,255),width=2)
    image_slot(im,p.get("image_url") or "",ib); d=ImageDraw.Draw(im)
    lines,f=wrap(d,name(p),tw,18,11,2,True); y=1054
    for line in lines: d.text((tx,y),line,font=f,fill=NAVY); y+=f.size+1
    high=tagline(p)
    if high:
        lines,hf=wrap(d,high,tw,12,9,1,False); d.text((tx,y+1),lines[0],font=hf,fill=(35,68,112))
    price_badge(d,pb,price(p),28); retailer_pill(d,rb,p.get("retailer") or p.get("platform") or "")
    y=sy
    for item in specs(p,3):
        d.rounded_rectangle((tx,y+2,tx+14,y+17),radius=4,fill=NAVY)
        lines,sf=wrap(d,item,tw-21,12,9,1,False); d.text((tx+20,y+1),lines[0],font=sf,fill=INK); y+=26

def parse_headline(meta):
    title=str(meta.get("campaign_title") or "").strip()
    category=str(meta.get("campaign_category") or "").strip()
    m=re.match(r"^(.*?)\s+Under\s+(₹\s*[\d,]+)\s*$",title,re.I)
    if m: return m.group(1).strip(), "Under "+m.group(2).replace(" ","")
    m=re.match(r"^(.*?)\s+(?:below|within)\s+(₹\s*[\d,]+)\s*$",title,re.I)
    if m: return m.group(1).strip(), "Under "+m.group(2).replace(" ","")
    return ("Best "+category if category else title), ""

def render(ad, asset_path=ASSET, output_dir=OUT):
    if not asset_path.exists(): raise FileNotFoundError(f"Master artwork missing: {asset_path}; install the V2 bundle asset.")
    im=Image.open(asset_path).convert("RGBA")
    if im.size!=(W,H): im=im.resize((W,H),Image.Resampling.LANCZOS)
    meta=ad.get("metadata") or {}; headline,budget=parse_headline(meta); products=ad.get("products") or []
    if len(products)<5: raise ValueError(f"{ad.get('source_ad_id')}: expected five products, got {len(products)}")
    for i,p in enumerate(products[:5],1):
        if p.get("price_inr") in (None,""): raise ValueError(f"Product #{i} has no source price; refusing to invent it.")
        if not (p.get("image_url") or "").strip(): print(f"WARNING: product #{i} has no image URL; blank slot will be shown.")
    # Replace only the text zone on top of the fixed artwork.
    poly=[(87,190),(700,83),(759,105),(753,267),(111,337),(79,306)]
    gradient_polygon(im,poly); d=ImageDraw.Draw(im)
    d.line([(93,187),(703,83),(753,104)],fill=(203,150,255),width=4)
    d.text((116,159),headline,font=fit(d,headline,610,58,28,True),fill=WHITE,stroke_width=4,stroke_fill=(31,8,74))
    if budget: d.text((127,218),budget,font=fit(d,budget,600,68,34,True),fill=YELLOW,stroke_width=4,stroke_fill=(91,42,0))
    d.polygon([(170,320),(703,282),(746,307),(718,351),(187,389),(161,368)],fill=YELLOW)
    d.polygon([(170,320),(703,282),(746,307)],fill=(255,236,73))
    subtitle=str(meta.get("subtitle") or "Top 5 Picks for Style, Fitness & Value")
    d.text((450,340),subtitle,font=fit(d,subtitle,530,26,14,True),fill=INK,anchor="mm")
    # Builder's product order is #2, #3, #4, #5, #1.
    leftp,rightp,bottomleft,bottomright,featured=products[:5]
    # Repaint the center #1 badge after the title ribbon so it is never covered.
    top_card(im,leftp,"left"); top_card(im,featured,"center"); top_card(im,rightp,"right")
    d=ImageDraw.Draw(im)
    d.ellipse((383,397,484,498),fill=(255,211,18),outline=(255,255,255),width=4)
    d.text((433,432),"#1",font=font(35,True),fill=INK,anchor="mm")
    d.text((433,458),"Best Value",font=font(12,True),fill=INK,anchor="mm")
    bottom_card(im,bottomleft,"left"); bottom_card(im,bottomright,"right")
    d=ImageDraw.Draw(im)
    d.ellipse((522,1055,585,1118),fill=(100,10,225),outline=(228,199,255),width=4)
    d.text((553,1086),"5",font=font(34,True),fill=WHITE,anchor="mm",stroke_width=1,stroke_fill=(54,0,120))
    output_dir.mkdir(parents=True,exist_ok=True)
    adid=str(ad.get("source_ad_id") or "trustfolio")
    out=output_dir/f"{adid}_master_v2b_1024x1536.png"
    rgb=Image.new("RGB",(W,H),WHITE); rgb.paste(im,mask=im.getchannel("A")); rgb.save(out,"PNG",optimize=True)
    print("TRUSTFOLIO MASTER TEMPLATE RENDERER V2")
    print("AD ID   :",adid); print("CATEGORY:",meta.get("campaign_category"))
    print("HEADLINE:",meta.get("campaign_title")); print("PRODUCTS:",len(products[:5]))
    print("OUTPUT  :",out); print("QA ONLY : inspect before publishing")
    return out

def main():
    input_path=Path(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_INPUT
    adid=sys.argv[2] if len(sys.argv)>2 else "tf-aa5900f0c166"
    payload=json.loads(input_path.read_text(encoding="utf-8"))
    ads=payload.get("ads") or []
    ad=next((x for x in ads if x.get("source_ad_id")==adid),None)
    if ad is None: raise SystemExit(f"Ad ID not found: {adid}")
    render(ad)

if __name__=="__main__": main()
