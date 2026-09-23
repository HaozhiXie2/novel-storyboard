# 本地小说影坊

## 打开和使用

双击项目根目录的 **Start-Studio.cmd**，浏览器会打开 `http://127.0.0.1:7860`。初次打开需等待生成服务就绪。

1. 粘贴章节正文，或选择 UTF-8 编码的 TXT / MD 文件。
2. 首次建议选择 10 秒试片。
3. 点击“开始制作”。本地文本模型读取正文，准备摘要、分镜与英文画面提示词。
4. 默认停在分镜审核，可以调整文字后生成。勾选“分镜完成后自动生成视频”则自动继续。
5. 在“我的作品”预览并下载 MP4。成片没有配音。

输出保存在 `media-tasks/studio/<任务编号>/`：包含原文、摘要、画面设定、分镜、提示词、逐镜画面、最终视频和错误日志。所有生成均在本机运行，不需要即梦额度。

## 当前画质和适用范围

画面优先走本机视频模型 Wan 2.1 1.3B：按中文分镜直接生成竖屏连续镜头，约 16 帧每秒，单镜大约 2 到 5 秒，导出为 720×1280。模型权重约 480×832，导出时放大，不会凭空增加细节。这条路径更接近即梦的连续写实视频，但显存只够 1.3B，清晰度、时长和人物锁定仍低于即梦成片。

权重未装好时，退回 DreamShaper 8 + AnimateDiff，每镜一段插画动画，只播放一次。

支持 10/30/60/90 秒成片、最长 60000 字输入、先审核或自动继续、保存中间产物和失败后继续已完成镜头。长文本分块处理，不上网寻找正文。成片不配音。原文摘录可在分镜中编辑，但不会被念出来。视频模型读中文分镜；插画动画只读很短的英文提示词。

不保证人物跨镜头完全同脸，不包含口型同步、多人独立配音、背景配乐或长时间连续动作。固定画风和种子不等于身份锁定。文本模型也可能误解古文，应在正式制作前审核分镜。单段输入覆盖范围由用户选择，短视频不可能逐字展现长章节。

## 暂停和退出

关闭浏览器不会结束后台服务。“暂停”会阻止后续生成；已经交给 ComfyUI 的当前镜头可能继续完成，以便恢复时复用。不要关闭电脑后期待任务继续运行。重新启动页面可查看保留的任务。生成时不要同时在 ComfyUI 手工提交其他大型任务。

## 常见问题

- 环境状态不全：查看 `.local/comfyui-error.log`；模型需要完整下载并校验。
- 任务失败：页面显示原因，详细日志在对应任务文件夹。分镜失败可重新编写；生成失败可从已有分镜继续。
- 画面不理想：先修改分镜里的中文 `prompt`，修改后对应镜头会重新制作。
- 视频模型：`python scripts/download-wan.py` 从 ModelScope 下载 Wan 2.1 1.3B，校验后重启生成服务才会出现在环境状态里。
- 显存不足：关闭其他占用显卡的软件；本机启动器已启用低显存模式。
- 界面无法连接：重新双击启动文件；页面服务使用 7860 端口，生成服务使用 8188 端口，均仅绑定本机。

## 开发入口

`app/server.py` 提供页面、任务状态、真实 ComfyUI 请求和视频合成；`app/planner.py` 在独立进程中执行本地文本模型。模型退出后释放显存，再生成镜头。`scripts/run-local-comfyui-pipeline.ps1 -TextFile <正文路径> -Duration 10 -Automatic` 通过同一接口提交任务。

下载脚本保留断点并做 SHA256 校验。`.local/` 和 `media-tasks/` 不进入 GitHub；换电脑时需要重新安装环境与模型。代码与生成材料的使用分别遵循仓库许可证和各模型许可证。

上游：[ComfyUI](https://github.com/Comfy-Org/ComfyUI)、[Wan 2.1 1.3B](https://www.modelscope.cn/models/Comfy-Org/Wan_2.1_ComfyUI_repackaged)、[AnimateDiff 扩展](https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved)、[Stable Diffusion 1.5](https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5)、[AnimateDiff 模型](https://huggingface.co/guoyww/animatediff)、[Qwen3-4B-Instruct](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)。分镜文本模型优先用这一版；显存不够时仍可退回已安装的 Qwen2.5-3B。
