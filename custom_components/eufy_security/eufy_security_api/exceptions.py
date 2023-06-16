"""Define all exceptions for module."""
from typing import Optional
from .event import Event
from .metadata import Metadata


class BaseEufySecurityException(Exception):
    """Base exception for module."""


class DriverNotConnectedException(BaseEufySecurityException):
    """Driver connection exception"""


class FailedCommandException(BaseEufySecurityException):
    """Failed command exception."""

    def __init__(self, message_id: str, error_code: str, message: Optional[str] = None) -> None:
        super().__init__(message or f"Command failed: {error_code} - {message}")
        self.message_id = message_id
        self.error_code = error_code


class WebSocketConnectionException(BaseEufySecurityException):
    """Web socket connection exception."""

    def __init__(self, msg: str) -> None:
        super().__init__(msg)


class IncompatibleVersionException(BaseEufySecurityException):
    """Incompatible version exception."""

    def __init__(self, supported_version: int, required_version: int) -> None:
        super().__init__(f"Eufy-Security-WS max supported version {supported_version} is lower than expected version {required_version}, update the add-on")
        self.supported_version = supported_version
        self.required_version = required_version


class UnexpectedMessageTypeException(BaseEufySecurityException):
    """Unexcepted message type exception."""

    def __init__(self, message: dict) -> None:
        super().__init__(f"Unexpected message type received, please create issue under github repository to track it, {message}")
        self.message = message


class UnknownEventSourceException(BaseEufySecurityException):
    """Unknown event source exception."""

    def __init__(self, event: Event) -> None:
        super().__init__(f"Unknown event source is received, type: {event.type}, data: {event.data}")
        self.event = event


class ValueNotSetException(BaseEufySecurityException):
    """Missing property value even it exists on metadata"""

    def __init__(self, metadata: Metadata) -> None:
        super().__init__(f"Property value is not set, defaulting to MIN, property: {metadata.name}, device: {metadata.product.name}")
        self.metadata = metadata


class CaptchaRequiredException(BaseEufySecurityException):
    """Captcha information required"""

    def __init__(self, captcha_id: str, captcha_img: str) -> None:
        super().__init__("Captcha code is required, please revalidate on Integrations page")
        self.captcha_id = captcha_id
        self.captcha_img = captcha_img


class MultiFactorCodeRequiredException(BaseEufySecurityException):
    """Multi factor code required"""

    def __init__(self) -> None:
        super().__init__("Multi factor code is required, please revalidate on Integrations page")


class DeviceNotInitializedYetException(BaseEufySecurityException):
    """Device not initialized yet"""

    def __init__(self, event: Event) -> None:
        super().__init__(f"Device not initialized yet, it will be initialized later on, type: {event.type}, data: {event.data}")
        self.event = event


class BaseEufySecurityModelException(Exception):
    """Base exception for model."""


class CameraRTSPStreamNotSupported(BaseEufySecurityModelException):
    """Camera does not support RTSP Streaming."""

    def __init__(self, camera_name: str) -> None:
        super().__init__("Camera (%s) does not support RTSP Stream", camera_name)


class CameraRTSPStreamNotEnabled(BaseEufySecurityModelException):
    """RTSP Streaming is not enabled for camera."""

    def __init__(self, camera_name: str) -> None:
        super().__init__("RTSP Streaming is not enabled for camera (%s)", camera_name)
