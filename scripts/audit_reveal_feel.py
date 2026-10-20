#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量"进出场动画还在不在、看不看得出来"。

与 measure_text_motion.py 配套使用——两个一起跑才算合格：

  · measure_text_motion.py  → 文字**不许**在屏幕上走动（位移 ≤2px）
  · 本脚本                 → 文字**必须**看得出显影（不是硬切）

为什么要分开量：修"零位移"时最容易把动画一起修没。常见情形是补间被
两条时间轴互相写坏、或窗口退化成 1px，于是文字在 0 与 1 之间直跳——
位移审计依然全绿，但观感是硬切。用户对这件事的反馈原话是
「文字的进入和退出动画要有」。

判据两条：
  1. **中间值**：整块可见度必须出现 0.05–0.95 之间的采样点（不是 0→1 一跳）。
  2. **逐项错开**：同一时刻，块内各元素的可见度要拉开差距
     （序号/细线/标题/正文/条目不应同时到达）。

用法：

    python audit_reveal_feel.py --url http://127.0.0.1:8137/ \
        --sel ".copy, .cta" \
        --parts ".eyebrow, h2 .ln>i, .display .glass, p, .facts > *, .meta > *"

退出码 1 = 有元素是硬切出现，或缺逐项节拍。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cdp as C  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:8137/")
ap.add_argument("--sel", default=".copy, .cta", help="文字块选择器")
ap.add_argument("--parts", default=".eyebrow, h2 .ln>i, .display .glass, p, .facts > *, .meta > *",
                help='块内各『项』（用于判逐项错开）')
ap.add_argument("--port", type=int, default=8341)
ap.add_argument("--width", type=int, default=1600)
ap.add_argument("--height", type=int, default=900)
ap.add_argument("--steps", type=int, default=60)
ap.add_argument("--min-mid", type=int, default=2, help="至少要几个中间值采样点")
ap.add_argument("--min-stagger", type=float, default=0.15,
                help="逐项错开的最小幅度（同一时刻可见度极差）")
ap.add_argument("--ready-js", default="document.readyState==='complete'")
ap.add_argument("--out", default="docs/qa/reveal-feel.json")
a = ap.parse_args()

proc = C.launch_chrome(port=a.port, profile=Path(C.DEFAULT_PROFILE).parent / ".chrome-rf",
                       width=a.width, height=a.height)
problems, rows = [], []
try:
    cdp = C.connect(port=a.port, width=a.width, height=a.height)
    cdp.send("Page.navigate", url=a.url)
    cdp.drain(2.5)
    cdp.wait_ready(timeout=60, ready_js=a.ready_js)
    cdp.drain(2.0)

    n = cdp.js("document.querySelectorAll('%s').length" % a.sel)
    print("待测文字块:", n)
    for idx in range(int(n)):
        label = cdp.js(
            "(function(){var e=document.querySelectorAll('%s')[%d];"
            "var s=e.closest('section,footer,div[id]');"
            "return ((s&&s.id)?s.id+'>':'')+(e.id||e.className||'?').toString().slice(0,34);})()"
            % (a.sel, idx))
        # 用可见度扫描定出该块的可见区段，再在其中密集采样
        scan_lo = 0
        docH = cdp.js("document.documentElement.scrollHeight - window.innerHeight")
        step = max(80, a.height // 3)
        vis_lo, vis_hi = None, None
        y = 0
        while y <= docH:
            cdp.js("window.scrollTo(0,%d)" % y)
            cdp.drain(0.04)
            op = cdp.js("parseFloat(getComputedStyle(document.querySelectorAll('%s')[%d]).opacity)"
                        % (a.sel, idx))
            if op > 0.02:
                if vis_lo is None:
                    vis_lo = y
                vis_hi = y
            elif vis_lo is not None and y - vis_hi > step * 3:
                break
            y += step
        if vis_lo is None:
            problems.append("%s：整页都没找到可见区间" % label)
            print("  --  %-42s 找不到可见区间" % label)
            continue
        lo = max(0, vis_lo - step)
        hi = min(docH, vis_hi + step)
        if hi <= lo:
            hi = lo + 1

        samples = []
        for i in range(a.steps + 1):
            yy = int(lo + (hi - lo) * i / a.steps)
            cdp.js("window.scrollTo(0,%d)" % yy)
            cdp.drain(0.06)
            r = json.loads(cdp.js(
                "(function(){var b=document.querySelectorAll('%s')[%d];"
                "var os=[];b.querySelectorAll('%s').forEach(function(e){"
                "os.push(Math.round(parseFloat(getComputedStyle(e).opacity)*100)/100);});"
                "return JSON.stringify([parseFloat(getComputedStyle(b).opacity), os]);})()"
                % (a.sel, idx, a.parts)))
            samples.append((yy, r[0], r[1]))

        mids = [s for s in samples if 0.05 < s[1] < 0.95]
        spread = 0.0
        for _, _, os_ in samples:
            vals = [v for v in os_ if v > 0.02]
            if len(vals) >= 2:
                spread = max(spread, max(vals) - min(vals))
        peak = max(s[1] for s in samples)
        row = {"index": idx, "label": label, "mid_samples": len(mids),
               "peak": round(peak, 3), "stagger_spread": round(spread, 3),
               "visible_window": [lo, hi], "samples": len(samples)}
        rows.append(row)
        ok = len(mids) >= a.min_mid and spread >= a.min_stagger and peak > 0.97
        print("  %s #%-2d %-42s 中间值=%2d 峰值=%.2f 错开幅度=%.2f"
              % ("OK " if ok else "FAIL", idx, label, len(mids), peak, spread))
        if len(mids) < a.min_mid:
            problems.append("%s：可见度只有 0 与 1（中间值采样 %d 个），进出场等于硬切"
                            % (label, len(mids)))
        if spread < a.min_stagger:
            problems.append("%s：各元素几乎同时显现（错开幅度 %.2f），缺逐项节拍"
                            % (label, spread))
        if peak <= 0.97:
            problems.append("%s：文字从未读满（峰值 %.2f）" % (label, peak))

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
