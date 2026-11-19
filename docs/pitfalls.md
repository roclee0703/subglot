# Pitfalls we hit building this pipeline

These are not hypothetical best practices. Every item below was hit on a
real production subtitle/dubbing pipeline, reproduced, measured, and fixed.
The numbers are from those measurements.

## 1. Forcing Whisper's `language` parameter to "check" the language causes fluent hallucinations

**Trap.** Whisper does not fail gracefully when you force the wrong
`language`. Given a **Chinese** recording transcribed with
`language="en"`, it will happily emit a fluent **English** transcript —
and the timestamps line up perfectly with the real Chinese speech, so the
output looks completely legitimate at a glance.

A real example from our pipeline (Chinese audio, forced `language="en"`):

> 「為什麼沒有公司推出老鼠餵貓糧」
> → `Why didn't the company push the mouse out to feed the cat?`

Same timestamp window. Fluent English. Nothing "wrong" to see — unless you
happen to know the source audio was Chinese.

**Rule.** Never force a `language` value as a way to detect or verify the
audio's language. Auto-detect (`language=None`, subglot's `--language
auto`) and report the detected language + confidence instead. If you truly
need to verify whether a language is present in a track, use one of the
signal methods below.

## 2. Verifying "language X is gone from this track" requires the interference-free track

Related to mixing/removal work: if you want to prove that e.g. English
speech has been removed from a mixed track, do **not** transcribe the mixed
track and look for English text — Whisper can hallucinate text in the
forced language even when nothing intelligible is there (see pitfall 1).

Two methods that actually work:

- **Transcribe the clean track** — run source separation first and check
  the accompaniment-only track, which contains no speech to hallucinate
  from.
- **Energy comparison** — compare mean loudness of segments known to be
  vocal vs. known to be instrumental. A delta under ~1 dB means there is
  no residual voice worth talking about.

## 3. Cross-correlation indexing: convolution gives you an off-by-template-length error

When placing a synthesized voice segment onto an audio timeline, the
reliable way to find where clip A lands inside track B is cross-correlation.
But the "obvious" numpy one-liner

```python
corr = np.fft.irfft(np.fft.rfft(seg) * np.fft.rfft(tmpl[::-1]))
```

is a **convolution**, not a correlation. In its output, index `k` corresponds
to correlation lag `k - m + 1` (where `m = len(tmpl)`). If you skip that
offset, every measured placement is late by **exactly the length of the
template** — and the symptom is subtle: your offset error always equals the
template duration, which looks like a bizarre systematic delay rather than a
bug.

**Rule.** Correlate via conjugation (`rfft(seg) * conj(rfft(tmpl))`) or add
the `k - m + 1` correction explicitly. And don't rely on energy thresholds
to find the placement: when background music is playing, a weak syllable
sits at the same magnitude as the music bed, so any threshold you pick is
wrong at one end or the other.

## 4. edge-tts clips carry ~0.9 s of trailing silence

Synthesized clips from edge-tts have ~0.15 s of leading silence and
**~0.9 s of trailing silence**. If you don't trim it, a 4-character line and
a 7-character line can both report the same duration (we measured both at
1.87 s) — which will wreck any duration-based placement or reading-speed
math and make TTS sound "too slow" when it isn't.

**Rule.** Trim leading/trailing silence from every synthesized clip before
measuring it or placing it on a timeline.

## 5. "Keep the background music as-is" usually means the music is inaudible

On real short-video masters, background music mixed under a voiceover often
sits around **-46 dBFS** — roughly 18 dB below the voice. Leaving it "as
is" means viewers cannot hear it at all.

If the music matters, the fix is:

1. AI source separation to extract the accompaniment,
2. gain the accompaniment up to around **-28 dBFS** (~+18 dB),
3. sidechain ducking against the voice track.

## 6. Center-channel cancellation (L-R) needs a mono-check first

Vocal removal via `L - R` only works on material with real stereo width.
Measure the correlation between left and right channels first: **≥ 0.95 is
effectively mono**, and L-R will destroy the music along with the vocal
(a track we measured: correlation 0.988, side energy only 7.7% of total —
that route is dead before you start).

**Rule.** Gate the L-R approach behind a correlation preflight; otherwise
use source separation.
