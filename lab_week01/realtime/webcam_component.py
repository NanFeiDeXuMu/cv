"""Browser-owned latest-frame Webcam component for Gradio 6."""

from __future__ import annotations

from html import escape
from typing import Callable

import gradio as gr

from .profiles import StreamProfile

WEBCAM_HTML = """
<section class="vt-realtime" aria-label="Real-time filter workspace">
  <div class="vt-toolbar">
    <label>Input source
      <select class="vt-source">
        <option value="camera">Camera</option>
        <option value="test-pattern">Synthetic test pattern</option>
      </select>
    </label>
    <label>Filter
      <select class="vt-filter">__FILTER_OPTIONS__</select>
    </label>
    <button type="button" class="vt-start">Start stream</button>
    <button type="button" class="vt-stop" disabled>Stop stream</button>
  </div>
  <div class="vt-grid">
    <figure>
      <figcaption>Live input</figcaption>
      <video class="vt-video" playsinline muted></video>
      <canvas class="vt-test-pattern" hidden></canvas>
    </figure>
    <figure>
      <figcaption>Processed output</figcaption>
      <div class="vt-output-wrap">
        <img class="vt-output" alt="Processed output" />
        <span class="vt-placeholder">Waiting for frames...</span>
      </div>
    </figure>
  </div>
  <canvas class="vt-capture" hidden></canvas>
  <p class="vt-status" role="status" aria-live="polite">Ready. Select a source and start the stream.</p>
</section>
"""

WEBCAM_CSS = """
.vt-realtime { display: grid; gap: 14px; }
.vt-toolbar { display: flex; gap: 10px; align-items: end; flex-wrap: wrap; }
.vt-toolbar label { display: grid; gap: 5px; font-weight: 600; }
.vt-toolbar select, .vt-toolbar button {
  min-height: 40px; border: 1px solid var(--border-color-primary);
  border-radius: 8px; padding: 7px 11px; background: var(--background-fill-primary);
  color: var(--body-text-color);
}
.vt-toolbar button { cursor: pointer; font-weight: 600; }
.vt-toolbar button:disabled { cursor: not-allowed; opacity: .5; }
.vt-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.vt-grid figure { margin: 0; display: grid; gap: 7px; }
.vt-grid figcaption { font-weight: 600; }
.vt-video, .vt-test-pattern, .vt-output-wrap {
  width: 100%; aspect-ratio: 4 / 3; border-radius: 10px; overflow: hidden;
  background: #111; border: 1px solid var(--border-color-primary);
}
.vt-video, .vt-test-pattern, .vt-output { object-fit: contain; }
.vt-output-wrap { position: relative; display: grid; place-items: center; }
.vt-output { width: 100%; height: 100%; display: none; }
.vt-placeholder { color: #bbb; }
.vt-status {
  margin: 0; padding: 10px 12px; border-radius: 8px;
  background: var(--background-fill-secondary); font-family: ui-monospace, Consolas, monospace;
}
@media (max-width: 700px) { .vt-grid { grid-template-columns: 1fr; } }
"""

WEBCAM_JS = r"""
const sourceSelect = element.querySelector('.vt-source');
const filterSelect = element.querySelector('.vt-filter');
const startButton = element.querySelector('.vt-start');
const stopButton = element.querySelector('.vt-stop');
const video = element.querySelector('.vt-video');
const testPattern = element.querySelector('.vt-test-pattern');
const capture = element.querySelector('.vt-capture');
const output = element.querySelector('.vt-output');
const placeholder = element.querySelector('.vt-placeholder');
const status = element.querySelector('.vt-status');

const maxWidth = Number(props.capture_width);
const maxHeight = Number(props.capture_height);
const targetFps = Number(props.target_fps);
const intervalMs = 1000 / targetFps;
let mediaStream = null;
let running = false;
let inFlight = false;
let generation = 0;
let animationId = null;
let lastSubmittedAt = -Infinity;
let testSequence = 0;

function setStatus(message) {
  status.textContent = message;
}

function stopStream() {
  generation += 1;
  running = false;
  inFlight = false;
  if (animationId !== null) cancelAnimationFrame(animationId);
  animationId = null;
  if (mediaStream) mediaStream.getTracks().forEach((track) => track.stop());
  mediaStream = null;
  video.srcObject = null;
  startButton.disabled = false;
  stopButton.disabled = true;
  sourceSelect.disabled = false;
  setStatus('Stopped.');
}

function sizeCanvas(sourceWidth, sourceHeight) {
  const scale = Math.min(maxWidth / sourceWidth, maxHeight / sourceHeight, 1);
  capture.width = Math.max(1, Math.round(sourceWidth * scale));
  capture.height = Math.max(1, Math.round(sourceHeight * scale));
}

function paintTestPattern(now) {
  testSequence += 1;
  testPattern.width = maxWidth;
  testPattern.height = maxHeight;
  const ctx = testPattern.getContext('2d');
  ctx.fillStyle = `hsl(${(testSequence * 19) % 360} 78% 42%)`;
  ctx.fillRect(0, 0, maxWidth, maxHeight);
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 46px sans-serif';
  ctx.fillText(`#${testSequence}`, 18, 58);
  ctx.fillRect((testSequence * 17) % Math.max(1, maxWidth - 54), maxHeight * .58, 54, 54);
  ctx.font = '18px sans-serif';
  ctx.fillText(`${Math.round(now)} ms`, 18, maxHeight - 18);
}

function captureLatestFrame(now) {
  let source;
  let width;
  let height;
  if (sourceSelect.value === 'camera') {
    source = video;
    width = video.videoWidth;
    height = video.videoHeight;
    if (!width || !height) return null;
  } else {
    paintTestPattern(now);
    source = testPattern;
    width = testPattern.width;
    height = testPattern.height;
  }
  sizeCanvas(width, height);
  const ctx = capture.getContext('2d');
  ctx.drawImage(source, 0, 0, capture.width, capture.height);
  return capture.toDataURL('image/jpeg', 0.70);
}

async function pump(now, token) {
  if (!running || token !== generation) return;
  animationId = requestAnimationFrame((nextNow) => pump(nextNow, token));
  if (inFlight || now - lastSubmittedAt < intervalMs) return;

  const payload = captureLatestFrame(now);
  if (!payload) return;
  lastSubmittedAt = now;
  inFlight = true;
  try {
    const result = await server.process_frame(payload, filterSelect.value);
    if (!running || token !== generation) return;
    if (!result.ok) {
      setStatus(`Processing error: ${result.error}`);
      return;
    }
    output.src = result.image_data_url;
    output.style.display = 'block';
    placeholder.style.display = 'none';
    setStatus(`${result.status} | Target ${targetFps.toFixed(1)} FPS`);
  } catch (error) {
    if (running && token === generation) setStatus(`Transport error: ${error.message || error}`);
  } finally {
    if (token === generation) inFlight = false;
  }
}

async function startStream() {
  if (running) return;
  startButton.disabled = true;
  sourceSelect.disabled = true;
  setStatus('Starting...');
  try {
    if (sourceSelect.value === 'camera') {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: maxWidth },
          height: { ideal: maxHeight },
          frameRate: { ideal: targetFps, max: targetFps }
        },
        audio: false
      });
      video.srcObject = mediaStream;
      await video.play();
      video.hidden = false;
      testPattern.hidden = true;
    } else {
      video.hidden = true;
      testPattern.hidden = false;
    }
    running = true;
    inFlight = false;
    lastSubmittedAt = -Infinity;
    stopButton.disabled = false;
    const token = ++generation;
    animationId = requestAnimationFrame((now) => pump(now, token));
  } catch (error) {
    startButton.disabled = false;
    sourceSelect.disabled = false;
    setStatus(`Camera error: ${error.message || error}`);
  }
}

startButton.addEventListener('click', startStream);
stopButton.addEventListener('click', stopStream);
sourceSelect.addEventListener('change', () => {
  if (running) stopStream();
});

const cleanupObserver = new MutationObserver(() => {
  if (!element.isConnected) {
    stopStream();
    cleanupObserver.disconnect();
  }
});
cleanupObserver.observe(document.body, { childList: true, subtree: true });
"""


def create_webcam_component(
    *,
    frame_function: Callable[[str, str], dict[str, object]],
    profile: StreamProfile,
    filter_choices: tuple[tuple[str, str], ...],
) -> gr.HTML:
    """Build the custom browser component with trusted registry options."""

    options = "".join(
        f'<option value="{escape(key, quote=True)}">{escape(label)}</option>'
        for label, key in filter_choices
    )

    # Gradio marks ordinary function objects when registering server_functions;
    # Python bound-method objects do not allow that attribute assignment.
    def process_frame(payload: object) -> dict[str, object]:
        # Gradio's component_server endpoint passes one body.data value.  Calls
        # with multiple JavaScript arguments arrive as a single list.
        if not isinstance(payload, (list, tuple)) or len(payload) != 2:
            return {"ok": False, "error": "Invalid browser frame request"}
        image_data_url, filter_key = payload
        if not isinstance(image_data_url, str) or not isinstance(filter_key, str):
            return {"ok": False, "error": "Invalid browser frame request"}
        return frame_function(image_data_url, filter_key)

    return gr.HTML(
        value="",
        html_template=WEBCAM_HTML.replace("__FILTER_OPTIONS__", options),
        css_template=WEBCAM_CSS,
        js_on_load=WEBCAM_JS,
        server_functions=[process_frame],
        capture_width=profile.width,
        capture_height=profile.height,
        target_fps=profile.target_fps,
        apply_default_css=False,
        container=True,
    )
