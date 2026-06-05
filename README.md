# SimpMusTex

手输简谱系统：MusTex 文本 → 简谱 JSON → SVG

重点不是 MusicXML 兼容，而是"手输方便、解析稳定、能出谱"。

## 快速开始

```bash
# 解析为 JSON
python3 -m SimpMusTex.cli parse 苦恋.mustex -o 苦恋.json

# 生成 SVG
python3 -m SimpMusTex.cli svg 苦恋.mustex -o 苦恋.svg

# 标准化打印
python3 -m SimpMusTex.cli print 苦恋.mustex

# 跑测试
python3 -m unittest SimpMusTex/test_simp_mustex.py -v
```

## 语法示例

```
title: 苦恋
key: 1=F
meter: 4/4
tempo: 107

6,_ 5,_ 6,_ 1_ 2_ 3_ 5_ 3__ 2__ | 3--- |
6~6 <s 3 2 1 > |
{5'}6 {/5'}6 6{>5'} |
3@trill 3@mordent 3@slide(up) 3@fermata 3@breath |
[1 6--- :|] [2 6-- 1 2 |] |
<tuplet 3:2 1_ 2_ 3_> |
( 6, 5, 6 1 2 ) |
```

### 已支持语法

| 类别 | 语法 | 说明 |
|------|------|------|
| 头信息 | `title` / `key: 1=F` / `meter: 4/4` / `tempo: 107` | 标题、调号、拍号、速度 |
| 音符 | `1 2 3 4 5 6 7` | 基础音符 |
| 休止 | `0` | 休止符 |
| 升降号 | `4#'` | 升号 + 高八度 |
| 八度 | `6,`（低）/ `1'`（高） | 八度偏移 |
| 附点 | `6.` | 附点 |
| 下横线 | `6_` / `6__` | 八分 / 十六分 |
| 延音 | `6---` | 延长音 `—` |
| 小节线 | `\|` / `\|\|` / `\|:` / `:\|` / `:\|:` | 各类小节线 |
| 连音线 | `6~6` | tie |
| 圆滑线 | `<s 3 2 1 >` | slur |
| 乐句线 | `<p 6 5 3 2 \| 1 >` | phrase |
| 不唱括号 | `( 6, 5, 6 1 2 )` | 跨小节也可 |
| 前倚音 | `{5'}6` | 倚音 + 高八度 |
| 短倚音 | `{/5'}6` | 带斜线 |
| 后倚音 | `6{>5'}` | 重音后倚音 |
| 装饰音 | `3@trill` / `@mordent` / `@slide(up)` / `@fermata` / `@breath` | 各类装饰音 |
| 房子 | `[1 6--- :\|]` / `[2 6-- 1 2 \|]` | 一房子 / 二房子 |
| 连音组 | `<tuplet 3:2 1_ 2_ 3_>` | 三连音等 |

### 设计约定

- **延音** `—` 按独立槽位布局，不是挂在前一个音后面
- **下横线** 按拍断开，同拍内端点统一，不按时值拉伸
- **倚音** 不允许写时值（`{6,__}` 会报错）
- **低音点** 自动避让下横线，普通音和倚音通用

## 项目结构

```
SimpMusTex/
├── __init__.py          # 包入口，导出核心 API
├── core.py              # 解析器 + SVG 渲染器
├── cli.py               # 命令行工具（parse / print / svg）
├── test_simp_mustex.py  # 测试
├── docs/
│   ├── spec.md          # 语法规范
│   ├── schema.json      # JSON schema
│   └── handoff.md       # 开发交接文档
└── examples/
    ├── demo.txt
    └── curves_demo.txt
```

## 许可

MIT
