"""Server-only renders of distinct payloads; design checks never compare product values."""
import json, sys, shutil, importlib.util
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops, ImageStat
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import master_template_renderer_html_v4 as renderer
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
data=json.loads((ROOT/'trustfolio_infographic_payload_v1.json').read_text())['ads']
# Cover the reference category plus four distinct product geometries. These are
# real five-product payloads already present in the production data; nothing is published.
test_categories=('smartwatches','headphones-earbuds','laptop','smart-phones','ceiling-fans')
selected=[]
for key in test_categories:
    match=next((a for a in data if len(a.get('products',[]))==5 and renderer.h.detect_category(a)[0]==key),None)
    if match is None:
        raise SystemExit(f'No five-product QA payload available for category: {key}')
    selected.append(match)
reference=Image.open(ROOT/'assets/trustfolio_approved_reference.jpg').convert('RGB')
reference.save(out/'approved-reference.png')
# Conservative reference-content extents, not product identities. These only mask data.
reference_dynamic=[(75,105,760,393),(75,451,322,695),(395,416,677,770),(719,453,934,696),
 (46,968,251,1245),(663,986,883,1268),(65,703,330,936),(357,780,673,1044),(704,703,959,938),
 (255,1080,497,1306),(865,1028,1024,1296)]
fixed_regions={'brand':(0,0,510,120),'benefits':(775,160,1000,424),'footer':(0,1315,1024,1536)}
report={'tested_categories':list(test_categories),'design_only':True,'reference_data_regression':'not requested: payloads differ from reference','datasets':[],'errors':[]}
images=[];masks=[];geometries=[]
for i,ad in enumerate(selected,1):
    try:
        png=renderer.render(ad)
        im=Image.open(png).convert('RGB');im.save(out/f'dataset-{i}.png')
        meta=json.loads(png.with_suffix('.json').read_text());(out/f'dataset-{i}.json').write_text(json.dumps(meta,indent=2))
        errors=list(meta['errors'])
        if im.size!=(1024,1536): errors.append('wrong canvas size')
        expected={int(p['rank']):p['name'] for p in ad['products']}
        for slot in meta['slots']:
            if expected[slot['rank']]!=slot['name']: errors.append('incorrect payload rank mapping')
            fields=slot['fields']
            for key,box in fields.items():
                if box[0]<0 or box[1]<0 or box[2]>1024 or box[3]>1315: errors.append(f'outside content canvas: {slot["rank"]} {key}')
            keys=list(fields)
            for j,k in enumerate(keys):
                for other in keys[j+1:]:
                    a,b=fields[k],fields[other]
                    if min(a[2],b[2])-max(a[0],b[0])>2 and min(a[3],b[3])-max(a[1],b[1])>2: errors.append(f'overlap rank {slot["rank"]}: {k}/{other}')
        mask=Image.new('L',im.size,255);draw=ImageDraw.Draw(mask)
        for box in reference_dynamic:
            draw.rectangle((int(box[0])-3,int(box[1])-3,int(box[2])+3,int(box[3])+3),fill=0)
        # CSS product drop-shadows extend beyond the image boxes; mask their support too.
        for box in meta['dynamic']:
            draw.rectangle((int(box[0])-20,int(box[1])-20,int(box[2])+20,int(box[3])+20),fill=0)
        mask.save(out/f'dataset-{i}-fixed-mask.png')
        diff=ImageChops.difference(reference,im)
        masked=sum(ImageStat.Stat(diff,mask).mean)/3
        diff.putalpha(mask);diff.save(out/f'dataset-{i}-masked-diff.png')
        fixed={name:sum(ImageStat.Stat(diff.convert('RGB').crop(box)).mean)/3 for name,box in fixed_regions.items()}
        for name,value in fixed.items():
            if value>8: errors.append(f'fixed artwork damaged: {name} MAE={value:.2f}')
        if masked>15: errors.append(f'masked layout mismatch: MAE={masked:.2f} exceeds 15')
        report['datasets'].append({'id':ad['source_ad_id'],'category':meta['category'],'fixed_regions_mae':fixed,'masked_layout_mae':masked,'errors':errors})
        report['errors']+=errors
        images.append(im);masks.append(mask);geometries.append(meta)
    except Exception as exc:
        report['errors'].append(f'dataset {i}: {type(exc).__name__}: {exc}')
if len(images)==len(selected):
    report['fixed_template_change_mae']=0.0
    for j in range(1,len(images)):
        union=ImageChops.darker(masks[0],masks[j])
        unchanged=ImageStat.Stat(ImageChops.difference(images[0],images[j]),union).mean
        change=sum(unchanged)/3
        report['fixed_template_change_mae']=max(report['fixed_template_change_mae'],change)
        if max(unchanged)>0.01:
            report['errors'].append(f'fixed template changes with data: {test_categories[j]}')
        for a,b in zip(geometries[0]['slots'],geometries[j]['slots']):
            if a['fields']!=b['fields']:
                report['errors'].append(f'slot geometry changes with data: {test_categories[j]}')
report['passed']=not report['errors']
(out/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)
