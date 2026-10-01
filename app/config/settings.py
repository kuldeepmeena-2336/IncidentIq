from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "incidentiq-agentic"
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./incidentiq.db"

    openai_api_key: str = ""
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment_name: str = "gpt-4"
    azure_openai_embedding_deployment_name: str = "text-embedding-ada-002"
    openai_compatible_api_key: str = ""
    openai_compatible_base_url: str = ""
    gemini_openai_api_key: str = "AQ.Ab8RN6LEUyTN23HII_9BIwl_s1TLbMNnkpQmm9SFDaUqFqPZpQ"
    gemini_openai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    default_llm_provider: str = "gemini_openai_compatible"
    default_embedding_provider: str = "gemini_openai_compatible"

    jira_base_url: str = ""
    jira_username: str = ""
    jira_api_token: str = ""
    jira_webhook_secret: str = ""

    secret_key: str = "change-me-in-production"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
