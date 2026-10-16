from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_NAME = Literal["dev", "prod", "test"]


class DbSettings(BaseModel):
    """数据库配置"""

    model_config = ConfigDict(extra="forbid")

    db: str = Field(min_length=1, description="数据库名称")
    host: str = Field(min_length=1, description="数据库 IP 地址")
    port: int = Field(ge=1, le=65535, description="数据库端口")
    username: str = Field(min_length=1, description="数据库用户名")
    password: SecretStr = Field(min_length=1, description="数据库密码")

    driver: Literal["postgresql+psycopg"] = "postgresql+psycopg"

    @property
    def url(self) -> URL:
        return URL.create(
            drivername=self.driver,
            username=self.username,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.db,
        )


class Settings(BaseSettings):
    """完整配置"""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="forbid",
        case_sensitive=False,
    )

    env: ENV_NAME = "dev"
    admin: DbSettings


settings = Settings()
