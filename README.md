# ai-video

一个**纯脚本驱动**的 AI 视频生成工具——一行命令，从模糊想法到成片 mp4。

底层用 [Token360](https://www.token360.ai)——一个 OpenAI 兼容的多模态网关，统一接入 LLM、图像生成、TTS、视频生成。

无 UI，无浏览器。你写：

```bash
aivideo make "一只想环游世界的章鱼" --style ghibli --duration short
```

仓库里的 Python pipeline 会自动规划分镜、生成每一帧、做质量审核、拼接成 mp4。

---

## 四个核心功能

| 功能 | 怎么用 |
|---|---|
| ① 上传真人照片 | `aivideo photo my.jpg` 或 `aivideo make "..." --portrait my.jpg` |
| ② 多片拼接达 30 秒 | 默认 `--duration short`（30 秒），自动多镜头串联 + 末帧 → 首帧无缝过渡 |
| ③ 选风格 | `--style ghibli` / `cyberpunk` / `wuxia` / `noir` ... 共 10 种 |
| ④ 自带 API key | 复制 `.env.example` 到 `.env`，填 `TOKEN360_API_KEY=sk-...` |

---

## 安装

```bash
# 1. 系统依赖
sudo apt-get install ffmpeg            # Debian/Ubuntu
# 或: brew install ffmpeg              # macOS

# 2. 克隆 + 安装
git clone https://github.com/beizhangnina/AI-video.git
cd AI-video
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 3. 配置 API key
cp .env.example .env
# 编辑 .env，填入 TOKEN360_API_KEY=sk-你的密钥
```

---

## 功能 ① 上传真人照片

把你（或任何人）的照片当作角色参考，让生成的视频里人物长相保持一致。

### 最简方式：`aivideo make` 直接传本地路径

```bash
aivideo make "妈妈带着我和狗狗去野餐" --portrait mom.jpg --style ghibli
```

`--portrait` 直接接受本地图片路径，pipeline 会自动上传到 Token360 的
**Virtual Portrait** 资产组（AI 角色参考，无需扫码验证），然后把生成的
`asset://ta_xxx` 用到每个分镜的 video gen 调用里——保证人物在所有镜头中
长相一致。

### 高级方式：`aivideo photo` 单独上传

如果你想反复用同一张照片，先上传一次拿到 URI，之后多个视频复用：

```bash
# Virtual Portrait（推荐，无验证）
aivideo photo mom.jpg
#   asset://ta_8b3f1c2a...        ← 复制下来

aivideo make "故事 A" --portrait asset://ta_8b3f1c2a...
aivideo make "故事 B" --portrait asset://ta_8b3f1c2a...
```

### 真人活体验证（RealFace）

如果你的应用场景需要"必须是真人本人"（比如品牌代言），用 `--real`：

```bash
aivideo photo myself.jpg --real
#   RealFace group created: grp_xxxxx
#   >>> Have the person scan this H5 link within 120 seconds:
#       https://...
```

本人用手机扫码完成活体验证后，照片才能用作 `asset://` 引用。

> ⚠️ Token360 的 RealFace / Virtual Portrait 只在 `seedance-2.0` 系列模型上有效。
> 默认的 `seedance-2.0-fast` 已经支持。

---

## 功能 ② 多片拼接达 30 秒（甚至更长）

Token360 的视频生成单次调用最长约 12 秒，所以 30 秒视频需要多个 clip 拼接。
本仓库通过两种方式处理这个问题，**两种都能保证镜头平滑过渡，不出现跳变**：

### 方式 A（默认）：planner 自动规划分镜 + 末帧 handoff

`aivideo make "..." --duration short` 默认会让 planner 输出 4-7 个 keyframe
（每个 5-8 秒），按"开头→铺陈→高潮→结尾"的剧本结构编排。Pipeline 会：

1. 为每个 keyframe 生成图片
2. 用图片做 first-frame I2V，生成视频片段
3. 如果这一帧标记了 `continues_from_prev: true`，**直接用上一段的最后一帧
   当本段的首帧**，跳过图像生成——这样两段拼接处画面完全衢接

### 方式 B：纯代码长镜头

如果你想要"一镜到底"的 24 秒长镜头：

```python
from aivideo.generate import video

mp4 = video.chain_from_first_frame(
    image="opening.png",
    motion_prompts=[
        "镜头缓慢前推，越过珊瑚礁，鱼群从两侧划过",
        "镜头继续前推，海藻林分开，露出开阔深海",
        "镜头上扬，阳光击破水面",
    ],
    seconds_per_clip=8,
)
# -> 单个 mp4，约 24 秒，每段最后一帧 = 下一段第一帧（真实像素级一致）
```

### 时长预设

| 预设 | 秒数 | 说明 |
|---|---|---|
| `--duration snippet` | 15s | 极短，3-4 个 keyframe |
| `--duration short` | 30s | **推荐默认**，4-6 个 keyframe |
| `--duration standard` | 45s | 更完整的故事 |
| `--duration long_form` | 75s | 长镜头，6-8 个 keyframe |
| `--duration 60` | 任意秒数 | 直接传整数 |

---

## 功能 ③ 选风格

10 种主流风格预设，避免选择困难症：

```bash
aivideo make "一只学冲浪的猫" --style ghibli       # 宫崎骏水彩
aivideo make "深夜霓虹的拉面店" --style cyberpunk  # 赛博朵克
aivideo make "侠客江湖归来" --style wuxia          # 武侠水墨
```

| `--style` 取值 | 风格描述 |
|---|---|
| `cyberpunk` | 赛博朵克：霓虹、雨夜、全息招牌、青紫色调 |
| `ghibli` | 宫崎骏：水彩绘本、暖光、手绘质感 |
| `pixar_3d` | 皮克斯 3D：表情丰富的角色、电影级灯光 |
| `photorealistic` | 写实摄影：35mm 胶片、自然光、浅景深 |
| `wuxia` | 武侠水墨：山雾、衣裂、书法笔意 |
| `cinematic` | 现代电影：宽银幕、戏剧调色、雾感 |
| `anime` | 日式动画：赛畑畑、粗线条、饱和色 |
| `cartoon_2d` | 2D 卡通：粗黑边、平涂大色块 |
| `noir` | 黑白电影：硬光阴影、烟雾、1940s 氛围 |
| `watercolor` | 水彩绘本：纸纹、暖色、绘本构图 |

也可以传你自己写的风格描述（不在预设列表里的字符串会原样传给 LLM）：

```bash
aivideo make "..." --style "1990 年代 VHS 录像带美学"
```

### 还有这些可调选项

```bash
--mood cheerful | melancholic | mysterious | epic | comedic | romantic | suspenseful | serene
--voice warm | energetic | deep | bright | gentle | dramatic
--aspect vertical | horizontal | square          # 默认 vertical (1080x1920)
--pacing slow | normal | fast                    # 镜头节奏
```

跑 `aivideo styles` 可以看到所有预设的完整描述。

---

## 功能 ④ 自带 API key

仓库不内置任何密钥。你需要：

1. 去 [Token360 console](https://www.token360.ai) 注册并创建 API key（格式 `sk-...`）
2. 在仓库根目录：
   ```bash
   cp .env.example .env
   ```
3. 编辑 `.env`：
   ```env
   TOKEN360_API_KEY=sk-你的真实密钥
   TOKEN360_BASE_URL=https://api.token360.ai/v1   # 默认值，一般不用改

   # 默认模型，可按需改成你 console 里启用的：
   AIVIDEO_LLM_MODEL=gpt-4o
   AIVIDEO_IMAGE_MODEL=dall-e-3
   AIVIDEO_TTS_MODEL=tts-1-hd
   AIVIDEO_TTS_VOICE=alloy
   AIVIDEO_VIDEO_MODEL=seedance-2.0-fast
   ```

`.env` 已加入 `.gitignore`，不会被提交。

> 💡 如果你 console 里没有 `dall-e-3` 或 `seedance-2.0-fast`，把上面对应行换成
> 你账号实际可用的模型名即可，代码会自动使用新值。

---

## 一键端到端示例

```bash
# 用妈妈的照片，宫崎骏风格，30 秒，温暖叙事，竖屏
aivideo make "妈妈带着我和狗狗去野餐" \
    --portrait mom.jpg \
    --style ghibli \
    --duration short \
    --mood cheerful \
    --voice warm \
    --aspect vertical
```

输出：`runs/<时间戳>-<slug>/final.mp4` + 同目录下的 `plan.json`、各分镜中间产物、
QC 报告、人类可读的 `report.md`。

---

## 完整流程图

```
┌──────────┐   ┌─────────┐   ┌──────────┐   ┌────┐   ┌──────────┐
│  idea    │ → │ planner │ → │ executor │ → │ QC │ → │ delivery │
│ (string) │   │  (LLM)  │   │  (loop)  │   │(视觉│   │ (folder) │
└──────────┘   └─────────┘   └──────────┘   │ LLM)│  └──────────┘
                                            └────┘
```

| 阶段 | 模块 | 做什么 |
|---|---|---|
| Planner | `agents/planner.py` | LLM 把模糊 idea 翻译成强类型 `Plan`：标题、风格、配音、完整旁白文本、4-7 个 keyframe（每个含 image_prompt、motion_prompt、时长、剧本角色） |
| Executor | `agents/executor.py` | 遍历每个 keyframe：生成图 → QC → 不合格则重试 → first-frame I2V 生成视频片段 → QC。每个产物都落到 run 文件夹里 |
| QC | `agents/qc.py` | 视觉 LLM 给每个产物打 0-1 分对比"导演意图"，不达标自动改 prompt 重试一次 |
| Delivery | `pipelines/auto.py` + `runs.py` | 拼接片段、烧字幕、混入旁白音轨，输出 `final.mp4` 和 `report.md` 到 `runs/<时间戳>-<slug>/` |

每个 run 完全可追溯：plan、每张图、每段视频、每个 QC 报告、markdown 摘要
都和最终 mp4 放在同一个文件夹里。

---

## Run 文件夹结构

```
runs/20260509-184523-妈妈和狗狗野餐/
├── plan.json                  # planner 输出的完整剧本
├── scenes/
│   ├── k01-image.png          # 第 1 镜的图
│   ├── k01-qc-image.json      # 第 1 镜图的质检报告
│   ├── k01-video.mp4          # 第 1 镜的视频（first-frame I2V）
│   ├── k01-qc-video.json      # 第 1 镜视频的质检报告
│   ├── k02-image.png
│   ...
├── narration.mp3              # TTS 旁白
├── final.mp4                  # 成片
└── report.md                  # 人类可读的总结：剧本 + 每镜 QC 分数
```

`runs/` 已被 gitignore，可以随便删。重跑同一个 idea 字符串会命中缓存
（`cache/` 也是 gitignore），不会重复花 token。

---

## 常用命令清单

```bash
aivideo make "<idea>" [选项]    # 主入口：从 idea 到 mp4
aivideo photo <image>           # 上传照片，拿到 asset:// URI
aivideo photo <image> --real    # 上传真人验证照片
aivideo styles                  # 列出所有 --style/--mood/--voice 预设
aivideo run scripts/xxx.py      # 跑自定义脚本
aivideo list                    # 列出 scripts/ 目录下的脚本
```

---

## 高级：手写 Python 脚本

如果你想完全自定义 pipeline（不走 planner），把 `.py` 文件丢进 `scripts/`：

```python
# scripts/my_video.py
from aivideo.generate import llm, image, tts, video
from aivideo.compose import stitch, render
from aivideo.config import settings

idea = llm.script(
    "写一段 15 秒赛博朵克 trailer 旁白，附 3 个分镜描述",
    json_mode=True,
)
clips = []
for shot in idea["shots"]:
    img = image.image(shot["image_prompt"], size="1024x1792")
    mp4 = video.from_first_frame(img, shot["motion"], duration=5)
    clips.append(stitch.fit_to_size(stitch.load(mp4), settings.width, settings.height))
final = stitch.with_audio(stitch.concat(clips), tts.speak(idea["narration"], voice="onyx"))
render.to_mp4(final, "cyberpunk.mp4")
```

然后：`python scripts/my_video.py` 或 `aivideo run my_video.py`。

仓库自带 4 个示例脚本：

| 文件 | 用途 |
|---|---|
| `scripts/00_make.py` | 等价于 `aivideo make`，命令行运行 |
| `scripts/01_hello_world.py` | 最小冑烟测试：1 张图 + 1 句旁白 + 5 秒 mp4 |
| `scripts/02_short_story.py` | 写死的 narrated_story（跳过 planner） |
| `scripts/03_kenburns_fallback.py` | 同 02 但用 Ken Burns 平移代替 video gen，更便宜 |

---

## 仓库结构

```
src/aivideo/
├── config.py              # .env 加载、默认模型、路径
├── client.py              # OpenAI SDK + httpx 客户端（都指向 Token360）
├── cache.py               # AI 输出的内容寻址磁盘缓存
├── runs.py                # 每次运行的文件夹分配
├── assets.py              # Token360 原生 Assets API（RealFace / Virtual Portrait）
├── presets.py             # 10 种风格 + 时长/比例/情绪/嗓音/节奏预设
│
├── agents/                # 「app」的大脑
│   ├── schemas.py         # Plan / Keyframe / QCReport dataclasses
│   ├── planner.py         # idea → Plan（认预设）
│   ├── executor.py        # 遍历 Plan，生成 + QC + 重试 + 帧 handoff
│   └── qc.py              # 多模态 LLM 质检
│
├── generate/              # Token360 各能力的薄包装，自带磁盘缓存
│   ├── llm.py
│   ├── image.py
│   ├── tts.py
│   └── video.py           # text / I2V / 首尾帧 / 多参考 / extend / chain / native
│
├── compose/               # 基于 ffmpeg 的合成
│   ├── stitch.py          # 拼接 / 配音 / 缩放裁切
│   ├── kenburns.py        # 静图缓推缩放
│   ├── subtitles.py       # Pillow 烧字幕
│   ├── handoff.py         # 抽末帧用作下一镜首帧
│   └── render.py          # 最终 h264 编码
│
├── pipelines/
│   ├── auto.py            # idea → Plan → execute → QC → 交付
│   └── narrated_story.py  # 写死模板（跳过 planner）
│
└── cli.py                 # `aivideo make` / `aivideo photo` / `aivideo styles` 等

scripts/                   # 你的视频想法，每个文件 = 一个视频
runs/                      # gitignore：每次运行的产物文件夹
cache/                     # gitignore：AI 输出缓存
output/                    # gitignore：手写脚本的输出目录
```

---

## QC 行为

- 每张生成的图 / 每段视频中帧都会被多模态 LLM 打 0.0-1.0 分
- 阈值 **0.65**。低于阈值则用 planner 改写过的 prompt 重试 **1 次**
- 仍不达标的镜头会被**标记**（flag），run 不会卡住，最后在 `report.md` 列出
  让你人工决定是接受还是手动重跑
- 加 `--no-qc` 可以跳过质检（省 LLM 调用，但会失去自纠错能力）

---

## 常见错误对照

| 现象 | 多半是因为 |
|---|---|
| `401 Unauthorized` | `TOKEN360_API_KEY` 没填或格式不对（必须以 `sk-` 开头） |
| `InvalidParameter on duration` | 传了字符串 `"5"`，应该传整数 `5` |
| `Asset validation failed` | `asset://ta_xxx` ID 错了或还没 active；正常情况 `assets.wait_active()` 已经处理 |
| `Model not supported` | `.env` 里写的模型名你 console 里没启用，换一个 |
| Plan JSON 缺 key | LLM 那一次返回的 JSON 不完整；改一下 idea 字符串重跑（缓存按 prompt 哈希，所以微调即可强制刷新） |
| 字幕变成方框 | 装 Noto CJK 字体，或在 `subtitles.burn(font_path=...)` 显式传字体路径 |

---

## License

MIT。
