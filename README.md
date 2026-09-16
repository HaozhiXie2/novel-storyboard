# 小说分镜 Agent

把你有权使用的小说章节，改编成剧情总结、分镜指导和生图/生视频提示词。

这不是独立网站，也不是爬虫。打开本文件夹，在 Cursor 里把任务交给 **novel-director**。模型用你的 Cursor 订阅，产出写在 `output/`。

## 怎么用

1. 把章节 `.txt` / `.md` 放进 `source/`（或直接把正文贴进对话）
2. 在对话里输入：`/novel-director` 或「用 novel-director 把 source 里的章节做成分镜」
3. 到 `output/<书名或章节名>/` 看四份稿：

| 文件 | 内容 |
|------|------|
| `01-summary.md` | 剧情摘要 |
| `02-bible.md` | 人物、场景、时间线 |
| `03-storyboard.md` | 分场分镜（景别、动作、对白、情绪） |
| `04-prompts.md` | 可复制给生图 / 生视频模型的提示词 |

首次使用可以直接参考 `source/example-chapter.md` 和
`output/example-chapter/`。示例文本是项目自带的虚构内容，不代表真实作品。

完成改编后，可运行校验脚本检查输出是否齐全：

```powershell
.\scripts\validate-output.ps1 -Path .\output\<书名或章节名>
```

更完整的运行约定见 `RUNBOOK.md`。

项目也预留了 Dreamina CLI 适配脚本，可在账号具备 CLI 权限后生成图片和视频；先阅读 `RUNBOOK.md` 中的“Dreamina CLI”部分。生成任务会消耗额度，示例不会自动提交付费任务。

## 边界（v1）

- **做：** 解析你提供的文本 → 总结 → 分镜 → 提示词
- **不做：** 爬番茄小说或任何网站；不调用外部生图/生视频 API（等你有 Key 再加）
- **素材：** 只处理你自己提供、且有权改编的文本

## 项目结构

```
source/                 你放入的原文
output/                 Agent 写出的改编包
rights/                 本项目用途说明
.cursor/agents/         novel-director 自定义 Agent
.cursor/skills/         分镜工作流（Agent 会读）
```

有了生图/生视频 Key 之后，在同一套目录上加第五步，不必另起一个 App。

长章节的自动生成入口是 `scripts/run-dreamina-pipeline.ps1`：它读取已有的 `04-prompts.md`，按镜头顺序串行调用 Dreamina，并把结果下载到 `media-tasks/`，不会创建额外的排队网页。
