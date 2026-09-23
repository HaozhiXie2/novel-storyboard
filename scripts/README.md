# 脚本索引

脚本均从仓库根目录使用。普通创作优先双击 `Start-Film.cmd`，不要为了试运行而执行未知生成或下载脚本。

## 推荐入口

- `start-images.ps1`：启动 7861 即梦工作台；只启动本机服务，点击页面生成才提交任务。
- `check-repo.py`：离线检查 Git 跟踪文件、文档相对链接与配图，不调用媒体平台。
- `validate-output.ps1`：检查 Agent 分镜包的五份交付文件与结构。

## 本地模型实验

- `start-studio.ps1`、`start-local-comfyui.ps1`：启动 7860 页面及本机 ComfyUI；需已有运行环境与模型。
- `check-local-backend.ps1`：检查本机 ComfyUI API。
- `run-local-comfyui-pipeline.ps1`：提交正文，默认先审核分镜；`-Automatic` 才自动继续。
- `download-planner.py`、`download-media-models.py`、`download-wan.py`：模型下载辅助，可能占用大量磁盘与网络，不由 CI 自动执行。
- `smoke-studio.py`、`probe-image.py`：本机集成排查工具；不同于纯离线测试，运行前阅读脚本、确认服务与资源开销。
- `narrate.ps1`、`narrate.py`：保留的语音辅助实验，当前页面成片流程没有接入配音。

详见 [本地使用指南](../LOCAL_GUIDE.md)。

## 早期 Dreamina 适配器

`dreamina-text2image.ps1`、`dreamina-text2video.ps1`、`dreamina-query.ps1` 和 `run-dreamina-pipeline.ps1` 保留作旧流程参考。它们不是新版页面的任务管理入口，不保证同样的恢复与防重复能力；生成脚本会消耗积分，重新运行可能重复计费。

推荐用新版 7861 页面提交，需排查既有任务时按 [运行手册](../RUNBOOK.md) 使用 CLI 查询。这里不把旧脚本改造成新的自动付费流水线。

## 开发检查

```powershell
python -m unittest discover -s app -p test_image_server.py -v
node app/test_images_ui.cjs
python scripts/check-repo.py
```

这三个命令不提交生成任务。测试方式、提交安全与人工验收范围见 [贡献指南](../CONTRIBUTING.md)。
