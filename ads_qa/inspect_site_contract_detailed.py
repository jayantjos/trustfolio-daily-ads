#!/usr/bin/env python3
"""Safe detailed read of specific website Top-5 ranking and redirect source.

The VPS is never changed. Emits only selected code lines with auth/config/secret
content excluded, not entire files. No production API requests or data changes.
"""
from pathlib import Path
import json,re,hashlib

root=Path.home()/"apps"/"trustfolio"
spec={
"top_controller":("node-backend/controllers/ProductController.js",r"async function getTopProducts|const getTopProducts\b|function getTopProducts",190),
"recommendation_api":("node-backend/services/ProductRecommendationService.js",r"async function getTop|async function recommend|async function findTop|function getTop",190),
"product_dto":("node-backend/models/ProductSummaryDto.js",r"function fromMyProduct|const fromMyProduct|function to",125),
"website_api":("trustfolio-main/src/services/api.service.ts",r"const PRODUCTION_API_BASE|async getTopProducts",45),
"website_category_form":("trustfolio-main/src/app/category/[slug]/page.tsx",r"const handleSubmit|const handleSearch|const handleFindProducts|const handleBudget",55),
}
secret=re.compile(r"api.?key|secret|token|password|credential|process\.env|bearer|cookie|mongodb|mongoose|razorpay|private.?key|auth|connectionstring|database_uri|firebase.?admin",re.I)
pattern=re.compile(r"\b(category|budget|brand|rank|score|sort|products|limit|price|fallback|match|request|filter|cache|query|return|top|response|confidence|select|dedup|platform|title|_id|productId|manufacturer)\b|[{}]|(?:\bconst|\bawait|\bif\b)",re.I)
result={}
for label,(relative,anchor,window) in spec.items():
    file=root/relative
    if not file.is_file():
        result[label]={"error":"file_missing"};continue
    data=file.read_bytes()
    lines=data.decode("utf8",errors="replace").splitlines()
    starts=[i for i,line in enumerate(lines) if re.search(anchor,line,re.I)]
    if not starts:
        result[label]={"source":relative,"hash":hashlib.sha256(data).hexdigest(),"anchors_found":False}
        continue
    spans=[]
    for start in starts[:2]:
        begin=max(0,start-8)
        end=min(len(lines),start+window)
        snippets=[]
        for i in range(begin,end):
            line=lines[i].strip()
            if secret.search(line) or len(line)>230 or not pattern.search(line):
                continue
            line=re.sub(r"https?://[^\s'\x22\\)]+","<URL>",line)
            if re.search(r"\b(?:ghp_|sk-|github_pat_)[A-Za-z0-9_-]{20,}",line):continue
            snippets.append({"line":i+1,"source":line})
            if len(snippets)>=115:break
        spans.append({"anchor_line":start+1,"snippets":snippets})
    result[label]={"source":relative,"hash":hashlib.sha256(data).hexdigest(),"total_lines":len(lines),"spans":spans}
print("SITE_CONTRACT_DETAIL_BEGIN")
print(json.dumps(result,indent=2))
print("SITE_CONTRACT_DETAIL_END")
