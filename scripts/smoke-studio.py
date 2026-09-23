"""Exercise a real local source -> planner -> animation -> narrated MP4 job."""
import json
from pathlib import Path
import re
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:7860'
with urllib.request.urlopen(BASE) as r:
    token = re.search("const token='([^']+)'", r.read().decode())[1]
def post(path, data):
    req = urllib.request.Request(BASE+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json','X-Studio-Token':token})
    with urllib.request.urlopen(req) as r:
        return json.load(r)
source = (ROOT/'source/赤壁之战正文.md').read_text(encoding='utf-8')
# The first prose paragraph is enough for a two-shot installation test.
paragraph = next(x for x in source.split('\n\n') if x.startswith('却说鲁肃'))
job = post('/api/jobs', {'title':'赤壁之战 · 本地部署试片', 'text':paragraph, 'duration':10, 'automatic':True})
print('JOB '+job['id'], flush=True)
last = None
for _ in range(1800):
    with urllib.request.urlopen(BASE+'/api/jobs') as r:
        current = next(x for x in json.load(r) if x['id']==job['id'])
    status = current['status'],current['message']
    if status != last:
        print(json.dumps(current,ensure_ascii=False),flush=True)
        last = status
    if current['status']=='done':
        print('PASS '+str(ROOT/'media-tasks/studio'/job['id']/'final.mp4'),flush=True)
        sys.exit(0)
    if current['status'] in ('error','paused'):
        sys.exit(1)
    time.sleep(2)
raise TimeoutError('Local video test exceeded one hour')
