"""Process-local sandbox registry shared by lifecycle and worker routing."""

import asyncio

records = {}
lifecycle_lock = asyncio.Lock()
