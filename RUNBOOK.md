# 运行手册

## 标准流程

1. 将自己写的、已获授权或属于公版的章节放入 `source/`，建议使用 `.md` 或 `.txt`。
2. 在 Cursor 中调用 `novel-director`，明确指定文件名和改编范围。
3. Agent 先写 `output/<slug>/00-rights.md`，再依次写摘要、设定、分镜和提示词。
4. 运行 `scripts/validate-output.ps1` 检查五份文件是否存在且非空。
5. 人工检查人物外观、时间线、对白归属和镜头连续性，再交给生图/生视频工具。

## 长章节

一次只处理一个章节或一个明确片段。超过单次上下文容量时，按完整场景切分，并在下一次处理时携带上一段的 `02-bible.md`，避免人物和场景设定漂移。

## 文件命名

- `source/` 中使用稳定文件名，例如 `chapter-01.md`。
- `output/` 使用对应 slug，例如 `output/chapter-01/`。
- 修改摘要或人物设定后，应重新生成其后的分镜和提示词，避免产出过期。

## 边界

本项目只处理用户主动提供的文本，不抓取网站、不补全未提供的原文，也不调用外部生图或生视频 API。

## Dreamina CLI（可选）

项目已提供三个适配脚本：

```powershell
.\scripts\dreamina-text2image.ps1 -Prompt "镜头提示词" -Ratio 16:9 -Resolution 2k -Poll 30
.\scripts\dreamina-text2video.ps1 -Prompt "镜头提示词" -Ratio 16:9 -Resolution 720p -Duration 5 -Poll 30
.\scripts\dreamina-query.ps1 -SubmitId <任务ID> -DownloadDir .\media-tasks\镜头01
```

脚本调用项目根目录 `.tools/dreamina.exe`，该目录已加入 `.gitignore`，不会上传到 GitHub。生成任务会消耗即梦额度；提交前应先确认账号有 CLI 使用权限。

## 一键生成镜头视频

先把长章节放入 `source/`，再让 `novel-director` 生成对应的 `output/<slug>/04-prompts.md`。之后按镜头顺序串行调用 Dreamina，避免并发限制：

```powershell
.\scripts\run-dreamina-pipeline.ps1 `
  -Slug chibi-zhengshi `
  -SourcePath .\source\赤壁之战正文.md `
  -Ratio 9:16 `
  -Resolution 720p `
  -Duration 5 `
  -Poll 60
```

生成文件写入 `media-tasks/<slug>/shot-01/` 等目录，任务和状态写入 `manifest.json`。脚本只使用项目已有分镜提示词，不联网搜索或补写剧情；配音、字幕、音效及最终 MP4 合成仍需单独接入 TTS 和 FFmpeg。

## 本地 Stable Diffusion / AnimateDiff

本地后端不依赖 Dreamina 排队，但需要先启动 ComfyUI API（默认 `http://127.0.0.1:8188`），并安装 Stable Diffusion checkpoint、AnimateDiff motion module 和视频合成节点。

```powershell
.\scripts\check-local-backend.ps1
.\scripts\run-local-comfyui-pipeline.ps1 -Slug chibi-zhengshi
```

脚本会解析现有 `04-prompts.md` 并生成本地镜头清单。由于不同 ComfyUI 工作流的节点名称和模型文件不同，`workflows/animatediff-api.example.json` 只是占位模板；导出你本机的 API workflow 后，再把它作为 `-WorkflowPath` 传入。
