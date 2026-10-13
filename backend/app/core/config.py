from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Comma-separated origins, e.g. http://localhost:3000
    cors_origins_raw: str = "http://localhost:3000"

    supabase_url: str = ""
    # Secret / service-role key. The anon key cannot write past row level security.
    supabase_key: str = ""

    google_api_key: str = ""
    gemini_chat_model: str = "gemini-2.5-flash"
    # Architecture: text-embedding-004 (768 dimensions). Must match schema.sql.
    gemini_embed_model: str = "models/text-embedding-004"
    embedding_dimensions: int = 768
    storage_bucket: str = "documents"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]


settings = Settings()
