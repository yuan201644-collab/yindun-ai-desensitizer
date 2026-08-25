# -*- coding: utf-8 -*-
"""隐盾 OCR 接口端到端冒烟：上传一张营业执照样例，校验识别与敏感标记返回。"""
import requests

img = "../testcases/dae1525f19f15fb2cfb736ac265b5f0c.jpg"
with open(img, "rb") as f:
    r = requests.post("http://127.0.0.1:8000/api/ocr", files={"file": f}, timeout=90)

print("http", r.status_code)
d = r.json()
if not d.get("success"):
    print("FAIL:", d.get("error"), d.get("type"))
    sys.exit(1)
print("success =", d.get("success"))
print("total_sensitive =", d.get("total_sensitive"))
tr = d.get("text_regions", [])
print("text_regions =", len(tr))
print("object_regions =", len(d.get("object_regions", [])))
for t in tr[:6]:
    s = t.get("sensitive") or {}
    print("   -", t["text"][:22], "|", s.get("object_label") or s.get("type") or "非敏感")