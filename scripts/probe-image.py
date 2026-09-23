import json
from pathlib import Path
import sys
import time
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from server import api, workflow
g=workflow('two Chinese male scholars sitting in a wooden boat on a river, medium shot, visible faces, traditional robes', '', 148329)
g['4']['inputs']['batch_size']=1
g['6']['inputs']['model']=['1',0]
g['8']['inputs']['filename_prefix']='novel-studio/probe-still'
del g['5']
task=api('/prompt',{'prompt':g})['prompt_id']
print(task,flush=True)
for _ in range(120):
    result=api('/history/'+task).get(task)
    if result:
        print(json.dumps(result,ensure_ascii=False),flush=True)
        break
    time.sleep(1)
