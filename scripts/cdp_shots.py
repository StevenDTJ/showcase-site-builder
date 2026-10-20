#!/usr/bin/env python3
"""受控 Chrome 的页面体检与逐幕/逐帧截图（CDP，真实时间滚动）。

为什么不能用 `chrome --screenshot --virtual-time-budget`：对 rAF 驱动、按需加载
的页面不可靠，会抓到全黑的中间态。必须用 CDP（`--remote-debugging-port` +
websocket）按真实时间滚动、等待、截图。

用法：
    python cdp_shots.py --url http://127.0.0.1:8123/ --out docs/qa --tag smoke
    python cdp_shots.py --url http://127.0.0.1:8123/ --acts act-s1,act-s4 --out docs/qa
    python cdp_shots.py --url http://127.0.0.1:8123/ --frames 0,120,240 --out docs/qa --tag f
    python cdp_shots.py --url http://127.0.0.1:8123/ --acts hero --progress 0.55
    python cdp_shots.py --url http://127.0.0.1:8123/ --probe "({st: !!window.__STAGE})"

要点（踩坑后确立，不是可选项）：
  · 启动参数必须带防遮挡冻结旗帜（见 cdp.FREEZE_FLAGS）——窗口被遮挡时 rAF 会被
    完全冻结，截图全是过期状态；
  · 每轮开跑前**必须清理残留 Chrome 实例**：同一 user-data-dir / 调试端口会连到旧
    标签页，截出来的是上一版页面。本脚本默认不复用已占用的端口，直接报错让你处理；
    确认要复用（比如想连自己手动开的那个受控窗口）再加 --reuse；
  · 收尾整棵进程树一起收掉，只杀启动器会留僵尸实例；
  · 关缓存 —— 复用 profile 时 Chrome 会拿旧 CSS/JS，验收到的其实是上一版；
  · 设备度量要显式覆盖，`--window-size` 不等于视口尺寸。

退出码：0 成功；1 页面有 JS 报错或失败请求（除非 --no-fail-on-error）。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cdp as C  # noqa: E402

# 页面就绪判据：默认通用。项目若有全局舞台对象，用 --ready-js 收紧，
# 例如 "document.readyState==='complete' && !!window.__STAGE"
READY_DEFAULT = "document.readyState === 'complete'"


def main():
    ap = argparse.ArgumentParser(
        description="受控 Chrome 的页面体检与逐幕/逐帧截图（CDP）")
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", default="docs/qa")
    ap.add_argument("--tag", default="shot")
    ap.add_argument("--port", type=int, default=C.DEFAULT_PORT)
    ap.add_argument("--profile", default="", help="受控 profile 目录（默认 <cwd>/.chrome-cdp）")
    ap.add_argument("--root", default="", help="用于解析相对 --out/--profile 的目录（默认 cwd）")
    ap.add_argument("--frames", default="",
                    help="逗号分隔的 ?frame= 值，逐帧截图（给帧序列 renderer 钉帧用）")
    ap.add_argument("--acts", default="",
                    help="逗号分隔的 section id: 逐个滚动到指定进度后截图")
    ap.add_argument("--progress", type=float, default=0.45,
                    help="逐幕落点：offsetTop + (offsetHeight - innerHeight) * p，默认 0.45")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--reuse", action="store_true",
                    help="允许复用已占用调试端口的现有实例（默认报错，避免连到旧标签页）")
    ap.add_argument("--ready-js", default=READY_DEFAULT,
                    help="页面就绪判据（一条返回真值的 JS 表达式）")
    ap.add_argument("--probe", default="",
                    help="额外求值的 JS 并打印其结果（用来读项目专属的全局状态）")
    ap.add_argument("--no-fail-on-error", action="store_true",
                    help="即使有 JS 报错/失败请求也返回 0")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else Path.cwd()
    out = (root / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # profile 默认也要跟着 --root 走；否则 --root 只影响截图落点、profile 仍落在 cwd，
    # 与 help 里"用于解析相对 --out/--profile"的承诺不符
    profile = (root / args.profile) if args.profile else (root / ".chrome-cdp")

    if C.port_alive(args.port) and not args.reuse:
        raise SystemExit(
            "端口 %d 已被占用。\n"
            "· 想连上去（例如已手动开好的受控窗口）：加 --reuse；\n"
            "· 想干净开一轮：先关掉那个 Chrome，或换 --port。\n"
            "复用残留实例会连到旧标签页、截出上一版页面 —— 这是验收假通过的常见来源。"
            % args.port)

    proc = C.launch_chrome(port=args.port, profile=profile, width=args.width,
                           height=args.height, headless=args.headless)
    try:
        cdp = C.connect(port=args.port, width=args.width, height=args.height)

        cdp.send("Page.navigate", url=args.url)
        cdp.drain(1.2)
        ready = cdp.wait_ready(timeout=45, ready_js=args.ready_js)
        if not ready:
            print("  WARN 页面未在超时内就绪（--ready-js 可能对该页不成立）")

        shots = []

        def snap(name):
            p = out / name
            shots.append((p, cdp.shot(p)))

        if args.frames:
            base = C.with_param(args.url, "smooth=0")
            for f in [x.strip() for x in args.frames.split(",") if x.strip()]:
                cdp.send("Page.navigate", url=C.with_param(base, "frame=" + f))
                cdp.drain(1.0)
                cdp.wait_ready(timeout=45, ready_js=args.ready_js)
                snap("%s_frame%s.png" % (args.tag, f))

        if args.acts:
            cdp.send("Page.navigate", url=C.with_param(args.url, "smooth=0"))
            cdp.drain(1.0)
            cdp.wait_ready(timeout=45, ready_js=args.ready_js)
            for name in [x.strip() for x in args.acts.split(",") if x.strip()]:
                if name in ("hero", "top"):
                    cdp.js("window.scrollTo(0, 0)")
                else:
                    top = cdp.scroll_to_progress(name, args.progress)
                    if top is None:
                        print("  skip (no such section):", name)
                        continue
                cdp.drain(1.5)
                snap("%s_%s.png" % (args.tag, name))

        if not args.frames and not args.acts:
            snap("%s_top.png" % args.tag)

        info = {"url": cdp.js("location.href"),
                "title": cdp.js("document.title"),
                "ready": cdp.js("document.readyState"),
                "scrollHeight": cdp.js("document.documentElement.scrollHeight"),
                "viewport": cdp.js("({w: innerWidth, h: innerHeight})")}
        if args.probe:
            try:
                info["probe"] = cdp.js(args.probe)
            except Exception as exc:
                info["probe_error"] = str(exc)[:200]
        print("PAGE", json.dumps(info, ensure_ascii=False))

        print("SHOTS")
        for p, n in shots:
            try:
                print("  %s  %d bytes" % (p.relative_to(root), n))
            except ValueError:
                print("  %s  %d bytes" % (p, n))

        errs, failed = cdp.collect_problems()
        print("ERRORS", len(errs))
        for e in errs:
            print("  " + str(e)[:300])
        print("FAILED_REQUESTS", len(failed))
        for f in failed:
            print("  " + str(f)[:300])

        if (errs or failed) and not args.no_fail_on_error:
            return 1
        return 0
    finally:
        C.kill_tree(proc)


if __name__ == "__main__":
    sys.exit(main())
