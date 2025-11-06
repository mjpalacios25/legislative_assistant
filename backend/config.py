from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class DatabaseSettings(BaseSettings):
  model_config = SettingsConfigDict(env_file='.env', 
                                    env_file_encoding='utf-8',
                                  )
  LANGCHAIN_TRACING_V2: str
  LANGCHAIN_ENDPOINT: str
  LANGCHAIN_API_KEY: str
  HF_TOKEN: str
  CONGRESS_API_KEY:str
  NEO4J_URL: str
  NEO4J_USERNAME: str
  NEO4J_PW: str
  NEO4J_DB: str

# if __name__ == '__main__':
settings = DatabaseSettings()