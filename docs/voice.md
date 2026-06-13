# 语音交互 (v0.3)

实现设计草案第六节的 Voice-Hermes：语音提问本草/方剂 → 系统检索 → 语音播报。
采用**可插拔后端 + 浏览器回退**的双层架构，保证无 GPU 也能用。

## 架构

```text
浏览器 (frontend/app.js · Voice)
  ├─ 录音 → POST /voice/asr ──► FireRedASR2-AED（服务端，GPU）── 文本
  │                              └─（未配置/失败）─► 回退 Web Speech API 识别
  ├─ 识别文本 → 自动分发到 本草溯源 / 方剂谱系
  └─ 🔊 朗读 → POST /voice/tts ──► CosyVoice3-0.5B（服务端，GPU）── wav
                                   └─（未配置/失败）─► 回退 speechSynthesis 朗读
```

服务端后端 **惰性加载**：仅当配置了模型目录且首次调用时才导入 torch 与模型，
因此 `import herb_hermes` 永不依赖深度学习栈。

## 服务端后端（GPU，可选）

| 能力 | 后端 | 模块 |
| --- | --- | --- |
| ASR 语音转文字 | FireRedASR2-AED | `voice/asr.py` |
| TTS 文字转语音 | CosyVoice3-0.5B | `voice/tts.py` |

实现严格对齐官方推理路径（见 `notebooks/HerbHermes_Voice_Server.ipynb`）：
ASR 先用 ffmpeg 转 16kHz 单声道再 `FireRedAsr2.transcribe`；TTS 用
`cosyvoice.cli.cosyvoice.AutoModel` 的 `inference_zero_shot` / `inference_instruct2`。

### 环境变量
```bash
export HERB_HERMES_ASR_MODEL_DIR=/path/to/FireRedASR2-AED
export HERB_HERMES_TTS_MODEL_DIR=/path/to/Fun-CosyVoice3-0.5B
export HERB_HERMES_COSYVOICE_REPO=/path/to/CosyVoice            # 提供 import 路径
export HERB_HERMES_TTS_PROMPT_WAV=/path/to/CosyVoice/asset/zero_shot_prompt.wav
export PYTHONPATH=/path/to/FireRedASR2S:/path/to/CosyVoice:$PYTHONPATH
uvicorn herb_hermes.api.server:app --port 8000
```

未配置时 `/voice/asr`、`/voice/tts` 返回 **503** 并给出指引，前端据此回退浏览器能力。

## API
- `GET /voice/status` — 报告 ASR/TTS 是否配置/加载（不触发加载）
- `POST /voice/asr` — 请求体为原始音频字节（webm/wav/mp3，ffmpeg 转码），返回
  `{text, confidence, timestamp, ...}`。**刻意不使用 multipart**，避免引入
  `python-multipart` 依赖。
- `POST /voice/tts` — `{text, prompt_text?, instruct?, prompt_wav?}` → `audio/wav`

## 浏览器回退（默认即可用）
前端 `Voice` 控制器优先探测 `/voice/status`：
- 配了服务端 ASR → 录音上传；否则用 `webkitSpeechRecognition`（Chrome，zh-CN）。
- 配了服务端 TTS（且有参考音频）→ 用 CosyVoice3；否则用 `speechSynthesis`。

因此在普通浏览器（无 GPU、未部署模型）下，点击 🎤 即可语音检索、点 🔊 即可朗读，
核心功能零依赖可用；接入 GPU 模型后获得更高质量的中文/方言识别与音色合成。

## 一键部署
见 `notebooks/HerbHermes_Voice_Server.ipynb`：在 Colab/GPU 上自动拉起
FireRedASR2S + CosyVoice3 + Herb-Hermes 服务并通过 ngrok 暴露研究驾驶舱。
