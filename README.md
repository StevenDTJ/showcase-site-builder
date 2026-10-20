# showcase-site-builder

一个 AI 编程代理（Kimi Code / Claude Code 兼容）的 **skill**，用于构建 pear.no 风格的展示性 / 营销网站（品牌官网、工作室网站、Awwwards 风格的滚动叙事单页）。

核心设计语言：**「活版印刷招股书」（letterpress prospectus）**——新古典主义油画图像、错位套印（misregistered）的半调字体、滚动驱动（scroll-scrubbed）的影片段落、克制的交互与戏剧化的排版节奏。桌面优先、单页叙事。

## 它做什么

这个 skill 覆盖从艺术方向到交付验收的完整流水线：

1. **定位与叙事结构** — 品牌主张、4–7 个叙事段落、故事板，并强制「影像驱动叙事」：一段文字必须有一帧属于它自己的画面，禁止一图多文。
2. **配色与视觉基调** — 由用户看过真实出图后拍板（2–3 套方案对比），agent 不得单方面决定，也不得为了对比搭 mock 页面。
3. **资产台账** — 逐项登记每张图 / 每段视频的用途、来源、状态、路径。
4. **图片资产获取** — 唯一路线：通过 CDP 自动化驱动 Midjourney 网页版生产（独立 Chrome profile，不动用户日常浏览器），按 jobid 认领任务、回收全尺寸 PNG、逐张检查、拼 2×2 对比图让用户挑定。
5. **视频资产获取** — 先交付视频脚本与参考图提示词，再通过 comfy-mcp 以首尾帧（FLF2V）方式生成；视频提示词经 `h3-json-director` skill 产出；后期焊接 / 循环收敛 / 转码统一走 `scripts/film.py`。
6. **前端实现** — 单页静态站点，GSAP + ScrollTrigger，「全页影片舞台」架构：固定底层舞台（活画循环 + 帧序列 canvas）+ 声明式时间轴，从 `templates/starter.html` 起步。
7. **验收** — 逐项清单：帧差数值验收、逐幕截图（CDP，不靠 `--screenshot`）、文字动画位移用脚本量化（不靠肉眼）。

## 目录结构

```
showcase-site-builder/
├── SKILL.md                          # skill 主文档：六阶段工作流 + 边界
├── references/
│   ├── asset-acquisition.md          # Midjourney 浏览器自动化规范（机制与坑位，均为实测）
│   ├── comfy-flf-video.md            # comfy-mcp 首尾帧视频生成规范（上传/选路/显存纪律/焊接收敛）
│   ├── film-language.md              # 对 pear.no 全部影片资产逐帧分析后的导演规范
│   └── pear-design-language.md       # 设计语言规范：配色、字体、半调、错位套印、动效、CDP 截图坑位
├── scripts/
│   ├── film.py                       # 影片后期：焊接 / 循环收敛 / 转码 / 数值留档（别手敲 ffmpeg）
│   ├── cdp.py                        # CDP 共享核心
│   ├── cdp_shots.py                  # 按真实时间滚动并逐幕截图的无头验收
│   ├── measure_text_motion.py        # 量化文字进出场位移（可见期间 ≤2px）
│   └── audit_reveal_feel.py          # 审计显现动画是否还在（中间值、逐项错开）
└── templates/
    ├── mj-browser-automation.py      # Midjourney 浏览器自动化参考实现（通用壳，走环境变量配置）
    └── starter.html                  # 「全页影片舞台」前端骨架
```

## 使用方法

把本目录放进代理的 skills 目录（如 Kimi Code 的 `~/.kimi-code/skills/` 或项目的 `.agents/skills/`），然后向代理提出这类需求即可触发：

> “帮我做一个 pear.no 风格的品牌官网 / 展示性网页 / 滚动叙事单页。”

代理会按 SKILL.md 的六阶段流程推进，每个阶段产出可检查的交付物，并在关键决策点（风格方向、配色方案、候选图挑定）停下让用户拍板。

### 脚本用法示例

```bash
# 影片后期（合成序列自测，不碰真实素材）
python scripts/film.py --selftest
python scripts/film.py --config docs/film-config.json --all

# 逐幕截图验收（按 act 或按帧号）
python scripts/cdp_shots.py --url http://127.0.0.1:8137/ --acts act-s1,act-s4 --out docs/qa --tag smoke

# 文字动画量化验收
python scripts/measure_text_motion.py --url http://127.0.0.1:8137/
python scripts/audit_reveal_feel.py --url http://127.0.0.1:8137/
```

## 依赖与前提

- **Midjourney 自动化**：系统 Chrome + 独立持久化 profile，用户需在该 profile 中登录 Midjourney 并明确授权自动化；自动化消耗账号的 fast hours。环境变量：`MJ_PORT` / `MJ_PROFILE` / `MJ_CHROME`。
- **视频生成**：本地 ComfyUI + comfy-mcp（comfy-cli）；视频提示词依赖本地已安装的 `h3-json-director` skill（MiniMax H3，FL2VA 模式）。16GB 档显卡遵守显存纪律（6s 片段 + int8 模型）。托管模型路线消耗 Comfy 额度，需用户明确同意。
- **前端**：无构建链，GSAP + ScrollTrigger（CDN 起步，交付前本地化）。

## 边界（重要）

- 不爬取第三方网站的图像资产；图片只走 Midjourney 浏览器自动化一条路（ToS 边缘行为，开始前向用户如实说明）。
- 不动用户的日常浏览器，不代填凭据。
- 不擅自消耗 Comfy 额度 / MJ fast hours。
- 不复刻 pear.no 本身——借鉴的是设计语言，不是其素材、文案或商标。

## License

仅供学习与研究用途。使用本 skill 产生的网站不得侵犯 pear.no 及任何第三方的知识产权。
