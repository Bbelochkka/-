from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class _ConfigData:
    service_name: str
    service_version: str
    default_generation_mode: str


class AppConfig:
    """Singleton with application settings.

    The pattern is used to provide a single, explicit configuration object
    for the whole backend service.
    """

    _instance: AppConfig | None = None

    def __new__(cls) -> "AppConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._data = _ConfigData(
            service_name=os.getenv("SERVICE_NAME", "courses-service"),
            service_version=os.getenv("SERVICE_VERSION", "2.0.0"),
            default_generation_mode=os.getenv("DEFAULT_GENERATION_MODE", "summary"),
        )
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "AppConfig":
        return cls()

    @property
    def service_name(self) -> str:
        return self._data.service_name

    @property
    def service_version(self) -> str:
        return self._data.service_version

    @property
    def default_generation_mode(self) -> str:
        return self._data.default_generation_mode
