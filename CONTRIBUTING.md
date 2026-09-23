# 参与开发与提交检查

欢迎修复问题和改进文档。请先阅读 [项目首页](README.md)、[目录规范](docs/PROJECT_STRUCTURE.md) 和 [路线图](docs/ROADMAP.md)，区分已经交付的单镜头工作台与尚未实现的完整短剧流水线。

## 最小离线环境

Python 3.12、Node.js 24 和 Git 即可运行以下检查，无需安装 Dreamina CLI、ComfyUI、FFmpeg 或媒体模型，也不需要 API Key。已部署电脑可用 `.local/venv/Scripts/python.exe` 替代 `python`。

在仓库根目录运行：

```powershell
python -m unittest discover -s app -p test_image_server.py -v
node app/test_images_ui.cjs
python scripts/check-repo.py
```

后端测试使用临时目录和模拟平台调用；前端测试使用 DOM 模拟。它们不向生成平台提交任务，不消耗积分。首次新增文件后先检查待提交清单，再暂存文件；仓库检查读取 Git 已跟踪 / 已暂存文件。

GitHub Actions 在推送和拉取请求上运行同一组检查：只读权限、不会部署应用、不会调用即梦、不会下载模型或读取生成账号凭据。工作流使用官方 [checkout](https://github.com/actions/checkout)、[setup-python](https://github.com/actions/setup-python) 和 [setup-node](https://github.com/actions/setup-node)，固定到经核对的提交版本；更新版本时重新核对官方来源。

## 这些测试不证明什么

测试通过不等于实际平台速度、生成质量或跨镜头一致性达标。UI 变更还须在真实浏览器验证布局、键盘操作、作品选择、播放与下载；云端真实生成应得到明确的范围和预算授权，不得作为自动测试偷偷执行。

## 提交约定

- 改动保持单一主题，代码行为变化补回归测试；修改使用方式时同步指南与截图。
- 新分支使用清楚的名称，例如 `codex/docs-preview-refresh`；不要强制覆盖他人的提交。
- 不移动正在使用的任务目录，不修改既有任务状态伪造成功，不破坏 `Start-Images.cmd` 等兼容入口。
- 私人正文放 `source/private/`，私人分镜放 `output/private/`。任何公开示例必须说明来源和使用依据。
- 不提交 `.env`、登录凭据、个人绝对路径、模型、运行环境、日志或整批生成素材。忽略规则不是秘密扫描器，已进入历史的内容不会自动撤回。
- 提交前检查 `git status` 和 `git diff --cached`；文档配图在 `docs/images/` 中逐张检查，只保留可公开内容。

## 报告问题

提供入口（7861 / 7860 / Agent）、复现步骤、预期与实际行为，以及已脱敏的错误片段。不要粘贴令牌、完整账户返回、个人正文、任务下载签名 URL 或未经授权的素材。生成速度问题须说明是单次记录，避免用一个样本承诺服务时延。
