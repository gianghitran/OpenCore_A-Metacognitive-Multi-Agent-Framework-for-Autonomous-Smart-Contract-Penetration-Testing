import os

import dataclasses
import sys
from strenum import StrEnum
from typing import Dict, Any
from pathlib import Path

from config.pydantic_settings_file import *
from config.pydantic_settings_file import BaseFileSettings

# PENTEST_ROOT = Path(os.environ.get("PENTEST_ROOT", ".")).resolve()

PENTEST_ROOT = Path(__file__).resolve().parent.parent

class Mode(StrEnum):
    Auto = "auto"
    Manual = "manual"
    SemiAuto = "semi"

    def __missing__(self, key):
        return self.Auto


class BasicConfig(BaseFileSettings):
    model_config = SettingsConfigDict(yaml_file=PENTEST_ROOT / "basic_config.yaml")

    log_verbose: bool = True

    stop_on_flag: bool = False

    mode: str = Mode.Auto

    @cached_property
    def LOG_PATH(self) -> Path:

        p = PENTEST_ROOT / "logs"
        return p


    http_default_timeout: int = 300

    kali: dict = {
        "hostname": "10.10.0.5",
        "port": 22,
        "username": "root",
        "password": "root",
    }

    default_bind_host: str = "0.0.0.0" if sys.platform != "win32" else "127.0.0.1"

    api_server: dict = {
        "host": default_bind_host,
        "port": 7861,
        "public_host": "127.0.0.1",
        "public_port": 7861,
    }

    def make_dirs(self):
        for p in [
            self.LOG_PATH,
        ]:
            p.mkdir(parents=True, exist_ok=True)


class DBConfig(BaseFileSettings):
    model_config = SettingsConfigDict(yaml_file=PENTEST_ROOT / "db_config.yaml")
    mysql: dict = {"host": "", "port": 3306, "user": "", "password": "", "database": ""}



class LLMConfig(BaseFileSettings):
    model_config = SettingsConfigDict(yaml_file=PENTEST_ROOT / "model_config.yaml")

    api_key: str = ""
    secret_key: str = ""
    aws_region: str = ""
    llm_model: str = "openai"
    base_url: str = ""
    llm_model_name: str = ""
    embedding_models: str = "maidalun1020/bce-embedding-base_v1"
    embedding_type: str = "local"
    context_length: int = 120000
    embedding_url: str = ""
    rerank_model: str = "maidalun1020/bce-reranker-base_v1"
    temperature: float = 0.5
    history_len: int = 5
    timeout: int = 600
    proxies: Dict[str, str] = dataclasses.field(default_factory=dict)
    max_tokens: int = 10000


class ConfigsContainer:
    PENTEST_ROOT = PENTEST_ROOT

    basic_config: BasicConfig = settings_property(BasicConfig())
    llm_config: LLMConfig = settings_property(LLMConfig())
    db_config: DBConfig = settings_property(DBConfig())

    def create_all_templates(self):
        self.basic_config.create_template_file(write_file=True, file_format="yaml")
        self.llm_config.create_template_file(write_file=True, file_format="yaml")
        self.db_config.create_template_file(write_file=True, file_format="yaml")

    def set_auto_reload(self, flag: bool = True):
        self.basic_config.auto_reload = flag
        self.llm_config.auto_reload = flag
        self.db_config.auto_reload = flag


Configs = ConfigsContainer()
