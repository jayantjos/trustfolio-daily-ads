#!/usr/bin/env python3
"""Non-generative product-photo collage for TrustFolio social publication.

Draws only deterministic Pillow geometric UI, text and *unmodified real
catalog photos* returned by the public live TrustFolio website Top-5 API.
Never uses AI master artwork, diffusion, or text-to-image generation.
Fails closed on incomplete product rankings or unavailable source images.
"""
from pathlib import Path
import io, json, math, re, hashlib, sys
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from site_top5_ads_v1 import build_site_ads_payload
from campaign_link_contract_v1 import check_ranked_site_snapshot

W,H=1080,1350
CANDIDATES=[("smart-phones",15000),("ceiling-fans",4000),("laptops",55000)]
FONT_BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PLAY="https://play.google.com/store/apps/details?id=com.trustfolio.app"


def font(size,bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG,int(size))


def rgb_bg():
    import numpy as np
    y,x=np.mgrid[0:H,0:W].astype("float32")
    glow=np.clip(1-np.sqrt(((x-540)/900)**2+((y-310)/750)**2),0,1)
    bottom=np.clip(y/H,0,1)
    out=np.empty((H,W,3),dtype=np.uint8)
    out[:,:,0]=np.clip(8+22*glow+1*bottom,0,255).astype(np.uint8)
    out[:,:,1]=np.clip(17+33*glow+11*bottom,0,255).astype(np.uint8)
    out[:,:,2]=np.clip(61+94*glow-10*bottom,0,255).astype(np.uint8)
    return Image.fromarray(out,"RGB")


def rounded_gradient(canvas, bbox, top, bottom, radius,outline=None):
    x0,y0,x1,y1=map(int,bbox)
    h=y1-y0;w=x1-x0
    stripe=Image.new("RGB",(w,h))
    pixels=stripe.load()
    for y in range(h):
        t=y/max(h-1,1)
        v=tuple(round(top[i]*(1-t)+bottom[i]*t) for i in range(3))
        for x in range(w):pixels[x,y]=v
    mask=Image.new("L",(w,h))
    m=ImageDraw.Draw(mask)
    m.rounded_rectangle((0,0,w-1,h-1),radius=radius,fill=255)
    canvas.paste(stripe,(x0,y0),mask)
    if outline:
        ImageDraw.Draw(canvas).rounded_rectangle((x0,y0,x1,y1),radius,outline=outline,width=3)


def right_fit(draw,x,y,text,maxw,minsz=16,maxsz=33,fill="white",bold=True):
    text=str(text)
    for z in range(maxsz,minsz-1,-1):
        ff=font(z,bold)
        if draw.textbbox((0,0),text,font=ff)[2] <= maxw:
            draw.text((x,y),text,font=ff,fill=fill,stroke_width=0)
            return z
    ff=font(minsz,bold)
    while text and draw.textbbox((0,0),text+"…",font=ff)[2]>maxw:
        text=text[:-1]
    draw.text((x,y),text+"…",font=ff,fill=fill)
    return minsz


def clipped_lines(draw,text,sz,maxw,count=2,bold=True):
    text=re.sub(r"\s+"," ",str(text or "")).strip()
    words=text.split(" ")
    lines=[];line=""
    f=font(sz,bold)
    for word in words:
        test=(line+" "+word).strip()
        if draw.textbbox((0,0),test,font=f)[2]<=maxw:
            line=test
        else:
            if line:lines.append(line)
            line=word
    if line:lines.append(line)
    if len(lines)>count:
        lines=lines[:count]
        last=lines[-1].strip()
        while last and draw.textbbox((0,0),last+"…",font=f)[2]>maxw:last=last[:-1].strip()
        lines[-1]=last+"…"
    return lines


def fetch_photo(url, opener=urlopen):
    from urllib.parse import urlsplit
    loc=urlsplit(str(url))
    if loc.scheme!="https" or not loc.hostname:
        raise ValueError("Product image requires source HTTPS URL")
    req=Request(url,headers={"User-Agent":"TrustFolioActualProductPhotos/1.0"})
    with opener(req,timeout=23) as res:
        if res.status!=200:raise ValueError("Product source image not accessible")
        data=res.read(6_000_001)
    if len(data)>6_000_000 or not data:raise ValueError("Product source image too large or absent")
    photo=Image.open(io.BytesIO(data))
    photo.load()
    if photo.width<120 or photo.height<120:
        raise ValueError("Product photograph has inadequate resolution")
    return photo.convert("RGB")


def photo_inside(canvas,photo,bbox):
    x0,y0,x1,y1=map(int,bbox)
    width=x1-x0;height=y1-y0
    # Neutral white product-photo panel and source image: no synthetic products.
    d=ImageDraw.Draw(canvas)
    d.rounded_rectangle((x0,y0,x1,y1),radius=20,fill=(245,249,255))
    inset=9
    fitted=ImageOps.contain(photo,(width-2*inset,height-2*inset),Image.Resampling.LANCZOS)
    canvas.paste(fitted,(x0+(width-fitted.width)//2,y0+(height-fitted.height)//2))


def podium(canvas,rank,product,photo,box):
    x,y,w,h=box
    draw=ImageDraw.Draw(canvas)
    rounded_gradient(canvas,(x,y,x+w,y+h),(18,92,207),(4,18,72),25,outline=(81,205,255))
    draw.ellipse((x+12,y-13,x+w-12,y+34),fill=(24,169,250),outline=(135,239,255),width=4)
    draw.ellipse((x+25,y-9,x+w-25,y+20),fill=(57,214,255))
    draw.ellipse((x+14,y+34,x+w-14,y+51),outline=(77,158,255),width=3)
    draw.ellipse((x+12,y-37,x+76,y+27),fill=(255,216,40),outline=(255,255,211),width=4)
    draw.text((x+26,y-28),f"#{rank}",font=font(29,True),fill=(28,23,79))
    if rank==1:
        draw.text((x+w-59,y-45),"★",font=font(42,True),fill=(255,207,62))
    padding=18
    img_h=205 if rank==1 else 168
    photo_inside(canvas,photo,(x+padding,y+34,x+w-padding,y+34+img_h))
    draw=ImageDraw.Draw(canvas)
    max_width=w-32
    name_y=y+34+img_h+14
    for idx,line in enumerate(clipped_lines(draw,product["title"],18 if rank==1 else 16,max_width,2)):
        boxwidth=draw.textbbox((0,0),line,font=font(18 if rank==1 else 16,True))[2]
        draw.text((x+(w-boxwidth)//2,name_y+idx*24),line,font=font(18 if rank==1 else 16,True),fill=(255,255,255))
    price_y=y+h-105
    rounded_gradient(canvas,(x+40,price_y,x+w-40,price_y+51),(255,252,102),(255,201,33),14)
    amount=f"₹{product['price_inr']:,.0f}"
    width=draw.textbbox((0,0),amount,font=font(31,True))[2]
    draw.text((x+(w-width)//2,price_y+5),amount,font=font(31,True),fill=(5,22,57))
    merchant=str(product.get("platform") or "Retail listing")
    right_fit(draw,x+26,y+h-43,merchant.title(),max_width-20,14,22,(212,237,255))
    # Only identity and price: product specs deliberately omitted until scraper QA.
    return


def bottom_product(canvas,rank,product,photo,box):
    x,y,w,h=box
    rounded_gradient(canvas,(x,y,x+w,y+h),(20,77,174),(9,29,83),20,(91,196,255))
    d=ImageDraw.Draw(canvas)
    d.ellipse((x+6,y-17,x+57,y+36),fill=(255,220,47),outline=(255,250,200),width=3)
    d.text((x+13,y-11),str(rank),font=font(29,True),fill=(12,21,79))
    photo_inside(canvas,photo,(x+15,y+38,x+183,y+h-23))
    maxw=w-210
    for n,line in enumerate(clipped_lines(d,product["title"],18,maxw,3)):
        d.text((x+202,y+39+n*27),line,font=font(18,True),fill=(255,255,255))
    price=f"₹{product['price_inr']:,.0f}"
    rounded_gradient(canvas,(x+203,y+h-105,x+w-16,y+h-51),(255,253,115),(255,203,31),12)
    d=ImageDraw.Draw(canvas)
    d.text((x+216,y+h-100),price,font=font(31,True),fill=(4,24,62))
    right_fit(d,x+206,y+h-38,str(product.get("platform") or "Retailer").title(),maxw-12,12,18,(194,228,255))
    

def render(product_data, category, budget, output):
    products=product_data["products"]
    if len(products)!=5 or [p["rank"] for p in products]!=[1,2,3,4,5]:
        raise ValueError("Exact ranked website Top Five required")
    if len({p["product_id"] for p in products})!=5:
        raise ValueError("Duplicate product IDs in website top five")
    imgs=[fetch_photo(p["image_url"]) for p in products]
    canvas=rgb_bg()
    d=ImageDraw.Draw(canvas)
    # Geometric starburst/speed lines; generated deterministically via Pillow.
    for i in range(22):
        x1=int((i*227)%W); y1=int((i*89)%500)
        d.line((x1,y1,x1+70,y1+28),fill=(36,92,174),width=2)
    d.rounded_rectangle((37,27,112,102),radius=20,fill=(68,84,225),outline=(118,230,252),width=4)
    d.text((49,31),"T",font=font(53,True),fill=(255,250,255))
    d.text((113,20),"Trust",font=font(51,True),fill=(255,255,255))
    d.text((261,20),"Folio",font=font(51,True),fill=(76,183,255))
    d.text((120,83),"Compare • Save • Shop Smart",font=font(21),fill=(194,213,241))
    d.rounded_rectangle((733,37,1047,92),radius=27,fill=(23,96,174),outline=(70,208,244),width=3)
    d.text((750,52),"LIVE WEBSITE TOP 5",font=font(19,True),fill=(238,249,255))
    rounded_gradient(canvas,(48,145,1032,335),(93,28,188),(22,19,107),32,outline=(142,96,250))
    d=ImageDraw.Draw(canvas)
    category_label={"smart-phones":"Smartphones","ceiling-fans":"Ceiling Fans","laptops":"Laptops"}.get(category,category.replace("-"," ").title())
    d.text((86,155),"BEST "+category_label.upper(),font=font(52,True),fill=(255,255,255))
    d.text((88,222),f"UNDER ₹{budget:,}",font=font(63,True),fill=(255,226,32))
    d.text((90,304),"Top 5 ranked products • Genuine website listings",font=font(17,True),fill=(255,255,255))
    for i,(emoji,text) in enumerate([("✓","Actual website ranking"),("✓","No invented products"),("✓","Prices may change")]):
        x=51+i*340
        d.rounded_rectangle((x,361,x+315,401),radius=18,fill=(16,73,141),outline=(78,153,226),width=2)
        d.text((x+14,368),emoji,font=font(19,True),fill=(80,253,213))
        d.text((x+43,373),text,font=font(14,True),fill=(223,244,255))
    # Stage: #1 center with taller visible podium, #2/#3 sides.
    podium(canvas,2,products[1],imgs[1],(35,477,305,425))
    podium(canvas,1,products[0],imgs[0],(382,444,316,459))
    podium(canvas,3,products[2],imgs[2],(740,477,305,425))
    bottom_product(canvas,4,products[3],imgs[3],(37,938,492,248))
    bottom_product(canvas,5,products[4],imgs[4],(549,938,493,248))
    d=ImageDraw.Draw(canvas)
    d.rounded_rectangle((31,1214,1049,1330),radius=25,fill=(3,15,52),outline=(48,104,192),width=3)
    rounded_gradient(canvas,(54,1234,737,1299),(255,244,92),(255,199,32),25)
    d=ImageDraw.Draw(canvas)
    d.text((75,1249),"COMPARE NOW ON TRUSTFOLIO  →",font=font(26,True),fill=(8,24,57))
    d.text((761,1236),"trustfolio.in",font=font(27,True),fill=(229,245,255))
    d.text((764,1272),"Website + App: link in bio",font=font(15),fill=(163,208,242))
    out=Path(output)
    out.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(out,"JPEG",quality=94,optimize=True,subsampling=0)
    with Image.open(out) as check:
        assert check.size==(W,H)
    return out


def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--output-dir",required=True)
    args=ap.parse_args()
    failures=[]
    for cat,budget in CANDIDATES:
        try:
            result=build_site_ads_payload(cat,budget)
            ad=result["ads"][0]
            # Source and rank must be the public website API, never local guesses.
            if ad.get("ranking_source")!="live_trustfolio_website_api":
                raise ValueError("Unknown product ranking provenance")
            if check_ranked_site_snapshot(ad,ad["website_snapshot"]):
                raise ValueError("Website ranking differs from ad")
            output_dir=Path(args.output_dir)
            image=render(ad,cat,budget,output_dir/"trustfolio-non-generative-catalog-ad.jpg")
            landing=f"https://www.trustfolio.in/category/{cat}/products?"+urlencode({"budget":budget})
            hub="https://media.trustfolio.in/trustfolio-links/index.html?"+urlencode({"category":cat,"budget":budget})
            display={"smart-phones":"Smartphones","ceiling-fans":"Ceiling Fans","laptops":"Laptops"}[cat]
            caption=(f"✨ Top 5 {display} Under ₹{budget:,}! 💜\n\n"
              "TrustFolio ki live website ranking se chune gaye 5 real products ko compare karo. "
              "Latest listed prices aur shopping options dekho.\n\n"
              f"🔎 ₹{budget:,} filtered results:\n{landing}\n\n"
              f"🔗 Website + App quick links:\n{hub}\n\n"
              f"📲 Android app on Google Play:\n{PLAY}\n\n"
              "Instagram feed URLs tappable nahi hote. Website/App ke liye profile ka link use karo. "
              "Prices, stock aur ranking badal sakti hain; buying se pehle latest details verify karo.\n\n"
              "#TrustFolio #SmartShopping #ProductComparison #Top5 #BudgetShopping #BestDealsIndia")
            report={
                "status":"qa_passed_not_published","generated_style":"algorithmic_graphics_no_ai_art",
                "source_product_images":"original_website_product_photographs",
                "rank_source":"live_trustfolio_website_api",
                "category":cat,"budget_inr":budget,"image_file":image.name,
                "image_dimensions":[W,H],"product_ids_by_rank":[p["product_id"] for p in ad["products"]],
                "product_names_by_rank":[p["title"] for p in ad["products"]],
                "product_prices_by_rank":[p["price_inr"] for p in ad["products"]],
                "ranking_observed_at":result.get("generated_at"),"landing_url":landing,
                "app_url":PLAY,"bio_url":hub,"instagram_target":"trustfolio3",
                "instagram_ai_flag":False,
                "caption":caption
            }
            (output_dir/"post.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
            print("NON_GENERATIVE_VISUAL_QA_PASSED="+cat)
            print("LIVE_RANKED_IDS="+",".join(report["product_ids_by_rank"]))
            print("IMAGE_JPG="+str(image))
            return
        except Exception as e:
            failures.append((cat,type(e).__name__,str(e)[:140]))
            print("CANDIDATE_SKIPPED="+cat+";"+type(e).__name__,file=sys.stderr)
    raise SystemExit("No eligible real five-product category, refuse to post: "+str(failures))


if __name__=="__main__":
    main()
