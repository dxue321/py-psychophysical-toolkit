**[English](README.md) | 中文 | [Español](README.es.md)**

---

# Python Psychophysical Toolkit

用 Python 实现的强制选择**主观评价（user study）**工具，流程类似 Psychtoolbox，专门用来比较图像处理方法。

- 两种试次设计，由配置中的 `mode` 选择：

**pairwise**（两两比较，2AFC）每次随机抽取两种方法的结果，左右随机并排显示，可选在中间加参考图；
**all**（全部对比，N-AFC）每次把一个场景下所有方法的结果一次性并排显示在一行，受试者从中选出最好的一张，可选在上方单独一行居中显示参考图。方法名不会显示，是盲测。

- 支持多名受试者依次参加，每人结果单独保存，不会互相覆盖。
- 自带分析流程：汇总所有受试者数据，做统计检验并画图。
- 可直接导出适合双栏论文模板的矢量图，并附带可粘贴的 LaTeX 代码。

## 快速开始

```bash
pip install -r requirements.txt
python make_demo_data.py                                     # 生成演示图像
python experiment.py --config config/config_with_reference.json --adapt 60   # 两两比较（2AFC）
python experiment.py --config config/config_all_methods.json --adapt 60      # 全部对比（N-AFC）
python analysis.py                                           # 结果 -> analysis/
python paper_figure.py --ours Ours                            # 论文图 -> paper_figures/
```

需要 Python 3.9 或更高版本。

## 文件说明

| 文件 | 作用 |
|---|---|
| `experiment.py` | 运行一名受试者的实验并保存结果 |
| `analysis.py` | 汇总 `results/`，输出统计表和总览图 |
| `paper_figure.py` | 导出论文用矢量图和 LaTeX 代码 |
| `make_demo_data.py` | 生成演示图像，方便试用 |
| `simulate.py` | 模拟受试者数据，用来测试流程或估算所需人数 |
| `config/config_with_reference.json` / `config/config_without_reference.json` | 两两比较配置样例（有 / 无参考图） |
| `config/config_all_methods.json` | 全部对比（N-AFC）配置样例 |

自动生成的输出文件夹（已加入 `.gitignore`）：`results/`、`analysis/`、`paper_figures/`。

## 第一步：整理图像

每种方法一个子文件夹，各文件夹内文件名要一致：

```
my_study/
├── methods/              ← 配置中的 "root"
│   ├── Ours/       001.png  002.png  003.png ...
│   ├── BM3D/       001.png  002.png  003.png ...
│   └── DnCNN/      001.png  002.png  003.png ...
└── reference/            ← 可选，配置中的 "reference"
    001.png  002.png  003.png ...
```

匹配时忽略扩展名（`001.png` 等于 `001.jpg`）。某方法（或参考图）缺少的场景会被跳过并给出警告。用 `exclude` 排除某个子文件夹，或用 `methods` 直接列出要用的文件夹。

## 第二步：编写配置文件

复制 `config/config_with_reference.json`（排列为"候选图 | 参考图 | 候选图"）、`config/config_without_reference.json`（只有两张候选图，无参考），或 `config/config_all_methods.json`（一次显示所有方法，见第四步）并修改。命令行参数会覆盖配置文件里的同名设置，例如 `--adapt 5`。

常用的键：

| 键 | 命令行参数 | 默认值 | 说明 |
|---|---|---|---|
| `mode` | `--mode` | pairwise | `pairwise`（两两比较）或 `all`（一次显示所有方法） |
| `root` | `--root` | — | 方法根目录，每个子文件夹是一种方法 |
| `reference` | `--reference` | 无 | 参考图文件夹，设为 `null` 表示不用 |
| `question` | `--question` | "Which image has better quality?" | 每个试次都会显示 |
| `adapt` | `--adapt` | 60 | 环境光适应时长（秒），0 表示跳过 |
| `n_trials` | `--n-trials` | 全部 | 随机抽取这么多试次（pairwise 模式下各方法对均衡） |
| `seed` | `--seed` | 随机 | 固定后试次顺序可复现 |
| `fullscreen` | `--fullscreen` | false | 正式实验建议打开 |
| `mouse` | `--mouse` | false | 允许鼠标点击图像作答（`mode: all` 超过 9 种方法时必须开启） |

<details>
<summary>完整配置项列表</summary>

| 键（命令行参数） | 默认 | 说明 |
|---|---|---|
| `mode` (`--mode`) | pairwise | `pairwise` 或 `all`（见第四步） |
| `root` (`--root`) | — | 方法根目录，每个子文件夹是一种方法 |
| `methods` (`--methods`) | — | 直接列出各方法文件夹，与 `root` 二选一 |
| `exclude` (`--exclude`) | 无 | 使用 `root` 时要排除的子文件夹名 |
| `reference` (`--reference`) | 无 | 参考图文件夹，设为 `null` 表示不显示 |
| `question` (`--question`) | 见上 | 实验要求 |
| `instructions` (`--instructions`) | 内置文本 | 说明页文本文件（UTF-8） |
| `adapt` (`--adapt`) | 60 | 环境光适应时长（秒），0 表示跳过 |
| `repeats` (`--repeats`) | 1 | 完整设计重复几遍——场景 × 所有方法对（pairwise）或仅场景（all） |
| `n_trials` (`--n-trials`) | 全部 | 随机抽取这么多试次，pairwise 下各方法对均衡，all 下按场景抽样 |
| `seed` (`--seed`) | 随机 | 固定后试次顺序可复现 |
| `fixation` / `iti` | 0.5 / 0.3 | 注视点时长、试次间隔（秒） |
| `duration` (`--duration`) | 0 | 图像呈现时长（秒），0 表示一直显示到作答 |
| `break_every` (`--break-every`) | 50 | 每多少个试次休息一次，0 表示不休息 |
| `show_progress` | false | 屏幕右下角显示进度 |
| `mouse` (`--mouse`) | false | 允许鼠标点击作答 |
| `fullscreen` (`--fullscreen`) | false | 正式实验建议打开 |
| `window` (`--window W H`) | 1600 900 | 非全屏时的窗口大小 |
| `bg` / `fg` | [128,128,128] / [230,230,230] | 背景色和文字颜色（RGB） |
| `gap` (`--gap`) | 0.02 | 图像间距，占屏幕宽度的比例 |
| `upscale` (`--upscale`) | false | 允许放大图像填满屏幕 |
| `out_dir` (`--out-dir`) | results | 结果文件夹 |
| （仅命令行）`--subject` | 屏幕输入 | 直接指定受试者代号，跳过输入姓名 |
| （仅命令行）`--dry-run` | — | 只检查文件夹并统计试次数，不运行实验 |

说明页文本支持占位符：`{question}`、`{n_trials}`、`{break_every}`、`{ref_sentence}`、`{ref_hint}`、`{mouse_sentence}`、`{n_methods}`，运行时都会自动填入。`mode: all` 且未指定 `--instructions` 时，会使用内置的、说明按数字键作答的模板，而不是两两比较的模板。
</details>

## 第三步：试运行

```bash
python experiment.py --config config/config_with_reference.json --dry-run     # 检查文件夹和试次数，不开窗口
python experiment.py --config config/config_with_reference.json --adapt 5 --n-trials 10   # 自己完整试一遍
```

打印的试次数取决于 `mode`：pairwise 是 `场景数 × M(M−1)/2 × 重复次数`，all 只是 `场景数 × 重复次数`（见实验设计建议）。试运行结果也会写进 `results/` —— 正式实验前请删除。

## 第四步：正式实验

每名受试者运行一次：

```bash
python experiment.py --config config/config_with_reference.json
```

流程：输入姓名 → 确认保存代号 → 说明页（按空格继续）→ 环境光适应 → 试次（注视点 → 图像 → 作答）→ 结束。

`mode: all` 且有参考图时，画面分两行：参考图单独居中显示在第一行，所有候选图并排显示在第二行。下面是用演示图像生成的实际试次截图，可以看出两种设计的区别：

| `mode: pairwise` | `mode: all` |
|---|---|
| ![pairwise 试次：两张候选图，参考图在中间](assets/screenshot_pairwise.png) | ![all 试次：参考图单独一行居中，候选图并排在下面](assets/screenshot_all.png) |
| 每次只比较两种方法，参考图在中间 | 所有方法一次性显示，参考图单独一行居中 |

**按键（`mode: pairwise`）：** `←`/`F` = 选左边，`→`/`J` = 选右边，`ESC` = 随时退出。
**按键（`mode: all`）：** `1`–`9` = 选择对应数字下的图像，`ESC` = 随时退出。超过 9 种方法时必须开启 `--mouse`（数字键最多只能对应 9 个位置）；开启 `mouse: true` 后，两种模式下都可以直接点击图像作答。

每名受试者的结果保存在 `results/<姓名>.csv`（重名自动改为 `<姓名>_2` 等，不会覆盖）。每完成一个试次就立即保存，中途退出也不会丢失数据。

## 第五步：数据分析

```bash
python analysis.py
```

读取 `results/` 中的全部数据，输出到 `analysis/`（两种设计的结果可以放在同一个文件夹里混合分析，见下面的统计方法说明）：

- **`results.png`/`.pdf`** —— 被选率、Thurstone 量表、两两偏好矩阵、各场景分布
- **`per_subject.png`** —— 检查受试者之间是否一致
- **`method_summary.csv`、`pairwise_tests.csv`、`preference_matrix.csv`、`per_scene.csv`、`per_subject.csv`**

每增加一名受试者重新运行即可，会自动重新读取全部数据。常用参数：`--boot-unit scene`（更保守的重抽样）、`--question "..."`（把实验要求印到图上）。

## 第六步：生成论文用图

```bash
python paper_figure.py --ours Ours
python paper_figure.py --ours Ours --rename Blur="Gaussian blur" --order Ours BM3D DnCNN
```

生成适合双栏论文模板尺寸的矢量 PDF（附 PNG 预览），以及含图注的 `latex_snippets.tex`：

| 文件 | 尺寸 | 内容 |
|---|---|---|
| `fig_preference_rate.pdf` | 单栏 | 各方法被选率 |
| `fig_scale.pdf` | 单栏 | Thurstone 量表值 |
| `fig_pairwise.pdf` | 单栏 | 两两偏好矩阵 |
| `fig_ours_vs.pdf` | 单栏 | 你的方法 vs. 各对比方法 |
| `fig_overview.pdf` | 通栏 | 以上三部分合并 |

`fig_overview` 示例（PNG 预览），数据来自 `simulate.py` 生成的演示数据：

![fig_overview 示例：被选率、感知量表、两两偏好三个面板](assets/paper_figure_example.png)

常用参数：`--ours NAME`（高亮并生成 `fig_ours_vs`）、`--rename 文件夹=显示名`、`--order A B C`、`--font serif|sans`、`--font-size N`。

LaTeX 中用 `\linewidth` / `\textwidth` 设置宽度 —— 图已经是这个尺寸，不会被缩放。

## 数据格式

每名受试者一个 CSV，每行一个试次，列结构取决于 `mode`：

**`mode: pairwise`**

| 列 | 含义 |
|---|---|
| `subject`、`trial`、`scene` | 受试者代号、试次序号、场景名 |
| `left` / `right` | 左右两侧显示的方法 |
| `chosen` / `not_chosen` | 被选中 / 未被选中的方法 |
| `chosen_side`、`rt`、`reference`、`scale`、`timestamp` | 选择的方向、反应时、是否有参考图、显示缩放、作答时间 |

**`mode: all`**

| 列 | 含义 |
|---|---|
| `subject`、`trial`、`scene` | 受试者代号、试次序号、场景名 |
| `shown` | 所有候选方法，用 `;` 连接，按左到右的显示顺序 |
| `chosen` | 被选中的方法 |
| `position`、`rt`、`reference`、`scale`、`timestamp` | `chosen` 在 `shown` 中的 1 起始位置、反应时、是否有参考图、显示缩放、作答时间 |

只要列名匹配其中一种格式，用其他工具（如 PsychoPy）采集的数据也能用 `analysis.py` / `paper_figure.py` 分析（两种格式会自动按文件识别）；至少需要 `subject`、`chosen`，以及 `not_chosen` 或 `shown` 之一。两种格式的结果可以放在同一个 `results/` 文件夹里：`analysis.py` 会把每个 all 模式的试次展开成"获胜方法 vs. 每个落选方法"的两两比较，再一起分析（这在无关选项独立性，IIA 假设下是合理的）。如果两批数据其实是两个独立的研究（而不是同一个研究里想顺便比较两种设计），建议用不同的 `out_dir` 分开保存——按研究分，而不是按 `mode` 分，避免把不相关的数据不小心混进同一次分析。

## 统计方法简述

- **被选率（choice rate）** —— 作为两两比较的胜率：被选次数 ÷ 出现次数（`mode: all` 的试次会展开为获胜方法战胜每个落选方法）。置信区间用 Wilson 方法。50% 为平均水平，两种模式下可直接比较。
- **选中率（selection rate，仅 `mode: all`）** —— 某方法在它参与的所有 N 选 1 试次中真正获胜的比例；机会水平是 `1/候选数`，不是 50%。
- **Thurstone 量表** —— 由所有两两比较推出的感知尺度（z 值，最差方法定为 0）。
- **Bradley–Terry** —— 另一种配对比较模型，作为对照输出，通常与 Thurstone 结果高度一致。
- **两两检验** —— 对每对方法做双侧二项检验（与 50% 比较），Holm 校正。`*` p<.05，`**` p<.01，`***` p<.001。
- **`--boot-unit`** —— bootstrap 重抽样的单位：`trial`（默认——一个 N 选 1 试次及其展开出的所有两两比较会作为一个整体重抽样，而不是分别重抽样）、`scene`（想推广到"这类图像"时用）、`subject`（建议至少 5 人）。

## 实验设计建议

- **试次数**：pairwise = 场景数 × M(M−1)/2 × 重复次数（M = 方法数）；all = 场景数 × 重复次数。太多时用 `n_trials` 抽样。
- **怎么选设计** —— `all` 用更少的试次直接得到"M 个里最好的是哪个"的判断，但每个试次产生的独立两两比较信息更少，而且屏幕上每张图更小；大约 5–6 种方法以内比较合适（硬上限：不开 `--mouse` 时最多 9 种）。
- **受试者人数** —— 建议 15–30 人以上。可先用 `simulate.py` 估算需要多少人（也支持 `--mode all`）。
- **显示条件** —— 用全屏，固定亮度/色温/观看距离。做画质评价时最好 100% 显示（注意"shown at xx%"的警告），显示不下就裁剪图像或去掉参考图。
- **非英文界面** —— 直接用你的语言写 `question` 和说明页文本即可，程序会自动选用匹配的字体。
- **计时精度** —— pygame 没有和显示器刷新同步；如需精确到帧，建议用 PsychoPy 采集数据，再用本项目的 `analysis.py` / `paper_figure.py` 分析。
