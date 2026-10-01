from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from openai import AzureOpenAI, OpenAI

from app.config.settings import settings

ProviderType = Literal["openai", "azure_openai", "openai_compatible", "gemini_openai_compatible"]


@dataclass
class ProviderConfig:
    name: ProviderType
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    embedding_model: str = ""
    supports_embeddings: bool = True

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key) or bool(self.base_url)


class ProviderAdapter(Protocol):
    provider: ProviderConfig

    def chat(self, prompt: str, *, system_prompt: str | None = None, **kwargs: Any) -> dict[str, Any]:
        ...

    def embed(self, text: str, **kwargs: Any) -> list[float]:
        ...


class BaseOpenAIAdapter:
    def __init__(self, config: ProviderConfig) -> None:
        self.provider = config

    def _build_client(self) -> OpenAI:
        return OpenAI(api_key=self.provider.api_key, base_url=self.provider.base_url or None)

    def chat(self, prompt: str, *, system_prompt: str | None = None, **kwargs: Any) -> dict[str, Any]:
        if not self.provider.api_key:
            raise RuntimeError(f"{self.provider.name} provider is not configured")

        client = self._build_client()
        response = client.chat.completions.create(
            model=self.provider.model,
            messages=[
                {"role": "system", "content": system_prompt or "You are a helpful incident investigation assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=kwargs.get("temperature", 0.2),
            max_tokens=kwargs.get("max_tokens", 500),
        )
        content = response.choices[0].message.content if response.choices else ""
        return {
            "provider": self.provider.name,
            "model": self.provider.model,
            "content": content,
            "status": "ok",
        }

    def embed(self, text: str, **kwargs: Any) -> list[float]:
        if not self.provider.api_key:
            raise RuntimeError(f"{self.provider.name} embedding provider is not configured")

        client = self._build_client()
        response = client.embeddings.create(
            model=self.provider.embedding_model,
            input=text,
        )
        return response.data[0].embedding


class OpenAIProviderAdapter(BaseOpenAIAdapter):
    pass


class AzureOpenAIProviderAdapter:
    def __init__(self, config: ProviderConfig) -> None:
        self.provider = config

    def chat(self, prompt: str, *, system_prompt: str | None = None, **kwargs: Any) -> dict[str, Any]:
        if not self.provider.api_key or not self.provider.base_url:
            raise RuntimeError("Azure OpenAI provider is not configured")

        client = AzureOpenAI(
            api_key=self.provider.api_key,
            azure_endpoint=self.provider.base_url,
            api_version=kwargs.get("api_version", "2024-02-01"),
        )
        response = client.chat.completions.create(
            model=self.provider.model,
            messages=[
                {"role": "system", "content": system_prompt or "You are a helpful incident investigation assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=kwargs.get("temperature", 0.2),
            max_tokens=kwargs.get("max_tokens", 500),
        )
        content = response.choices[0].message.content if response.choices else ""
        return {
            "provider": self.provider.name,
            "model": self.provider.model,
            "content": content,
            "status": "ok",
        }

    def embed(self, text: str, **kwargs: Any) -> list[float]:
        if not self.provider.api_key or not self.provider.base_url:
            raise RuntimeError("Azure OpenAI embedding provider is not configured")

        client = AzureOpenAI(
            api_key=self.provider.api_key,
            azure_endpoint=self.provider.base_url,
            api_version=kwargs.get("api_version", "2024-02-01"),
        )
        response = client.embeddings.create(
            model=self.provider.embedding_model,
            input=text,
        )
        return response.data[0].embedding


class OpenAICompatibleProviderAdapter(BaseOpenAIAdapter):
    pass


class GeminiCompatibleProviderAdapter(BaseOpenAIAdapter):
    pass


class ProviderRouter:
    def __init__(self) -> None:
        self.providers = self._build_provider_list()

    def _build_provider_list(self) -> list[ProviderConfig]:
        providers: list[ProviderConfig] = []

        if settings.openai_api_key:
            providers.append(
                ProviderConfig(
                    name="openai",
                    api_key=settings.openai_api_key,
                    model="gpt-4o-mini",
                    embedding_model="text-embedding-3-small",
                )
            )

        if settings.azure_openai_api_key and settings.azure_openai_endpoint:
            providers.append(
                ProviderConfig(
                    name="azure_openai",
                    api_key=settings.azure_openai_api_key,
                    base_url=settings.azure_openai_endpoint,
                    model=settings.azure_openai_deployment_name,
                    embedding_model=settings.azure_openai_embedding_deployment_name,
                )
            )

        if settings.openai_compatible_api_key and settings.openai_compatible_base_url:
            providers.append(
                ProviderConfig(
                    name="openai_compatible",
                    api_key=settings.openai_compatible_api_key,
                    base_url=settings.openai_compatible_base_url,
                    model="gpt-4o-mini",
                    embedding_model="text-embedding-3-small",
                )
            )

        if settings.gemini_openai_api_key and settings.gemini_openai_base_url:
            providers.append(
                ProviderConfig(
                    name="gemini_openai_compatible",
                    api_key=settings.gemini_openai_api_key,
                    base_url=settings.gemini_openai_base_url,
                    model="gemini-flash-latest",
                    embedding_model="gemini-embedding-001",
                )
            )

        return providers

    def is_available(self) -> bool:
        return bool(self.providers)

    def get_llm_provider(self) -> ProviderConfig | None:
        if not self.providers:
            return None

        preferred = settings.default_llm_provider
        for provider in self.providers:
            if provider.name == preferred:
                return provider
        return self.providers[0]

    def get_embedding_provider(self) -> ProviderConfig | None:
        if not self.providers:
            return None

        preferred = settings.default_embedding_provider
        for provider in self.providers:
            if provider.name == preferred:
                return provider
        return self.providers[0]

    def build_adapter(self, provider: ProviderConfig | None) -> ProviderAdapter | None:
        if provider is None:
            return None
        if provider.name == "openai":
            return OpenAIProviderAdapter(provider)
        if provider.name == "azure_openai":
            return AzureOpenAIProviderAdapter(provider)
        if provider.name == "openai_compatible":
            return OpenAICompatibleProviderAdapter(provider)
        if provider.name == "gemini_openai_compatible":
            return GeminiCompatibleProviderAdapter(provider)
        return None

    def get_llm_adapter(self) -> ProviderAdapter | None:
        return self.build_adapter(self.get_llm_provider())

    def get_embedding_adapter(self) -> ProviderAdapter | None:
        return self.build_adapter(self.get_embedding_provider())

    def status_summary(self) -> dict[str, Any]:
        return {
            "degraded_mode": not self.providers,
            "configured_providers": [provider.name for provider in self.providers],
            "preferred_llm": self.get_llm_provider().name if self.get_llm_provider() else None,
            "preferred_embedding": self.get_embedding_provider().name if self.get_embedding_provider() else None,
        }


provider_router = ProviderRouter()
