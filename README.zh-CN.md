# subglot

[![CI](https://github.com/roclee0703/subglot/actions/workflows/ci.yml/badge.svg)](https://github.com/roclee0703/subglot/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**本地优先的字幕转写与翻译流水线。** Whisper 在你自己的机器上跑，翻译走任意
OpenAI 兼容 API（OpenAI、Azure、自托管 vLLM 均可）。本项目在一条真实生产的
短视频字幕流水线上长期使用、持续打磨。

[English](README.md)

## 为什么做这个

大多数字幕工具止步于"把 Whisper 输出倒进一个 SRT"。subglot 补上了字幕要
真正上屏可读时那些没人帮你做的部分：

- **中日韩感知的换行**——按显示单位折行（CJK 字符 = 1，拉丁字符 = 0.5），
  而不是按字符数硬切，一个 `--max-units` 同时适用于英文和中文。
- **阅读速度 QA**——每个输出文件都过校验：时间轴重叠、非正时长、空文本、
  超长行、观众来不及读完的字幕，按 `error`/`warning` 分级上报。
- **带上下文的翻译**——字幕分批请求，每次请求携带前几条已译结果，保证
  术语在一整条视频里一致。
- **语种检测护栏**——为什么本工具永远不会为了让 Whisper"判断语种"而
  强制传 `language` 参数，见 [docs/pitfalls.md](docs/pitfalls.md)。

## 安装

```bash
pip install "subglot[asr]"       # 转写 + 翻译 + 校验
pip install subglot              # 只要翻译 + 校验（不带 Whisper）
```

## 快速上手

```bash
# 1. 视频转写 -> 源语言 SRT（Whisper 自动检测语种）
subglot transcribe talk.mp4 --model base

# 2. 翻译（任意 OpenAI 兼容端点）
export OPENAI_API_KEY=sk-...
subglot translate talk.srt -o talk.zh.srt --target "Chinese (Simplified)"

# 3. 校验结果（有硬错误时退出码为 1）
subglot validate talk.zh.srt
```

或一步到位：

```bash
subglot pipeline talk.mp4 -o talk.zh.srt --model base --target "Chinese (Simplified)"
```

用自托管或第三方模型？指定 `--base-url` 即可：

```bash
subglot translate talk.srt -o talk.zh.srt \
  --base-url http://localhost:8000/v1 --model my-model \
  --api-key-env MY_KEY_VAR
```

## 设计决策

| 决策 | 理由 |
|---|---|
| faster-whisper（CTranslate2）、延迟导入 | CPU 上比 openai-whisper 快约 4 倍；只用翻译功能时不必装推理引擎 |
| 一次请求 = N 条字幕 + 前文上下文 | 每条一请求成本高 20 倍且术语不一致；整文件一请求长视频质量下降 |
| 严格 JSON 数组契约 + 一次重试 | 模型偶尔多行/少行；静默错位会让后面所有字幕对不上音频 |
| 折行不截断 | 行太长是排版问题；丢文本是数据丢失 bug |
| 用显示单位而非字符数 | `"中文字幕"` 和 `"Hello"` 在同一个 `--max-units 20` 下都合理 |

## 路线图

- **v0.2 配音摆位**：edge-tts 合成（裁尾部静音）、时间窗摆位、互相关对位
  校验（以及卷积/相关差一个模板长度的坑——见
  [docs/pitfalls.md](docs/pitfalls.md)）。
- **v0.3 音乐处理**：源分离提取 BGM、增益归一、sidechain ducking，以及
  "这首歌能不能用中置消除去人声"的预检。
- **v0.4 成品输出**：ASS 样式与 ffmpeg 烧录。

## 开发

```bash
pip install -e ".[dev]"
pytest -q
```

CI 在 Python 3.10–3.13 上跑测试。

## 许可

[MIT](LICENSE)
