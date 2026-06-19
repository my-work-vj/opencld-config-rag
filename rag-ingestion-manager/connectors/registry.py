"""Registry for data source connector types."""

from __future__ import annotations

from connectors.base import ConnectorTypeInfo, DataSourceConnector


class ConnectorNotFoundError(Exception):
    pass


class ConnectorRegistry:
    _connectors: dict[str, DataSourceConnector] = {}

    @classmethod
    def register(cls, connector: DataSourceConnector) -> None:
        cls._connectors[connector.type_id] = connector

    @classmethod
    def get(cls, type_id: str) -> DataSourceConnector:
        connector = cls._connectors.get(type_id)
        if not connector:
            raise ConnectorNotFoundError(f"Unknown connector type: {type_id}")
        return connector

    @classmethod
    def list_types(cls) -> list[ConnectorTypeInfo]:
        return [c.type_info() for c in cls._connectors.values()]

    @classmethod
    def has(cls, type_id: str) -> bool:
        return type_id in cls._connectors

