"""Submit a local text file through the same tested studio API as the UI."""
import argparse
import json
from pathlib import Path
import re
import urllib.request

p = argparse.ArgumentParser()
p.add_argument('text_file', type=Path)
p.add_argument('--duration', type=int, choices=[10,30,60,90], default=30)
p.add_argument('--automatic', action='store_true')
args = p.parse_args()
base = 'http://127.0.0.1:7860'
with urllib.request.urlopen(base) as r:
    token = re.search("const token='([^']+)'", r.read().decode())[1]
payload = {'title':args.text_file.stem,'text':args.text_file.read_text(encoding='utf-8-sig'),'duration':args.duration,'automatic':args.automatic}
req = urllib.request.Request(base+'/api/jobs',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Studio-Token':token})
with urllib.request.urlopen(req) as r:
    print(json.dumps(json.load(r),ensure_ascii=False,indent=2))
