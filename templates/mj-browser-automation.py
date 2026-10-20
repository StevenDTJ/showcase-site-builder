#!/usr/bin/env python3
"""Midjourney 受控浏览器自动化（v2 机制 · 通用壳）。

提交提示词 → 认领新 jobid → 等齐 4 张 → 回收到全尺寸 PNG → 拼对比图。

**图片资产获取的唯一路线**：驱动受控浏览器在 Midjourney 网页端生产，不爬第三方站、
不走"交付提示词等人工回填"的中转。机制与坑位出处：references/asset-acquisition.md。

设计目标：机制照抄实测通过的 v2 实现，外壳不含任何具体项目假设。

用法：
    python mj-browser-automation.py status
    python mj-browser-automation.py run --ids fh --deadline 420
    python mj-browser-automation.py run --ids f1,f2,f3,f4
    python mj-browser-automation.py run --text "<临时提示词>" --id adhoc --out assets/src/alt
    python mj-browser-automation.py run --all --prompts tools/mj-prompts.json
    python mj-browser-automation.py sheets --ids fh,f1
    python mj-browser-automation.py probe                 # 读 Network 域为"提交"取证
    python mj-browser-automation.py shot docs/qa/now.png  # 逃生口：截当前页
    python mj-browser-automation.py eval "location.href"  # 逃生口：页面里跑 JS
    python mj-browser-automation.py clear                 # 逃生口：硬清空输入框

环境变量（都可选，均有合理默认）：
    MJ_PORT      调试端口，默认 9455
    MJ_PROFILE   受控 profile 目录，默认 <cwd>/.mj-profile
    MJ_CHROME    Chrome 可执行文件路径，默认自动探测
    MJ_HOME      Midjourney imagine 页，默认 https://www.midjourney.com/imagine

── 提示词清单（--prompts）────────────────────────────────────────────
本脚本**不在 import 时读盘**：清单只在真正需要 entries 的子命令里惰性加载，
so 它被别的脚本 `from mj_browser_automation import MJ` 复用时不会因清单缺失而炸。

    {
      "browser": {"port": 9455, "home": "https://www.midjourney.com/imagine"},
      "out":     {"alt": "assets/src/alt"},          # 候选图落地目录（--out 优先）
      "entries": [
        {"id": "fh", "key": "<可辨认短语>", "prompt": "... --ar 16:9 --seed 4100"}
      ]
    }

`key` 只用于**日志与逐条自检**（确认提示词确实是那一条），**不参与任务匹配**——
原因见下面「任务识别」。

── 提交机制（v2，实测修正）──────────────────────────────────────────
**规范正文在 skill 的 `references/asset-acquisition.md`「自动化闭环」第 2、3 条——
那里是唯一权威，本文件只留代码必需的要点，避免两份文本各自漂移。**

  1) `keyDown`（带 `text="\r"`）+ `keyUp`  —— 实测唯一生效的序列；
  2) `rawKeyDown` + `char` + `keyUp`  —— 兜底序列。
**不要"找一个按钮点下去"**：当前作曲框里没有发送按钮（只有 Add Images 与设置），
误点会打开文件选择器/设置面板并抢走焦点，之后 Enter 也不再生效——那是一条会
**加剧故障**的歧路，不是备用方案。

**提交成功的判据是双判据**（输入框被清空 **或** 出现本次之前没有的 jobid）。两档
都失败就**硬清空输入框**并如实报错，绝不把残留文字留在框里。`probe` 子命令读
Network 域给出权威判据——注意它默认**真的提交**（烧额度），加 `--dry` 才只输入不回车。

── 任务识别：用新 jobid，**不要用提示词文本**────────────────────────
`cdn.midjourney.com/<jobid>/0_N_640_N.webp` 里的 jobid 就是任务身份。为什么文本匹配
在本 skill 下必然失效、以及两条必须保留的纪律（跨任务累积 `self.seen` 防 feed 虚拟化
误判、新任务取 feed 顶部），规范正文同样在 `asset-acquisition.md`「自动化闭环」第 3 条。

── 从项目专用版移植（mj.py 之类）的 API 差异 ──────────────────────────
本模板是**通用壳**，机制与项目实测版本一致，但外壳刻意去掉了项目假设。移植时注意：

  不变（可直接复用）：MJ(port=..., verbose=..., home=...)、connect()、send()、js()、
    jobids()、fetch_b64()、full_url()（staticmethod）、status()、clear_composer()、
    ensure_imagine()

  变了：
    · 提示词清单**不在 import 时加载** —— 旧版模块级 `json.loads(...)` 会让"清单缺失"
      变成 import 崩溃；现在只有真要 entries/out 时才读（load_prompts()）。
    · `submit(prompt, tries=2)` —— 多一个 `tries`（旧版固定走两档）。
    · `wait_new_job(before, deadline)` —— **返回值从 2 个变 3 个**：
      `(urls, jid, synthesized)`。
    · `grab(id_, prompt=None, out=None, stem=None, deadline_s=420, tries=2)`
      —— **不再接收 key 位置参数**。旧写法 `grab(id_, entry["key"], args.deadline)`
      里的 key 早已不参与匹配（认领走 jobid），照旧传位置参数会让 `out` 收到一个
      **秒数**（如 `420`）→ `Path(out)` 抛 TypeError。**迁移时该调用点必须改成关键字
      形式，否则会以报错而非静默错图收场**（报错好于错图，但仍要改）。清单里的 `key`
      现在只用于日志与逐条自检。
    · `sheet(id_, out_dir=None, sheet_dir=None, **labels**=None)` —— 目录可传参，
      并新增 `labels`（只影响一张 sheet 内的候选标号）。
    · 输出目录不再隐含绑定清单：`out` / `--out` 优先，缺省才回落 `out.alt`。
    · 新增 `shot()` / `probe_submit()` 与 CLI 的 `shot` / `eval` / `probe` /
      `--text` 逃生口；旧版靠另写脚本做这些事。
    · `grab()` 会把 `id -> jobid` 与每张的回收档位写进 `<候选目录的上一级>/jobids.json`
      （台账与补漏要用；旧版只打印到 stdout，滚动缓冲一过就没了）。

  配置来源：`MJ_PORT` / `MJ_PROFILE` / `MJ_CHROME` / `MJ_HOME` / `MJ_PROMPTS`，
  以及 `--prompts` —— 代码里不再出现项目专属绝对路径。

  依赖差异：
    · **中文字体**：对比图的标题/图注是中英混排，必须用含 CJK 字形的字体
      （`_load_fonts()` 自动找 msyh / 黑体 / PingFang / Noto CJK）。旧版写死
      `arial.ttf`，中文会渲染成豆腐块——在中文文件名或中文图注下才暴露。
      目标机完全没有 CJK 字体时会打印明确警告，而不是静默出豆腐。

── 回收 ────────────────────────────────────────────────────────────
  · CDN 对裸 urllib 返回 403 —— 必须在**页面上下文里 fetch**（带会话）→ base64 回传；
  · 全尺寸 `0_N.png` 间歇 403 属常态（延迟就绪）—— 退避重试；再三试不过才退到
    640px 预览图兜底，并把 `full`/`preview` 随文件一起记录，供台账标注、稍后补拉
    （`refetch` 之类的补漏工具见 mj-fetch 模式：dup / discover / refetch）。
"""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websocket

try:  # Windows 控制台默认 GBK，日志里的符号会直接抛 UnicodeEncodeError
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CWD = Path.cwd()

# ── 配置（环境变量 > 默认值；项目专属路径一律不进代码）──────────────────
PORT = int(os.environ.get("MJ_PORT") or 9455)
PROFILE = Path(os.environ.get("MJ_PROFILE") or (CWD / ".mj-profile"))
HOME = os.environ.get("MJ_HOME") or "https://www.midjourney.com/imagine"

_CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    str(Path(os.environ.get("LOCALAPPDATA") or "") / "Google/Chrome/Application/chrome.exe"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]


def resolve_chrome():
    """MJ_CHROME > 常见安装位置 > PATH 上的 chrome/chromium。找不到就如实报错。"""
    env = os.environ.get("MJ_CHROME")
    if env:
        return env
    for p in _CHROME_CANDIDATES:
        if p and Path(p).exists():
            return p
    for name in ("chrome", "google-chrome", "chromium", "chromium-browser", "chrome.exe"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("找不到 Chrome。设 MJ_CHROME 指向可执行文件，或确认它已加入 PATH。")


# ── 提示词清单：惰性加载（import 时不读盘）──────────────────────────────
_DEFAULT_PROMPTS = CWD / "tools" / "mj-prompts.json"
_prompts_path = Path(os.environ.get("MJ_PROMPTS") or _DEFAULT_PROMPTS)
_prompts_cache = None


def load_prompts(path=None):
    """读提示词清单；只在需要 entries/out 时才调用。缺文件时报错要能自解释。"""
    global _prompts_path, _prompts_cache
    p = Path(path) if path else _prompts_path
    if _prompts_cache is None or Path(p) != Path(_prompts_path):
        if not p.exists():
            raise SystemExit(
                "提示词清单不存在：%s\n"
                "用 --prompts 指定，或设 MJ_PROMPTS；临时单条投喂可直接用 "
                "`run --text ... --id ... --out ...`。" % p)
        _prompts_path = Path(p)
        raw = _prompts_path.read_text(encoding="utf-8-sig")  # 容忍 BOM
        try:
            _prompts_cache = json.loads(raw)
        except ValueError as exc:
            # 手写清单很常见；JSON 出错要指到文件，不要吐裸 traceback
            raise SystemExit("提示词清单 %s 不是合法 JSON：%s" % (_prompts_path, exc))
        if not _prompts_cache.get("entries"):
            raise SystemExit("清单 %s 里没有 entries。" % _prompts_path)
    return _prompts_cache


_BIG_FONT = None
_SMALL_FONT = None


def _load_fonts():
    """选一个**含 CJK 字形**的字体。

    对比图的标题与图注是中英混排（"全尺寸 / 预览(640) / 从 4 张里选一张"），
    arial.ttf 没有汉字——直接用它会渲染成一排豆腐块。这在旧版不易发现：当时
    标题只放文件名与数字，中文只在文件名里偶尔出现。
    """
    global _BIG_FONT, _SMALL_FONT
    if _BIG_FONT is not None:
        return _BIG_FONT, _SMALL_FONT
    from PIL import ImageFont
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",       # 微软雅黑（Win）
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",     # 黑体
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            _BIG_FONT = ImageFont.truetype(path, 22)
            _SMALL_FONT = ImageFont.truetype(path, 14)
            return _BIG_FONT, _SMALL_FONT
        except Exception:
            continue
    # 兜底：位图字体，汉字会缺字 —— 但要让它显式发生而不是静默变豆腐
    _BIG_FONT = _SMALL_FONT = ImageFont.load_default()
    print("  !! 找不到含中文字形的字体（msyh/黑体/Noto CJK），对比图上的中文会缺字")
    return _BIG_FONT, _SMALL_FONT


class MJ:
    """受控浏览器会话。无参构造 —— `from mj_browser_automation import MJ` 可直接复用。"""

    def __init__(self, port=None, verbose=True, home=None):
        self.port = int(port or PORT)
        self.home = home or HOME
        self.verbose = verbose
        self.mid = 0
        self.ws = None
        self.seen = set()       # 跨任务累积的 jobid，防 feed 虚拟化误判（见模块 docstring）
        self._calls = []        # 最近一次 enable_capture 期间的 CDP 事件

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    # ── 连接 ──────────────────────────────────────────────
    def connect(self):
        """复用已在跑的受控 Chrome；没有才启动。**绝不关闭用户已有实例。**"""
        if not self._port_alive():
            self.log("  端口 %d 无响应，尝试启动受控 Chrome…" % self.port)
            # 防遮挡冻结旗帜与设备度量缺一不可，否则窗口被遮挡时 rAF 冻结、截到的
            # 全是过期状态。**这组旗帜要与 scripts/cdp.py 的 FREEZE_FLAGS 保持一致**：
            # 本文件刻意不自包含式地 import 它（模板要能整份拷走），所以只能靠人工同步。
            flags = ["--disable-backgrounding-occluded-windows",
                     "--disable-renderer-backgrounding",
                     "--disable-background-timer-throttling",
                     "--disable-features=CalculateNativeWinOcclusion",
                     "--hide-scrollbars"]
            subprocess.Popen(
                [resolve_chrome(), "--remote-debugging-port=%d" % self.port,
                 "--remote-allow-origins=*", "--user-data-dir=%s" % PROFILE,
                 "--no-first-run", "--no-default-browser-check", "--mute-audio",
                 "--new-window", self.home] + flags,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(40):
                time.sleep(0.7)
                if self._port_alive():
                    break
            else:
                raise SystemExit(
                    "启动受控 Chrome 后端口 %d 仍无响应。\n"
                    "· profile 正被另一个 Chrome 占用？换个 MJ_PROFILE 或先关掉那个实例；\n"
                    "· 路径不对？设 MJ_CHROME。" % self.port)
        tabs = json.load(urllib.request.urlopen(
            "http://127.0.0.1:%d/json" % self.port, timeout=5))
        pages = [t for t in tabs if t.get("type") == "page"]
        if not pages:
            raise SystemExit("没有可用标签页")
        page = next((t for t in pages if "midjourney" in (t.get("url") or "")), pages[0])
        self.ws = websocket.create_connection(
            page["webSocketDebuggerUrl"], timeout=300, suppress_origin=True)
        self.send("Page.enable")
        self.send("Runtime.enable")

    def _port_alive(self):
        try:
            urllib.request.urlopen(
                "http://127.0.0.1:%d/json/version" % self.port, timeout=3).read()
            return True
        except Exception:
            return False

    def send(self, method, **params):
        self.mid += 1
        mid = self.mid
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError("%s -> %s" % (method, msg["error"]))
                return msg.get("result", {})

    def _drain(self, seconds=0.5):
        """非阻塞读走事件（send 之外的事件响应都落进 self._calls）。"""
        end = time.time() + seconds
        self.ws.settimeout(0.3)
        try:
            while time.time() < end:
                try:
                    msg = json.loads(self.ws.recv())
                except Exception:
                    continue
                if msg.get("id") is None and msg.get("method"):
                    self._calls.append(msg)
        finally:
            self.ws.settimeout(300)

    def js(self, expr, timeout=60):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True,
                      awaitPromise=True, timeout=timeout * 1000)
        if "exceptionDetails" in r:
            raise RuntimeError(json.dumps(r["exceptionDetails"], ensure_ascii=False)[:500])
        return r.get("result", {}).get("value")

    # ── 逃生口 ────────────────────────────────────────────
    def shot(self, path):
        """截当前页。中文/绝对路径都安全（自行建目录后落盘）。"""
        data = self.send("Page.captureScreenshot", format="png")["data"]
        dest = Path(path)
        if dest.parent and str(dest.parent) not in ("", "."):
            dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(data))
        return dest, dest.stat().st_size

    # ── 状态 ──────────────────────────────────────────────
    def status(self):
        return self.js(r"""(() => {
          const txt = (document.body.innerText || '');
          const hasTasks = !!document.querySelector('[href*="/tasks"], nav a[href*="tasks"]');
          const composer = !!document.querySelector('textarea, [contenteditable="true"]');
          const signIn = !hasTasks && /Sign\s?in|Log\s?in|登录/i.test(txt.slice(0, 800));
          return {url: location.href, title: document.title, composer, hasTasks,
                  signIn, loggedIn: composer && !signIn};
        })()""")

    def ensure_imagine(self):
        if "/imagine" not in (self.js("location.href") or ""):
            self.log("  导航到 /imagine")
            self.send("Page.navigate", url=self.home)
            time.sleep(6)

    # ── 输入框 ────────────────────────────────────────────
    def composer_text(self):
        return self.js(r"""(() => {
          const ta = document.querySelector('textarea');
          if (ta) return ta.value || '';
          const ce = document.querySelector('[contenteditable="true"]');
          return ce ? (ce.innerText || '') : '';
        })()""") or ""

    def focus_composer(self):
        return self.js(r"""(() => {
          const ta = document.querySelector('textarea');
          if (ta) {
            ta.focus(); ta.click();
            const set = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
            set.call(ta, '');
            ta.dispatchEvent(new Event('input', {bubbles:true}));
            return 'textarea';
          }
          const ce = document.querySelector('[contenteditable="true"]');
          if (ce) {
            ce.focus(); ce.click();
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
            return 'contenteditable';
          }
          return null;
        })()""")

    def clear_composer(self):
        """硬清空：CDP 全选 + 删除，再兜一次 JS 置空。返回残留文本。"""
        self.focus_composer()
        for t in ("rawKeyDown", "keyUp"):
            self.send("Input.dispatchKeyEvent", type=t, key="a", code="KeyA",
                      windowsVirtualKeyCode=65, nativeVirtualKeyCode=65, modifiers=2)
        for t in ("rawKeyDown", "keyUp"):
            self.send("Input.dispatchKeyEvent", type=t, key="Backspace", code="Backspace",
                      windowsVirtualKeyCode=8, nativeVirtualKeyCode=8)
        time.sleep(0.3)
        if self.composer_text().strip():
            self.focus_composer()
        return self.composer_text().strip()

    # ── 提交 ──────────────────────────────────────────────
    def try_enter(self, rich=True):
        if rich:      # 实测唯一生效的序列：keyDown 必须带 text="\r"
            evs = [dict(type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13,
                        nativeVirtualKeyCode=13, text="\r", unmodifiedText="\r"),
                   dict(type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13,
                        nativeVirtualKeyCode=13)]
        else:         # 兜底序列
            evs = [dict(type="rawKeyDown", key="Enter", code="Enter",
                        windowsVirtualKeyCode=13, nativeVirtualKeyCode=13),
                   dict(type="char", key="Enter", text="\r", unmodifiedText="\r"),
                   dict(type="keyUp", key="Enter", code="Enter",
                        windowsVirtualKeyCode=13, nativeVirtualKeyCode=13)]
        for e in evs:
            self.send("Input.dispatchKeyEvent", **e)

    def submit(self, prompt, tries=2):
        """投喂一条提示词。返回 (how, leftover)：how=None 表示没能提交。

        成功判据是**双判据**（清空 或 新 jobid）——见模块 docstring 里"白烧 fast
        hours"那段。失败路径一定清空输入框，不留残留。
        """
        kind = self.focus_composer()
        if not kind:
            raise RuntimeError("找不到输入框（页面结构变了、或未登录）")
        before = self.jobids()
        time.sleep(0.4)
        self.send("Input.insertText", text=prompt)
        time.sleep(0.6)
        plans = [("enter", True), ("enter-raw", False)][:max(1, min(2, tries))]
        for label, rich in plans:
            self.try_enter(rich)
            for _ in range(12):
                time.sleep(0.4)
                if not self.composer_text().strip():
                    return label, ""
                if any(k not in before for k in self.jobids()):
                    return label + "+job", ""
        leftover = self.composer_text().strip()
        self.clear_composer()
        return None, (leftover[:60] + "…" if len(leftover) > 60 else leftover)

    def probe_submit(self, text, dry=False):
        """为「提交」取证：读 Network 域，看有没有真的发出提交请求。

        **这不是只读操作**：`dry=False` 会真的提交一条提示词，**消耗账号额度**。
        只想验证"输入能被 React 组件接受、Enter 序列能不能触发请求"时用 `dry=True`
        ——它只输入不回车，不产生任务。

        返回 {"typed":..., "submitted":bool, "requests":[url...], "composer_left":...}。
        """
        if not text:
            raise SystemExit("probe 需要一条提示词（--text），没有通用的默认值")
        self.send("Network.enable")
        kind = self.focus_composer()
        if not kind:
            return {"typed": False, "submitted": False, "requests": [],
                    "composer_left": "", "error": "找不到输入框"}
        self._calls = []
        before = self.jobids()
        self.send("Input.insertText", text=text)
        time.sleep(0.4)
        if dry:
            return {"typed": True, "dry": True, "submitted": False,
                    "requests": [], "new_jobids": [],
                    "composer_left": self.composer_text().strip()[:60],
                    "note": "dry：只输入未回车，未产生任务、未消耗额度"}
        self.try_enter(True)
        deadline = time.time() + 8
        while time.time() < deadline:
            self._drain(0.4)
        urls = []
        for ev in self._calls:
            if ev.get("method") == "Network.requestWillBeSent":
                u = (ev.get("params") or {}).get("request", {}).get("url") or ""
                if "midjourney" in u and re.search(
                        r"/(submit|imagine|jobs|api)/", u):
                    urls.append(u)
        after = self.jobids()
        submits = [u for u in urls if "/submit" in u or "/imagine" in u]
        new_jobs = [k for k in after if k not in before]
        return {"typed": True, "request_count": len(urls), "requests": urls[:8],
                "submitted": bool(submits) or bool(new_jobs),
                "new_jobids": new_jobs,
                "composer_left": self.composer_text().strip()[:60]}

    # ── 认领任务 + 回收 ────────────────────────────────────
    def jobids(self):
        """页面上出现过的 cdn.midjourney jobid -> 该 job 的图片数。"""
        srcs = self.js(r"""[...document.querySelectorAll('img')].map(i => i.src)
                          .filter(s => s && s.includes('cdn.midjourney'))""") or []
        out = {}
        for s in srcs:
            m = re.search(r"cdn\.midjourney\.com/([0-9a-fA-F\-]{20,})/", s)
            if m:
                out[m.group(1)] = out.get(m.group(1), 0) + 1
        return out

    def wait_new_job(self, before, deadline_s):
        """认领本次提交产生的新 jobid，等它出齐 4 张，返回 (urls, jid, synthesized)。

        `synthesized=True` 表示 DOM 没渲染全、URL 是按固定模式补出来的（可能不存在），
        调用方应据此放弃退避重试，避免在死链上空转。

        用 jobid 而不是提示词文本匹配（原因见模块 docstring），并用 self.seen
        跨任务累积已见 jobid —— 否则 feed 虚拟化导致的旧卡重现会被误判成新任务。
        """
        end = time.time() + deadline_s
        self.seen |= set(before)
        jid = None
        while time.time() < end:
            time.sleep(4)
            now = self.jobids()
            fresh = [k for k in now if k not in before and k not in self.seen]
            if fresh:
                ordered = list(now.keys())          # 新任务在 feed 顶部
                jid = ordered[0] if ordered[0] in fresh else fresh[0]
                self.seen.add(jid)
                self.log("    新任务 jobid=%s" % jid)
                break
        if not jid:
            return [], None
        while time.time() < end:                    # 等这个 job 出齐 4 张
            if self.jobids().get(jid, 0) >= 4:
                break
            time.sleep(4)
        srcs = self.js(r"""[...document.querySelectorAll('img')].map(i => i.src)
                          .filter(s => s && s.includes('cdn.midjourney'))""") or []
        urls = [s.split("?")[0] for s in srcs
                if "/%s/" % jid in s
                and re.search(r"/0_\d+_\d+_[A-Za-z]+\.webp$", s.split("?")[0])]
        urls = sorted(set(urls))
        synthesized = len(urls) < 4
        if synthesized:
            # DOM 未渲染全就按固定模式补齐（0_0 … 0_3）。这些 URL 可能并不存在，
            # 所以 grab 对它们只试一次全尺寸、不进退避重试——否则会在不存在的地址上
            # 静默空转（6 次 × 4 张 × 单次 120s 超时）。
            urls = ["https://cdn.midjourney.com/%s/0_%d_640_N.webp" % (jid, i)
                    for i in range(4)]
        return urls[:4], jid, synthesized

    def fetch_b64(self, url, timeout=120):
        """在页面上下文里 fetch（带会话）。裸 urllib 对 CDN 会 403。"""
        return self.js(r"""(async () => {
          try {
            const r = await fetch(%s);
            if (!r.ok) return null;
            const b = await r.blob();
            const bytes = new Uint8Array(await b.arrayBuffer());
            let s = '';
            for (let k = 0; k < bytes.length; k += 8192) s += String.fromCharCode(...bytes.subarray(k, k + 8192));
            return btoa(s);
          } catch (e) { return null; }
        })()""" % json.dumps(url), timeout=timeout)

    @staticmethod
    def full_url(u):
        """0_1_640_N.webp -> 0_1.png

        必须用正则剥掉 `_640_N`：写成 `u.replace('_640_N.webp', '.png')` 能过，
        但换成 `rsplit` 之类的近似写法会得到 `0_1_640_N.png` —— 那只是 640 预览，
        不是全尺寸。后缀形态可能变，所以按模式匹配而不是按字面量。
        """
        u = u.split("?")[0]
        return re.sub(r"_\d+_[A-Za-z]+\.webp$", ".png", u)

    def grab(self, id_, prompt=None, out=None, stem=None, deadline_s=420, tries=2):
        """投喂 → 认领 → 回收。返回 (saved_paths, jid)；失败返回 ([], jid 或 None)。

        id_       任务标识，用于日志与台账；--text 模式下仅作标签
        prompt    提示词；None 时从清单里按 id_ 查
        out       落地目录；None 时取清单 out.alt
        stem      文件名前缀；默认 id_
        deadline_s 从提交到收齐 4 张的总预算（秒）
        tries     提交序列尝试档数：1=只试实测生效的 Enter，2（默认）=再试兜底序列
        """
        if prompt is None:
            entries = load_prompts()["entries"]
            try:
                prompt = next(e for e in entries if e["id"] == id_)["prompt"]
            except StopIteration:
                raise SystemExit("清单里没有 id=%s" % id_)
        if out is None:
            out = (load_prompts().get("out") or {}).get("alt")
            if not out:
                raise SystemExit("清单里没有 out.alt；用 --out 指定候选图目录。")
        self.ensure_imagine()
        outdir = Path(out)
        outdir.mkdir(parents=True, exist_ok=True)
        stem = stem or str(id_)

        before = self.jobids()
        how, leftover = self.submit(prompt, tries=tries)
        if not how:
            self.log("  [x] 提交失败（输入框未清空且无新 jobid）；残留=%r" % leftover)
            return [], None
        self.log("  已提交（%s）" % how)

        urls, jid, synthesized = self.wait_new_job(before, deadline_s)
        if len(urls) < 4:
            self.log("  [x] 只等到 %d 张，放弃本条" % len(urls))
            return [], jid
        self.log("  jobid=%s%s" % (jid, "（URL 为按模式补出的，可能不全）" if synthesized else ""))

        saved, tiers = [], {}
        for i, u in enumerate(urls[:4]):
            got = None
            attempts = 1 if synthesized else 6      # 补出的 URL 不值得退避重试
            for attempt in range(attempts):
                data = self.fetch_b64(self.full_url(u))      # 先要全尺寸 PNG
                if data:
                    got = (data, ".png", "full")
                    break
                if attempt >= 2 or synthesized:              # 再三试不过（或补出的 URL）退预览
                    data = self.fetch_b64(u)
                    if data:
                        got = (data, ".webp", "preview")
                        break
                time.sleep(3 + attempt * 4)
            if not got:
                self.log("    [x] 第 %d 张回收失败：%s" % (i, u))
                continue
            data, ext, kind = got
            dest = outdir / ("%s_%d%s" % (stem, i, ext))
            dest.write_bytes(base64.b64decode(data))
            saved.append(str(dest))
            tiers[dest.name] = kind
            # kind 必须留痕：preview 只够选图，进页面/进 FLF2V 前要补拉全尺寸
            self.log("    %s  %d bytes  (%s)" % (dest.name, dest.stat().st_size, kind))

        # 把 jobid 与每张的回收档位落成**索引文件**（台账与补漏工具都要用）。
        # 只写日志是不够的：滚动缓冲一过就没了，而 refetch 需要 id -> jobid 的映射。
        self._write_index(outdir, id_, jid, tiers)
        return saved, jid

    @staticmethod
    def _write_index(outdir, id_, jid, tiers):
        """维护 <outdir 的上一级>/jobids.json：{id: jobid} + {"_tiers": {id: {文件名: 档位}}}。

        合并写入、幂等；写失败只告警，不影响回收结果。
        """
        if not jid:
            return
        try:
            index = outdir.parent / "jobids.json"
            data = {}
            if index.exists():
                try:
                    loaded = json.loads(index.read_text(encoding="utf-8-sig"))
                    if isinstance(loaded, dict):
                        data = loaded
                except Exception:
                    data = {}
            data[id_] = jid
            if tiers:
                data.setdefault("_tiers", {})[id_] = tiers
            index.parent.mkdir(parents=True, exist_ok=True)
            index.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        except Exception as exc:
            print("    (jobid 索引写入失败，不影响回收：%s)" % exc)

    # ── 对比图（供人工挑选：一组 4 张，编号 0–3）──────────────
    def sheet(self, id_, out_dir=None, sheet_dir=None, labels=None):
        """2×2 对比图，带大号编号徽章 —— 便于口述"选第 1 张"。

        out_dir   候选图目录；默认清单 out.alt
        sheet_dir 对比图输出目录；默认 docs/qa/sheets
        labels    给**本张 2×2 内**的候选换一套标号（如 A/B/C/D），默认用候选下标 0–3。
                  注意它不改变"每组 4 张候选"的语义：跨方向比较靠**每个方向各出一张
                  sheet，再并排看**，而不是把方向号塞进一张 sheet。
        """
        from PIL import Image, ImageDraw
        if out_dir is None:
            out_dir = (load_prompts().get("out") or {}).get("alt")
        if not out_dir:
            raise SystemExit("清单里没有 out.alt；用 --out 指定候选图目录。")
        files = [f for f in sorted(Path(out_dir).glob("%s_*" % id_))
                 if f.suffix.lower() in (".png", ".webp") and f.stat().st_size > 0]
        if not files:
            return None
        files = files[:4]
        # 徽章 = 文件名里的候选下标（`fh_3.png` → "3"），**不是**列表位置。
        # 候选短缺是常态（回收失败会 continue），用位置编号会把 fh_3 显示成 "2" ——
        # 那正好是让用户"口述编号"时最容易出错的地方。
        tags = []
        for i, f in enumerate(files):
            tail = f.stem.rsplit("_", 1)[-1]
            tags.append(tail if tail.isdigit() else str(i))
        # labels：给**本张 2×2 内**的候选换一套标号（例如一次校准里用 A/B/C/D 指四个候选）。
        # 注意它不改变"每组 4 张"的候选下标语义——跨方向比较靠生成三张 sheet 再并看。
        if labels:
            tags = [str(x) for x in labels][:len(files)]
            while len(tags) < len(files):
                tags.append(str(len(tags)))
        TW, BAR = 640, 46
        tiles = []
        for f in files:
            im = Image.open(f).convert("RGB")
            im = im.resize((TW, int(im.height * TW / im.width)), Image.LANCZOS)
            tiles.append((f, im))
        TH = max(t[1].height for t in tiles)
        W, H = 2 * TW + 12, BAR + 2 * (TH + 30) + 8
        sh = Image.new("RGB", (W, H), (26, 21, 18))
        d = ImageDraw.Draw(sh)
        big, small = _load_fonts()
        d.text((10, 12), "%s   —— 从 %d 张里选一张（编号 %s）"
               % (id_, len(tiles), " / ".join(tags)), fill=(244, 239, 230), font=big)
        for i, (f, im) in enumerate(tiles):
            x = (i % 2) * (TW + 4) + 4
            y = BAR + (i // 2) * (TH + 30)
            sh.paste(im, (x, y))
            # 编号徽章：大而清楚，便于口头指认；宽度随标号长度（A/B/C 也要够大）
            bw = 52 if len(tags[i]) < 2 else 34 + 18 * len(tags[i])
            d.rectangle([x, y, x + bw, y + 34], fill=(178, 58, 46))
            d.text((x + 18, y + 6), tags[i], fill=(244, 239, 230), font=big)
            kind = "预览(640，按后缀推断)" if f.suffix.lower() == ".webp" else "全尺寸(按后缀推断)"
            d.text((x + bw + 10, y + 10), "%s  %d KB" % (kind, f.stat().st_size // 1024),
                   fill=(200, 195, 185), font=small)
        outdir = Path(sheet_dir or (CWD / "docs" / "qa" / "sheets"))
        outdir.mkdir(parents=True, exist_ok=True)
        out = outdir / ("%s.png" % id_)
        sh.save(out)
        return out


# ── CLI ───────────────────────────────────────────────────────────────
def _split_ids(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def _resolve_ids(args, all_ids):
    """--all / --ids 解析；--text 路径在 main() 里提前返回，不经这里。"""
    ids = all_ids if args.all else _split_ids(args.ids)
    if not ids:
        raise SystemExit("请给 --ids / --all，或用 --text 投喂单条临时提示词。")
    return ids


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Midjourney 受控浏览器自动化（v2 机制 · 通用壳）")
    ap.add_argument("cmd", choices=["status", "run", "sheets", "probe", "shot", "eval", "clear"])
    ap.add_argument("arg", nargs="?", default="",
                    help="shot 的输出路径 / eval 的 JS 表达式")
    ap.add_argument("--ids", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--text", default="", help="不经清单，直接投喂这一条提示词")
    ap.add_argument("--id", default="", help="配合 --text 的标识（默认 adhoc）")
    ap.add_argument("--out", default="", help="候选图落地目录（默认清单 out.alt）")
    ap.add_argument("--sheet-dir", default="", help="对比图输出目录（默认 docs/qa/sheets）")
    ap.add_argument("--labels", default="",
                    help="对比图徽章标号，逗号分隔（如 A,B,C）；默认 0,1,2,3")
    ap.add_argument("--prompts", default="", help="提示词清单路径（默认 tools/mj-prompts.json）")
    ap.add_argument("--deadline", type=int, default=420)
    ap.add_argument("--dry", action="store_true",
                    help="probe 专用：只输入不回车，不产生任务、不消耗额度")
    ap.add_argument("--port", type=int, default=0)
    args = ap.parse_args(argv)

    if args.prompts:
        load_prompts(args.prompts)

    # sheets 不需要连浏览器。**只有 --all 才需要清单**：拼校准对照图时清单往往还不存在
    # （风格校准按规矩发生在写全量提示词之前），这里若无条件读清单会让 --ids 直接崩。
    if args.cmd == "sheets":
        ids = _split_ids(args.ids)
        if args.all:
            ids = [e["id"] for e in load_prompts()["entries"]]
        if not ids:
            raise SystemExit("sheets 需要 --ids（或 --all，用清单里的全部 id）")
        mj = MJ(port=args.port or None, verbose=False)
        labels = [x.strip() for x in args.labels.split(",") if x.strip()] or None
        for i in ids:
            print(i, "->", mj.sheet(i, out_dir=args.out or None,
                                    sheet_dir=args.sheet_dir or None, labels=labels))
        return 0

    mj = MJ(port=args.port or None)
    mj.connect()

    if args.cmd == "status":
        st = mj.status()
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0 if st.get("loggedIn") else 2
    if args.cmd == "clear":
        print("清空输入框，残留=%r" % mj.clear_composer())
        return 0
    if args.cmd == "probe":
        # 注意：不加 --dry 就是真的提交一条，会消耗账号额度
        print(json.dumps(mj.probe_submit(args.text, dry=args.dry),
                         ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "shot":
        if not args.arg:
            raise SystemExit("shot 需要输出路径，例如 shot docs/qa/now.png")
        dest, size = mj.shot(args.arg)
        print("%s  %d bytes" % (dest, size))
        return 0
    if args.cmd == "eval":
        if not args.arg:
            raise SystemExit("eval 需要 JS 表达式")
        print(json.dumps(mj.js(args.arg, timeout=60), ensure_ascii=False))
        return 0

    # run
    if args.text:
        st = mj.status()
        if not st.get("loggedIn"):
            print("!! 未检测到登录态，停止。请先在该受控 Chrome 窗口登录。", flush=True)
            return 2
        print("浏览器：%s" % st.get("url"), flush=True)
        saved, jid = mj.grab(args.id or "adhoc", prompt=args.text,
                             out=args.out or None, deadline_s=args.deadline)
        print("  %s：回收 %d/4" % (args.id or "adhoc", len(saved)), flush=True)
        return 0 if saved else 1

    prompts = load_prompts()
    all_ids = [e["id"] for e in prompts["entries"]]
    ids = _resolve_ids(args, all_ids)

    st = mj.status()
    print("浏览器：%s" % st.get("url"), flush=True)
    if not st.get("loggedIn"):
        print("!! 未检测到登录态，停止。请先在该受控 Chrome 窗口登录。", flush=True)
        return 2

    for id_ in ids:
        t0 = time.time()
        print("\n=== %s ===" % id_, flush=True)
        try:
            saved, jid = mj.grab(id_, out=args.out or None, deadline_s=args.deadline)
        except Exception as exc:
            print("  ✗ 异常：%s" % exc, flush=True)
            saved = []
        print("  %s：回收 %d/4，用时 %.0fs" % (id_, len(saved), time.time() - t0),
              flush=True)
        if saved:
            mj.sheet(id_, out_dir=args.out or None, sheet_dir=args.sheet_dir or None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
