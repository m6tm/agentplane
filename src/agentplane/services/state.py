"""Shared application state.

This module holds singletons that need to be accessed from multiple places,
such as the heartbeat scheduler.
"""

from agentplane.services.scheduler import HeartbeatScheduler

scheduler = HeartbeatScheduler()
