"""Gradio Webcam interface for the Week 01 real-time filter lab."""

from __future__ import annotations

import argparse
from pathlib import Path

import gradio as gr

from .access import create_access_plan
from .frame_gateway import BrowserFrameGateway
from .processor import RealtimeFrameProcessor
from .profiles import (
    DEFAULT_STREAM_PROFILE,
    STREAM_PROFILES,
    StreamProfile,
    get_stream_profile,
)
from .webcam_component import create_webcam_component

APP_TITLE = "Real-time Webcam Filters"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

APP_CSS = """
.app-shell { max-width: 1180px; margin: 0 auto; }
"""


def create_app(
    processor: RealtimeFrameProcessor | None = None,
    profile: StreamProfile | None = None,
) -> gr.Blocks:
    """Build the UI without launching it, enabling isolated tests and reuse."""

    frame_processor = processor or RealtimeFrameProcessor()
    stream_profile = profile or get_stream_profile()
    gateway = BrowserFrameGateway(frame_processor, stream_profile)

    with gr.Blocks(title=APP_TITLE, analytics_enabled=False) as app:
        with gr.Column(elem_classes=["app-shell"]):
            gr.Markdown(
                """
# Real-time Webcam Filters

Choose a filter, allow camera access, and start the Webcam stream. The browser
sends RGB frames; the processing core converts them to OpenCV BGR, applies the
selected filter, and returns RGB frames for display.
                """
            )

            gr.Markdown(
                f"**Stream profile:** {stream_profile.label} — "
                f"{stream_profile.width}×{stream_profile.height}, "
                f"target {stream_profile.target_fps:g} FPS. "
                "The latest frame is preferred over building a delayed backlog."
            )

            create_webcam_component(
                frame_function=gateway.process_frame,
                profile=stream_profile,
                filter_choices=frame_processor.registry.choices(),
            )

            gr.Markdown(
                "Only one frame request is allowed in flight. When the response "
                "arrives, the browser captures the current camera frame instead of "
                "processing an outdated backlog."
            )

    return app.queue(
        max_size=stream_profile.queue_size,
        default_concurrency_limit=stream_profile.concurrency_limit,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--access",
        choices=["local", "lan", "mobile"],
        default="local",
        help=(
            "local: this computer only; lan: same-network HTTP; "
            "mobile: temporary password-protected public HTTPS tunnel"
        ),
    )
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument(
        "--stream-profile",
        choices=tuple(STREAM_PROFILES),
        default=DEFAULT_STREAM_PROFILE,
        help="Trade image detail for lower transport latency.",
    )
    parser.add_argument("--username", default="visiontrace")
    parser.add_argument(
        "--password",
        help="Optional mobile-mode password; a random one is generated if omitted.",
    )
    args = parser.parse_args()

    access = create_access_plan(
        args.access,
        port=args.port,
        username=args.username,
        password=args.password,
    )
    print("\n=== Access information ===")
    for notice in access.notices:
        print(f"- {notice}")
    print()

    stream_profile = get_stream_profile(args.stream_profile)
    print(
        f"- Stream profile: {stream_profile.label} "
        f"({stream_profile.width}x{stream_profile.height} at "
        f"{stream_profile.target_fps:g} FPS target)"
    )

    app = create_app(profile=stream_profile)
    app.launch(
        server_name=access.server_name,
        server_port=args.port,
        share=access.share,
        auth=access.auth,
        pwa=access.pwa,
        show_error=True,
        css=APP_CSS,
        blocked_paths=[str(PROJECT_ROOT)],
        max_file_size="5mb",
    )


if __name__ == "__main__":
    main()
