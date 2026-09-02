"""Reusable real-time processing components for the Week 01 lab."""

from .access import AccessPlan, create_access_plan, discover_lan_ipv4_addresses
from .frame_gateway import BrowserFrameGateway, FramePayloadError, GatewayFrame
from .processor import (
    FrameContractError,
    ProcessedFrame,
    ProcessingMetrics,
    RealtimeFrameProcessor,
    RealtimeProcessingError,
    UnknownFilterError,
)
from .profiles import (
    DEFAULT_STREAM_PROFILE,
    STREAM_PROFILES,
    StreamProfile,
    get_stream_profile,
)
from .registry import FilterDefinition, FilterRegistry
from .telemetry import CadenceSnapshot, FrameCadenceTracker

__all__ = [
    "AccessPlan",
    "BrowserFrameGateway",
    "CadenceSnapshot",
    "DEFAULT_STREAM_PROFILE",
    "FilterDefinition",
    "FilterRegistry",
    "FrameCadenceTracker",
    "FrameContractError",
    "FramePayloadError",
    "GatewayFrame",
    "ProcessedFrame",
    "ProcessingMetrics",
    "RealtimeFrameProcessor",
    "RealtimeProcessingError",
    "STREAM_PROFILES",
    "StreamProfile",
    "UnknownFilterError",
    "create_access_plan",
    "discover_lan_ipv4_addresses",
    "get_stream_profile",
]
