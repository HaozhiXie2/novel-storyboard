"""Run the local language model in an isolated process to release GPU RAM."""
import json
import math
import os
from pathlib import Path
import re
import sys

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def split_sentences(text):
    parts = []
    buf = []
    quote = False
    for ch in text:
        buf.append(ch)
        if ch in '“‘「『':
            quote = True
        elif ch in '”’」』':
            quote = False
            sentence = ''.join(buf)
            if re.search(r'[。！？][”’」』]$', sentence):
                if len(sentence.strip()) >= 6:
                    parts.append(sentence.strip())
                buf = []
        elif ch in '。！？' and not quote:
            sentence = ''.join(buf).strip()
            if len(sentence) >= 6:
                parts.append(sentence)
            buf = []
    tail = ''.join(buf).strip()
    if len(tail) >= 6:
        parts.append(tail)
    return parts


def beats_from_sentences(sentences, count):
    count = min(count, len(sentences))
    groups = [[] for _ in range(count)]
    for i, sentence in enumerate(sentences):
        groups[min(count - 1, i * count // len(sentences))].append(sentence)
    return [''.join(group) for group in groups if group]


def clean_direction(raw):
    parts = [p.strip() for p in re.split(r'\n+', raw.strip().strip('`')) if re.search(r'[\u4e00-\u9fff]', p)]
    prose = ''.join(parts)
    prose = re.sub(r'^镜头\s*\d+[^：:]{0,16}[：:]\s*', '', prose)
    return prose.strip()


def other_phrases(beat, beats):
    cues = ('推开木门', '还没拆', '灯笼被风', '影子拉得', '老槐树', '撑伞', '多年未见', '抬起头', '回来就好', '并肩走进')
    previous = None
    for other in beats:
        if other == beat:
            break
        previous = other
    banned = []
    for other in beats:
        if other == beat or other == previous:
            continue
        for cue in cues:
            if cue in other and cue not in beat and cue not in banned:
                banned.append(cue)
    if previous:
        for cue in ('推开木门', '认出那是', '抬起头', '回来就好'):
            if cue in previous and cue not in beat and cue not in banned:
                banned.append(cue)
    return banned[:5]


def leaks(direction, banned):
    return [phrase for phrase in banned if phrase[:6] in direction]


EXAMPLE_ECHO = ('雪粒子', '斗篷', '灯罩', '光暗交界')


def copied_example(direction, beat):
    return any(token in direction and token not in beat for token in EXAMPLE_ECHO)


def grounded(direction, beat):
    if copied_example(direction, beat) or leaks(direction, []):
        return False
    for token in ('路灯', '油纸', '藤蔓', '柳树', '姐妹', '斗篷', '蓝布', '枯叶'):
        if token in direction and token not in beat:
            return False
    for color in ('红', '蓝', '黑', '白', '黄', '绿', '金', '紫'):
        if color in direction and color not in beat:
            return False
    for token in ('青石', '灯笼', '影子', '木门', '信', '槐', '伞', '姐姐', '灯火', '回来就好'):
        if token in beat and token not in direction:
            return False
    if '撑伞的人' in beat and re.search(r'少年[^。]{0,48}伞', direction):
        return False
    return len(direction) >= 40


def enrich(beat):
    if any(token in beat for token in ('走进', '远了', '远去')):
        camera = '跟拍中景'
    elif any(token in beat for token in ('站着', '站立')):
        camera = '固定中景'
    else:
        camera = '固定镜头'
    return camera + '，' + beat


def write_direction(ask, beat, banned):
    ban = '；'.join(banned) or '无'
    raw = ask(
        '你写给视频模型用的中文分镜提示词。只输出一段话，不要编号，不要列表，不要解释。',
        '只拍下面这一段，不要写成整篇故事梗概，也不要改写成别的故事：\n' + beat + '\n\n'
        '禁止出现：' + ban + '。\n'
        '写成 80 到 140 字，按这个顺序：景别和这一镜开始时的环境（雨或风落在什么物体上、光从哪来），然后人物的动作和手里的物件，最后画面停在哪里。'
        '沿用原文的物件名称。不新增原文没有的物件、颜色和情节。原文里的对话最多保留一句原话。',
        320,
    )
    return clean_direction(raw)


def main(folder):
    root = Path(__file__).resolve().parents[1]
    text = (folder / 'source.txt').read_text(encoding='utf-8')
    job = json.loads((folder / 'job.json').read_text(encoding='utf-8'))
    model_path = root / '.local/models/planner'
    for name in ('planner-4b', 'planner-3b', 'planner'):
        candidate = root / '.local/models' / name
        if (candidate / 'READY').exists():
            model_path = candidate
            break
    print(f'Planner model: {model_path.name}', flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True, torch_dtype=torch.float16, device_map='cuda')
    def ask(system, content, tokens=1800):
        messages = [{'role':'system','content':system}, {'role':'user','content':content}]
        try:
            chat = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            chat = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(chat, return_tensors='pt').to(model.device)
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=tokens, do_sample=False, repetition_penalty=1.05)
        text = tokenizer.decode(output[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.S)
        return text.strip()
    # Read every chunk. Long source is summarized in bounded blocks, never silently truncated.
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    if len(chunks) > 1:
        summaries = []
        for i, chunk in enumerate(chunks):
            print(f'Reading section {i+1}/{len(chunks)}', flush=True)
            summaries.append(ask('你是忠于原文的编辑。只提取本段的角色、事件、因果和外貌信息，不补充原文没有的内容。用中文简要记录。', chunk, 600))
        text = '\n'.join(summaries)
    original = (folder / 'source.txt').read_text(encoding='utf-8')
    source_for_beats = text if len(chunks) > 1 else original
    sentences = split_sentences(source_for_beats)
    if len(original) <= 1200:
        count = min(6, max(2, len(sentences) // 2 or 2))
    else:
        count = min(18, max(3, math.ceil(job['duration'] / 6)))
    beats = beats_from_sentences(sentences or [original], count)
    plan = {'shots': []}
    notes = []
    for index, beat in enumerate(beats, 1):
        narration = beat[:180].lstrip('”’」』')
        seconds = min(8, max(5, round(len(beat) / 8) or 6))
        print(f'Writing shot direction {index}/{len(beats)}', flush=True)
        banned = other_phrases(beat, beats)
        direction = write_direction(ask, beat[:420], banned)
        spilled = leaks(direction, banned)
        if len(direction) < 70 or spilled or copied_example(direction, beat):
            revised = clean_direction(ask(
                '你改分镜。只输出改完的一段话，80 到 140 字。',
                '只根据这一段原文重写，写成看得见的连续画面：\n' + beat[:420] + '\n\n不要出现：' + '；'.join(list(spilled) + list(banned) + list(EXAMPLE_ECHO)),
                320,
            ))
            if grounded(revised, beat) and not leaks(revised, banned):
                direction = revised
        if not grounded(direction, beat) or leaks(direction, banned):
            direction = enrich(beat)
        prompt = f'镜头{index}（约{seconds}s）：{direction}'
        print(f'Preparing visual prompt {index}/{len(beats)}', flush=True)
        visual = ask('Translate this Chinese shot literally into one English image prompt, 25 to 40 words. Keep who does each action. 少年 is a teenage boy, 姐姐 is his older sister, 槐树 is a locust tree. Medium shot, subject large in frame. No new people or objects. English only.', direction, 160).strip()
        if re.search(r'[\u4e00-\u9fff]', visual):
            visual = ask('Translate into English only. Return only the English sentence, no Chinese.', direction, 160).strip()
        if re.search(r'[\u4e00-\u9fff]', visual) or len(visual) < 15:
            raise ValueError('本地模型未能生成英文画面提示词，请重试分镜')
        shot = {'narration': narration, 'source_excerpt': beat, 'seconds': seconds, 'prompt': prompt, 'image_prompt': visual}
        plan['shots'].append(shot)
        notes.append(prompt)
    (folder / 'planner-raw.txt').write_text('\n\n'.join(notes), encoding='utf-8')
    setting = ask('用 20 到 40 字写全片统一的时间、天气、地点和光线。不要复述情节，不要人名。', original[:800], 60).strip()
    setting = setting.splitlines()[0] if setting else ''
    if (not re.search(r'[\u4e00-\u9fff]', setting)) or re.search(r'少年|姐姐|姐妹|重逢|推开|走进', setting):
        setting = ask('只写天气、地点和光线，20字以内。不要人物，不要情节。', original[:240], 40).strip()
        setting = setting.splitlines()[0] if setting else ''
    plan['anchor'] = setting
    plan['summary'] = '\n'.join(s['narration'] for s in plan['shots'])
    (folder / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Plan ready', flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]))
