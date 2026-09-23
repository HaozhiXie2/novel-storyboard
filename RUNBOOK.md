# Agent 与脚本运行手册

普通创作优先使用 [7861 即梦工作台](IMAGE_GUIDE.md)。本手册主要说明保留的 Agent 分镜路径和实验脚本，不代表长章节与云端视频已经全自动串联。

## 标准分镜流程

1. 准备自己写的、已获授权或可合法改编的章节，使用 UTF-8 TXT / MD。私人材料放 `source/private/`，不要放入公开示例目录。
2. 在支持本项目 Agent 的编辑器中调用 `novel-director`，明确文件名、改编范围与输出目录。私人稿件明确输出到 `output/private/<slug>/`。
3. 先写 `00-rights.md`，再依次写 `01-summary.md`、`02-bible.md`、`03-storyboard.md`、`04-prompts.md`。
4. 在仓库根目录检查交付文件：

```powershell
.\scripts\validate-output.ps1 -Path .\output\example-chapter
```

5. 人工检查人物外观、时间线、对白归属和镜头连续性，再把选定镜头提示词用于工作台。校验脚本只检查文件和结构，不判断改编质量。

## 长章节与修改

一次处理一个章节或明确片段；超过上下文容量时按完整场景切分，携带已有的 `02-bible.md` 作为约束。修改原文或人物设定后，同步更新后续分镜和提示词。

公有示例可使用 `source/chapter-01.md`、`output/chapter-01/`；未获公开许可的原文和中间稿留在 `private/`。忽略规则不会抹去已提交历史。

## 平台查询与生成

7861 页面调用项目内 `.tools/dreamina.exe`，生成会消耗账号积分；查看说明或运行离线测试不会提交生成任务。网页模式具备状态持久化、重复提交保护和已有任务恢复，推荐优先使用。

`scripts/dreamina-text2image.ps1`、`dreamina-text2video.ps1`、`dreamina-query.ps1` 和 `run-dreamina-pipeline.ps1` 是早期命令行适配器，保留作参考，**不作为当前推荐生产入口**。串行脚本面向特定 `04-prompts.md` 格式，不能等同于新版页面的防重复和恢复机制；重新运行可能重新提交并产生费用。它们也不负责声音、字幕和最终云端多镜头合成。

如需排查单个已有任务，可直接用官方 CLI 查询，`<任务ID>` 应取自本机任务记录：

```powershell
.\.tools\dreamina.exe query_result --submit_id=<任务ID>
```

这里只查询，不提交新任务。不要把包含账户信息的原始返回直接贴到公开 Issue。

## 本地模型实验

本地路径详见 [LOCAL_GUIDE.md](LOCAL_GUIDE.md)，需要先安装对应文本模型、ComfyUI、媒体模型和 FFmpeg。已部署电脑可双击 `Start-Studio.cmd`。

已有环境中，也可从仓库根目录提交正文：

```powershell
.\scripts\run-local-comfyui-pipeline.ps1 -TextFile .\source\example-chapter.md -Duration 10
```

默认停在分镜审核；显式增加 `-Automatic` 才连续生成。该入口提交正文到 7860，不读取 `04-prompts.md`，也没有 `-WorkflowPath` 参数。`workflows/animatediff-api.example.json` 是 API 工作流参考，实际模型与节点仍须匹配本机环境。

本地模型无即梦积分开销，但会使用本机显卡、磁盘与电力；不能据此保证画质或速度，当前输出没有配音。

## 提交前检查

只公开经检查的代码、示例和文档截图。详细存放规则见 [目录规范](docs/PROJECT_STRUCTURE.md)，脚本用途见 [脚本索引](scripts/README.md)，离线检查见 [贡献指南](CONTRIBUTING.md)。

项目不抓取网站、不补全未提供的原文；不同生成路径是否调用云端，以各自指南为准，不使用笼统的「全部本地」描述。
