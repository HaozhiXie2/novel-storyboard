# 目录与文件规范

目录按应用、脚本、说明示例和本机数据分工。现有启动入口与任务目录保持兼容；以下规则用于后续添加文件，不要求迁移旧素材。

## 目录概览

```text
novel-storyboard/
├─ Start-Film.cmd            即梦影像工作台推荐入口（7861）
├─ Start-Images.cmd          同一工作台的兼容入口
├─ Start-Studio.cmd          本地模型实验入口（7860）
├─ app/                     页面、服务、规划逻辑与离线测试
├─ scripts/                 启动、下载、查询、校验和流水线脚本
├─ config/                  可公开的配置示例
├─ workflows/               ComfyUI 工作流示例
├─ docs/                    文档索引、目录规范与路线图
│  └─ images/               可公开的文档预览图片
├─ source/                  可公开的示例原文；私人材料放 private/
├─ output/                  可公开的示例分镜包；私人产出放 private/
├─ rights/                  原文来源与权利说明模板
├─ .github/workflows/        离线回归与文档检查
├─ .cursor/                 novel-director Agent 与分镜技能
├─ .local/                  本机运行环境、模型及日志（不提交）
├─ .tools/                  本机工具（不提交）
└─ media-tasks/             生成任务与媒体原件（不提交）
```

根目录保留项目首页、`IMAGE_GUIDE.md`、`LOCAL_GUIDE.md`、`RUNBOOK.md`、`AGENTS.md` 和许可证，便于启动和查阅。新增长篇说明放进 `docs/`，并补充[文档索引](README.md)。

## 应用与脚本

- 即梦工作台：`app/image_server.py` 与 `app/images.html`；启动器调用 `scripts/start-images.ps1`。
- 本地模型实验：`app/server.py`、`app/index.html`、`app/planner.py` 与 `app/cli.py`；相关启动脚本为 `scripts/start-studio.ps1` 和 `scripts/start-local-comfyui.ps1`。
- 离线回归：`app/test_image_server.py` 与 `app/test_images_ui.cjs`，用于检查即梦工作台逻辑，不提交付费生成任务。
- 早期平台适配参考：`scripts/dreamina-*.ps1` 与 `scripts/run-dreamina-pipeline.ps1`，不作为当前推荐生产入口；新创作使用 7861 工作台。
- 本地后端：`scripts/run-local-comfyui-pipeline.ps1`、`scripts/check-local-backend.ps1` 与 `scripts/download-*.py`。
- 输出校验：`scripts/validate-output.ps1`。辅助脚本留在 `scripts/`；存在语音相关脚本不代表当前页面已接入配音。

新脚本使用含义明确的名称，沿用 `start-`、`download-`、`check-`、`run-` 等前缀。页面和后端逻辑放在 `app/`，不要把运行时日志、测试生成视频或下载的工具放在代码目录。

## 正文与分镜示例

正文使用稳定名称，例如 `source/chapter-01.md`；对应改编包放在 `output/chapter-01/`，保留五份文件：

- `00-rights.md`：来源、使用范围与改编依据。
- `01-summary.md`：剧情摘要。
- `02-bible.md`：人物、场景和时间线设定。
- `03-storyboard.md`：逐场或逐镜分镜。
- `04-prompts.md`：生图与生视频提示词。

原文或人物设定变更后，应同步更新后续分镜和提示词，再运行输出校验。示例输出应能帮助读者理解格式；不要把每次试验生成的整套任务直接提交到 `output/`。

只有确认可公开的正文与改编稿才进入 GitHub。私人正文默认放在 `source/private/`，对应分镜包放在 `output/private/<slug>/`；这两处由 `.gitignore` 排除。

忽略规则不会替已经提交过的文件撤回历史记录。提交前仍须检查变更清单；放在其他 `source/`、`output/` 路径的 Markdown 或文本文件不会自动保密。

## 文档预览图片

文档配图统一放在 `docs/images/`。新增文件建议采用小写英文、连字符和明确主题，例如 `film-studio-overview.png`；同一界面更新时优先替换对应配图，避免不断积累含糊的「最终版」文件。

截图应对应当前界面，使用相对路径引用，并提供说明文字。公开前检查账号信息、凭据、个人正文和本机路径；注明样片的生成方式与限制，不把单次效果当作稳定能力承诺。

## 本机数据

- `.local/`：Python 环境、本地模型、服务日志等；换电脑需要重新部署。
- `.tools/`：Dreamina CLI，以及可选的 FFmpeg 等本机工具；登录凭据不得放入可提交配置。
- `media-tasks/images/<任务编号>/`：即梦图片与视频任务；沿用 `images` 目录名以兼容历史任务，`job.json` 记录任务状态等信息。
- `media-tasks/studio/<任务编号>/`：本地模型任务，包括中间稿、逐镜素材、成片和错误信息。
- `media-tasks/<slug>/shot-01/` 等：Dreamina 串行脚本的镜头素材；对应清单为 `manifest.json`。

不要手动修改活动任务的状态文件或只移动部分素材。需要备份或清理时，先确认任务已结束，并以完整任务目录为单位处理。兼容预览 `preview.webm` 是本机转码副本，原始 MP4 应与任务一起保留。

提交前检查 `.gitignore` 和变更清单：环境、模型、工具、凭据、日志及生成媒体原件保持本地；仓库只保留代码、必要配置示例、说明和经过挑选的可公开样例。
