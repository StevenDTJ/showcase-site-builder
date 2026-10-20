#!/usr/bin/env python3
"""受控 Chrome / CDP 会话的共享核心。

给 skill 内其它脚本复用：截图、滚动到指定进度、等页面就绪、收日志与失败请求。
不含任何具体项目假设（不读某个网站的全局变量、不假设 section 类名）。

被 cdp_shots.py 使用；mj-browser-automation.py 是自包含的单文件模板（可整份拷走），
两者刻意不互相 import，避免模板被拷出后还要连带拷别的文件。

环境变量：
    CDP_CHROME   Chrome 可执行文件路径（默认自动探测）
    CDP_PORT     调试端口（默认 9461）
    CDP_PROFILE  受控 profile 目录（默认 <cwd>/.chrome-cdp）
"""
import base64
import json
import os
import shutil
import signal
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
DEFAULT_PORT = int(os.environ.get("CDP_PORT") or 9461)
DEFAULT_PROFILE = Path(os.environ.get("CDP_PROFILE") or (CWD / ".chrome-cdp"))

# 防遮挡冻结旗帜：窗口被遮挡时 rAF 会被完全冻结，截图全是过期状态。
# 这一组是实测确立的，不是可选项。
FREEZE_FLAGS = [
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "--disable-features=CalculateNativeWinOcclusion",
    "--no-first-run", "--no-default-browser-check", "--mute-audio",
    "--hide-scrollbars",
]

_CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    str(Path(os.environ.get("LOCALAPPDATA") or "") / "Google/Chrome/Application/chrome.exe"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def resolve_chrome():
    """CDP_CHROME > 常见安装位置 > PATH。找不到就如实报错。"""
    env = os.environ.get("CDP_CHROME")
    if env:
        return env
    for p in _CHROME_CANDIDATES:
        if p and Path(p).exists():
            return p
    for name in ("chrome", "google-chrome", "chromium", "chromium-browser", "chrome.exe"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("找不到 Chrome。设 CDP_CHROME 指向可执行文件，或把它加入 PATH。")


def port_alive(port, timeout=2):
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/json/version" % port, timeout=timeout).read()
        return True
    except Exception:
        return False


def wait_devtools(port, timeout=25):
    """等调试端口就绪，返回 /json/version 的内容。"""
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % port,
                                        timeout=2) as r:
                return json.load(r)
        except Exception:
            time.sleep(0.5)
    raise SystemExit("调试端口未就绪：%d\n"
                     "· 该端口已被别的东西占用（可能是残留实例）？换 --port；\n"
                     "· profile 被另一个 Chrome 锁住？换 --profile。" % port)


def launch_chrome(port=None, profile=None, width=1440, height=900, headless=False,
                  extra_flags=()):
    """启动一个受控 Chrome，返回 Popen。

    先查端口：已在跑就**直接复用**而不重启（与本 skill 的 MJ 流程一致——绝不关掉
    用户正在用的实例）。
    """
    port = int(port or DEFAULT_PORT)
    if port_alive(port):
        return None
    chrome = resolve_chrome()
    profile = Path(profile or DEFAULT_PROFILE)
    cmd = [chrome, "--remote-debugging-port=%d" % port, "--remote-allow-origins=*",
           "--user-data-dir=%s" % profile,
           "--window-size=%d,%d" % (width, height)]
    cmd += list(FREEZE_FLAGS) + list(extra_flags)
    if headless:
        cmd += ["--headless=new", "--disable-gpu"]
    cmd += ["about:blank"]
    # POSIX：必须自成进程组，否则 kill_tree 里的 os.killpg(getpgid(pid)) 会打到
    # **脚本自己所在的进程组** —— 那不是清理，是把自己和同组的父进程/兄弟任务一起杀掉。
    kwargs = {} if os.name == "nt" else {"start_new_session": True}
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            **kwargs)


def kill_tree(proc):
    """整棵进程树一起收掉。

    只杀启动器会留下僵尸实例，下一轮会连到旧标签页 —— 这是截到过期状态的经典原因。
    Windows 用 taskkill /T；其它平台杀进程组。
    """
    if proc is None:
        return
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            return
        except Exception:
            pass
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            time.sleep(0.5)
            return
        except Exception:
            pass
    try:
        proc.kill()
    except Exception:
        pass


class CDP:
    """一条 websocket 上的裸 CDP 会话。"""

    def __init__(self, ws):
        self.ws = ws
        self.mid = 0
        self.events = []

    def send(self, method, _timeout=20.0, **params):
        self.mid += 1
        mid = self.mid
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        self.ws.settimeout(_timeout)
        while True:
            try:
                msg = json.loads(self.ws.recv())
            except Exception as exc:
                raise RuntimeError("CDP 调用无响应：%s（%s）" % (method, exc))
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})
            if "method" in msg:
                self.events.append(msg)

    def drain(self, seconds):
        """在 seconds 秒内持续读事件（不阻塞发送）。"""
        end = time.time() + seconds
        self.ws.settimeout(0.25)
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if "method" in msg:
                self.events.append(msg)
        self.ws.settimeout(120)

    def js(self, expr, _timeout=30, **kw):
        r = self.send("Runtime.evaluate", _timeout=_timeout, expression=expr,
                      returnByValue=True, awaitPromise=True, timeout=_timeout * 1000)
        if "exceptionDetails" in r:
            raise RuntimeError(json.dumps(r["exceptionDetails"], ensure_ascii=False)[:600])
        return r.get("result", {}).get("value")

    def shot(self, path, full=False):
        """截图落盘，返回字节数。自动建目录；中文/绝对路径都安全。"""
        params = {"format": "png"}
        if full:
            params["captureBeyondViewport"] = True
        data = self.send("Page.captureScreenshot", **params)["data"]
        dest = Path(path)
        if str(dest.parent) not in ("", "."):
            dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(data))
        return dest.stat().st_size

    # ── 页面等待与滚动 ────────────────────────────────────
    def wait_ready(self, timeout=45, ready_js="document.readyState === 'complete'"):
        """等页面真就绪。固定 sleep 会在 CDN 脚本还没执行完时抢跑，
        抓到的中间态看起来像页面坏了。"""
        end = time.time() + timeout
        while time.time() < end:
            try:
                if self.js(ready_js, _timeout=6):
                    self.drain(0.8)
                    return True
            except Exception:
                pass
            time.sleep(0.4)
        return False

    def scroll_to_progress(self, section_id, progress=0.45):
        """把某个 section 滚到「自身滚动跨度」的 progress 处。

        **落点必须用滚动进度，不能用 section 高度的百分比。** 后者换算随视口高度
        变化：窄屏 .act=230vh、vh=844 时，高度的 45% 相当于进度 0.796，越过让位
        窗口，截到的是空幕。正确式：offsetTop + (offsetHeight - innerHeight) * p。

        返回实际滚动像素；section 不存在返回 None。
        """
        top = self.js(
            "(() => { const el = document.getElementById(%s);"
            " if (!el) return null;"
            " const span = Math.max(1, el.offsetHeight - innerHeight);"
            " return el.offsetTop + Math.round(span * %s); })()"
            % (json.dumps(section_id), float(progress)))
        if top is None:
            return None
        self.js("window.scrollTo(0, %d)" % int(top))
        return int(top)

    # ── 诊断 ──────────────────────────────────────────────
    def collect_problems(self):
        """从已收事件里提取报错与失败请求。返回 (errs, failed)，均已去重。

        **已知噪声会被过滤**：浏览器自动请求的 `/favicon.ico` 在健康页面上也是 404，
        主动中止的请求（导航打断、预取取消）也是常态。不过滤的话每一轮都会退出码 1，
        "退出码反映页面健康"这条约定就废了。
        """
        errs, failed = [], []
        for e in self.events:
            m = e.get("method")
            p = e.get("params") or {}
            if m == "Runtime.exceptionThrown":
                d = p.get("exceptionDetails") or {}
                errs.append("EXCEPTION %s" % ((d.get("exception") or {}).get("description")
                                              or d.get("text")))
            elif m == "Runtime.consoleAPICalled" and p.get("type") == "error":
                msg = " ".join(str(a.get("value")) for a in p.get("args", []))
                if "favicon.ico" in msg:
                    continue
                errs.append("CONSOLE " + msg)
            elif m == "Log.entryAdded" and (p.get("entry") or {}).get("level") == "error":
                text = p["entry"].get("text") or ""
                if "favicon.ico" in text:
                    continue
                errs.append("LOG " + text)
            elif m == "Network.loadingFailed":
                why = p.get("errorText") or ""
                if why in ("net::ERR_ABORTED", "net::ERR_ABORTED_BY_CLIENT"):
                    continue          # 被导航/预取取消，不是缺陷
                failed.append("%s %s" % (p.get("type"), why))
            elif m == "Network.responseReceived":
                r = p.get("response") or {}
                url = r.get("url") or ""
                if (r.get("status") or 0) >= 400 and not url.endswith("/favicon.ico"):
                    failed.append("HTTP %d %s" % (r["status"], url))
        return list(dict.fromkeys(errs)), list(dict.fromkeys(failed))


def connect(port=None, timeout=120, enable=("Page.enable", "Runtime.enable",
                                            "Log.enable", "Network.enable"),
            width=None, height=None, disable_cache=True, quiet=False):
    """连上运行中的受控 Chrome 的第一个 page 目标，返回 CDP。

    这些 enable / 度量设置都不是可选项，失败要能看见：
      · 关缓存：复用同一 profile 时 Chrome 会拿旧 CSS/JS 渲染，**验收到的其实是
        上一版页面**——这是最隐蔽的一类假通过。
      · 设备度量：--window-size 不等于视口尺寸，不覆盖就会按真实窗口算断点。
    """
    port = int(port or DEFAULT_PORT)
    wait_devtools(port)
    with urllib.request.urlopen("http://127.0.0.1:%d/json" % port, timeout=10) as r:
        tabs = json.load(r)
    pages = [t for t in tabs if t.get("type") == "page"]
    if not pages:
        raise SystemExit("没有可用标签页（受控 Chrome 起来了但没有 page 目标）")
    page = pages[0]
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=timeout,
                                     suppress_origin=True)
    cdp = CDP(ws)
    for m in enable:
        try:
            cdp.send(m, _timeout=8.0)
        except Exception as exc:
            if not quiet:
                print("  enable 失败（忽略）：%s -> %s" % (m, exc))
    if width and height:
        try:
            cdp.send("Emulation.setDeviceMetricsOverride", _timeout=8.0, width=width,
                     height=height, deviceScaleFactor=1, mobile=False)
        except Exception as exc:
            if not quiet:
                print("  设备度量设置失败（忽略）：%s" % exc)
    if disable_cache:
        try:
            cdp.send("Network.setCacheDisabled", _timeout=8.0, cacheDisabled=True)
        except Exception as exc:
            if not quiet:
                print("  关缓存失败（忽略）：%s" % exc)
    return cdp


def with_param(url, extra):
    """给 URL 追加一个 query 参数（已带 ? 时用 &）。"""
    return url + ("&" if "?" in url else "?") + extra
