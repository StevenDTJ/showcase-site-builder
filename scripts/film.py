#!/usr/bin/env python3
"""影片后期：帧序列导出 → 段间焊接 → 循环收敛 → 编码 → 数值留档。

规范出处：references/comfy-flf-video.md「焊接与循环收敛」。段表、循环段、导出尺寸
全部来自配置（不再硬编码某个项目的剧本）。

用法：
    python film.py --selftest                       # 合成序列验证数学，不碰真实素材
    python film.py --config film-config.json --all
    python film.py --config film-config.json --seg s4

── 为什么需要焊接与收敛（实测数值）────────────────────────────────────
  · **段间焊接**：FL2VA 两次独立运行的端点帧并非像素一致（实测 mean abs diff
    12–15，VAE 重建 + 细节抖动）。所以焊接不靠「两张图看起来一样」，而是**取上一段
    的末帧文件直接替换下一段帧序列的第 1 帧**，再向自然帧做 ~6 帧渐变混入
    `blend(shared, natural[i], i/6)`，消除替换处的跳变。
  · **循环收敛**：raw 输出的首末帧差可达 ~17（主要是画面元素呼吸亮度差）。先裁掉
    尾部冻结静帧（相邻帧 diff < 0.05 判冻结），尾部 ~12 帧向首帧交叉溶解，
    **末帧 = 首帧精确拷贝**。目标首末帧 mean abs diff ≤ 3。
  · **必须在提取出的 PNG 上做焊接/收敛**，不要在已编码的 WebP 上做——混入会被二次
    压缩污染。

── 配置（--config）────────────────────────────────────────────────────
    {
      "raw_root":   "assets/video/raw",       # 原始 mp4：<raw_root>/<seg>/<seg>.mp4
      "film_root":  "assets/film",            # 帧序列输出：<film_root>/<seg>/w<width>/
      "video_root": "assets/video",           # 循环 mp4 与 poster 输出
      "work_root":  ".work/film",             # 中间 PNG（焊接/收敛在这里做）
      "report":     "docs/qa/weld-report.json",
      "widths":     [1440, 768],              # 导出档位；不给则只导出不缩放
      "web_quality": 94,                      # 见下面「为什么是 q94」
      "sharpen":    true,
      "chain_head": "loop",                   # 见下面「链首」
      "loops":   [{"name": "l1", "out": "loop-hero.mp4", "frames": "l_%04d.png"}],
      "segments":[{"name": "s0", "out": "f_%03d.webp"},
                  {"name": "s1", "out": "f_%03d.webp"}]
    }

`loops[].frames` 是**中间 PNG** 的命名（在 work_root 下，不进仓库）；可选 `loops[].fps`
（默认 24，须与源片帧率一致，否则循环时长会被悄悄改变）。
`segments[].out` 是**导出 WebP** 的命名（在 `film_root/<seg>/w<width>/` 下；`widths` 为空时
导出到 `film_root/<seg>/full/`，即不缩放的原尺寸）。
`widths` 两种写法都行：`[1440, 768]`，或按档给质量 `[{"width":1440},{"width":768,"quality":88}]`
（未给质量的档用顶层 `web_quality`）。
每段的 `<raw_root>/<name>/<name>.mp4` 是输入。缺输入的段会计为失败（除非 `--allow-missing`）。
留档是**读改写**：`--seg s4` 只更新 s4 的数字，不会抹掉其它段。

**为什么是 q94 + 轻度 USM**：实测 limbo 类平坦画面在 q82 下会被量化吃掉大量高频
（某段锐度从 31.0 掉到 15.3，砍掉一半），而这类画面恰好是这种站的主体。USM 用很轻
的档（radius 1.2 / percent 55 / threshold 2），只提边缘锐度、不放大噪声与色带。

── 三个必须保留的顺序纪律（都是踩坑换来的）──────────────────────────────
  1. **循环段先处理**：前端常从首页活画**交叉淡化**进第一段帧序列，接缝两侧必须是
     同一画面。第一版把循环段放最后，第一段首帧就一直没人焊，淡化处可见跳变。
  2. **跳跃处理时仍推进 shared**：即使某段不在本次 target 里，也要读它已有的末帧
     更新 shared，否则只跑 `--seg s5` 会焊到错误的「上一段末帧」。
  3. **链首**：第一段帧序列的首帧要和谁焊？
       `"chain_head": "loop"` —— 焊到第一个循环段的首帧（循环段首尾同帧，取哪帧等价）；
       `{"frame": "<路径>"}` —— 焊到指定图片；
       `"none"` —— 不焊。
     循环段不在本次 target 里但 work 目录已有帧时，照样能取到链首。

退出码：0 成功；1 有循环段未收敛到阈值（阈值 `--converge-max`，默认 3）。
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

WELD_BLEND = 6          # 焊接处向自然帧渐变混入的帧数
LOOP_DISSOLVE = 12      # 循环段尾部向首帧交叉溶解的帧数
FREEZE_EPS = 0.05       # 相邻帧 diff 低于此判为冻结静帧
CONVERGE_MAX = 3.0      # 循环段收敛目标（mean abs diff）

DEFAULTS = {
    "raw_root": "assets/video/raw",
    "film_root": "assets/film",
    "video_root": "assets/video",
    "work_root": ".work/film",
    "report": "docs/qa/weld-report.json",
    "widths": [],
    "web_quality": 94,
    "sharpen": True,
    "chain_head": "loop",
    "loops": [],
    "segments": [],
}


# ── 基础 ─────────────────────────────────────────────────────
def run(cmd):
    # encoding/errors 必须显式给：Windows 非 UTF-8 区域下 ffmpeg 的 stderr 会在读取线程里
    # 解码失败，RuntimeError 于是只剩"命令失败"而没有真正的原因（中文路径最容易触发）。
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError("命令失败：%s\n%s" % (" ".join(str(c) for c in cmd),
                                              (p.stderr or "")[-800:]))
    return p.stdout


def load(path):
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB")).astype(np.float32)


def save(arr, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(path)


def mad(a, b):
    """mean abs diff，逐像素逐通道均值。"""
    return float(np.abs(a - b).mean())


def blend(a, b, t):
    return a * (1.0 - t) + b * t


def seq_paths(d, pattern="f_*.png"):
    return sorted(Path(d).glob(pattern))


def glob_of(printf_pattern):
    """把 printf 风格帧名（f_%04d.png）转成 glob（f_*.png）。"""
    return re.sub(r"%0?\d*d", "*", printf_pattern)


# ── 焊接 ─────────────────────────────────────────────────────
def weld(shared_img, seq_dir, pattern="f_*.png", blend_n=WELD_BLEND):
    """把 seq_dir 的第 1 帧替换为 shared_img，并向自然帧渐变混入。

    逐帧读改写，不把整段载入内存。返回 (焊接前 diff, **焊接缝最大跳变**, 混入帧数)。

    ⚠️ 后一个数**不是**"焊接后与共享帧的差"——那个数按构造恒为 0（第 1 帧就是共享帧的
    副本），拿它做验收等于没验。真正要看的是**混入斜坡里的最大逐帧跳变**：混入段是
    共享帧向自然帧的渐变，如果斜坡本身有台阶，接缝处就还会看到跳。

    量级预期：斜坡最后一跳约等于 `mad(共享帧, 自然首帧) / blend_n`。所以共享帧与自然
    首帧差 12–15 时，6 帧混入的残余跳变在 2–3 左右。这是**诊断量**（用来判断要不要
    加长混入或改用更接近的共享帧），不设阈值——段落间本来就是有意的大幅场景转换。
    """
    paths = seq_paths(seq_dir, pattern)
    if not paths:
        raise RuntimeError("没有帧：%s（pattern=%s）" % (seq_dir, pattern))
    before = mad(shared_img, load(paths[0]))
    n = max(1, min(blend_n, len(paths)))
    for i in range(n):
        if i == 0:
            save(shared_img, paths[i])          # 纯共享帧
        else:
            nat = load(paths[i])
            save(blend(shared_img, nat, i / float(n)), paths[i])
    seam = _max_step_jump(paths[:n])
    return before, seam, n


def _max_step_jump(paths):
    """一串连续帧里的最大逐帧 mean abs diff（相邻两帧读一次，不驻留内存）。"""
    if len(paths) < 2:
        return 0.0
    prev = load(paths[0])
    worst = 0.0
    for p in paths[1:]:
        cur = load(p)
        worst = max(worst, mad(prev, cur))
        prev = cur
    return worst


# ── 循环收敛 ─────────────────────────────────────────────────
def loop_converge(seq_dir, pattern="f_*.png", dissolve=LOOP_DISSOLVE,
                  freeze_eps=FREEZE_EPS):
    """裁掉尾部冻结静帧 + 尾部向首帧交叉溶解 + 末帧=首帧精确拷贝。

    逐帧读改写（只保留首帧与相邻两帧），不把整段载入内存。
    返回 (裁掉的帧数, 溶解帧数, 收敛前首末 diff, **溶解斜坡最大逐帧跳变**)。

    ⚠️ 最后一个数是**收敛判据**，不是"收敛后首末 diff"。末帧是首帧的精确拷贝，
    所以"首末 diff"按构造恒为 0——用它做验收等于没验（旧版就是这样：`--converge-max`
    只在负数时才可能触发）。真正会被读者看见的是**溶解斜坡里的最大逐帧跳变**：
    斜坡平滑，接缝就不跳；有台阶，接缝就跳。
    """
    paths = seq_paths(seq_dir, pattern)
    if len(paths) < 4:
        raise RuntimeError("帧太少：%d（%s）" % (len(paths), seq_dir))

    # 1) 从尾部往前找第一处「还在动」的相邻对，之后的都算冻结
    cut = 0
    prev = load(paths[-1])
    for i in range(len(paths) - 2, -1, -1):
        cur = load(paths[i])
        if mad(cur, prev) >= freeze_eps:
            cut = len(paths) - 1 - (i + 1)
            break
        prev = cur
    if cut:
        for p in paths[len(paths) - cut:]:
            p.unlink()
        paths = paths[:len(paths) - cut]

    first = load(paths[0])
    before = mad(first, load(paths[-1]))

    # 2) 尾部 dissolve 帧向首帧交叉溶解；3) 末帧 = 首帧精确拷贝
    n = max(1, min(dissolve, len(paths) - 1))
    start = len(paths) - n
    for k in range(n):
        idx = start + k
        cur = load(paths[idx])
        t = (k + 1) / float(n)
        out = first.copy() if idx == len(paths) - 1 else blend(cur, first, t)
        save(out, paths[idx])
    seam = _max_step_jump(paths[start:])
    return cut, n, before, seam


# ── 编解码 ───────────────────────────────────────────────────
def extract(mp4, out_dir, pattern="f_%04d.png"):
    """抽帧为 PNG（原分辨率）。先清空目录，避免上一轮残留帧混进新序列。

    缩放不在这里做——它由 to_webp 按档完成（原版留了个没人传的 width 参数，
    看着像"抽帧时就缩放"，实际从未生效）。
    """
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-i", str(mp4), "-an", str(out_dir / pattern)])
    return seq_paths(out_dir, glob_of(pattern))


def to_webp(src_dir, dest_dir, width=None, quality=94, start=1, sharpen=True,
            pattern="f_*.png", out_pattern="f_%03d.webp"):
    """导出页面用 WebP。质量默认 q94 + 轻度 USM —— 见模块 docstring。"""
    from PIL import ImageFilter
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for i, p in enumerate(seq_paths(src_dir, pattern), start=start):
        with Image.open(p) as im:
            im = im.convert("RGB")
            if width and im.width != width:
                im = im.resize((width, round(im.height * width / im.width)),
                               Image.LANCZOS)
            if sharpen:
                im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=55,
                                                       threshold=2))
            im.save(dest_dir / (out_pattern % i), "WEBP", quality=quality, method=6)
        n += 1
    return n


def encode_loop(src_dir, out_mp4, fps=24, pattern="l_%04d.png"):
    """编码循环段 mp4 + 出 poster。pattern 是 **printf 风格**（ffmpeg 要的），
    glob 由内部换算——别把 glob 传进来。"""
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-framerate", str(fps), "-i", str(Path(src_dir) / pattern),
         "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-g", "30",
         "-an", "-movflags", "+faststart", "-pix_fmt", "yuv420p", str(out_mp4)])
    ps = seq_paths(src_dir, glob_of(pattern))
    if not ps:
        return
    with Image.open(ps[0]) as im:
        im.convert("RGB").save(out_mp4.with_name(out_mp4.stem + "-poster.jpg"),
                               "JPEG", quality=88)


# ── 配置 ─────────────────────────────────────────────────────
def load_config(path):
    if not path or not Path(path).exists():
        raise SystemExit(
            "需要 --config <配置.json>（含 segments / loops / 路径）。\n"
            "schema 见本文件 docstring；也可以直接跑 --selftest 验证环境。")
    cfg = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    out = dict(DEFAULTS)
    out.update(cfg)
    if not out["segments"] and not out["loops"]:
        raise SystemExit("配置里 segments 与 loops 都是空的，没有可处理的内容。")
    for key in ("segments", "loops"):
        for item in out[key]:
            if not item.get("name"):
                raise SystemExit("配置里 %s 有条目缺 name。" % key)
    return out


# ── 自测：用合成序列验证数学，不碰真实素材 ────────────────────
def selftest():
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="film_selftest_"))
    ok = True
    try:
        # 焊接：末帧与下段首帧故意差很多，焊接后应几乎为 0
        a = np.zeros((32, 32, 3), np.float32); a[..., 0] = 200
        b = np.zeros((32, 32, 3), np.float32); b[..., 1] = 200
        d = tmp / "seq"; d.mkdir()
        for i in range(10):
            save(blend(b, a, i / 9.0), d / ("f_%04d.png" % (i + 1)))
        before, seam, n = weld(a, d)
        print("焊接自测：自然首帧与共享帧 diff=%.2f -> 斜坡最大跳变 %.4f（混入 %d 帧）"
              % (before, seam, n))
        # 斜坡是 b→a 的线性混入，逐帧台阶应远小于首末差；接缝（第 1 帧=共享帧）本身
        # 的落差由 diff 反映，不在这里判
        ok &= seam < before / 3.0 and before > 50

        # 循环收敛：造一条首末差很大的序列 + 尾部冻结
        d2 = tmp / "loop"; d2.mkdir()
        base = np.random.RandomState(0).rand(32, 32, 3) * 60 + 120
        for i in range(30):
            save(base + (i * 2.0 if i < 20 else 40.0), d2 / ("f_%04d.png" % (i + 1)))
        cut, nd, b_, seam2 = loop_converge(d2)
        print("循环自测：裁掉冻结 %d 帧，溶解 %d 帧，收敛前首末 diff %.2f -> 斜坡最大跳变 %.4f"
              % (cut, nd, b_, seam2))
        # 收敛判据必须**不是**恒 0：末帧是首帧拷贝，所以绝不能拿"首末 diff"当判据
        ok &= cut > 0 and seam2 > 0 and seam2 < b_

        # 收敛后帧数应等于原帧数减裁掉的部分，且目录里确实少了文件
        print("循环自测：剩余帧数 %d" % len(seq_paths(d2)))
        ok &= len(seq_paths(d2)) == 30 - cut
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("自测结论：" + ("通过" if ok else "不通过"))
    return 0 if ok else 1


# ── 主流程 ───────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="影片后期：焊接 / 循环收敛 / 转码 / 数值留档")
    ap.add_argument("--config", default="", help="配置文件（见 docstring schema）")
    ap.add_argument("--seg", default="", help="只处理某一段/某个循环段")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--converge-max", type=float, default=CONVERGE_MAX,
                    help="循环段**溶解斜坡最大跳变**的阈值（默认 3）")
    ap.add_argument("--allow-missing", action="store_true",
                    help="缺输入 mp4 的段落只跳过、不算失败（默认视为失败并返回 1）")
    ap.add_argument("--report", default="", help="覆盖配置里的 report 路径")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    cfg = load_config(args.config)
    # printf 风格给 ffmpeg/导出命名，glob 风格给目录列举 —— 两者不能混用
    seg_printf, loop_printf = "f_%04d.png", "l_%04d.png"
    seg_glob, loop_glob = glob_of(seg_printf), glob_of(loop_printf)
    raw_root = Path(cfg["raw_root"])
    film_root = Path(cfg["film_root"])
    video_root = Path(cfg["video_root"])
    work_root = Path(cfg["work_root"])
    # widths 支持两种写法：纯数字 [1440,768]，或带质量的对象 [{"width":1440},{"width":768,"quality":88}]
    raw_widths = list(cfg.get("widths") or [])
    widths, q_by_w = [], {}
    for item in raw_widths:
        if isinstance(item, dict):
            w = int(item["width"])
            widths.append(w)
            if item.get("quality") is not None:
                q_by_w[w] = int(item["quality"])
        else:
            widths.append(int(item))
    quality = int(cfg.get("web_quality", 94))
    sharpen = bool(cfg.get("sharpen", True))

    print("RAW   = %s" % raw_root)
    print("FILM  = %s" % film_root)
    print("VIDEO = %s" % video_root)
    print("WORK  = %s" % work_root)

    target = args.seg if args.seg else ("all" if args.all else "")
    if not target:
        raise SystemExit("给 --seg <段号> / --all / --selftest")

    report = {}
    loops = cfg["loops"]
    segments = cfg["segments"]
    loop_names = [l["name"] for l in loops]
    seg_names = [s["name"] for s in segments]

    # 段名打错必须报错：否则什么都不做、把留档文件清成 {}、还返回 0
    known = loop_names + seg_names
    if target != "all" and target not in known:
        raise SystemExit("配置里没有段 %r。可用：%s"
                         % (target, ", ".join(known) or "（无）"))

    skipped, failed = [], []

    # 1) 循环段先做（纪律 1）
    for lp in loops:
        name = lp["name"]
        if target not in ("all", name):
            continue
        mp4 = raw_root / name / ("%s.mp4" % name)
        if not mp4.exists():
            print("跳过 %s：缺 %s" % (name, mp4))
            skipped.append(name)
            continue
        d = work_root / name
        pat = lp.get("frames", loop_printf)
        gpat = glob_of(pat)
        n = len(extract(mp4, d, pattern=pat))       # 循环段用原始分辨率编码 mp4
        cut, nd, b_, seam = loop_converge(d, pattern=gpat)
        try:
            encode_loop(d, video_root / lp.get("out", "loop-%s.mp4" % name),
                        fps=int(lp.get("fps", 24)), pattern=pat)
        except Exception as exc:
            print("!! %s 编码失败：%s" % (name, exc))
            failed.append(name)
            continue
        report[name] = {"帧数": n - cut, "冻结裁剪": cut, "溶解帧": nd,
                        "收敛前首末diff": round(b_, 2), "溶解斜坡最大跳变": round(seam, 4)}
        print("%-4s 帧数=%-4d 冻结裁剪=%-3d 溶解=%-3d 首末diff %.2f -> 斜坡最大跳变 %.4f"
              % (name, n - cut, cut, nd, b_, seam))

    # 2) 链首（纪律 3）——配置写错必须报错，不能静默"不焊接"
    head = cfg.get("chain_head", "loop")
    shared = None
    if isinstance(head, dict):
        frame = head.get("frame")
        if not frame:
            raise SystemExit('chain_head 是对象时必须给 "frame" 键（或改用 "loop" / "none"）。')
        if not Path(frame).exists():
            raise SystemExit("chain_head.frame 指向的文件不存在：%s" % frame)
        shared = load(frame)
        print("链首：%s 首帧焊接到指定图 %s" % (seg_names[0] if seg_names else "—", frame))
    elif head == "loop":
        if loop_names:
            lp0 = loops[0]
            ps = seq_paths(work_root / lp0["name"], glob_of(lp0.get("frames", loop_printf)))
            if ps:
                shared = load(ps[0])
                print("链首：%s 首帧焊接到 %s 首帧（循环段首尾同帧）"
                      % (seg_names[0] if seg_names else "—", lp0["name"]))
            else:
                print("  提示：%s 还没有帧，链首未建立；%s 的首帧将不被焊接。"
                      "先跑循环段（--all）可建立链首。"
                      % (lp0["name"], seg_names[0] if seg_names else "—"))
    elif head == "none":
        print("链首：none —— 第一段首帧不焊接")
    else:
        raise SystemExit('chain_head 只能是 "loop" / "none" / {"frame": "路径"}，收到 %r' % (head,))

    # 3) 滚动叙事段：按配置顺序处理，才能把上一段末帧焊到下一段（纪律 2）
    todo = seg_names if target == "all" else [target]
    for sg in segments:
        name = sg["name"]
        d = work_root / name
        if name not in todo:
            ps = seq_paths(d, seg_glob)
            if ps:                       # 仍要推进 shared
                shared = load(ps[-1])
            continue
        mp4 = raw_root / name / ("%s.mp4" % name)
        if not mp4.exists():
            print("跳过 %s：缺 %s" % (name, mp4))
            skipped.append(name)
            continue
        # 焊接链断裂必须报错：否则会拿**过期的 shared**（上一个有帧的段、甚至循环段）
        # 去焊本段首帧 —— 看起来成功，实际焊错了前驱。
        if shared is None and seg_names and name != seg_names[0]:
            raise SystemExit(
                "焊接链断了：%s 不是第一段，但它之前没有任何段有帧（work_root 下找不到）。\n"
                "先在 --all 里按顺序生成前置段，或单独重跑它，否则本段首帧会被焊到错误的前驱。"
                % name)
        n = len(extract(mp4, d, pattern=seg_printf))
        before = seam = None
        welds = 0
        if shared is not None:
            before, seam, welds = weld(shared, d, pattern=seg_glob)
        ps = seq_paths(d, seg_glob)
        shared = load(ps[-1])
        exported = []
        for w in (widths or [None]):
            dest = film_root / name / ("w%d" % w if w else "full")
            cnt = to_webp(d, dest, width=w, quality=q_by_w.get(w, quality),
                          sharpen=sharpen, out_pattern=sg.get("out", "f_%03d.webp"))
            exported.append("%s:%d" % (dest.name, cnt))
        report[name] = {"帧数": n,
                        "焊接前diff": None if before is None else round(before, 2),
                        "焊接缝最大跳变": None if seam is None else round(seam, 4),
                        "混入帧": welds,
                        "导出": exported}
        print("%-4s 帧数=%-4d 焊接前diff=%-8s 缝最大跳变=%-8s 混入=%-3d 导出=%s"
              % (name, n,
                 "—" if before is None else "%.2f" % before,
                 "—" if seam is None else "%.4f" % seam,
                 welds, " ".join(exported)))

    # 4) 数值留档：**读改写**，不是整文件覆盖 —— 否则 `--seg s4` 会抹掉别的段的实测数字
    out = Path(args.report or cfg["report"])
    out.parent.mkdir(parents=True, exist_ok=True)
    merged = {}
    if out.exists():
        try:
            loaded = json.loads(out.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                merged = loaded
        except Exception:
            merged = {}
    merged.update(report)
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n数值留档 -> %s（本轮 %d 段，累计 %d 段）" % (out, len(report), len(merged)))

    bad = [k for k, v in report.items()
           if (v.get("溶解斜坡最大跳变") or 0) > args.converge_max]
    if bad:
        print("!! 循环段溶解斜坡未收敛到 ≤%g：%s" % (args.converge_max, bad))
        return 1
    if failed:
        print("!! 有段落编码失败：%s" % failed)
        return 1
    if skipped and not args.allow_missing:
        print("!! 有段落缺输入而被跳过：%s（确认这是有意的就加 --allow-missing）" % skipped)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
