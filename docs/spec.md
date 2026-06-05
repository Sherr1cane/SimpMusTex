# MusTex v0.1

`MusTex` 是第一版手动输入简谱的文本格式。目标不是取代 MusicXML，而是先把“人工好输、机器好解析”的桥搭起来：

`MusTex 文本 -> MusTex JSON -> 标准化简谱文本输出`

当前版本只处理音符、休止、小节线与基础谱面头信息，不处理歌词。

## 设计原则

- 简谱是独立记谱系统，JSON 先保留 `degree`、`octaveShift`、`underlines`、`dots`、`extensions`。
- 文本输入优先让人直接敲出来，不要求一开始就写大段 JSON。
- 导出阶段先做“标准化文本打印”，后续再接 SVG / PDF / MusicXML。

## 文件结构

头信息使用 `key: value`，正文放在空行后。

```text
title: 示例
key: 1=F
meter: 4/4
tempo: 88

6, 1 2 3 | 6 6_ 1 2 | 3--- ||
```

支持的头信息：

- `title`
- `composer`
- `arranger`
- `key`
- `meter`
- `tempo`

其中：

- `key: 1=F` 表示简谱 `1` 对应 `F`
- `meter: 4/4` 表示拍号
- `tempo: 88` 表示四分音符 BPM

## Token 规则

### 音符

基础格式：

```text
degree accidental octave underlines dots extensions
```

其中顺序写成一个 token，例如：

- `6`
- `6,`
- `1'`
- `4#`
- `5__`
- `3.`
- `2---`
- `6,_.`

### 符号说明

| 写法 | 含义 |
| --- | --- |
| `1`..`7` | 简谱音级 |
| `0` | 休止符 |
| `#` | 升号 |
| `b` | 降号 |
| `n` | 还原号 |
| `'` | 高八度点，重复可叠加，如 `1''` |
| `,` | 低八度点，重复可叠加，如 `6,,` |
| `_` | 下横线，一条表示八分音符，两条表示十六分音符 |
| `.` | 附点，可重复 |
| `-` | 延音线，写在当前音后面 |
| <code>\|</code> | 普通小节线 |
| <code>\|\|</code> | 双小节线 / 终止线打印形式 |
| <code>\|:</code> | 反复开始 |
| <code>:\|</code> | 反复结束 |
| <code>:\|:</code> | 反复结束并再次开始 |
| `~` | 延音线 tie，连接两个相同音 |
| `<s ... >` | 圆滑线 slur，包住一个音组 |
| `<p ... >` | 乐句线 phrase，包住一个音组 |
| `( ... )` | 不唱括号 / 哼唱外括号组 |
| `{5'}6` | 前倚音 |
| `{/5'}6` | 带斜杠前倚音 |
| `6{>5'}` | 后倚音 / 强调倚音 |
| `3@trill` | 波音装饰 |
| `3@mordent` | 回音装饰 |
| `3@slide(up)` | 滑音装饰 |
| `3@fermata` | 延长记号 |
| `3@breath` | 换气记号 |
| `[1 ... ]` | 一房子 |
| `[2 ... ]` | 二房子 |
| `<tuplet 3:2 ... >` | 连音组 / 三连音等 |

### 时值约定

在 v0.1 里，默认一拍是四分音符。

- `6` = 1 拍
- `6_` = 0.5 拍
- `6__` = 0.25 拍
- `6.` = 1.5 拍
- `6_.` = 0.75 拍
- `6---` = 4 拍

JSON 中会同时保留：

- `underlines`
- `dots`
- `extensions`
- `beats`

其中 `beats` 是便于计算的派生值，原始视觉写法仍以前三项为准。

## JSON 结构

顶层 schema：

- `schema`: `mustex-score/v0.1`
- `format`: `MusTex`
- `metadata`
- `global`
- `sections`
- `source`

音符元素示例：

```json
{
  "type": "note",
  "degree": 6,
  "octaveShift": -1,
  "accidental": null,
  "duration": {
    "unit": "quarter",
    "underlines": 0,
    "dots": 0,
    "extensions": 0,
    "beats": 1.0
  },
  "raw": "6,"
}
```

休止符示例：

```json
{
  "type": "rest",
  "duration": {
    "unit": "quarter",
    "underlines": 1,
    "dots": 0,
    "extensions": 0,
    "beats": 0.5
  },
  "raw": "0_"
}
```

## v0.1 范围

已支持：

- 头信息
- 音符
- 休止符
- 升降还原
- 高低八度
- 下横线
- 附点
- 延音线
- 小节线
- 反复线
- 显式 `tie`：`6~6`、`6~ | 6`
- 显式 `slur`：`<s 3 2 1 >`、`<s 3 2 | 1 >`
- `phrase`：`<p 6 5 3 2 | 1 >`
- 不唱括号：`( 6, 5, 6 1 2 )`
- 倚音：`{5'}6`、`{/5'}6`、`6{>5'}`
- 装饰音：`@trill`、`@mordent`、`@slide(up)`、`@fermata`、`@breath`
- 房子：`[1 6--- :|]`、`[2 6-- 1 2 |]`
- 连音组：`<tuplet 3:2 1_ 2_ 3_>`
- JSON 输出
- 从 JSON 打印标准化 MusTex 谱面
- SVG 基础排版

暂未支持：

- 歌词
- 多声部
- 正式出版级页面布局
- PDF 图形排版

## CLI

解析为 JSON：

```bash
python archive/tools/mustex.py parse archive/data/examples/mustex_demo.txt
```

从文本打印标准化谱面：

```bash
python archive/tools/mustex.py print archive/data/examples/mustex_demo.txt
```

从 JSON 打印标准化谱面：

```bash
python archive/tools/mustex.py print archive/data/examples/mustex_demo.json
```
