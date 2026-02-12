from pydantic_settings import BaseSettings, SettingsConfigDict

class DatabaseSettings(BaseSettings):
  model_config = SettingsConfigDict(env_file='.env',
                                    env_file_encoding='utf-8',
                                    case_sensitive=False,
                                    extra='ignore',
                                    secrets_dir='settings/secrets'
                                  )
  # LANGCHAIN_TRACING_V2: str
  # LANGCHAIN_ENDPOINT: str
  # LANGCHAIN_API_KEY: str
  # HF_TOKEN: str
  # CONGRESS_API_KEY:str
  NEO4J_URL: str
  NEO4J_USERNAME: str
  NEO4J_DB: str
  db_password: str

settings = DatabaseSettings()

if __name__ == '__main__':
  settings = DatabaseSettings()
  print(settings.model_dump())