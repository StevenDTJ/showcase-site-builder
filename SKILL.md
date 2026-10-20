---
name: showcase-site-builder
description: Build pear.no-style showcase / marketing websites (展示性网页、品牌官网、工作室网站) with a letterpress-prospectus design language, scroll-scrubbed video, neoclassical imagery, and misregistered halftone typography. Covers the full pipeline — art direction, asset acquisition (image assets produced exclusively through automated Midjourney browser driving via CDP, plus first-frame/last-frame 首尾帧 video generation via ComfyUI comfy-mcp), and front-end implementation. Use when the user asks for a pear.no-like site, an awwwards-style showcase page, or a cinematic scroll-driven brand site.
---

# Showcase Site Builder (pear.no 风格展示性网页)

构建 pear.no 一类的展示性网页：以"活版印刷招股书"为设计语言——新古典主义油画图像、错位套印（misregistered）半调字体、滚动驱动（scroll-scrubbed）的影片段落、克制的交互与戏剧化的排版节奏。桌面优先、单页叙事、横向/纵向混合滚动均可。

本 skill 覆盖完整流水线：艺术方向 → 资产规划 → 资产获取（Midjourney 浏览器自动化生产图片 / comfy-mcp 首尾帧生成视频）→ 前端实现 → 验收。

## 工作流程

按以下阶段推进，每个阶段产出可检查的交付物：

### 1. 定位、艺术方向与叙事结构

先确定：品牌/主题、一句话主张（像 pear.no 的 "Pear makes you appear"）、目标受众、语气。然后把站点拆成 4–7 个叙事段落，典型结构：

1. **Hero** — 大标题 + 全屏背景图或循环视频；
2. **宣言（Manifesto）** — 大字排版逐行显现，阐述主张；
3. **滚动影片** — 一段首尾帧生成的视频，由滚动进度驱动播放（scroll-scrub）；
4. **服务/作品陈列（Spread）** — 类似 pear.no 的 "Gilding the pear" 服务版面，不对称网格；
5. **案例/证据** — 图片拼贴 + 短文案；
6. **申请表单 / CTA** — pear.no 的 "application" 段；
7. **页脚 + 彩蛋** — 例如趣味 404。

为每个段落写一行"功能 + 所需资产"说明，形成叙事大纲。大纲里同时给出**"节拍 ↔ 影像"对照表**：每一段叙事文字各自对应哪一帧 / 哪一段运镜——两段文字指向同一帧就是错的（见 §1a）。

#### 1a. 故事板写作必须坚持"影像驱动叙事"：一段文字，一帧属于它的画面（本项目踩坑，反面教材）

**影像驱动叙事 = 每一段叙事文字都由它自己的画面承担**（新的帧、新的运镜、新的构图）。**禁止一张图当两段以上文字的背景板**——同一帧 ID、同一活画循环、同一 `data-frames` 区间，只能承载一段文字；否则影像没有为每个节拍生产画面，是文字在替影像推进叙事。

- **反面教材（本项目实测）**：首屏那张 **F00 活画被复用成了三幕文字的背景**——
  1. 幕 1 hero 标语（`data-video="hero"` ⇄ L01 活画循环 = F00）："让差异成光，让匹配成弦"；
  2. 幕 2"三十秒档案"（`data-frames="0,0" data-hold="0,0"`，**定格在 F00**）："三十秒的档案 / 以数字归档……"；
  3. 幕 3 宣言（`data-frames="0,123" data-hold="0,14"`，V01 首帧**仍是 F00**，文字落在 hold 0–14 上）："先理解人 / 再设计系统"。

  **一段动画承载了三段文字叙事**——这正是违反影像驱动叙事的地方（用户原话：首页那段动画承载了开头标语、三十秒档案、先理解人再设计系统等多段文字）。
- **判定法则**：逐幕列出（幕序、文字块、背景帧 ID / `data-frames` 区间）。**同一个帧 ID 出现在两幕以上的文字背景上即违规**；页面实现层表现为 `data-hold` / `data-frames` 的定格区间被相邻两幕的文字共用或交叠。
- **修法二选一**：给这个节拍**补一帧画面/一段运镜**（让画面自己说出这句话——可以是新生成的帧，也可以是本段内尚未被文字占用的区间），或者**删掉这段文字**（它说的往往就是相邻幕的同一件事）。**不要**靠调字号、压行数、改落位来"解决"。
- **共享帧的唯一合法用途是焊接边界**（前段末帧 = 后段首帧）：焊接复用的那一帧上，文字只能属于焊接点所属的**一段**，不能被前一段、后一段同时挂上文字。
- **分镜阶段就出表**：故事板交付时必须带"节拍 ↔ 帧"对照表，每个节拍指向一个**独有**画面；QA 阶段按表逐幕复核，出现一图多文即不合格（见 §6 与 pear-design-language.md「少即是多」第 2 条）。

#### 1b. 配色方案与视觉基调必须和用户商量后定（不得单方面拍板）

**agent 不得自行决定配色方案与视觉基调。** 在写第一行 CSS 设计 token 之前（也就是在提示词里把色调固化之前）：

- 给出 **2–3 套完整配色方案**——纸底色 / 墨色 / 强调色、明度策略（亮字压暗区还是墨字压亮区）、冷暖倾向、半调与双色化（duotone）处理；
- **停下让用户拍板**，选定后才写进 `:root` 变量、写进图片提示词的调色句和视频脚本；挑定结果与时间记进项目文档（如 `docs/art-direction.md`）；
- 这与 §3 第 0 步的"风格校准 A/B/C"是**同一轮**用户决策：把媒介方向与配色基调**一起**摆给用户选，不要先自己定色再补问；
- **⚠️ 不要为了对比专门做页面。** 不要写 HTML/CSS mock、不要搭一个"单页展示性"的样张页给用户看。对比物就是**风格校准产出的真实画面**（Midjourney 原始出图，见 §3 第 0 步的横向对照图）。理由不只是慢：自己搭页面等于引入**第二层变量**——版式、字体、留白全都是 agent 的选择，会盖过配色本身，用户最后分不清自己是在选色调还是在选版式。判据应当是真实像素（网点、套准、纸张、明度），不是 CSS 近似出来的效果；
- 已经做完才意识到没问过的：如实说明当前配色与成因，给出可选替代方案，请用户确认或改。

### 2. 资产台账（Asset Ledger）

维护一份资产台账，逐项记录：用途（hero 背景 / 影片首尾帧 / 陈列图）、来源（MJ 自动化任务 id / comfy 视频）、状态（待生成 / 已回收 / 已检查 / 已处理）、本地路径。不要凭文件名推断未检查的资产内容——每张图都必须用图像读取工具（`read_image` / `view_image`）看过实际像素。

**目录分工**（实测确立，别混用；全尺寸原图与页面用图必须分开放，否则"原图"会被压缩产物覆盖且无法重导出）：

| 目录 | 放什么 |
|---|---|
| `assets/src/` | **全尺寸定稿原图**（挑选后的 PNG；候选图另存 `assets/src/alt/`） |
| `assets/img/frames/` | 影片首尾帧的页面用 WebP（一帧一图） |
| `assets/img/plates/` | 陈列图的页面用 WebP |
| `assets/film/<segment>/<tier>/f_001.webp` | 滚动叙事段的**帧序列**（按视口宽度分档，如 1440/768） |
| `assets/video/` | 循环段 mp4 + poster |

### 3. 图片资产获取（唯一路线：Midjourney 浏览器自动化）

**图片资产只通过自动化驱动 Midjourney 网页版生产，不经人工中转，也不爬取第三方网站。** 完整机制与坑位见 [references/asset-acquisition.md](references/asset-acquisition.md)，参考实现 [templates/mj-browser-automation.py](templates/mj-browser-automation.py)。闭环：

0. **先定风格**：正式写全量提示词之前，用同一个替身画面跑**三种参考方向**（只让"媒介 + 空间"这一个变量变化），拼成横向对照图，**停下让用户选一个**（A/B/C）——风格锚点一旦批量开跑就很难回头。机制与典型三方向见 asset-acquisition.md「风格校准」。**同一轮必须把配色方案与视觉基调（§1b）一起交给用户拍板**：三条方向各自带着一套候选色板与明度策略，用户同时选媒介与色调。**对照物是这三条方向的真实出图，不是 agent 另做的 HTML/CSS mock 页面**（§1b 末条）；选定前不要写死提示词里的调色句，更不要写 `:root`；
1. 按叙事大纲与视频脚本写提示词——遵守 asset-acquisition.md 的「提示词规范」（风格锚点共享、媒介质感、光线、`--ar`）与「构图与留白」规范（平静区、主体偏移、明度分区、overscan）；
2. CDP 连接受控浏览器（独立 Chrome profile，不占用用户日常浏览器），`Input.insertText` + `dispatchKeyEvent` 可信输入提交提示词——Enter **必须带 `text="\r"`**；**不要点击发送按钮**（作曲框里没有，误点会抢焦点并使 Enter 失效）。提交成功的判据是**双判据**：输入框清空 **或** 出现新 jobid；两档都失败就硬清空输入框并如实报错，绝不留下残留文字（否则下一条提示词会被拼接）；
3. **按新出现的 jobid 认领任务**（不是按提示词文本匹配——本 skill 的提示词共享风格锚点前缀、卡片文本又被截断，文本匹配必然抓错），等齐 4 张；
4. 页面上下文 fetch → base64 回收**全尺寸 PNG**（需退避重试，全尺寸延迟就绪）——候选先落 `assets/src/alt/`，挑定后再收档为 `assets/src/`；
5. **逐张检查**（用 `read_image` / `view_image` 读实际像素，不要凭文件名推断）：机位、光线、主体位置、留白区是否符合脚本与设计要求；不合格就修订提示词重跑，不带病进入下游；
6. **每组 4 张标号让用户挑定**：拼带大号编号徽章（0–3，即文件名下标）的 2×2 对比图，徽章同时标出「全尺寸 / 预览(640)」；用户挑定后写进 `docs/qa/picks.json` 再收档。**不要替用户选**，也不要只用文件名报图让用户猜。格式见 asset-acquisition.md「候选挑定」。

前提条件：用户已在该受控 profile 中登录 Midjourney 并授权自动化。未登录时引导用户完成登录后再继续，不得回退到"把提示词交给用户手动生成"的人工中转流程。

图像获取后统一处理：转 WebP/压缩、生成半调/雕刻质感变体（可用 CSS 叠加实现，不必烘焙进图片）。

### 4. 视频资产获取（comfy-mcp 首尾帧 + scripts/ 里的后期工具）

**强制顺序：先交付视频脚本与参考图提示词，再碰 ComfyUI。** 任何视频生成之前，必须先向用户提交两份东西：

1. **视频脚本**：按 film-language.md 原则写成转场链故事板——每段一行：首帧画面 → 尾帧画面、段内变化（首帧到尾帧的具体转化过程：转化路径 + 摄像机运动 + 主体微动）、隐喻功能、时长（4–6 秒）、与前后段的焊接点（前段末帧 = 后段首帧 = **同一张图片文件**，共享帧只生成一次）；循环段注明首帧=尾帧。脚本还须标注：**每段采用的转化策略**（推近变形 / 运动转化——不用"同画面双状态"，MJ 无法稳定复现同构图，每帧必须是不同主体或场景）、**贯穿全片的线索物及其固定描写句**、**每帧的文字落位区**（左/右、明度方向），供提示词设计构图（规范见 asset-acquisition.md「构图与留白」）。
2. **参考图提示词**：为脚本中每一个独立首尾帧写一条 Midjourney 提示词。每帧是不同的主体或场景；全部帧共享同一段"风格锚点"文字（媒介质感、光线方向、色调、透视）与线索物固定描写句——跨帧一致性靠锚点维持，不靠场景复制。规范见 [references/asset-acquisition.md](references/asset-acquisition.md) 的"首尾帧配对"。

脚本与提示词交付后，按 §3 的 MJ 自动化闭环逐帧生成并回收到 `assets/src/`，收档为页面用 WebP 放 `assets/img/frames/`，逐张用 `read_image` 检查：机位、光线、主体位置、帧对转化路径是否与脚本要求一致；不一致就修订提示词重新生成，不要带着错配的帧进 FLF2V。

**视频提示词用 `h3-json-director` skill 撰写，派子代理执行。** 帧图齐备后，为每一段启动一个子代理运行本地已安装的 h3-json-director skill（MiniMax H3 官方提示词语义，FL2VA 模式），产出校验通过的 `h3-director-json-v1` JSON 作为该段的视频 prompt——必须清晰描述首帧到尾帧的具体变化过程。子代理简报与交接规范见 [references/comfy-flf-video.md](references/comfy-flf-video.md) 第三步。用子代理是为了把 H3 skill 的大量规范文本隔离在主上下文之外。

视频一律通过 comfy-mcp 以**首尾帧（first-frame / last-frame, FLF2V）**方式生成，工具流程见 [references/comfy-flf-video.md](references/comfy-flf-video.md)。**导演规范先读 [references/film-language.md](references/film-language.md)**——它是对 pear.no 全部影片资产逐帧分析后的总结，核心原则：

- **一段一镜，没有硬切**：pear.no 的影片全是单一构图的连续镜头；"切镜"由摄像机运动（推近细节变成下一场景、拉远揭示"这是纸上的一张图"）和**首尾帧焊接**（前段末帧 = 后段首帧）完成；
- **每段一个隐喻主体**，全片构成商业模式/品牌故事的寓言链（参考 pear.no：嫁接→成树→金梨→切半分梨=收益分成）；
- **hero/页脚用"活画"循环**（10 秒无缝 loop、构图不动、只有环境微动），滚动叙事段用帧序列而非视频 scrub；
- **印刷缺陷进入影像内部**：半调网点的云、棋盘格水流、彩虹色差——与排版层的错位套印同一世界观。

执行要点：

1. 视频脚本 + 参考图提示词已交付，帧图已经 MJ 自动化生成、回收并逐张检查，每段已有子代理产出并校验通过的 h3-director-json-v1 视频提示词（见上）；
2. `upload_file` 上传帧图 → 选定本地 FLF2V 工作流/模板（或 `partner_model_schema` 确认托管模型的首尾帧参数）→ 填入对应段的 H3 JSON 作为 prompt → 校验 → 运行 → `fetch_outputs`；
3. 循环段导出 mp4（首帧=尾帧），滚动叙事段导出帧序列（`f_001.webp` 编号）；ffmpeg 命令见 comfy-flf-video.md。

**后期（焊接 / 循环收敛 / 转码 / 数值留档）不要手敲 ffmpeg 串**，用 [scripts/film.py](scripts/film.py)——段表与尺寸走配置，把 `comfy-flf-video.md「焊接与循环收敛」` 的数值规范实现成了代码：

```bash
python scripts/film.py --selftest                      # 合成序列验证数学，不碰真实素材
python scripts/film.py --config docs/film-config.json --all
python scripts/film.py --config docs/film-config.json --seg s4
```

它强制三条顺序纪律（都是踩坑换来的）：**循环段先处理**（否则第一段首帧没人焊、首页活画交叉淡化处会跳变）、**跳跃处理某段时仍推进焊接链**、**链首**可配 `"loop"` / 指定图 / `"none"`。配置文件 schema 见脚本 docstring；本项目现成的配置是 `docs/film-config.json`。

**留档里的数是"斜坡最大跳变"，不是"收敛后首末 diff"**——末帧是首帧的精确拷贝，那个数按构造恒为 0，用它验收等于没验。判据看溶解斜坡（与焊接斜坡）的逐帧台阶：斜坡平滑，接缝就不跳。退出码 1 的含义是**有循环段斜坡没收敛 / 有段编码失败 / 有段缺输入**（最后一条加 `--allow-missing` 可豁免）。

**显存纪律（16GB 档显卡）**：片段用 6s 档 + int8 模型，每个任务提交前 `free_memory` + `system_stats` 确认 `vram_free`，两次 OOM 后降分辨率而非硬闯——详见 comfy-flf-video.md「显存纪律」。

若 comfy-mcp 不可用或 ComfyUI 未运行，先 `server_info` 检查，必要时 `launch_comfyui`，并把阻塞情况如实告知用户。

### 5. 前端实现

技术基线：单页静态站点（`index.html` + 少量原生 JS），GSAP + ScrollTrigger（CDN 起步，**交付前本地化**）驱动滚动叙事，可选 Lenis 平滑滚动或自实现 lerp 惯性滚动。不引入构建链，除非用户要求。设计语言规范（配色、字体、半调纹理、错位套印、动效、响应式与降级策略）见 [references/pear-design-language.md](references/pear-design-language.md)。可从 [templates/starter.html](templates/starter.html) 起步——它是"全页影片舞台"骨架：固定舞台层（两个活画循环 + 帧序列 canvas）+ 声明式时间轴（`data-seg` / `data-video` / `data-in`）+ 帧序列 renderer（按 820px 选档，帧数按 404 探测自动推导，不需写死）。

硬性要求：

- **设计 token 只能来自用户拍板的艺术方向**：`:root` 里的纸底/墨色/强调色必须逐条对应 §1b 用户选定的方案（选中的对照图与决策记进 `docs/art-direction.md`），**禁止**在前端阶段"顺手调一版更好看的配色"；确需偏离就在改动前再问一次用户；
- **一段文字一帧画面（一图一文）**：实现前先核对"节拍 ↔ 影像"对照表——同一帧 ID（活画循环的 F 帧，或某段的定格帧）**不得作为两幕以上文字的背景**；发现 `data-hold` / `data-frames` 的定格区间被相邻两幕文字共用或交叠，**回故事板补画面或删文字**，不要在 CSS 里挪位置、压字号掩盖；
- **全页影片舞台架构**（pear-design-language.md 有专节）：影片是 `position: fixed` 的底层舞台贯穿整页，内容 section 透明覆盖其上随滚动表演；**禁止**把影片做成中段一个孤立的 scrub section——那会让影片与其他内容割裂。每个 section 用 `data-seg="s1"`（滚动映射到该段帧序列）/ `data-video="hero|footer"`（切回对应活画循环）/ 皆无（定格在上一段末帧，注意冷启动吸附）声明自己的影片角色；**帧号每段各自从 `f_001` 起**，不要写全站绝对帧号——每段帧数由后期导出决定，写死必然错位；
- **hero/页脚循环段**用 mp4：`muted playsinline preload="auto"` + poster；**滚动叙事段优先用帧序列**（WebP `f_001.webp` 编号 + `new Image()` 预取相邻帧，滚动进度映射帧号绘到 `<canvas>`）——这是 pear.no 的实际做法，比 `video.currentTime` scrub 更顺滑；资产不足时退回视频 scrub（转码需密集关键帧）；
- 段落衔接处按 film-language.md 的首尾帧焊接原则排布，允许用 CSS/Canvas 叠加噪点、色差、溶解过渡模拟 pear.no 的 shader 转场层；
- 错位套印标题用两层文字 + `mix-blend-mode` 实现，禁止用图片代替可索引的标题文本；
- 所有图片有 `alt`，视频有 poster 与字幕/说明（如适用）；
- 资产路径全部相对化，页面离线打开可用（CDN 除外，需在交付说明中注明）。

### 6. 验收清单

交付前逐项确认：

- [ ] 台账中每项资产已落地到 `assets/` 并在页面中引用，每张图片已经用 `read_image` / `view_image` 逐张看过实际像素；
- [ ] 影片符合 film-language.md 原则：一段一镜无硬切、段间首尾帧焊接（已用像素对比校验）、循环段首帧=尾帧无跳变——**循环段首末帧 mean abs diff ≤ 3，各焊接点差值实测数字已记入资产台账**（实测数值与收敛方法见 comfy-flf-video.md「焊接与循环收敛」）；
- [ ] **影像驱动叙事逐幕审查（一图一文）**：列出每幕文字所依赖的帧 ID / `data-frames` 区间，确认**没有两段文字共用同一帧**——本项目实测失误是 F00 活画同时承担了 hero 标语、"三十秒档案"、宣言"先理解人，再设计系统"三段文字；出现一图多文即不合格，回故事板补画面或删文字（见 §1a 与 pear-design-language.md「少即是多」第 2 条）；
- [ ] **配色与视觉基调经用户拍板**：`:root` 每个色值都能对回用户在 §1b/§3 第 0 步选定的方案，`docs/art-direction.md` 记有候选方案、用户选择与时间；无用户拍板记录即不合格；
- [ ] **少即是多逐帧审查**：QA 逐帧（不只段首段尾）确认文字不遮画面主体、落位随帧区间让位换位置、一幕一观点（规范见 pear-design-language.md「少即是多」）；
- [ ] **版式与画面呼应逐幕审查**：每个文字块都能指认与背景构图的具体关系（边缘/基线对齐、左右对话、动线衔接、明暗反用），无一处脱离画面孤立摆放（规范见 pear-design-language.md「少即是多」第 1 条）；
- [ ] 滚动叙事段用帧序列（或密集关键帧视频），scrub 流畅无黑帧；循环段 mp4 无缝；
- [ ] 页面在本地直接打开（或 `python -m http.server`）完整渲染，无 404 资源；
- [ ] 逐幕截图验收：无头 Chrome 的 `--screenshot --virtual-time-budget` 对 rAF/按需加载的页面不可靠（会抓到全黑的中间态），要用 CDP（`--remote-debugging-port` + websocket）按真实时间滚动、等待、截图——直接用 [scripts/cdp_shots.py](scripts/cdp_shots.py)（共享核心 [scripts/cdp.py](scripts/cdp.py)）：

  ```bash
  python scripts/cdp_shots.py --url http://127.0.0.1:8137/ --acts act-s1,act-s4 --out docs/qa --tag smoke
  python scripts/cdp_shots.py --url http://127.0.0.1:8137/ --frames 0,120,240 --out docs/qa --tag f
  ```

  它已封装必须做的几件事：**防遮挡冻结旗帜**（窗口被遮挡时 rAF 完全冻结，截图全是过期状态）、**开跑前不复用残留实例**（复用同一 profile/端口会连到旧标签页、截出上一版页面；要连自己已开的窗口才加 `--reuse`）、**整棵进程树收尾**（只杀启动器会留僵尸实例）、**关缓存**（复用 profile 时 Chrome 拿旧 CSS/JS，验收到的其实是上一版）、**显式设备度量**（`--window-size` 不等于视口尺寸）。逐幕落点按**滚动进度** `offsetTop + (offsetHeight - innerHeight) * p`（`--progress`，默认 0.45）——用「section 高度的百分比」会随视口高度漂移，窄屏下越过让位窗口截到空幕；页面有 JS 报错或失败请求时**退出码为 1**（`--no-fail-on-error` 可关）；项目专属的全局状态用 `--probe "<js>"` 读、就绪判据用 `--ready-js` 收紧（默认只看 `readyState`）。坑位背景见 pear-design-language.md「CDP 截图验收坑位」；
- [ ] 标题层叠、半调纹理、滚动叙事节奏符合设计语言规范；
- [ ] `prefers-reduced-motion` 下降级为静态版式；
- [ ] **文字进出场必须用脚本量，不能靠肉眼看截图**（本项目返工五轮的教训）。要量两件互不冲突的事，缺一条都不合格——两个脚本已随 skill 提供，直接跑：
  - **位移**：[scripts/measure_text_motion.py](scripts/measure_text_motion.py)——在**真实交互模式**下给一次真滚轮推进，按帧记录视口坐标直到停稳，**可见期间位移 ≤2px**。⚠️ **不要用 `?smooth=0` 之类把 `scrollY` 钉死的调试钩子**：用户用的是惯性滚动，文字位移恰恰发生在滚轮停手后的滑行里，钉死后该量**恒为 0**。脚本已内置三条必需纪律：块**与块内每一行**分别量（行盒遮罩会让行在动而块不动）、找不到可见区间自动收紧推进量（采到 0 个可见样本就是**假清白**）、扫描式定位可见窗口而不是猜 `offsetTop`；
  - **动画还在不在**：[scripts/audit_reveal_feel.py](scripts/audit_reveal_feel.py)——可见度必须**经过中间值**（不是 0→1 一跳），且同一时刻各元素的可见度要**拉开差距**（逐项错开）。修"零位移"时极易把动画一起修没。
  完整成因表（7 条）、可抄的 `--vis × --ev` 实现、位移预算，见 pear-design-language.md「分幕文字动画：巡游式退场的完整错误与修法」；
- [ ] 向用户说明：哪些图片由 MJ 自动化生成（提示词可复查）、哪些视频由 comfy 生成及消耗情况。

## 边界

- **不爬取第三方网站的图像资产**；图片只走 MJ 浏览器自动化一条路。MJ 自动化属于 ToS 边缘行为，开始前向用户如实说明，并确认用户已在受控 profile 登录、明确授权；自动化消耗用户账号的 fast hours，批量生成前告知规模。
- 不动用户的日常浏览器：自动化只用独立 Chrome profile + 独立调试端口；用户未登录时引导登录，不尝试绕过或代填凭据。
- 不擅自消耗 Comfy 额度：`confirm_spend` 仅在用户明确同意后设置（自动权限模式下沿用该原则，付费调用前先向用户说明）。
- 不用 pear.no 的实际素材、文案或商标复刻该站本身；借鉴的是设计语言，不是内容。
- **不擅自定配色方案与视觉基调**：色板、明度策略、强调色必须由用户看过**真实出图**后拍板（§1b）；没有用户决策记录就不进入前端与图片批量生成。**但也不得为了对比去搭 mock 页面**——对比物是真实出图（§1b 末条）。
- **不擅自把叙事塞进文字**：坚持影像驱动叙事（一段文字一帧属于它的画面）；一句话找不到属于它的画面时，解法是补画面/改分镜，**不是把文字挂到已有的一张图上**。
