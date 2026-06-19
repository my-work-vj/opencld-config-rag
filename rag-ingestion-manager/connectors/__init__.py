"""Connector package — registers all data source connector types."""

from connectors.google_drive import AwsS3Connector, GoogleDriveConnector
from connectors.registry import ConnectorRegistry

ConnectorRegistry.register(GoogleDriveConnector())
ConnectorRegistry.register(AwsS3Connector())

__all__ = ["ConnectorRegistry"]
