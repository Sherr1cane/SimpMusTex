# MusTex 交接摘要

日期：2026-06-05

## 目标

本轮工作是在 `ToneCraft_Teochew` 里推进一个手动输入简谱系统 `MusTex`：

`MusTex 文本 -> 简谱 JSON -> 标准化文本 -> SVG`

重点不是 MusicXML 兼容，而是先把“手输方便、解析稳定、能出谱”的链路做通。

## 主要文件

- 核心实现：
  - `/Users/sherricane/Documents/workspace/ToneCraft_Teochew/archive/pkgs/mustex/core.py`
  - `/Users/sherricane/Documents/workspace/ToneCraft_Teochew/archive/pkgs/mustex/__init__.py`
- CLI：
  - `/Users/sherricane/Documents/workspace/ToneCraft_Teochew/archive/tools/mustex.py`
- 文档：
  - `/Users/sherricane/Documents/workspace/ToneCraft_Teochew/archive/docs/mustex_v0_1.md`
  - `/Users/sherricane/Documents/workspace/ToneCraft_Teochew/archive/docs/mustex_score.schema.json`
- 测试：
  - `/Users/sherricane/Documents/workspace/ToneCraft_Teochew/archive/tests/test_mustex.py`
- 示例：
  - `/Users/sherricane/Documents/workspace/ToneCraft_Teochew/archive/data/examples/mustex_demo.txt`
  - `/Users/sherricane/Documents/workspace/ToneCraft_Teochew/archive/data/examples/mustex_curves_demo.txt`
- 当前用户谱：
  - `/Users/sherricane/Documents/workspace/ToneCraft_Teochew/苦恋.mustex`
  - `/Users/sherricane/Documents/workspace/ToneCraft_Teochew/苦恋.svg`

## 当前已支持语法

### 基础

- 头信息：
  - `title`
  - `key: 1=F`
  - `meter: 4/4`
  - `tempo: 107`
- 音符、休止、升降号、八度、附点、下横线、延音
- 小节线：
  - `|`
  - `||`
  - `|:`
  - `:|`
  - `:|:`

### 曲线和分组

- `tie`：
  - `6~6`
  - `6~ | 6`
- `slur`：
  - `<s 3 2 1 >`
  - `<s 3 2 | 1 >`
- `phrase`：
  - `<p 6 5 3 2 | 1 >`
- 不唱括号：
  - `( 6, 5, 6 1 2 )`

### 倚音与装饰音

- 前倚音：
  - `{5'}6`
- 短倚音：
  - `{/5'}6`
- 后倚音：
  - `6{>5'}`
- 装饰音：
  - `3@trill`
  - `3@mordent`
  - `3@slide(up)`
  - `3@fermata`
  - `3@breath`

### 房子和连音组

- 房子：
  - `[1 6--- :|]`
  - `[2 6-- 1 2 |]`
- 连音组 / 三连音：
  - `<tuplet 3:2 1_ 2_ 3_>`

## 当前规则约定

### 延音

- `-` 是延长音，写在当前音后面
- SVG 不再画小线段，而是直接画 `—`
- 延音在布局里按独立槽位处理，不是挂在前一个音后面

### 下横线

- 下横线按拍断开
- 同拍内端点已做统一
- 横向位置不按时值拉伸，主要按音符序列排
- 时值主要由下横线和延长音表达

### 倚音

- 倚音里不允许写时值
- 如 `{6,__}` 这类写法会直接报错
- `/` 只表示短倚音
- SVG 上倚音统一画两条小横线
- 倚音连接线现在改成画在下面，接近用户给的图例

### 低音点避让

- 这已经抽成通用规则
- 普通音和倚音如果下方有横线，低音点都会自动下移，避免遮挡

## SVG 当前状态

### 已完成

- 标题、调号、拍号、速度
- 一行 5 个小节
- 行内小节宽度按内容自适应
- 音符最小横向间距
- 下横线按拍断开
- 延长音 `—`
- `tie / slur / phrase`
- 倚音双横线与下方小钩
- 房子基础线条
- tuplet 基础线条与比值文字
- 跨行 `()` 已能显示：
  - 起始行画 `(`
  - 结束行画 `)`

### 还不够好的地方

- 倚音的小钩现在方向和层级对了，但形状还不够像正式印刷谱
- `phrase / slur / tuplet / ornament / house` 之间还缺少系统性的碰撞避让
- 跨行 `()` 只是显示左右括号，还没有更强的“整段包络感”
- 房子、tuplet、装饰音还是基础可见版，不是正式出版级

## 苦恋.mustex 的现状

当前文件：

`/Users/sherricane/Documents/workspace/ToneCraft_Teochew/苦恋.mustex`

目前内容大意是一个跨多小节的括号组，里面包含：

- 基础音符
- `tie`
- 延长音
- 一个倚音：`{6,}1--`

最新 `苦恋.svg` 已成功生成：

`/Users/sherricane/Documents/workspace/ToneCraft_Teochew/苦恋.svg`

## 已验证命令

解析：

```bash
python3 archive/tools/mustex.py parse '/Users/sherricane/Documents/workspace/ToneCraft_Teochew/苦恋.mustex'
```

标准化打印：

```bash
python3 archive/tools/mustex.py print '/Users/sherricane/Documents/workspace/ToneCraft_Teochew/苦恋.mustex'
```

生成 SVG：

```bash
python3 archive/tools/mustex.py svg '/Users/sherricane/Documents/workspace/ToneCraft_Teochew/苦恋.mustex' -o '/Users/sherricane/Documents/workspace/ToneCraft_Teochew/苦恋.svg'
```

跑测试：

```bash
python3 -m unittest archive/tests/test_mustex.py -v
```

## 当前测试状态

最后一次确认：

- `python3 -m unittest archive/tests/test_mustex.py -v`
- 全部通过

## 本轮关键设计决策

1. 不按时值压缩十六分音横向位置
2. 延长音按独立槽位布局
3. 倚音不允许写时值
4. 低音点避让抽成通用规则，不只修倚音
5. 跨行括号必须能显示，不能因为跨行直接跳过

## 建议下一个 agent 优先做的事

### 第一优先级

- 倚音样式精修
  - 小钩更像印刷谱里的逗号形
  - 双横线长度再细一点
  - 倚音与主音的相对位置再压紧一点

### 第二优先级

- 统一做纵向碰撞避让
  - `phrase`
  - `slur`
  - `tuplet`
  - `ornament`
  - `house`
  - 高音点 / 低音点

### 第三优先级

- 跨行分组体验优化
  - `()` 跨行时做更强的视觉连贯
  - `phrase / slur` 跨行如何表达

## 注意事项

- 不要破坏当前 `苦恋.mustex -> 苦恋.svg` 这条链路
- 倚音时值报错是明确约定，不要放宽
- 当前许多测试是坐标级别断言，改样式时需要同步更新测试
