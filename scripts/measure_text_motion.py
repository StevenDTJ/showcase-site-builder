#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在**真实交互模式**下量"文字在屏幕上有没有走动"。

为什么必须有这个脚本（一个项目返工五轮的教训）：
最容易被写成"量位移"的审计，是用 `?smooth=0` 之类的调试钩子把 `scrollY` 钉在采样点，
然后读 `getBoundingClientRect()`。那样量到的只是"落位"，**恒为 0**——
可用户用的是 lerp 惯性滚动：滚轮停手后页面还会继续滑行一段，
sticky 壳的贴住状态、以及各幕的进出场进度都跟着这段滑行一起变。
**文字位移恰恰发生在这段滑行里。** 钉死 scrollY 的审计结构性地看不见它。

所以这里给一次真实的滚轮推进，再按帧记录元素视口坐标，直到页面停稳。

同样重要的两条覆盖率纪律（都踩过）：
  · **一行一行量**：行盒遮罩（`overflow:hidden` + `translateY(120%)`）会让
    **块本身不动、块内每一行在动**——只量整块会得到 0.00px 的假清白；
  · **首屏 / 只挂 scroll-frames 的幕也必须量**：它们不走通用路径，
    最容易从审计里整体溜掉（实测漏掉的那一幕位移最大，720px）。

用法（把 `--sel` 换成本项目的文字块选择器）：

    python measure_text_motion.py --url http://127.0.0.1:8137/ \
        --sel ".copy, .hero-copy, .cta" --line-sel "h2 .ln>i, .display .glass"

退出码 1 = 有元素在可见期间移动超过阈值。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cdp as C  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:8137/")
ap.add_argument("--sel", default=".copy, .hero-copy, .cta",
                help="文字块选择器（逗号分隔）")
ap.add_argument("--line-sel", default="h2 .ln>i, .display .glass, .display .misreg",
                help="块内**逐行**元素（行盒遮罩下真正在动的是它们）")
ap.add_argument("--port", type=int, default=8301)
ap.add_argument("--width", type=int, default=1600)
ap.add_argument("--height", type=int, default=900)
ap.add_argument("--wheel", type=int, default=900,
                help="一次推进的目标像素量；会自动收窄到小于该元素的可见窗口")
ap.add_argument("--samples", type=int, default=26)
ap.add_argument("--max-travel", type=float, default=2.0,
                help="可见期间允许的最大位移（px）")
ap.add_argument("--driver",
                default="(window.__SCROLL__ && window.__SCROLL__.by) ? 1 : 0",
                help="页面是否有『按量推进』的滚动钩子（lerp 实现通常有）")
ap.add_argument("--ready-js",
                default="document.readyState==='complete'")
ap.add_argument("--out", default="docs/qa/text-motion-live.json")
a = ap.parse_args()

proc = C.launch_chrome(port=a.port, profile=Path(C.DEFAULT_PROFILE).parent / ".chrome-tml",
                       width=a.width, height=a.height)
problems, rows = [], []
try:
    cdp = C.connect(port=a.port, width=a.width, height=a.height)
    cdp.send("Page.navigate", url=a.url)
    cdp.drain(2.5)
    cdp.wait_ready(timeout=60, ready_js=a.ready_js)
    cdp.drain(2.0)

    has_driver = bool(cdp.js(a.driver))
    print("滚动驱动钩子:", "有（走真实推进）" if has_driver else "无（退回直接 scrollTo，位移判据仍然有效）")

    blocks = json.loads(cdp.js(
        "(function(){var i=0;return JSON.stringify(Array.prototype.map.call("
        "document.querySelectorAll('%s'),function(e){e.__m=i++;return i-1;}));})()" % a.sel))
    n = len(blocks)
    print("待测文字块:", n)
    for idx in range(n):
        box = json.loads(cdp.js(
            "(function(){var e=document.querySelectorAll('%s')[%d];var r=e.getBoundingClientRect();"
            "return JSON.stringify([Math.round(r.y*100)/100,Math.round(r.height*10)/10]);})()" % (a.sel, idx)))
        label = cdp.js(
            "(function(){var e=document.querySelectorAll('%s')[%d];"
            "var s=e.closest('section,footer,div[id]');"
            "return ((s&&s.id)?s.id+'>':'')+(e.id||e.className||'?').toString().slice(0,34);})()"
            % (a.sel, idx))
        # 先扫一遍找出"它到底在哪一段可见"。
        # ⚠️ 不能靠"offsetTop − 0.6 屏"这种猜法：全页影片舞台类的页面里，
        # 文字挂在 sticky 壳上，可见窗口与 offsetTop 没有简单关系，
        # 猜错就会采到 0 个可见样本、得到"位移 0.00px"的**假清白**。
        top = cdp.js("(function(){var e=document.querySelectorAll('%s')[%d];"
                     "var y=0,n=e;while(n){y+=n.offsetTop||0;n=n.offsetParent;}return y;})()"
                     % (a.sel, idx))
        scan_lo = max(0, int(top) - a.height)
        vis_lo, vis_hi = None, None
        step = max(60, a.height // 4)
        y = scan_lo
        limit = scan_lo + a.height * 5
        while y <= limit:
            cdp.js("window.scrollTo(0,%d)" % y)
            cdp.drain(0.04)
            op = cdp.js("parseFloat(getComputedStyle(document.querySelectorAll('%s')[%d]).opacity)"
                        % (a.sel, idx))
            if op is not None and op > 0.02:
                if vis_lo is None:
                    vis_lo = y
                vis_hi = y
            elif vis_lo is not None:
                break
            y += step
        if vis_lo is None:
            problems.append("%s：在 offsetTop 附近 5 屏内都没找到可见区间" % label)
            print("  --  %-44s 找不到可见区间，跳过" % label)
            rows.append({"index": idx, "label": label, "error": "no-visible-window"})
            continue
        win_span = max(step, vis_hi - vis_lo)

        # 推进量自适应：先试请求值，若整个跨过文字（可见样本 <3），减半重试。
        ys, ops, lines = [], [], []
        for attempt in range(5):
            wheel = int(max(60, min(a.wheel, win_span * 0.6) / (2 ** attempt)))
            cdp.js("window.scrollTo(0,%d)" % max(0, vis_lo - step))
            cdp.drain(0.45)
            if has_driver:
                cdp.js("window.__SCROLL__.by(%d)" % wheel)
            else:
                cdp.js("window.scrollTo(0,%d)" % (max(0, vis_lo - step) + wheel))
            ys, ops, lines = [], [], []
            for _ in range(a.samples):
                r = json.loads(cdp.js(
                    "(function(){var e=document.querySelectorAll('%s')[%d];"
                    "var r=e.getBoundingClientRect();"
                    "var l=e.querySelector('%s');"
                    "return JSON.stringify([Math.round(r.y*100)/100, parseFloat(getComputedStyle(e).opacity),"
                    "l?Math.round(l.getBoundingClientRect().y*100)/100:null, window.scrollY]);})()"
                    % (a.sel, idx, a.line_sel.split(",")[0].strip())))
                ys.append(r[0]); ops.append(r[1]); lines.append(r[2])
                cdp.drain(0.05)
            if sum(1 for o in ops if o > 0.02) >= 3:
                break

        vis = [(y, l) for y, o, l in zip(ys, ops, lines) if o > 0.02]
        travel = (max(v[0] for v in vis) - min(v[0] for v in vis)) if len(vis) > 1 else 0.0
        lvis = [v[1] for v in vis if v[1] is not None]
        ltravel = (max(lvis) - min(lvis)) if len(lvis) > 1 else 0.0
        row = {"index": idx, "label": label, "block_travel_px": round(travel, 2),
               "line_travel_px": round(ltravel, 2), "visible_samples": len(vis),
               "samples": a.samples}
        rows.append(row)
        ok = travel <= a.max_travel and ltravel <= a.max_travel
        note = "" if vis else "  ⚠ 可见样本为 0——推进量可能跨过了整段文字，等于没量"
        print("  %s #%-2d %-40s 块位移=%6.2fpx 行位移=%6.2fpx 可见样本 %d/%d%s"
              % ("OK " if ok else "FAIL", idx, label, travel, ltravel, len(vis), a.samples, note))
        if travel > a.max_travel:
            problems.append("%s：可见期间文字块移动 %.2fpx" % (label, travel))
        if ltravel > a.max_travel:
            problems.append("%s：块内标题行移动 %.2fpx（行盒遮罩的典型症状）" % (label, ltravel))
        if len(vis) == 0:
            problems.append("%s：可见样本为 0，未真正测到（需收紧推进量）" % label)

    errs, failed = cdp.collect_problems()
    print("JS_ERRORS", len(errs), "FAILED_REQUESTS", len(failed))
    if errs or failed:
        problems.append("页面报错 %d / 失败请求 %d" % (len(errs), len(failed)))
finally:
    C.kill_tree(proc)

out = Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"rows": rows, "problems": problems}, ensure_ascii=False, indent=2),
               encoding="utf-8")
print("\n写出 %s  problems=%d" % (out, len(problems)))
for p in problems:
    print("  ✗", p)
sys.exit(1 if problems else 0)
