# TTS Integration Design Spec

## Overview

Add Text-to-Speech (TTS) to MuseAI's two LLM conversation features — intelligent Q&A and AI guided tour — using the Xiaomi Mimo-V2.5-TTS API. Audio is delivered as base64-encoded PCM16 chunks embedded in the existing SSE streams, played back via the Web Audio API.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| TTS trigger | Embedded in SSE stream | Backend generates TTS after LLM completes, sends audio events after text events in the same stream |
| Audio format | Base64 PCM16 via SSE | Frontend can start playback before full synthesis; no separate binary endpoint needed |
| Activation | Global toggle + per-message fallback | Auto-play when enabled; speaker icon when disabled |
| Q&A voice | User-selectable from 8 presets | Stored in localStorage (`tour_workbench_tts_preferences` for tour, new key for chat) |
| Q&A style | Default museum guide style | "用清晰专业的语气讲解，语速适中" |
| Tour TTS prompts | Per-persona (3 prompts) | Admin-configurable via existing prompt versioning system |
| TTS model (Q&A) | `mimo-v2.5-tts` (preset voice) | Uses `audio.voice` parameter with preset voice ID |
| TTS model (Tour) | `mimo-v2.5-tts` with style control | Preset voice + `user` message with persona-specific style instruction from prompt |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend                                               │
│                                                         │
│  ChatMainArea.vue ──┐     ExhibitChat.vue ──┐           │
│                     │                        │           │
│  useChat.js ────────┤     useTour.js ────────┤           │
│                     │                        │           │
│  useTTSPlayer.js ◄──┴────────────────────────┘           │
│  (Web Audio API, PCM16 decoding, playback control)      │
│                                                         │
│  TourSettingsPanel.vue (existing ttsPreferences UI)     │
│  ChatTtsSettings.vue (new, for Q&A voice selection)     │
└─────────────────────────────────────────────────────────┘
            │ SSE with audio events
            ▼
┌─────────────────────────────────────────────────────────┐
│  Backend                                                │
│                                                         │
│  chat_stream_service.py ──┐  tour_chat_service.py ──┐   │
│                           │                         │   │
│  sse_events.py ◄──────────┴─────────────────────────┘   │
│  (new: audio_start, audio_chunk, audio_end events)      │
│                                                         │
│  api/tts.py (standalone TTS endpoint for click-to-play) │
│  tts_service.py (orchestrates TTS calls)                │
│  infra/providers/tts.py (Xiaomi TTS API client)         │
│                                                         │
│  prompt_service.py (existing, for tour TTS prompts)     │
│  config/settings.py (new TTS settings)                  │
└─────────────────────────────────────────────────────────┘
```

## Backend

### 1. Configuration — `config/settings.py`

Add new settings fields:

```python
TTS_ENABLED: bool = True
TTS_BASE_URL: str = "https://api.xiaomimimo.com/v1"
TTS_API_KEY: str = ""
TTS_MODEL: str = "mimo-v2.5-tts"
TTS_DEFAULT_VOICE: str = "冰糖"
TTS_TIMEOUT: float = 30.0
```

- `TTS_API_KEY` required in production (add to `validate_production_secrets`).
- `TTS_ENABLED` allows disabling TTS entirely (e.g. in tests or when API key is unavailable).

### 2. TTS Provider — `infra/providers/tts.py`

New module wrapping the Xiaomi TTS API via the OpenAI SDK (same pattern as `llm.py`).

```python
class TTSProvider:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self.model = model

    async def synthesize_stream(self, text: str, voice: str, style: str | None = None):
        """Yield PCM16 audio chunks (base64-encoded) for streaming playback."""
        messages = []
        if style:
            messages.append({"role": "user", "content": style})
        messages.append({"role": "assistant", "content": text})

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            audio={"format": "pcm16", "voice": voice},
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            audio = getattr(delta, "audio", None) if delta else None
            if audio and "data" in audio:
                yield audio["data"]  # base64-encoded PCM16

    async def synthesize(self, text: str, voice: str, style: str | None = None) -> bytes:
        """Return complete WAV audio bytes (non-streaming)."""
        # Similar but format="wav", stream=False, returns decoded bytes
```

Key decisions:
- Uses `AsyncOpenAI` client (already a dependency) — no new pip packages needed.
- `synthesize_stream` yields base64 strings directly — no server-side audio buffering.
- No retry logic for streaming (consistent with `LLMProvider.generate_stream`).
- Graceful degradation: if TTS fails, emit an `audio_error` event; the text response is already delivered.

### 3. TTS Service — `application/tts_service.py`

Orchestrates TTS calls for both chat and tour scenarios.

```python
class TTSService:
    def __init__(self, provider: TTSProvider, prompt_gateway: PromptGateway):
        self.provider = provider
        self.prompt_gateway = prompt_gateway

    def get_qa_tts_config(self, user_voice: str | None = None) -> TTSConfig:
        """Return voice + style for Q&A. User-selected voice, default museum guide style."""
        return TTSConfig(
            voice=user_voice or settings.TTS_DEFAULT_VOICE,
            style="用清晰专业的语气讲解，语速适中",
        )

    async def get_tour_tts_config(self, persona: str) -> TTSConfig:
        """Return voice + style for tour persona. Style from prompt system."""
        prompt_key = f"tour_tts_persona_{persona}"
        style = await self.prompt_gateway.get(prompt_key)
        return TTSConfig(
            voice=settings.TTS_DEFAULT_VOICE,
            style=style or "用温和亲切的语气讲解，语速适中",
        )
```

`TTSConfig` is a simple dataclass holding `voice: str` and `style: str | None`.

### 4. SSE Events — `application/sse_events.py`

Add new event builder helpers. The existing builders accept `**kwargs`, so no changes needed to the builder functions themselves. Define constants and helper functions:

```python
# New event type constants
TTS_AUDIO_START = "audio_start"
TTS_AUDIO_CHUNK = "audio_chunk"
TTS_AUDIO_END = "audio_end"
TTS_AUDIO_ERROR = "audio_error"

def sse_chat_audio_start(**fields) -> str:
    return sse_chat_event("audio_start", **fields)

def sse_chat_audio_chunk(data: str) -> str:
    return sse_chat_event("audio_chunk", data=data)

def sse_chat_audio_end() -> str:
    return sse_chat_event("audio_end")

def sse_chat_audio_error(code: str, message: str) -> str:
    return sse_chat_event("audio_error", code=code, message=message)

# Same set for tour: sse_tour_audio_start, sse_tour_audio_chunk, etc.
```

### 5. Chat Stream Integration — `application/chat_stream_service.py`

Modify `ask_question_stream_with_rag` and `ask_question_stream` to append TTS events after the existing `done` event:

```python
# After emitting done event, if TTS enabled:
yield sse_chat_audio_start(voice=config.voice, format="pcm16")
try:
    async for chunk in tts_provider.synthesize_stream(full_text, config.voice, config.style):
        yield sse_chat_audio_chunk(chunk)
    yield sse_chat_audio_end()
except Exception:
    yield sse_chat_audio_error("TTS_ERROR", "语音合成失败")
```

Parameters needed: `tts_enabled: bool`, `tts_voice: str | None` passed from the API endpoint (derived from request body or user preferences).

### 6. Tour Chat Stream Integration — `application/tour_chat_service.py`

Same pattern as chat, but uses persona-based TTS config:

```python
# After emitting done event, if TTS enabled:
config = await tts_service.get_tour_tts_config(persona)
yield sse_tour_audio_start(voice=config.voice, format="pcm16")
try:
    async for chunk in tts_provider.synthesize_stream(full_text, config.voice, config.style):
        yield sse_tour_audio_chunk(chunk)
    yield sse_tour_audio_end()
except Exception:
    yield sse_tour_audio_error("TTS_ERROR", "语音合成失败")
```

### 7. API Layer Changes

**Chat endpoint** (`api/chat.py`): Add optional `tts` and `tts_voice` fields to the request model. Pass through to the streaming generator.

**Tour endpoint** (`api/tour.py`): Add optional `tts` field. Voice is determined server-side from persona prompt.

### 8. Standalone TTS Endpoint — `api/tts.py`

For click-to-play and re-play scenarios:

```python
POST /api/v1/tts/synthesize
Body: { "text": "...", "voice": "冰糖", "style": "用清晰专业的语气讲解" }
Response: { "audio": "<base64-wav>", "format": "wav" }
```

- Non-streaming synthesis (WAV format).
- No RAG, no session context — pure text-to-speech.
- Rate-limited to prevent abuse.

### 9. Singleton Initialization — `main.py`

Add `TTSProvider` to the lifespan initialization:

```python
tts_provider = TTSProvider(
    base_url=settings.TTS_BASE_URL,
    api_key=settings.TTS_API_KEY,
    model=settings.TTS_MODEL,
    timeout=settings.TTS_TIMEOUT,
) if settings.TTS_ENABLED and settings.TTS_API_KEY else None

app.state.tts_provider = tts_provider
```

Store as `app.state.tts_provider`. Services check for `None` to gracefully skip TTS.

### 9. Tour TTS Prompts — Admin Configuration

Three new prompts to be created via the admin API (or seed script):

| Key | Name | Category | Content (example) |
|-----|------|----------|-------------------|
| `tour_tts_persona_a` | Tour TTS - Archaeologist | tts | `用沉稳专业的语气讲解，语速适中，带有学术气息，像一位资深考古学家在分享发现` |
| `tour_tts_persona_b` | Tour TTS - Villager | tts | `用亲切朴实的语气讲述，语速稍慢，带有乡音的温暖感，像一位老村民在回忆往事` |
| `tour_tts_persona_c` | Tour TTS - Teacher | tts | `用生动有趣的语气讲解，语速适中，善于用比喻和提问吸引注意力，像一位热情的历史老师` |

These use the existing prompt versioning system — admin can edit, version, and rollback via `/admin/prompts/*` endpoints.

## Frontend

### 1. TTS Player Composable — `composables/useTTSPlayer.js`

New composable handling Web Audio API playback of PCM16 chunks.

```javascript
export function useTTSPlayer() {
  const isPlaying = ref(false)
  const currentSource = ref(null)

  let audioContext = null
  let pcmBuffer = []
  let scheduledEndTime = 0

  function initContext() {
    if (!audioContext) {
      audioContext = new AudioContext({ sampleRate: 24000 })
    }
  }

  function feedChunk(base64Chunk) {
    initContext()
    // Decode base64 -> Int16 -> Float32
    const raw = atob(base64Chunk)
    const int16 = new Int16Array(raw.length / 2)
    for (let i = 0; i < int16.length; i++) {
      int16[i] = (raw.charCodeAt(i * 2 + 1) << 8) | raw.charCodeAt(i * 2)
    }
    const float32 = Float32Array.from(int16, v => v / 32768)

    // Create AudioBuffer and schedule playback
    const buffer = audioContext.createBuffer(1, float32.length, 24000)
    buffer.getChannelData(0).set(float32)
    const source = audioContext.createBufferSource()
    source.buffer = buffer
    source.connect(audioContext.destination)

    const startTime = Math.max(audioContext.currentTime, scheduledEndTime)
    source.start(startTime)
    scheduledEndTime = startTime + buffer.duration
    currentSource.value = source
    isPlaying.value = true
  }

  function stop() {
    if (currentSource.value) {
      try { currentSource.value.stop() } catch {}
    }
    isPlaying.value = false
    scheduledEndTime = 0
  }

  return { isPlaying, feedChunk, stop }
}
```

Key decisions:
- 24kHz sample rate matches Xiaomi TTS PCM16 output.
- Chunks are scheduled sequentially for gapless playback.
- No buffering — chunks are played as they arrive (low latency).

### 2. Chat Integration — `composables/useChat.js` + `ChatMainArea.vue`

Modify the event loop in `sendMessage` / `handleSendMessage`:

```javascript
// In the event loop, after handling chunk/done:
case 'audio_start':
  ttsPlayer.stop() // clear any previous
  break
case 'audio_chunk':
  if (ttsEnabled.value) ttsPlayer.feedChunk(event.data)
  break
case 'audio_end':
  // playback finishes naturally
  break
case 'audio_error':
  // show toast or ignore silently
  break
```

Add a speaker icon button on each assistant message for click-to-play. When clicked:
- A dedicated `POST /tts/synthesize` endpoint is called with `{ text, voice, style }`.
- Backend synthesizes non-streaming (WAV format), returns base64 audio.
- Frontend decodes and plays via Web Audio API.
- This endpoint is also used for re-playing audio after a page refresh.

### 3. Tour Integration — `composables/useTour.js` + `ExhibitChat.vue`

Same event handling pattern, using the existing `ttsPreferences` from `useTourWorkbench.js`:

```javascript
const { ttsPreferences } = useTourWorkbench()
// ttsPreferences.voice, ttsPreferences.autoPlay already defined
```

The `TourSettingsPanel.vue` already has the TTS settings UI placeholder — fill it in with voice selector and auto-play toggle.

### 4. Q&A Voice Selection

Add a voice preference to the chat settings. Two options:
- **Simple**: A new `chat_tts_voice` localStorage key, selected via a dropdown in the chat header/settings area.
- **Profile-integrated**: Add to `VisitorProfile` and persist server-side. Requires migration.

Recommendation: Start with localStorage (`chat_tts_voice`), same pattern as tour workbench preferences. Can migrate to server-side later if needed.

### 5. Global TTS Toggle

Add to both chat and tour UIs:
- A toggle switch (e.g. in the header bar or settings panel)
- State stored in localStorage: `tts_enabled` (default: `false`)
- When ON: `audio_chunk` events automatically trigger playback
- When OFF: audio events are ignored; speaker icon on messages allows manual playback

## Data Flow

### Q&A with TTS enabled

```
1. User sends message
2. Frontend POST /chat/ask/stream { message, tts: true, tts_voice: "冰糖" }
3. Backend runs RAG pipeline, streams text chunks (existing)
4. Backend emits: chunk × N → done
5. Backend calls TTS API with full text + voice + style
6. Backend emits: audio_start → audio_chunk × N → audio_end
7. Frontend accumulates text (existing), feeds audio chunks to Web Audio API
8. User sees text appear + hears audio simultaneously
```

### Tour with TTS enabled

```
1. User sends message
2. Frontend POST /tour/sessions/{id}/chat/stream { message, tts: true }
3. Backend loads persona, runs RAG, streams text chunks (existing)
4. Backend emits: chunk × N → done
5. Backend loads persona TTS prompt from prompt system
6. Backend calls TTS API with full text + persona voice style
7. Backend emits: audio_start → audio_chunk × N → audio_end
8. Frontend plays audio via Web Audio API
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| TTS API timeout | Emit `audio_error` event, text response already delivered |
| TTS API auth failure | Log error, emit `audio_error`, skip TTS |
| TTS disabled (config) | No TTS events emitted at all |
| TTS provider is None | Services check before calling, skip silently |
| Frontend AudioContext blocked | Browser requires user gesture — auto-play may need a click to unlock |
| SSE disconnect during TTS | Client stops playback naturally |

## Configuration

### Environment Variables

```bash
TTS_ENABLED=true
TTS_BASE_URL=https://api.xiaomimimo.com/v1
TTS_API_KEY=your_api_key_here
TTS_MODEL=mimo-v2.5-tts
TTS_DEFAULT_VOICE=冰糖
TTS_TIMEOUT=30.0
```

### Dependencies

No new pip packages — uses `openai` (already installed) for the Xiaomi TTS API.

## Testing Strategy

1. **Unit tests**: Mock TTS provider, verify SSE events are emitted correctly after text events
2. **Contract tests**: Verify API endpoints accept `tts`/`tts_voice` parameters
3. **Integration tests**: Verify TTS provider correctly calls Xiaomi API with proper message format
4. **Frontend tests**: Verify useTTSPlayer decodes PCM16 correctly, schedules playback
