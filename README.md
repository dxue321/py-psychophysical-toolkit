# Py Psychophysical Toolkit：图像处理方法的两两比较主观评价工具

用 Python 实现的心理物理实验工具，流程类似 Psychtoolbox，专门用来做图像处理方法的**主观评价（user study）**：

- 同一组原图经过多种方法处理后，程序每次随机抽取一个场景和其中两种方法的结果，左右随机并排显示，让受试者选出更符合要求的一张。可以选择在两张图中间显示参考图。
- 支持多名受试者依次参加。每人的结果单独保存，代号重复时自动改名，不会覆盖已有结果。
- 实验结束后，按方法汇总所有受试者的选择，做统计检验并画图。
- 能直接生成适合 CVPR 等双栏论文模板的矢量图，并附带可以直接粘贴的 LaTeX 代码。

---

## 目录

1. [文件说明](#文件说明)
2. [安装](#安装)
3. [使用流程](#使用流程)
4. [第一步：准备图像](#第一步准备图像)
5. [第二步：编写配置文件](#第二步编写配置文件)
6. [第三步：试运行](#第三步试运行)
7. [第四步：正式实验](#第四步正式实验)
8. [第五步：数据分析](#第五步数据分析)
9. [第六步：生成论文用图](#第六步生成论文用图)
10. [数据格式](#数据格式)
11. [统计方法说明](#统计方法说明)
12. [实验设计建议与注意事项](#实验设计建议与注意事项)

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `experiment.py` | 实验程序：输入姓名、实验说明、环境光适应、两两比较试次、保存结果 |
| `analysis.py` | 数据分析：汇总 `results/` 中所有受试者的结果，输出统计表和总览图 |
| `paper_figure.py` | 论文用图：按 CVPR 双栏尺寸生成矢量 PDF 和 LaTeX 代码 |
| `config_with_reference.json` | 配置样例：**有**中间参考图 |
| `config_without_reference.json` | 配置样例：**无**参考图，只有两张对比图 |
| `instructions_example.txt` | 实验说明页文本样例，两个配置共用 |
| `make_demo_data.py` | 生成演示图像（8 个场景 × 4 种方法 + 参考图），用来试跑 |
| `simulate.py` | 模拟受试者数据，用来检查分析流程、估算需要多少受试者 |

运行后会自动生成的文件夹：

| 文件夹 | 内容 |
|---|---|
| `results/` | 每名受试者一个 CSV，以及 `session_info/` 中每次实验的完整参数 |
| `analysis/` | `analysis.py` 输出的统计表和总览图 |
| `paper_figures/` | `paper_figure.py` 输出的论文用图和 LaTeX 代码 |

`paper_figures_sim/` 是用模拟数据生成的论文图示例。演示图像 `demo_images/` 不在仓库里，运行 `python make_demo_data.py` 即可生成。

`.gitignore` 已经排除了 `results/`、`analysis/`、`paper_figures/` 等文件夹，受试者的数据和生成的图不会被提交到仓库。

## 安装

需要 Python 3.9 或更高版本。

```bash
pip install -r requirements.txt
```

## 使用流程

```
准备图像 → 编写配置文件 → 试运行（--dry-run / 演示数据）→ 正式实验（每名受试者运行一次）
        → analysis.py 查看结果 → paper_figure.py 生成论文用图
```

最快的体验方式：

```bash
python make_demo_data.py                                     # 生成演示图像
python experiment.py --config config_with_reference.json --adapt 5
python analysis.py                                           # 结果在 analysis/
python paper_figure.py --ours Ours                           # 论文图在 paper_figures/
```

---

## 第一步：准备图像

每种方法的结果放在一个子文件夹里，**子文件夹名就是方法名**。同一场景在各个文件夹里的文件名要一致：

```
my_study/
├── methods/              ← 配置中的 "root"
│   ├── Ours/       001.png  002.png  003.png ...
│   ├── BM3D/       001.png  002.png  003.png ...
│   └── DnCNN/      001.png  002.png  003.png ...
└── reference/            ← 配置中的 "reference"（可选）
    001.png  002.png  003.png ...
```

- 匹配时只看文件名，不看扩展名，所以 `001.png` 和 `001.jpg` 算同一场景。
- 某种方法缺少的场景会被剔除，终端会给出警告。用了参考图时，参考图缺少的场景也会被剔除。
- 屏幕上不会显示方法名，受试者不知道每张图来自哪种方法，是盲测。
- 如果某个子文件夹不想参加比较，可以用 `exclude` 排除；也可以用 `methods` 直接列出要比较的文件夹。

## 第二步：编写配置文件

参数建议写在 JSON 配置文件里，便于复现。项目提供两个样例：

**有参考图**（`config_with_reference.json`）：屏幕上的排列是"左候选图 | 参考图 | 右候选图"，适合"哪张更接近原图 / 保真度更高"这类问题。

**无参考图**（`config_without_reference.json`）：只有左右两张图，适合"哪张更好看 / 更自然"这类无参考的问题。

两个文件只在 `reference`、`question` 和 `gap` 这几项上不同。以 `_` 开头的键是注释，会被忽略。写错的键名会在终端给出警告。命令行参数会覆盖配置文件里的同名设置，例如 `--adapt 5`。

### 配置项

| 键（命令行参数） | 默认 | 说明 |
|---|---|---|
| `root` (`--root`) | — | 方法根目录，每个子文件夹是一种方法 |
| `methods` (`--methods`) | — | 直接列出各方法文件夹，与 `root` 二选一 |
| `exclude` (`--exclude`) | 无 | 使用 `root` 时要排除的子文件夹名 |
| `reference` (`--reference`) | 无 | 参考图文件夹；设为 `null` 表示不显示参考图 |
| `question` (`--question`) | Which image has better quality? | 实验要求，显示在说明页和每个试次的屏幕上方 |
| `instructions` (`--instructions`) | 内置文本 | 说明页文本文件（UTF-8），可以写中文 |
| `adapt` (`--adapt`) | 60 | 环境光适应时长（秒），0 表示跳过 |
| `repeats` (`--repeats`) | 1 | 完整设计（场景 × 所有方法对）重复几遍 |
| `n_trials` (`--n-trials`) | 全部 | 只随机抽取这么多个试次，各方法对的次数保持均衡 |
| `seed` (`--seed`) | 随机 | 随机种子，固定后试次顺序可复现 |
| `fixation` / `iti` | 0.5 / 0.3 | 注视点时长、试次间隔（秒） |
| `duration` (`--duration`) | 0 | 图像呈现时长（秒），0 表示一直显示到作答 |
| `break_every` (`--break-every`) | 50 | 每多少个试次休息一次，0 表示不休息 |
| `show_progress` | false | 屏幕右下角显示进度 |
| `mouse` (`--mouse`) | false | 允许鼠标点击图像作答 |
| `fullscreen` (`--fullscreen`) | false | 全屏，正式实验建议打开 |
| `window` (`--window W H`) | 1600 900 | 非全屏时的窗口大小 |
| `bg` / `fg` | [128,128,128] / [230,230,230] | 背景色和文字颜色（RGB），适应期也用这个背景色 |
| `gap` (`--gap`) | 0.02 | 图像间距，占屏幕宽度的比例 |
| `upscale` (`--upscale`) | false | 允许放大图像填满屏幕。默认只在放不下时缩小，避免插值影响画质 |
| `out_dir` (`--out-dir`) | results | 结果文件夹 |
| （仅命令行）`--subject` | 屏幕输入 | 直接指定受试者代号，跳过输入姓名界面 |
| （仅命令行）`--dry-run` | — | 只检查文件夹并统计试次数，不运行实验 |

### 自定义说明页

`instructions_example.txt` 是一个样例，可以直接改写，中文英文都可以。文本中可以使用下面的占位符，运行时会被自动替换：

| 占位符 | 替换为 |
|---|---|
| `{question}` | 实验要求 |
| `{n_trials}` | 本次的试次总数 |
| `{break_every}` | 休息间隔 |
| `{ref_sentence}` / `{ref_hint}` | 有参考图时，自动加上关于参考图的说明；无参考图时为空 |
| `{mouse_sentence}` | 开启鼠标作答时，自动加上相应的提示 |

第一行如果比较短，会作为标题加大显示。文字太多时会自动缩小字号，保证完整显示。

## 第三步：试运行

```bash
# 检查文件夹匹配情况和试次数（不打开窗口）
python experiment.py --config config_with_reference.json --dry-run

# 自己完整做一遍，适应期设短一点
python experiment.py --config config_with_reference.json --adapt 5 --n-trials 10
```

试跑的结果也会写进 `results/`，**正式实验前请删除或移走**，否则会被一起分析。

## 第四步：正式实验

每名受试者运行一次同样的命令：

```bash
python experiment.py --config config_with_reference.json
```

### 受试者看到的流程

1. **输入姓名**：输入姓名或代号后按 Enter，支持中文输入法。不输入直接按 Enter，会自动分配代号。
2. **确认页**：显示本次结果的保存代号。如果代号重复，会说明已经自动改名。
3. **实验说明页**：按空格继续。
4. **环境光适应**：屏幕显示背景色，只有很暗的倒计时，不能跳过。
5. **正式试次**：注视点 → 图像 → 按键作答，中间按设定间隔休息。
6. **结束页**。

**按键：**
- `←` 或 `F`：选左边
- `→` 或 `J`：选右边
- `ESC`：随时退出

### 结果保存规则

```
results/
├── Alice.csv           ← 每名受试者一个文件
├── Alice_2.csv         ← 再次输入 "Alice" 时自动改名，不会覆盖之前的结果
├── P001.csv            ← 未输入姓名时，自动分配 P001、P002……
├── 张三.csv
└── session_info/       ← 每次实验的完整参数（JSON），便于事后核查
```

- **重名**：自动改为 `代号_2`、`代号_3`……。判断时不区分大小写，`alice` 和 `Alice` 算重名。结果文件以独占方式创建，即使多台电脑同时写入同一个共享文件夹，也不会互相覆盖。
- **非法字符**：文件名里不能用的字符（`\ / : * ? " < > |`）会被去掉，空格换成 `_`。
- **中途退出**：每完成一个试次就立即写入文件，已完成的试次不会丢失。如果一个试次都没做就退出，空文件会被删除，代号也会释放。

## 第五步：数据分析

```bash
python analysis.py                              # 分析 results/ 中的全部受试者，输出到 analysis/
python analysis.py --boot-unit scene            # 按场景做 bootstrap 重抽样（更保守，见下文）
python analysis.py --question "Which image is closer to the reference?"   # 把实验要求写在图上
```

每次运行都会重新读取 `results/` 里当前的全部结果，所以每多一名受试者，重新运行一次即可。终端会列出参与分析的受试者和各自的试次数；空文件和格式不对的文件会被跳过并给出提示。

**图（输出到 `analysis/`）：**
- `results.png` / `results.pdf`：总览图，包含四个面板：
  - A 各方法被选率（含 95% 置信区间）
  - B Thurstone 量表值
  - C 方法两两偏好矩阵（含显著性标记）
  - D 各场景下的被选率
- `per_subject.png`：每名受试者的被选率，用来检查受试者之间是否一致。

**表（输出到 `analysis/`）：**
- `method_summary.csv`：排名、被选次数、被选率、Thurstone 和 Bradley–Terry 量表值、置信区间
- `pairwise_tests.csv`：每对方法的胜负数、p 值、Holm 校正后的 p 值
- `preference_matrix.csv`、`per_scene.csv`、`per_subject.csv`

## 第六步：生成论文用图

```bash
python paper_figure.py --ours Ours
python paper_figure.py --ours Ours --rename Blur="Gaussian blur" JPEG="JPEG (q=12)"
python paper_figure.py --ours Ours --order Ours BM3D DnCNN --font sans --font-size 9
```

图按 CVPR 双栏模板的实际尺寸绘制。字号就是印到论文上的字号：默认 8 pt，正文是 10 pt，图注是 9 pt。PDF 是矢量格式，字体以 TrueType 嵌入，符合大多数会议的投稿要求。

| 输出文件 | 尺寸 | 内容 |
|---|---|---|
| `fig_preference_rate.pdf` | 单栏 3.25 in | 各方法被选率（含 95% 置信区间） |
| `fig_scale.pdf` | 单栏 3.25 in | Thurstone 量表值（含 95% bootstrap 置信区间） |
| `fig_pairwise.pdf` | 单栏 3.25 in | 两两偏好矩阵（百分比，含显著性标记） |
| `fig_ours_vs.pdf` | 单栏 3.25 in | "我们的方法 vs. 各对比方法"的偏好比例，user study 最常用的形式 |
| `fig_overview.pdf` | 通栏 6.875 in | (a) 被选率、(b) 量表值、(c) 两两偏好矩阵 |
| `latex_snippets.tex` | — | 每张图的 LaTeX 代码，图注里已经填好受试者人数、比较次数和统计方法 |

每张图另外生成一张 PNG 预览。

### 参数

| 参数 | 说明 |
|---|---|
| `--ours NAME` | 你的方法名：用蓝色突出显示，并生成 `fig_ours_vs`。如果有名为 `ours` 的方法文件夹，会自动识别 |
| `--rename 文件夹名=显示名` | 图中显示的方法名，例如 `Blur="Gaussian blur"`。文件夹名不方便改时使用 |
| `--order A B C` | 方法从上到下的顺序，默认按量表值从高到低 |
| `--font serif\|sans` | `serif` 与 CVPR 的 Times 正文一致（默认），`sans` 为无衬线字体 |
| `--font-size` | 印刷后的字号（pt），默认 8 |
| `--boot`、`--boot-unit` | bootstrap 次数和重抽样单位，含义同 `analysis.py` |
| `--results-dir`、`--out` | 输入结果文件夹（默认 `results`）和输出文件夹（默认 `paper_figures`） |

### 在 LaTeX 中使用

```latex
% 单栏
\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{fig_ours_vs.pdf}
  \caption{...}
\end{figure}

% 通栏
\begin{figure*}[t]
  \centering
  \includegraphics[width=\textwidth]{fig_overview.pdf}
  \caption{...}
\end{figure*}
```

宽度请用 `\linewidth` 或 `\textwidth`，图已经是这个尺寸，不会被缩放，字号也就保持不变。

---

## 数据格式

每名受试者的 CSV 中，每行是一个试次：

| 列 | 含义 |
|---|---|
| `subject` | 受试者代号 |
| `trial` | 试次序号 |
| `scene` | 场景（图像文件名，不含扩展名） |
| `left` / `right` | 左、右两侧显示的方法 |
| `chosen` / `not_chosen` | 被选中、未被选中的方法 |
| `chosen_side` | `left` 或 `right`，可以用来检查位置偏好 |
| `rt` | 反应时（秒），从图像出现开始计时 |
| `reference` | 是否显示参考图（1/0） |
| `scale` | 图像的显示缩放比例（1 表示原始大小） |
| `timestamp` | 作答时间 |

只要列名一致，`analysis.py` 和 `paper_figure.py` 也可以分析用其他软件（例如 PsychoPy）采集的数据。至少需要 `subject`、`chosen`、`not_chosen` 三列。

## 统计方法说明

- **被选率**：某方法被选中的次数除以它出现的次数，置信区间用 Wilson 方法计算。50% 表示与平均水平相当。
- **Thurstone Case V 量表**：假设受试者选 i 而不选 j 的概率为 Φ(sᵢ − sⱼ)，由所有两两比较结果求出各方法在同一感知尺度上的位置。单位是 z 值，最差的方法定为 0。为避免 0% 或 100% 的比例导致无穷大，计算前对比例做了 (w+0.5)/(n+1) 校正，因此极端值会略微向中间收缩。
- **Bradley–Terry 模型**：另一种常用的配对比较模型，作为对照一并输出，结果通常与 Thurstone 量表高度一致。
- **两两检验**：对每对方法做双侧二项检验（与 50% 比较），用 Holm 方法校正多重比较。`*` 表示 p<.05，`**` 表示 p<.01，`***` 表示 p<.001。
- **bootstrap 重抽样单位**（`--boot-unit`）：
  - `trial`（默认）：只考虑试次层面的随机性。
  - `scene`：把场景当作随机因素。如果想说明"在这类图像上"更好，推荐用这个。
  - `subject`：把受试者当作随机因素。建议至少有 5 名受试者。

## 实验设计建议与注意事项

- **试次数** = 场景数 × M(M−1)/2 × 重复次数（M 为方法数）。例如 20 个场景、5 种方法时是 200 次，约 15–20 分钟。时间过长可以用 `n_trials` 抽样，各方法对的次数保持均衡。
- **受试者人数**：顶会论文中的 user study 一般有 15–30 人以上。可以先用 `simulate.py` 估算多少人能让置信区间足够窄：
  ```bash
  python simulate.py --root my_study/methods --subjects 20 --truth Ours=1 BM3D=0.7 DnCNN=0.5
  python analysis.py --results-dir data_sim --out analysis_sim
  ```
- **显示条件**：用全屏，固定显示器亮度、色温、房间照明和观看距离。Windows 高分屏下，程序会自动关闭系统的 DPI 缩放，避免图像被放大变模糊。
- **图像大小**：如果终端提示"Images ... are shown at xx%"，说明图像超出了屏幕的可用区域、被缩小显示了。做画质评价时最好以 100% 显示，可以裁剪图像、去掉参考图，或者换更大的显示器。
- **语言**：代码、屏幕提示和图表标签都是英文。如果需要中文界面，用中文写 `question` 和说明页文本即可，程序会自动选用中文字体。
- **计时精度**：pygame 对主观偏好实验已经足够，但刺激呈现没有和显示器刷新同步。如果需要精确到帧的呈现，可以改用 PsychoPy 采集数据，按上面的列名保存后，分析和画图仍然用本项目的脚本。
