#!/usr/bin/env python3
"""Create a genuine 9:16 motion ad from a QA-approved TrustFolio Top-5 poster.

Uses only the actual website-ranked, approved PNG/JPEG source. This creates
video bytes (MP4/H.264), NOT a static-image upload, AI-generated replacement,
YouTube account post, synthetic product or unlicensed soundtrack.

Frames: title + full Top-5 image; Top-3 close-up; #4/#5 detail; CTA.
4 x 3s scenes, slow zoom, 1080x1920 @ 24fps; video remains QA-only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from automation.meta_graph_publish_v1 import validate_approved_manifest

W,H,FPS,SCENES,FRAMES_PER_SCENE=1080,1920,24,4,72
FPS_TOTAL=FPS*12
NAVY=(6,16,49)
PURPLE=(104,72,245)
YELLOW=(254,212,53)
WHITE=(246,247,255)
MUTED=(191,201,231)


def font(size,bold=False):
    candidates=(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for name in candidates:
        if Path(name).exists():
            return ImageFont.truetype(name,size)
    raise RuntimeError("Missing permitted system font (DejaVu Sans or Liberation Sans)")


def fit_lines(draw,text,face,width,max_lines=3):
    # No product names or ranks are ever hallucinated.
    words=str(text).split()
    rows=[]; line=""
    for word in words:
        candidate=(line+" "+word).strip()
        if line and draw.textbbox((0,0),candidate,font=face)[2]>width:
            rows.append(line);line=word
        else:
            line=candidate
    if line: rows.append(line)
    if len(rows)>max_lines:
        raise ValueError("Video headline does not fit; never clip text")
    return rows


def gradient():
    base=Image.new("RGB",(W,H))
    d=ImageDraw.Draw(base)
    for y in range(H):
        ratio=y/H
        tone=(int(6+24*ratio),int(16+8*ratio),int(49+55*ratio))
        d.line((0,y,W,y),fill=tone)
    glow=Image.new("RGBA",(W,H),(0,0,0,0))
    g=ImageDraw.Draw(glow)
    g.ellipse((260,-290,1150,700),fill=(120,70,241,80))
    g.ellipse((-400,1280,700,2260),fill=(12,141,233,45))
    return Image.alpha_composite(base.convert("RGBA"),
                                 glow.filter(ImageFilter.GaussianBlur(115))).convert("RGB")


def centered(draw,text,y,size,color,bold=False):
    face=font(size,bold)
    box=draw.textbbox((0,0),text,font=face)
    draw.text(((W-(box[2]-box[0]))//2,y),text,font=face,fill=color)


def text_block(draw,text,y,size,color,bold=False,max_lines=3):
    face=font(size,bold)
    lines=fit_lines(draw,text,face,W-140,max_lines)
    step=int(size*1.32)
    for index,line in enumerate(lines):
        centered(draw,line,y+index*step,size,color,bold)
    return y+len(lines)*step


def card(base,photo,bbox,*,crop=None):
    x,y,width,height=bbox
    current=photo.crop(crop) if crop else photo
    thumbnail=current.copy()
    thumbnail.thumbnail((width,height),Image.Resampling.LANCZOS)
    x=x+(width-thumbnail.width)//2
    y=y+(height-thumbnail.height)//2
    shade=Image.new("RGBA",(thumbnail.width+18,thumbnail.height+18),(0,0,0,0))
    d=ImageDraw.Draw(shade)
    d.rounded_rectangle((0,0,shade.width-1,shade.height-1),radius=28,
                        fill=(242,245,255,255))
    shade.alpha_composite(thumbnail.convert("RGBA"),(9,9))
    mask=Image.new("L",shade.size,0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,shade.width-1,shade.height-1),
                                           radius=28,fill=255)
    base.paste(shade.convert("RGB"),(x-9,y-9),mask)
    return y+thumbnail.height


def banner(draw,label,y):
    x1,x2=75,W-75
    draw.rounded_rectangle((x1,y,x2,y+78),radius=28,fill=YELLOW)
    f=font(34,True)
    box=draw.textbbox((0,0),label,font=f)
    assert box[2]-box[0]<=x2-x1-38
    draw.text(((W-(box[2]-box[0]))//2,y+17),label,font=f,fill=NAVY)


def make_scene(post,photo,number):
    img=gradient()
    d=ImageDraw.Draw(img)
    d.rounded_rectangle((69,66,1011,139),radius=30,fill=(56,41,149))
    centered(d,"TRUSTFOLIO  •  SMART SHOPPING",88,37,WHITE,True)
    category=post["category"].replace("-"," ").title()
    mode={"budget":"BEST UNDER BUDGET",
          "brand_budget":"SAME BRAND • REAL TOP 5",
          "comparison":"FIVE DIFFERENT TOP PICKS"}[post["mode"]]
    if number==0:
        centered(d,mode,187,37,YELLOW,True)
        heading=("Best "+(post["brand"]+" " if post["brand"] else "")
                 +category+" Under ₹"+format(post["budget_inr"],","))
        end=text_block(d,heading,248,48,WHITE,True,max_lines=2)
        card(img,photo,(70,max(400,end+10),940,1150))
        banner(d,"COMPARE ON TRUSTFOLIO  →",1683)
        centered(d,"Actual website-ranked picks  •  Prices may change",1813,27,MUTED)
    elif number==1:
        centered(d,"THE TOP 3 RANKED PICKS",235,45,YELLOW,True)
        centered(d,"Real website products • No fabricated rankings",325,28,MUTED)
        card(img,photo,(56,440,968,995),crop=(0,160,1080,1080))
        banner(d,"RANK #1  •  #2  •  #3",1562)
        centered(d,"See today's listed prices before buying",1711,32,WHITE)
    elif number==2:
        centered(d,"TWO MORE SMART PICKS",235,47,YELLOW,True)
        centered(d,"#4 and #5 • Same website Top 5 ranking",327,30,MUTED)
        card(img,photo,(56,465,968,1050),crop=(0,680,1080,1350))
        banner(d,"RANK #4  +  #5",1562)
        centered(d,"More choice within your budget",1713,33,WHITE)
    elif number==3:
        centered(d,"YOUR BUDGET. SMARTER CHOICE.",219,39,YELLOW,True)
        card(img,photo,(270,354,540,830))
        centered(d,"Compare real products",1273,48,WHITE,True)
        centered(d,"www.trustfolio.in",1362,44,YELLOW,True)
        banner(d,"COMPARE NOW  →",1516)
        centered(d,"TrustFolio Android app on Google Play",1645,30,WHITE)
        centered(d,"Verify current prices and availability",1775,29,MUTED)
    return img


def command(args,timeout=240):
    try:
        return subprocess.run(args,check=True,timeout=timeout,capture_output=True,text=True)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        raise RuntimeError("FFmpeg/FFprobe video generation or validation failed: "+
                           type(exc).__name__) from None


def render(post_json,jpg,report_json,output,*,ffmpeg="ffmpeg",ffprobe="ffprobe"):
    post=json.loads(Path(post_json).read_text("utf8"))
    report=json.loads(Path(report_json).read_text("utf8"))
    campaign=validate_approved_manifest(post)
    if (report.get("source")!="live_trustfolio_website_api"
        or report.get("source_product_ids_by_rank")!=post["ranked_product_ids"]
        or report.get("visual_product_ids_by_rank")!=post["ranked_product_ids"]
        or report.get("campaign_mode")!=post["mode"]
        or report.get("visual_geometry_errors")!=[]
        or report.get("dimensions")!=[1024,1536]
        or report.get("renderer")!="master_template_renderer_html_v4"):
        raise ValueError("Video generation blocked: website/render/top-five QA mismatch")
    if Path(jpg).name!=post["output_jpg"] or campaign not in Path(jpg).name:
        raise ValueError("Video input is not the approved immutable JPG")
    if shutil.which(ffmpeg) is None or shutil.which(ffprobe) is None:
        raise RuntimeError("FFmpeg and FFprobe are required to create real MP4 assets")
    with Image.open(jpg) as photo:
        if photo.size!=(1080,1350) or photo.format!="JPEG":
            raise ValueError("Video source must be the exact 1080x1350 approved social JPG")
        photo=photo.convert("RGB")
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="trustfolio_shorts_") as tmp:
        tmp=Path(tmp)
        segments=[]
        for index in range(SCENES):
            still=tmp/("scene_"+str(index)+".png")
            make_scene(post,photo,index).save(still,optimize=False)
            clip=tmp/("clip_"+str(index)+".mp4")
            filters=(
                "zoompan=z='min(zoom+0.00055,1.045)':"
                "x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':"
                "d=72:s=1080x1920:fps=24,"
                "fade=t=in:st=0:d=0.20,fade=t=out:st=2.83:d=0.17,"
                "format=yuv420p"
            )
            command([ffmpeg,"-nostdin","-hide_banner","-loglevel","error",
                     "-loop","1","-i",str(still),"-vf",filters,
                     "-frames:v",str(FRAMES_PER_SCENE),"-r",str(FPS),
                     "-an","-c:v","libx264","-preset","veryfast",
                     "-crf","24","-pix_fmt","yuv420p","-y",str(clip)])
            segments.append(clip)
        playlist=tmp/"list.txt"
        playlist.write_text("".join("file '"+str(x)+"'\n" for x in segments),"utf8")
        command([ffmpeg,"-nostdin","-hide_banner","-loglevel","error",
                 "-f","concat","-safe","0","-i",str(playlist),
                 "-c","copy","-movflags","+faststart","-y",str(output)])
    probe=json.loads(command([ffprobe,"-v","error","-show_streams",
                              "-show_format","-of","json",str(output)]).stdout)
    videos=[s for s in probe.get("streams",[]) if s.get("codec_type")=="video"]
    if len(videos)!=1:
        raise ValueError("Shorts video must contain exactly one video stream")
    v=videos[0]
    duration=float(probe["format"]["duration"])
    if (v["codec_name"]!="h264" or v["width"]!=W or v["height"]!=H
        or v["pix_fmt"]!="yuv420p" or not 11.7<=duration<=12.4
        or output.stat().st_size<50000):
        raise ValueError("Output is not a valid 12-second, 9:16 H264 YouTube Short")
    sha=hashlib.sha256(output.read_bytes()).hexdigest()
    label={"budget":"Budget Top 5","brand_budget":"Brand Top 5",
           "comparison":"Top 5 Comparison"}[post["mode"]]
    audit={
        "status":"qa_video_rendered_not_uploaded_to_social_accounts",
        "campaign_id":campaign,
        "mode":post["mode"],"brand":post["brand"],
        "category":post["category"],"budget_inr":post["budget_inr"],
        "ranked_product_ids":post["ranked_product_ids"],
        "ranking_source":"live_trustfolio_website_api",
        "video_file":output.name,"video_sha256":sha,
        "width":W,"height":H,"fps":FPS,"duration_seconds":duration,
        "codec":"h264","pixel_format":"yuv420p",
        "has_music":False,"publishing_enabled":False,
        "title":f"TrustFolio {label}: {post['category']} Under ₹{post['budget_inr']:,} #Shorts",
        "description":post["caption"]+"\n\n#Shorts",
        "landing_url":post["landing_url"],
    }
    report_out=output.with_suffix(".qa.json")
    report_out.write_text(json.dumps(audit,indent=2,ensure_ascii=False)+"\n","utf8")
    print("TRUSTFOLIO_REAL_SHORTS_VIDEO_QA_PASSED="+campaign)
    print("YOUTUBE_UPLOAD_ATTEMPTED=NO")
    print("VIDEO_PATH="+str(output))
    return audit


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--post",required=True)
    parser.add_argument("--jpg",required=True)
    parser.add_argument("--report",required=True)
    parser.add_argument("--output",required=True)
    opts=parser.parse_args()
    render(opts.post,opts.jpg,opts.report,opts.output)


if __name__=="__main__":
    main()
