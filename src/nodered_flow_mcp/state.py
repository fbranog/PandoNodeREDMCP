from __future__ import annotations

from .api.client import NodeRedClient
from .domain.draft import Draft
from .library.loader import Library
from .registry.node_registry import NodeRegistry
from .settings import Settings, get_settings


class AppState:
    def __init__(self, settings: Settings | None = None, client: NodeRedClient | None = None):
        self.settings = settings or get_settings()
        self._client = client
        self.registry = NodeRegistry()
        self._registry_loaded = False
        self.library = Library(self.settings.examples_dir)

    @property
    def client(self) -> NodeRedClient:
        if self._client is None:
            self._client = NodeRedClient(self.settings)
        return self._client

    async def ensure_registry(self, force: bool = False) -> NodeRegistry:
        if force or not self._registry_loaded:
            await self.registry.refresh(self.client)
            self._registry_loaded = True
        return self.registry

    def load_draft(self, draft_id: str) -> Draft:
        return Draft.load(self.settings.drafts_dir, draft_id)

    def save_draft(self, d: Draft) -> None:
        d.save(self.settings.drafts_dir)
