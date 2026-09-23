# 结构化改编包

这里保存可公开示例，每个章节一个目录。目前有 [虚构章节](example-chapter/) 和 [赤壁示例](chibi-zhengshi/)。

每组交付保留：

- `00-rights.md`：来源和改编依据。
- `01-summary.md`：剧情摘要。
- `02-bible.md`：人物、场景与时间线。
- `03-storyboard.md`：分镜。
- `04-prompts.md`：媒体生成提示词。

私人原文对应的产出默认放在 `output/private/<slug>/`，该目录已被 Git 忽略。生成图片、视频、声音和任务状态放在 `media-tasks/`，不要批量堆入本目录。

可以人工审核和修改内容，但要保留文件结构；改动剧情或人物设定时，同步更新后续分镜和提示词。完成后使用 `scripts/validate-output.ps1` 校验，并按 [运行手册](../RUNBOOK.md) 进入下一步。
