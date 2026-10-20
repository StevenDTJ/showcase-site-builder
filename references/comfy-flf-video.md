# comfy-mcp 首尾帧视频生成规范

所有视频资产通过 comfy-mcp 工具以首尾帧（FLF2V / first-frame-last-frame）方式生成。先生成/准备好首尾两帧图像，再让视频模型在两帧之间插值出运动。

**导演层面的分镜与转场规范（一段一镜、首尾帧焊接、隐喻链）见 [film-language.md](film-language.md)，生成前必读。**

## 前置检查

1. 调 `mcp__comfy-mcp__server_info` 确认本地 ComfyUI 在运行、comfy-cli 兼容；`freshness` 提示核心或节点过期时先提示用户更新。
2. 未运行则 `mcp__comfy-mcp__launch_comfyui` 启动；硬件 VRAM 不足时用 `mcp__comfy-mcp__system_stats` 确认，必要时改用托管模型路线。
3. 本地模板路线免费（跑本地硬件）；托管 partner 模型路线消耗 Comfy 额度——**必须用户明确同意后**才在 `partner_generate` / `run_template` / `run_workflow` 上设 `confirm_spend: true`。

## 第一步：准备首尾帧

- 来源：Midjourney 浏览器自动化生产的帧图（见 asset-acquisition.md 的「首尾帧配对」）。首帧与尾帧是**不同的主体或场景**（MJ 无法稳定复现同构图），两者共享风格锚点与线索物固定描写句；两帧画幅必须与目标视频一致（展示网页 hero 通常 16:9）。
- 段间共享的边界帧必须复用同一图片文件（A 段尾帧 = B 段首帧 = 同一文件），绝不分别生成。
- 用 `read_image` 逐一检查两帧：确认两帧之间存在可读的转化路径（推近细节、线索物延续、明度/色温衔接）——突变过大、毫无关联的两帧插值容易崩坏。
- **不要用 `mcp__comfy-mcp__generate_image` 生产本站的图片资产**——它只用于纯技术打样（试工作流、试分辨率），产物不进页面。图片资产一律走 Midjourney 自动化（见 asset-acquisition.md 开头「唯一路线」）；本文件不构成对该原则的例外。

## 第二步：上传与选路

```text
mcp__comfy-mcp__upload_file(paths=["C:/abs/path/first.png", "C:/abs/path/last.png"])
```

路径必须为本机绝对路径。上传后文件名即 ComfyUI input 目录中的引用名。

**路线 1：本地 FLF2V 模板（免费，优先）**

```text
mcp__comfy-mcp__search_templates(query="first last frame")   # 或 "wan flf2v" / "video"
mcp__comfy-mcp__get_template(name=<选中的模板>)               # 看 local_check.runnable
mcp__comfy-mcp__fetch_template(name=<模板>, out_path="C:/work/flf.json")
mcp__comfy-mcp__list_workflow_slots(workflow_path="C:/work/flf.json")
mcp__comfy-mcp__set_workflow_slot(workflow_path=..., overrides=[...])  # 设首帧/尾帧文件名、prompt、时长
mcp__comfy-mcp__validate_workflow(workflow_path="C:/work/flf.json")
mcp__comfy-mcp__run_workflow(workflow_path="C:/work/flf.json", wait=false)
mcp__comfy-mcp__job(action="wait", prompt_id=..., timeout_seconds=600)
mcp__comfy-mcp__fetch_outputs(prompt_id=..., out_dir="项目/assets/video/")
```

`local_check` 报告缺模型时用 `mcp__comfy-mcp__search_models` 先查本地是否已有（避免重复下载数 GB），缺节点用 `workflow_deps` + `install_node`（安装第三方节点前向用户说明），然后 `restart_comfyui`。

**路线 2：托管模型（消耗额度）**

```text
mcp__comfy-mcp__list_partner_models(query="video")           # 找支持首尾帧的模型
mcp__comfy-mcp__partner_model_schema(model=<alias>)          # 确认有 start/end frame 参数（binary=本地文件路径）
mcp__comfy-mcp__partner_generate(model=<alias>,
    params={"prompt": "...", "start_frame": "C:/abs/first.png", "end_frame": "C:/abs/last.png"},
    out_path="项目/assets/video/", confirm_spend=true)        # 仅用户同意后
```

参数名以 `partner_model_schema` 的实际返回为准，不要凭猜测填。

## 生成配置基线（本地 NanFeng H3 节点，实测可用）

模型与编码器：

- 主模型 `minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors`（FL2VA/Ref2VA 混合，int8）
- 文本编码器 `qwen3vl_32b_minimax_h3_int8_convrot.safetensors`（类型 minimax）
- 视频 VAE `H3\minimax_h3_video_vae_fp16.safetensors`；音频 VAE `H3\minimax_h3_audio_vae_fp32.safetensors`

生成开关与采样：

- `首尾帧 = True`（文生/图生视频均 False）；图片1=首帧、图片2=尾帧；`参考图尺寸 = match`、`参考图最长边 = 1920`
- 画面比例 16:9；**百万像素 = 0.7**（生成分辨率压到 0.7MP 提速，再由 DLSS 超分补到目标尺寸）；时长 4–6 秒
- 采样器 `er_sde` + 调度器 `simple`，采样步数 10，降噪强度 1
- **DLSS 超分模式开启**，倍率按目标分辨率选。**倍率不要凭算式推**——0.5MP 时代的台账就记错过（0.5MP 16:9 ≈ 943×530，2× 只有约 1886 宽，根本到不了它自己写的 1920×1088）。按你想要的交付尺寸选倍率，再用 `ffprobe` 复核产物实际宽高，把实测值记进资产台账；实测 0.7MP 档位可到 **2240×1280**。需要完整版 ffmpeg（含 ffprobe）在 PATH，见排错
- **Sage 加速开启**：`SageAttention = auto`、`H3专用注意力 = H3专用Sage加速`
- **TRT 加速开启**：`启用TRT视频VAE = True`，且**必须同时选择引擎文件**——`TRT视频解码引擎 = minimax_h3_vae_decoder.engine`、`TRT视频编码引擎 = minimax_h3_vae_encoder.engine`（选项来自本机已编译的 .engine 文件；留 `None` 会直接报"请先选择本机编译的TRT视频decoder.engine"）。若下拉无引擎可选，需先在节点包里编译引擎
- 其余高级项默认关闭：LoRA / SolAttn / T8 缓存 / 双采样 / 高清二采 / 潜空间放大 / SLA / 各类脸部与全局修复

输出（VHS_VideoCombine）：24fps、h264-mp4、yuv420p、crf 23、无音轨；滚动叙事段再转 WebP 帧序列（见第四步）。

## 画廊模板改造：多锚帧 Ref2VA → FL2VA 双锚帧（本地 MiniMax H3 实测）

不走 NanFeng 节点时，可用画廊模板 `video_minimax_h3_multiframe_reference` 改造。该模板是 **4 锚帧 Ref2VA 结构**（首帧 ref_image + 多枚 AddGuide 中间锚帧），改造为 FL2VA 双锚帧的方法：

1. **拆除中段的 AddGuide 节点**，只保留末枚 AddGuide 作为尾帧锚点；
2. 末枚 AddGuide 的 `frame_idx` 接 length 表达式 `a-1`（锚在最后一帧）；
3. **本机模型文件名常与画廊模板不同**，按 `local_check` / `validate_workflow` 报错逐个替换为本机实际文件名——实测差异：VAE 带 `H3\` 前缀（`H3\minimax_h3_video_vae_fp16.safetensors`）、unet 用 int8 版（`minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors`）、挂 FL2V turbo 8 步 LoRA（`minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16`，steps=8 + res_multistep/simple）。

### 显存纪律（16GB 卡实测）

- **基线是 0.7MP**（见上「生成配置基线」）。**0.5MP 是提速退档，不是默认**：实测它省时间但削掉高频细节，本项目为此把 12 段全部按 0.7MP 重跑了一遍（`tools/rerun_mp07.py`）。只有在显存吃紧、愿意用画质换时间时才降档，并明确告知用户这是一次画质交换；
- H3 动态加载约 20GB staged——16GB 卡始终处于临界；
- 带 `--reserve-vram 3.5` 启动时 **10 秒片段会 CUDA OOM**，且 OOM 可使 ComfyUI 进程僵死（worker 在 OOM 后二次崩溃、HTTP 半死不活）——**片段一律用 6s 档、unet 用 int8**；
- **每个任务提交前先 `free_memory` + `system_stats` 确认 `vram_free`**，再 `run_workflow`；
- 同一配置**两次 OOM 后降分辨率**（百万像素 0.7 → 0.5，或再低）重试，不要硬闯；降档后如采用该批产物，记得在交付说明里写明画质代价。

### Windows 启动坑

comfy-cli 的 `launch` 可能误用系统 Python（缺 sqlalchemy 等依赖，起不来）。standalone 安装应直接用其自带启动脚本/内嵌 Python，例如：

```bash
.\python\python.exe -s ComfyUI\main.py --port 8189 --reserve-vram 3.5
```

standalone 版自带完整 ffmpeg（含 ffprobe）在 `tools\ffmpeg\bin\`——DLSS 超分与转码都可指向它，不必另装系统 ffmpeg。

## 第三步：视频提示词（h3-json-director skill + 子代理）

首帧与尾帧是两个不同画面，prompt 必须清晰描述**首帧到尾帧的具体变化过程**：转化路径（推近哪个细节 / 镜头如何运动带出场景转换）、主体微动、节奏。只写"镜头缓慢推近"不够——模型需要知道画面如何从 A 变成 B。

**提示词一律用本地已安装的 `h3-json-director` skill 撰写**（MiniMax H3 官方提示词语义，FL2VA 模式：`<Picture 1>` = 首帧 @ 0.0s，`<Picture 2>` = 尾帧 @ 结尾；产出 `h3-director-json-v1` JSON 并用其自带校验脚本验证）。**通过子代理执行以保持主上下文干净**：启动一个子代理，任务简报中给出——

1. 首帧/尾帧的绝对路径（要求子代理先 `read_image` 检查两帧实际内容，禁止凭文件名推断）；
2. 该段在脚本中的叙事功能、时长（4–6 秒）、画幅；
3. 脚本里写明的转化路径与焊接约束；
4. 要求产出：校验通过的 FL2VA JSON 文件路径。

子代理返回后，把 JSON 作为视频 prompt 填入工作流，JSON 之外不附加其他 prompt 文本。时长 4–6 秒足够滚动 scrub 使用。

## 第四步：转码为 Web 格式

**后期（抽帧 → 段间焊接 → 循环收敛 → 导出 WebP → 编码 → 数值留档）一律用 [../scripts/film.py](../scripts/film.py)，不要手敲 ffmpeg 串。** 它把下面的数值规范实现成了代码，带 `--selftest`（合成序列验证数学，不碰真实素材）与逐段数值留档；段表/尺寸走 `--config`，schema 见脚本 docstring。下面两段裸命令仅作**排查单个环节**时参考。

**循环段（hero/页脚活画）**：导出 mp4，首帧必须等于尾帧（无缝循环）：

```bash
ffmpeg -i input.mp4 -c:v libx264 -preset slow -crf 23 -g 30 \
  -an -movflags +faststart -pix_fmt yuv420p assets/video/loop.mp4
# poster 帧
ffmpeg -i assets/video/loop.mp4 -vf "select=eq(n\,0)" -frames:v 1 assets/video/loop-poster.jpg
```

**滚动叙事段**：导出帧序列而非视频（pear.no 的实际做法，scrub 更顺滑）：

```bash
ffmpeg -i input.mp4 -vf scale=1440:-2 assets/film/section/w1440/f_%03d.webp
# 目录要落在 <segment>/<tier>/ 下（与 starter.html / cdp_shots 的取图约定一致）
# 校验段间焊接：本段末帧与下段首帧应几乎一致
```

⚠️ **上面这两段是参考命令，不是推荐做法**——直接用它们会**绕过焊接/循环收敛**，而且转 WebP 用的是 ffmpeg 默认质量，**丢掉 q94 + 轻度 USM 的锐度策略**（实测平坦画面在低质量下高频会被量化吃掉一半）。正式交付一律用 `scripts/film.py`，它做完整条流水线并按段留数值；只在排查单个环节时用上面的裸命令。

若坚持用视频 scrub，则必须密集关键帧（`-g 4 -keyint_min 4`）保证任意帧可快速解码。视频一律静音，不加音轨（`-an`）。

### 焊接与循环收敛的数值依据（为什么必须做）

- **FL2VA 两次独立运行的端点帧并非像素一致**：同一张首帧图经两次生成的末帧/首帧，实测 mean abs diff 1.5–15.9（VAE 重建 + 细节抖动，随画面细节量变化，集中在纹理边缘）。所以段间焊接**不能只靠"两张图看起来一样"，必须执行共享帧文件复用**：取一段的末帧文件直接作为相邻段的首帧（帧序列里直接替换第 1 帧），并向自然帧做 ~6 帧渐变混入（`blend(shared, natural[i], i/6)`），消除替换处的跳变。
- **循环段** raw 输出的首末帧差可达 ~17（实测 17.07，主因画面元素呼吸亮度差）：**尾部 ~12 帧向首帧交叉溶解收敛 + 末帧=首帧精确拷贝，并先裁掉尾部冻结静帧**（相邻帧 diff < 0.05 即冻结尾帧）。目标首末帧 mean abs diff ≤ 3（实测可从 5.12 / 17.07 收敛到 1.29 / 2.17）。
- **判据不要用"收敛后首末 diff"**：末帧是首帧的精确拷贝，那个数按构造恒为 0，拿它做验收等于没验（`film.py` 早期版本就是这样，`--converge-max` 只在负数时才可能触发）。要比的是**溶解斜坡（与焊接斜坡）的最大逐帧跳变**——斜坡平滑，接缝就不跳。`film.py` 现在留档的就是这个量。
- **顺序纪律（三条，都是踩坑换来的）**：① **循环段先处理**——前端是从首页活画**交叉淡化**进第一段帧序列的，接缝两侧必须是同一画面，所以要用循环段的首帧去焊第一段的首帧；第一版把循环段放最后，第一段首帧一直没人焊，淡化处可见跳变。② **跳跃处理时仍要推进焊接链**，否则只跑 `--seg s5` 会焊到错误的"上一段末帧"。③ **焊接/收敛必须在提取出的 PNG 上做**，不能在已编码的 WebP 上做——混入会被二次压缩污染。
- 校验用 mean abs diff（numpy 逐像素均值），焊接点与循环段的实测数字写进资产台账。

## 排错

- `ffmpeg/ffprobe: command not found`：配置基线开启了 DLSS 超分，它依赖完整版 ffmpeg（含 ffprobe）在 PATH。实测可用装法（winget/GitHub 直连在本机网络下均失败）：从 ghfast.top 镜像下载 BtbN 静态构建 `https://ghfast.top/https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip`（curl 加 `--ssl-no-revoke`，支持 `-C -` 断点续传），解压 bin 下的 ffmpeg/ffprobe/ffplay 到 PATH 目录（如 `C:\Users\1345\bin`），装完**重启 ComfyUI** 让它继承新 PATH。imageio-ffmpeg 自带的二进制只含 ffmpeg 不含 ffprobe，不能替代。
- 任务失败：`mcp__comfy-mcp__job(action="error", prompt_id=...)` 看错误节点；进程崩溃（OOM）：`mcp__comfy-mcp__get_logs`，然后降分辨率/时长重试。OOM 后 ComfyUI 可能进程僵死（worker 二次崩溃、HTTP 半死），此时 `stop_comfyui` + 重启，不要继续往半死的实例提交任务。
- 转码工具链：无系统 ffmpeg 时用 standalone 自带的 `tools\ffmpeg\bin\ffmpeg.exe`；**cv2.imwrite 不支持中文路径**（静默失败）——用 `cv2.imencode` + `buf.tofile()` 绕（读用 `cv2.imdecode(np.fromfile(...))`），但帧序列/转码优先直接用 ffmpeg，少一道 cv2。
- 两帧差异过大导致形变崩坏：缩短时长、简化转化路径（如改用推近细节过渡），或更换其中一帧为转化路径更可读的画面——不要试图把尾帧重制成"接近首帧"（异场景设计是有意的）。
- 缺额度/未登录：`mcp__comfy-mcp__auth_status` 检查，需要时 `mcp__comfy-mcp__auth_login` 引导用户登录。
