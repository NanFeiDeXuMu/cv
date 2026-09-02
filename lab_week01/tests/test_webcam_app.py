from __future__ import annotations

import gradio as gr

from lab_week01.realtime.profiles import get_stream_profile
from lab_week01.realtime.webcam_app import create_app


def test_gradio_app_uses_browser_owned_latest_frame_component() -> None:
    profile = get_stream_profile("low-latency")
    app = create_app(profile=profile)
    config = app.get_config_file()

    assert config["mode"] == "blocks"
    html_components = [
        component for component in config["components"] if component["type"] == "html"
    ]
    assert len(html_components) == 1
    props = html_components[0]["props"]
    custom_props = props["props"]
    assert custom_props["capture_width"] == 320
    assert custom_props["capture_height"] == 240
    assert custom_props["target_fps"] == 8.0
    assert "Synthetic test pattern" in props["html_template"]
    assert "server.process_frame" in props["js_on_load"]
    assert "inFlight" in props["js_on_load"]

    # The built-in Image.stream state machine caused the first-frame freeze.
    assert not any(
        target[1] == "stream"
        for dependency in config["dependencies"]
        for target in dependency["targets"]
    )


def test_all_registered_filters_are_rendered_in_browser_selector() -> None:
    app = create_app()
    config = app.get_config_file()
    html = next(
        component["props"]["html_template"]
        for component in config["components"]
        if component["type"] == "html"
    )

    for key in (
        "original",
        "vintage_warm",
        "cool_tone",
        "high_contrast",
        "faded",
        "grayscale",
    ):
        assert f'value="{key}"' in html


def test_component_server_adapter_unpacks_javascript_argument_array() -> None:
    app = create_app()
    component = next(
        block for block in app.blocks.values() if isinstance(block, gr.HTML)
    )

    malformed_frame = component.process_frame(["not-a-data-url", "original"])
    malformed_request = component.process_frame("not-an-array")

    assert malformed_frame["ok"] is False
    assert "data URL" in str(malformed_frame["error"])
    assert malformed_request == {
        "ok": False,
        "error": "Invalid browser frame request",
    }
