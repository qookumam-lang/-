# -*- coding: utf-8 -*-
"""
間柱・耐風梁・水平ブレースリストを、鉄骨部材リスト（参考図「小梁・間柱・その他」表）の
書式で DXF(R12, cp932) と PDF に書き出す。

使い方:
    python sub_member_list.py <入力.json> <出力.dxf> <出力.pdf> [--scale 50]

- 列は参考図どおり「符号・部材・鋼種・接合部(nw×mw-HTB, ピッチnP/mP, G.PL板厚/e, TYPE)・備考」。
- 寸法は紙上mm（A1想定）。--scale を付けると DXF の座標をその倍率で拡大する
  （1/50 の図面のモデル空間に置くなら --scale 50）。PDF は常に紙上寸法。
- 外部ライブラリは matplotlib だけ（ezdxf 不要）。日本語フォントは
  Noto Sans CJK JP → IPAGothic の順に探す。
- 図枠・表題欄は付けない（ユーザー指定）。
"""
import json
import sys

# ---------------------------------------------------------------- レイアウト（紙上mm）
COLS = [  # (キー, 見出し, 幅)
    ("sym",  "符　号",     22),
    ("sec",  "部　材",     52),
    ("mat",  "鋼　種",     18),
    ("bolt", "nw × mw-HTB", 26),
    ("nP",   "nP",          9),
    ("mP",   "mP",          9),
    ("gpl",  "板厚",        9),
    ("e",    "e",           9),
    ("type", "TYPE",       10),
    ("rem",  "備　考",     80),
]
HDR_ROW = 6.0      # 見出し1段の高さ
ROW_H = 7.0        # データ行の高さ
TITLE_H = 7.0      # 表名の枠の高さ
GAP = 10.0         # 表と表の間隔
TXT = 2.5          # 文字高さ
TXT_TITLE = 3.0
LEFT_ALIGN = {"sec", "rem"}

# ACI 色（参考図に合わせる）
LAYERS = {
    "LIST_LINE":  7,    # 表の罫線
    "LIST_TEXT":  7,    # 表の文字
    "LIST_TITLE": 40,   # 表名・特記（オレンジ）
}


def col_x(x0):
    """各列の左端 x と右端 x を返す。"""
    xs = []
    x = x0
    for _, _, w in COLS:
        xs.append((x, x + w))
        x += w
    return xs, x


# ---------------------------------------------------------------- 描画プリミティブの収集
class Canvas:
    """LINE と TEXT をためて、あとで DXF / PDF に流す。"""

    def __init__(self):
        self.lines = []   # (x1, y1, x2, y2, layer)
        self.texts = []   # (x, y, text, h, align, layer)  align: 'c' | 'l'

    def line(self, x1, y1, x2, y2, layer="LIST_LINE"):
        self.lines.append((x1, y1, x2, y2, layer))

    def rect(self, x1, y1, x2, y2, layer="LIST_LINE"):
        self.line(x1, y1, x2, y1, layer)
        self.line(x2, y1, x2, y2, layer)
        self.line(x2, y2, x1, y2, layer)
        self.line(x1, y2, x1, y1, layer)

    def text(self, x, y, s, h=TXT, align="c", layer="LIST_TEXT"):
        if s is None or s == "":
            return
        self.texts.append((x, y, str(s), h, align, layer))

    def cell_text(self, xl, xr, yb, yt, s, h=TXT, align="c", layer="LIST_TEXT"):
        yc = (yb + yt) / 2
        if align == "l":
            self.text(xl + 1.5, yc, s, h, "l", layer)
        else:
            self.text((xl + xr) / 2, yc, s, h, "c", layer)


def draw_table(cv, x0, ytop, table):
    """表名・見出し・データ行を描き、表の下端 y を返す。"""
    xs, xr_end = col_x(x0)
    name = table.get("name", "")

    # 表名の枠（参考図の「小梁・間柱・その他」の書き方）
    y = ytop
    tw = max(40.0, TXT_TITLE * len(name) * 1.1 + 6)
    cv.rect(x0, y - TITLE_H, x0 + tw, y, "LIST_TITLE")
    cv.text(x0 + 2, y - TITLE_H / 2, name, TXT_TITLE, "l", "LIST_TITLE")
    y -= TITLE_H

    # 見出し 3段
    h3 = HDR_ROW * 3
    yh_top, yh_bot = y, y - h3
    y1 = yh_top - HDR_ROW          # 1段目の下
    y2 = yh_top - HDR_ROW * 2      # 2段目の下
    cv.rect(x0, yh_bot, xr_end, yh_top)
    # 符号・部材・鋼種・備考は 3段ぶち抜き
    for i, (key, label, _) in enumerate(COLS):
        xl, xr = xs[i]
        if key in ("sym", "sec", "mat", "rem"):
            cv.line(xr, yh_bot, xr, yh_top)
            cv.cell_text(xl, xr, yh_bot, yh_top, label)
    # 接合部グループ（bolt〜type）
    xb_l = xs[3][0]
    xb_r = xs[8][1]
    cv.line(xb_l, y1, xb_r, y1)
    cv.cell_text(xb_l, xb_r, y1, yh_top, "接　合　部")
    # nw×mw-HTB は 2段ぶち抜き
    xl, xr = xs[3]
    cv.line(xr, yh_bot, xr, y1)
    cv.cell_text(xl, xr, yh_bot, y1, "nw × mw-HTB")
    # ピッチ (nP, mP)
    xl, xr = xs[4][0], xs[5][1]
    cv.line(xl, y2, xr, y2)
    cv.line(xr, yh_bot, xr, y1)
    cv.cell_text(xl, xr, y2, y1, "ピッチ")
    cv.line(xs[4][1], yh_bot, xs[4][1], y2)
    cv.cell_text(xs[4][0], xs[4][1], yh_bot, y2, "nP")
    cv.cell_text(xs[5][0], xs[5][1], yh_bot, y2, "mP")
    # G.PL (板厚, e)
    xl, xr = xs[6][0], xs[7][1]
    cv.line(xl, y2, xr, y2)
    cv.line(xr, yh_bot, xr, y1)
    cv.cell_text(xl, xr, y2, y1, "G.PL")
    cv.line(xs[6][1], yh_bot, xs[6][1], y2)
    cv.cell_text(xs[6][0], xs[6][1], yh_bot, y2, "板厚")
    cv.cell_text(xs[7][0], xs[7][1], yh_bot, y2, "e")
    # TYPE は 2段ぶち抜き
    xl, xr = xs[8]
    cv.cell_text(xl, xr, yh_bot, y1, "TYPE")

    # データ行
    y = yh_bot
    rows = table.get("rows", [])
    for row in rows:
        yb = y - ROW_H
        cv.line(x0, yb, xr_end, yb)
        for i, (key, _, _) in enumerate(COLS):
            xl, xr = xs[i]
            cv.line(xl, yb, xl, y)
            val = row.get(key, "")
            if val is None or str(val).strip() == "":
                val = "-" if key not in ("rem", "sym", "sec", "mat") else ""
            cv.cell_text(xl, xr, yb, y, val, TXT, "l" if key in LEFT_ALIGN else "c")
        cv.line(xr_end, yb, xr_end, y)
        y = yb
    if not rows:
        yb = y - ROW_H
        cv.rect(x0, yb, xr_end, y)
        cv.cell_text(x0, xr_end, yb, y, "（該当部材なし）")
        y = yb
    return y


def build(data, x0=0.0, y0=0.0):
    cv = Canvas()
    y = y0
    title = data.get("title")
    if title:
        cv.text(x0, y + 2, title, 4.0, "l", "LIST_TITLE")
        y -= 8
    for t in data.get("tables", []):
        y = draw_table(cv, x0, y, t)
        y -= GAP
    notes = data.get("notes", [])
    if notes:
        cv.text(x0, y, "特記事項", TXT_TITLE, "l", "LIST_TITLE")
        y -= 6
        for n in notes:
            cv.text(x0 + 2, y, "・" + n, TXT, "l", "LIST_TITLE")
            y -= 5
    _, xr = col_x(x0)
    return cv, (x0, y, xr, y0 + 6)


# ---------------------------------------------------------------- DXF R12
def write_dxf(cv, path, scale=1.0):
    def g(code, val):
        return "%3d\n%s\n" % (code, val)

    out = []
    out.append(g(0, "SECTION") + g(2, "HEADER") + g(9, "$ACADVER") + g(1, "AC1009") + g(0, "ENDSEC"))
    out.append(g(0, "SECTION") + g(2, "TABLES"))
    out.append(g(0, "TABLE") + g(2, "LTYPE") + g(70, 1))
    out.append(g(0, "LTYPE") + g(2, "CONTINUOUS") + g(70, 0) + g(3, "Solid line") + g(72, 65) + g(73, 0) + g(40, "0.0"))
    out.append(g(0, "ENDTAB"))
    out.append(g(0, "TABLE") + g(2, "LAYER") + g(70, len(LAYERS)))
    for name, color in LAYERS.items():
        out.append(g(0, "LAYER") + g(2, name) + g(70, 0) + g(62, color) + g(6, "CONTINUOUS"))
    out.append(g(0, "ENDTAB") + g(0, "ENDSEC"))
    out.append(g(0, "SECTION") + g(2, "ENTITIES"))
    s = scale
    for x1, y1, x2, y2, layer in cv.lines:
        out.append(g(0, "LINE") + g(8, layer)
                   + g(10, "%.3f" % (x1 * s)) + g(20, "%.3f" % (y1 * s)) + g(30, "0.0")
                   + g(11, "%.3f" % (x2 * s)) + g(21, "%.3f" % (y2 * s)) + g(31, "0.0"))
    for x, y, text, h, align, layer in cv.texts:
        just = 1 if align == "c" else 0
        out.append(g(0, "TEXT") + g(8, layer)
                   + g(10, "%.3f" % (x * s)) + g(20, "%.3f" % (y * s)) + g(30, "0.0")
                   + g(40, "%.3f" % (h * s)) + g(1, text)
                   + g(72, just) + g(73, 2)
                   + g(11, "%.3f" % (x * s)) + g(21, "%.3f" % (y * s)) + g(31, "0.0"))
    out.append(g(0, "ENDSEC") + g(0, "EOF"))
    with open(path, "wb") as f:
        f.write("".join(out).encode("cp932", errors="replace"))


# ---------------------------------------------------------------- PDF (matplotlib)
def _jp_font():
    from matplotlib import font_manager
    names = {f.name: f.fname for f in font_manager.fontManager.ttflist}
    for cand in ("Noto Sans CJK JP", "Noto Sans JP", "IPAGothic", "IPAPGothic", "IPAexGothic"):
        if cand in names:
            return font_manager.FontProperties(fname=names[cand])
    return font_manager.FontProperties()


ACI_RGB = {7: "#000000", 40: "#d26a00", 1: "#d00000", 2: "#b8a000", 3: "#00a000", 4: "#008c9e"}


def write_pdf(cv, bbox, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fp = _jp_font()
    x0, y0, x1, y1 = bbox
    m = 10.0
    w_in = (x1 - x0 + 2 * m) / 25.4
    h_in = (y1 - y0 + 2 * m) / 25.4
    fig = plt.figure(figsize=(w_in, h_in))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(x0 - m, x1 + m)
    ax.set_ylim(y0 - m, y1 + m)
    ax.set_aspect("equal")
    ax.axis("off")
    for xa, ya, xb, yb, layer in cv.lines:
        ax.plot([xa, xb], [ya, yb], color=ACI_RGB.get(LAYERS[layer], "#000"), lw=0.5)
    for x, y, text, h, align, layer in cv.texts:
        pt = h / 25.4 * 72 * 0.95  # mm → pt
        ax.text(x, y, text, fontproperties=fp, fontsize=pt,
                ha="center" if align == "c" else "left", va="center",
                color=ACI_RGB.get(LAYERS[layer], "#000"))
    fig.savefig(path, format="pdf")
    plt.close(fig)


# ---------------------------------------------------------------- main
def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 1
    scale = 1.0
    if "--scale" in argv:
        i = argv.index("--scale")
        scale = float(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    src, dxf, pdf = argv[1:4]
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    cv, bbox = build(data)
    write_dxf(cv, dxf, scale)
    write_pdf(cv, bbox, pdf)
    n = sum(len(t.get("rows", [])) for t in data.get("tables", []))
    print("tables=%d rows=%d -> %s, %s" % (len(data.get("tables", [])), n, dxf, pdf))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
