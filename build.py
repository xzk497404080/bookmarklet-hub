#!/usr/bin/env python3
"""从本地源工作区生成可公网发布的静态站点。

源：~/OPC！/书签工具  （只读，不改动任何源文件）
出：本目录（index.html + tools/），可直接 git push 到 GitHub Pages

用法：python3 build.py
换源目录：SRC_HOME=/path/to/书签工具 python3 build.py
"""
import json
import os
import pathlib
import re
import shutil
import sys

OUT = pathlib.Path(__file__).resolve().parent
SRC = pathlib.Path(os.environ.get("SRC_HOME", "~/OPC！/书签工具")).expanduser()
TOOLS_SRC = SRC / "tools"

GH_USER = "xzk497404080"
GH_REPO = "bookmarklet-hub"
REPO_URL = "https://github.com/%s/%s" % (GH_USER, GH_REPO)
FEEDBACK_URL = REPO_URL + "/issues/new/choose"
FORM_URL = ""  # 填了问卷链接（腾讯问卷/飞书表单）就会多出一个入口
SITE_TITLE = "书签工具"

# 只发布跑在公开站点上的工具。oa-worktime-tool 打的是公司内网 HR 系统，绝不对外。
WHITELIST = [
    "bili-follow-tool",
    "douyin-history-tool",
    "douyin-need-tool",
    "tzx-temp-trend-tool",
]
BLOCKED = {
    "oa-worktime-tool": "硬编码 imgo.tv 与 /Hr/SignRecord 接口，属公司内网系统",
}

REQUIRED = ["id", "name", "tagline", "desc", "install", "site", "siteLabel",
            "purpose", "source", "storage", "tags", "color", "status"]


def die(msg):
    print("✗ " + msg)
    sys.exit(1)


def sub1(text, old, new, label):
    """精确替换一次；没命中就报错，避免源文件结构变动后静默产出坏页面。"""
    if old not in text:
        die("替换点未命中：%s\n  期望片段开头：%r" % (label, old[:70]))
    return text.replace(old, new, 1)


def load_tools():
    items = []
    for tid in WHITELIST:
        meta_path = TOOLS_SRC / tid / "meta.json"
        if not meta_path.is_file():
            die("找不到 %s" % meta_path)
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        missing = [k for k in REQUIRED if k not in data]
        if missing:
            die("%s 缺字段: %s" % (tid, ", ".join(missing)))
        if not (TOOLS_SRC / tid / data["install"]).is_file():
            die("%s 的安装页不存在: %s" % (tid, data["install"]))
        data.pop("notes", None)  # 站点知识卡是内部资料，不发布
        items.append(data)
    return items


def build_data_block(items):
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    if "</script" in payload.lower():
        die("标签内容含 </script，拒绝注入")
    return payload, len(items)


def patch_index(html, items):
    # 1. 数据块
    payload, _ = build_data_block(items)
    block = ('<!-- TOOLS_DATA_START -->\n'
             '<script id="tool-data" type="application/json">\n'
             + payload + '\n</script>\n<!-- TOOLS_DATA_END -->')
    html = re.sub(re.escape("<!-- TOOLS_DATA_START -->") + r"[\s\S]*?" +
                  re.escape("<!-- TOOLS_DATA_END -->"),
                  lambda _m: block, html, count=1)

    # 2. 站点分组里去掉「内网 OA」
    html = sub1(html,
                "order: ['B 站', '抖音', '内网 OA']",
                "order: ['B 站', '抖音', '投资科学']",
                "分组顺序")

    # 3. 顶部链接：内部开发文档 → 对外入口
    links_new = ['    <div class="links">',
                 '      <a href="%s" target="_blank" rel="noopener">提需求 / 报 Bug →</a>'
                 % FEEDBACK_URL]
    if FORM_URL:
        links_new[-1] += '<span class="sep">·</span>\n      <a href="%s" target="_blank" rel="noopener">填问卷（不用 GitHub 账号）</a>' % FORM_URL
    links_new += ['<span class="sep">·</span>',
                  '      <a href="%s" target="_blank" rel="noopener">GitHub 仓库</a>' % REPO_URL,
                  '<span class="sep">·</span>',
                  '      <a href="README.md">使用说明</a>',
                  '    </div>']
    links_old = ('    <div class="links">\n'
                 '      <a href="SPEC.md">开发规范 SPEC.md</a><span class="sep">·</span>\n'
                 '      <a href="README.md">总索引 README.md</a><span class="sep">·</span>\n'
                 '      <a href="build_index.py">标签数据来源 build_index.py</a>\n'
                 '    </div>')
    html = sub1(html, links_old, "\n".join(links_new), "顶部链接")

    # 4. 规范速览（写工具的人才看）→ 对外讲安全与边界
    rules_old = re.search(r'  <section class="rules">[\s\S]*?</section>', html)
    if not rules_old:
        die("替换点未命中：规范速览区块")
    rules_new = '''  <section class="rules">
    <h2>它是什么，以及边界在哪</h2>
    <p class="rsub">书签工具就是一段存在书签栏里的 JavaScript，不是扩展，也不装东西</p>
    <div class="rgrid">
      <div class="rule"><div class="k">代码全可见</div><div class="v">没有压缩混淆的黑箱，装之前可以先读一遍，觉得不对就不装</div></div>
      <div class="rule"><div class="k">数据不出本机</div><div class="v">不经过任何服务器，cookie 只在你自己浏览器里用，作者看不到你的数据</div></div>
      <div class="rule"><div class="k">随时能删</div><div class="v">删掉书签就什么都没了，不留后台进程、不改站点配置</div></div>
    </div>
  </section>'''
    html = html[:rules_old.start()] + rules_new + html[rules_old.end():]

    # 5. 页脚：维护者说明 → 用户说明
    foot_old = re.search(r'  <div class="foot">[\s\S]*?\n  </div>\n', html)
    if not foot_old:
        die("替换点未命中：页脚区块")
    foot_new = '''  <div class="foot">
    <b>怎么装</b>：打开任意工具的安装页，按住彩色按钮拖到书签栏（<code>⌘⇧B</code> / <code>Ctrl+Shift+B</code> 调出）。<br>
    <b>装不上</b>：点「复制代码，手动新建书签」，把内容粘到书签的地址栏里。手机端只能用这个办法。<br>
    <b>有问题</b>：<a href="%s" target="_blank" rel="noopener">去 GitHub 提需求或报 Bug</a>，说清楚你在哪个站、点了什么、期待什么。按用途分组时，一个工具可能出现在多个分组里。
  </div>
''' % FEEDBACK_URL
    html = html[:foot_old.start()] + foot_new + html[foot_old.end():]

    # 6. 卡片底部的「站点知识卡」指向内部知识卡文档，已随 notes 一起排除
    html = sub1(html,
                """        '<a class="know" href="' + esc(t.notes) + '">站点知识卡</a></div>' +""",
                """        '</div>' +""",
                "知识卡链接")

    # 7. 标题
    html = sub1(html, "<title>书签工具 · 统一入口</title>",
                "<title>%s · 跑在网页里的实用小工具</title>" % SITE_TITLE, "页面标题")
    return html


def copy_install_pages(items):
    tools_dir = OUT / "tools"
    if tools_dir.exists():
        shutil.rmtree(tools_dir)
    for t in items:
        dst_dir = tools_dir / t["id"]
        dst_dir.mkdir(parents=True)
        shutil.copy2(TOOLS_SRC / t["id"] / t["install"], dst_dir / t["install"])


def write_readme(items):
    lines = ["# %s" % SITE_TITLE, "",
             "一批跑在目标站点页面里的小工具。装上书签、点一下就出面板 —— 不装扩展、不起服务、不上传任何数据。",
             "", "## 工具", ""]
    for t in items:
        lines.append("- **%s** — %s（%s）" % (t["name"], t["tagline"], t["siteLabel"]))
    lines += ["", "## 怎么用", "",
              "1. 打开站点首页，点进任意工具的安装页",
              "2. 按住彩色按钮拖到书签栏（`⌘⇧B` / `Ctrl+Shift+B` 调出）",
              "3. 拖不动就点「复制代码，手动新建书签」，粘到书签地址栏",
              "4. 登录目标站点，点一下书签",
              "", "## 提需求 / 报 Bug", "",
              "发 [Issue](%s)，或直接改代码提 PR。" % FEEDBACK_URL,
              "", "## 说明", "",
              "书签工具以目标网站的 origin 执行，能读到你的登录态 —— 这是它有用的原因，也是它必须开源的原因。",
              "所有代码都是明文 JavaScript，装之前可以先读。", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    if not TOOLS_SRC.is_dir():
        die("源目录不存在：%s（可用 SRC_HOME 指定）" % TOOLS_SRC)

    items = load_tools()
    html = patch_index((SRC / "index.html").read_text(encoding="utf-8"), items)
    (OUT / "index.html").write_text(html, encoding="utf-8")

    copy_install_pages(items)
    write_readme(items)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    # 扫一遍产物里有没有漏网的内网域名
    leaked = []
    for f in OUT.rglob("*.html"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for pat in ("imgo.tv", "hunantv", "mgtv.com", "内网 OA"):
            if pat in text:
                leaked.append("%s → %s" % (f.relative_to(OUT), pat))

    print("工具 %d 个：%s" % (len(items), "、".join(t["name"] for t in items)))
    print("排除 %d 个：%s" % (len(BLOCKED), "；".join("%s（%s）" % kv for kv in BLOCKED.items())))
    print("产物：%s" % OUT)
    for f in sorted(OUT.rglob("*")):
        if f.is_file():
            print("  %-46s %6.1f KB" % (f.relative_to(OUT), f.stat().st_size / 1024))
    if leaked:
        print("⚠ 产物中出现内网字样，发布前请核对：")
        for x in leaked:
            print("    " + x)
    else:
        print("✓ 敏感词扫描通过（无内网域名）")


if __name__ == "__main__":
    main()
