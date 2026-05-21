"""WebSocket consumer that streams live query metrics to the analytics dashboard."""

import json
import asyncio

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model

from apps.query_analytics.models import QueryExecutionMetric

User = get_user_model()


class MetricsStreamConsumer(AsyncWebsocketConsumer):
    """SSE-like streaming over WebSocket — sends new metrics to subscribed clients."""

    GROUP_NAME = "metrics_stream"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data=None):
        pass  # client -> server messages are a no-op

    async def send_metric_update(self, event):
        """Handler called by Celery beat or background task on new metric."""
        await self.send(text_data=json.dumps({
            "type": "metric",
            "data": event.get("payload", {}),
        }))

    async def send_alert(self, event):
        await self.send(text_data=json.dumps({
            "type": "alert",
            "severity": event.get("severity", "info"),
            "message": event.get("message", ""),
        }))

    async def send_snapshot(self, event):
        await self.send(text_data=json.dumps({
            "type": "snapshot",
            "snapshot": event.get("payload", {}),
        }))
