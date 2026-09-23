/*
 * Offline interaction checks for images.html.
 * Run: node app/test_images_ui.cjs (or node test_images_ui.cjs from app/).
 *
 * This is a deliberately small DOM mock, not a real browser. It verifies
 * application state, request payloads, element identity, and plain-text output.
 * It does not verify CSS layout, native focus/validation, video decoding,
 * downloads, accessibility-tree behavior, or the real generation service.
 * All fetch calls are intercepted. No network or paid generation is performed.
 * No packages, browser installation, server, or files outside this folder are
 * required. The test reads images.html without changing it.
 */

'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');

const html = fs.readFileSync(path.join(__dirname, 'images.html'), 'utf8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(scriptMatch, 'images.html must contain its application script');
const flush = () => new Promise(resolve => setImmediate(resolve));

function response(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => JSON.parse(JSON.stringify(data)),
  };
}

function createHarness(initialJobs, savedStorage = new Map()) {
  const elements = new Map();
  const ratioButtons = [];
  const filterButtons = [];

  class Element {
    constructor(tag = 'div') {
      this.tagName = tag.toUpperCase();
      this.children = [];
      this.attrs = {};
      this.dataset = {};
      this.handlers = {};
      this._text = '';
      this.value = '';
      this.disabled = false;
      this.hidden = false;
      this.classList = { add() {} };
    }

    set id(value) { this._id = value; elements.set(value, this); }
    get id() { return this._id; }
    set textContent(value) { this._text = String(value ?? ''); this.children = []; }
    get textContent() {
      return this._text + this.children.map(child => child.textContent ?? String(child)).join('');
    }
    set src(value) { this.attrs.src = value; }
    get src() { return this.attrs.src; }
    setAttribute(key, value) { this.attrs[key] = String(value); }
    getAttribute(key) { return this.attrs[key] ?? null; }
    append(...items) { this.children.push(...items); }
    prepend(...items) { this.children.unshift(...items); }
    replaceChildren(...items) { this._text = ''; this.children = items; }
    addEventListener(event, callback) { (this.handlers[event] ??= []).push(callback); }
    scrollIntoView() {}
    focus() {}
    querySelector(tag) {
      return this.children.find(child => child.tagName?.toLowerCase() === tag)
        || this.children.map(child => child.querySelector?.(tag)).find(Boolean)
        || null;
    }
  }

  for (const match of html.matchAll(/<([a-z]+)[^>]*\bid="([^"]+)"[^>]*>/g)) {
    const element = new Element(match[1]);
    element.id = match[2];
  }
  for (const ratio of ['9:16', '16:9', '1:1', '3:4']) {
    const button = new Element('button');
    button.dataset.ratio = ratio;
    ratioButtons.push(button);
  }
  for (const filter of ['all', 'image', 'video']) {
    const button = new Element('button');
    button.dataset.filter = filter;
    filterButtons.push(button);
  }
  // Initialize the form defaults from the actual markup, not a separate copy.
  for (const match of html.matchAll(/<textarea\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)<\/textarea>/g)) {
    elements.get(match[1]).value = match[2];
  }
  for (const match of html.matchAll(/<select\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)) {
    const firstOption = match[2].match(/<option\b[^>]*value="([^"]+)"/);
    if (firstOption) elements.get(match[1]).value = firstOption[1];
  }

  const document = {
    getElementById: id => elements.get(id),
    createElement: tag => new Element(tag),
    createElementNS: (_namespace, tag) => new Element(tag),
    createTextNode: text => {
      const element = new Element('#text');
      element.textContent = text;
      return element;
    },
    querySelectorAll: selector => selector === '[data-ratio]' ? ratioButtons
      : selector === '[data-filter]' ? filterButtons : [],
    addEventListener() {},
    hidden: false,
  };

  const harness = {
    jobs: initialJobs,
    posts: [],
    elements,
    storage: new Map(savedStorage),
    postHandler: null,
    jobsHandler: null,
  };
  const fetch = async (url, options = {}) => {
    if (options.method === 'POST') {
      assert.ok(['/api/generate', '/api/video'].includes(url), 'Only known local POST routes are allowed');
      assert.equal(options.headers['X-Studio-Token'], '__TOKEN__');
      const payload = JSON.parse(options.body);
      harness.posts.push({ url, payload });
      if (harness.postHandler) return harness.postHandler(payload);
      throw new Error('Test must explicitly provide a mocked POST result');
    }
    if (url === '/api/jobs') {
      return harness.jobsHandler ? harness.jobsHandler() : response(harness.jobs);
    }
    if (url === '/api/account') return response({ credits: 120, membership: 'VIP' });
    if (url === '/api/models') {
      return response([
        { id: 'seedance2.0fast_vip', label: 'Seedance 2.0 Fast · 会员', description: '快速模型' },
        { id: 'seedance2.0_vip', label: 'Seedance 2.0 · 会员' },
      ]);
    }
    throw new Error('Unexpected fetch target: ' + url);
  };

  const context = {
    document,
    window: { innerWidth: 1400 },
    localStorage: {
      getItem: key => harness.storage.get(key) ?? null,
      setItem: (key, value) => harness.storage.set(key, value),
      removeItem: key => harness.storage.delete(key),
    },
    fetch,
    crypto: webcrypto,
    AbortSignal,
    // Polling and toast timers are not run implicitly: each refresh is explicit.
    setTimeout: () => 1,
    clearTimeout() {},
    setInterval: () => 1,
    console, Promise, Date, Set, Uint8Array,
  };
  context.globalThis = context;
  // Expose selected closure methods in memory only; never rewrite images.html.
  assert.match(scriptMatch[1], /\}\)\(\);\s*$/, 'Expected the application IIFE wrapper');
  const script = scriptMatch[1].replace(
    /\}\)\(\);\s*$/,
    'globalThis.testApi={state,refresh,renderPreview,chooseSource,submit,updateButtons,setFilter};})();',
  );
  vm.runInNewContext(script, context, { filename: 'images.html application script' });
  harness.api = context.testApi;
  return harness;
}

async function main() {
  const source = {
    id: '11111111111111111111111111111111',
    status: 'done', // Intentionally omit kind to verify legacy image handling.
    images: ['picture.png'], videos: [],
    prompt: '一位书生在江边', ratio: '9:16', created: 1726000000,
  };
  const h = createHarness([source]);
  await flush();
  const a = h.api;
  const element = id => h.elements.get(id);
  assert.ok(a.state.ready);
  assert.equal(h.posts.length, 0, 'Startup must not submit jobs');
  assert.equal(element('videoModel').value, 'seedance2.0fast_vip');

  a.chooseSource(source, 'picture.png');
  assert.equal(a.state.mode, 'video');
  assert.equal(a.state.source.image, 'picture.png');
  assert.equal(element('generateVideo').disabled, false);

  const video = {
    id: '22222222222222222222222222222222', kind: 'video',
    source_job: source.id, source_image: 'picture.png', status: 'done',
    videos: ['clip.mp4'], images: [], prompt: '克制运动', duration: 5,
    model: 'seedance2.0fast_vip', created: 1726000050,
  };
  h.jobs = [video, source];
  await a.refresh();
  a.state.selectedId = video.id;
  a.renderPreview();
  const player = element('previewStage').children[0];
  assert.equal(player.tagName, 'VIDEO');
  const originalVideoUrl = '/media/' + video.id + '/clip.mp4';
  assert.equal(player.src, originalVideoUrl, 'Without a compatibility preview, use the original video');
  assert.equal(element('previewFooter').querySelector('a').href, originalVideoUrl);
  element('videoPrompt').value = '用户仍在编辑的运动说明';
  video.credits = 18;
  await a.refresh();
  assert.equal(element('previewStage').children[0], player, 'Polling must keep the same video element');
  assert.equal(element('videoPrompt').value, '用户仍在编辑的运动说明');

  video.preview_video = 'preview.webm';
  video.preview_status = 'done';
  await a.refresh();
  const compatiblePlayer = element('previewStage').children[0];
  assert.notEqual(compatiblePlayer, player, 'The player must update when a compatibility preview becomes available');
  assert.equal(compatiblePlayer.src, '/media/' + video.id + '/preview.webm');
  assert.equal(element('previewFooter').querySelector('a').href, originalVideoUrl, 'Downloads must retain the original MP4');
  assert.equal(element('previewFooter').querySelector('a').download, 'clip.mp4');
  video.credits = 19;
  await a.refresh();
  assert.equal(element('previewStage').children[0], compatiblePlayer, 'Unrelated updates must not restart the compatible player');
  assert.equal(element('videoPrompt').value, '用户仍在编辑的运动说明');

  video.preview_video = 'preview-v2.webm';
  await a.refresh();
  assert.notEqual(element('previewStage').children[0], compatiblePlayer, 'The actual preview filename must participate in the player cache key');
  assert.equal(element('previewStage').children[0].src, '/media/' + video.id + '/preview-v2.webm');
  assert.equal(element('previewFooter').querySelector('a').href, originalVideoUrl);

  delete video.preview_video;
  video.preview_status = 'failed';
  await a.refresh();
  assert.equal(element('previewStage').children[0].src, originalVideoUrl);
  assert.ok(element('jobNotice').textContent.includes('预览兼容转换未完成，可下载原始视频。'));
  assert.equal(element('previewFooter').querySelector('a').href, originalVideoUrl);

  let resolvePost;
  h.postHandler = payload => new Promise(resolve => {
    resolvePost = () => {
      const job = {
        ...payload, id: payload.request_id, kind: 'video', status: 'waiting',
        message: '处理中', images: [], videos: [],
      };
      h.jobs = [job, ...h.jobs];
      resolve(response(job));
    };
  });
  const firstSubmit = a.submit('video');
  await a.submit('video');
  assert.equal(h.posts.length, 1, 'A double click must produce only one POST');
  assert.equal(h.posts[0].url, '/api/video');
  assert.equal(h.posts[0].payload.source_job, source.id);
  assert.equal(h.posts[0].payload.source_image, 'picture.png');
  assert.equal(h.posts[0].payload.duration, 5);
  await a.refresh();
  assert.equal(element('generateVideo').disabled, true, 'Polling must not release the submission lock');
  assert.equal(a.state.inflight.video, true);
  resolvePost();
  await firstSubmit;
  assert.equal(a.state.pending.video, null);
  assert.equal(element('generateImage').disabled, false, 'Image and video queues must have separate locks');

  h.jobs = [source];
  await a.refresh();
  h.postHandler = async () => { throw new Error('offline'); };
  await a.submit('video');
  const pending = a.state.pending.video;
  assert.match(pending.request_id, /^[a-f0-9]{32}$/);
  assert.ok(h.storage.get('novel-studio-v2:video'));
  const savedPendingStorage = new Map(h.storage);
  element('videoPrompt').value = '完全不同的新文字';
  await a.refresh();
  assert.equal(h.posts.length, 2, 'Status polling must never retry a POST');
  await a.submit('video');
  assert.equal(h.posts.length, 3);
  assert.deepEqual(h.posts[1].payload, h.posts[2].payload, 'Explicit retry must preserve the complete original request');

  const failed = {
    ...pending, id: pending.request_id, kind: 'video', status: 'failed',
    message: '平台拒绝', detail: 'Permission denied <img src=x onerror=alert(1)>',
    images: [], videos: [],
  };
  h.jobs = [failed, source];
  await a.refresh();
  assert.equal(a.state.pending.video, null, 'An existing job must reconcile its stored pending request');
  assert.ok(element('jobNotice').textContent.includes('Permission denied <img'));
  assert.equal(element('jobNotice').children.length, 0, 'Failure details must be assigned as plain text');
  assert.equal(h.posts.length, 3);

  const reloaded = createHarness([failed, source], savedPendingStorage);
  await flush();
  assert.equal(reloaded.api.state.pending.video, null, 'A fresh page must reconcile a persisted request');
  assert.equal(reloaded.storage.has('novel-studio-v2:video'), false);
  assert.equal(reloaded.posts.length, 0, 'Reloading must not resubmit any task');

  console.log('PASS: legacy image selection and current model default');
  console.log('PASS: stable video element and preserved user edits during polling');
  console.log('PASS: compatibility preview playback, original MP4 download, preview replacement and failure fallback');
  console.log('PASS: double-click protection and independent image/video submission locks');
  console.log('PASS: ambiguous retry preserves payload/request_id; polling and reload never POST');
  console.log('PASS: persisted pending request reconciliation and plain-text failure detail');
  console.log('DOM mock only; browser rendering/media playback require separate browser checks.');
  console.log('All requests mocked. No external service or paid generation was called.');
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
