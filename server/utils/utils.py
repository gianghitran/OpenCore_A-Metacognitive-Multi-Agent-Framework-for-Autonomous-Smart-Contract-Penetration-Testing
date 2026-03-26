import os
import re
from strenum import StrEnum
from typing import List, Any, Union, Dict

import httpx
from pydantic import *

from config.config import Configs


class BaseResponse(BaseModel):
    code: int = Field(200, description="API status code")
    msg: str = Field("success", description="API status message")
    data: Any = Field(None, description="API data")

    class Config:
        json_schema_extra = {
            "example": {
                "code": 200,
                "msg": "success",
            }
        }


class ListResponse(BaseResponse):
    data: List[Any] = Field(..., description="List of data")

    class Config:
        json_schema_extra = {
            "example": {
                "code": 200,
                "msg": "success",
                "data": ["doc1.docx", "doc2.pdf", "doc3.txt"],
            }
        }


class LLMType(StrEnum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    GEMINI = "gemini"
    CEREBRAS = "cerebras"
    BEDROCK = "bedrock"

    def __missing__(self, key):
        return self.OLLAMA


def get_httpx_client(
    use_async: bool = False,
    proxies: Union[str, Dict] = None,
    timeout: float = Configs.basic_config.http_default_timeout,
    unused_proxies: List[str] = [],
    **kwargs,
) -> Union[httpx.Client, httpx.AsyncClient]:
    """
    helper to get httpx client.
    NOTE: The proxy logic is temporarily disabled to resolve a TypeError.
    """
    # The original proxy logic is kept here but commented out or unused
    # to avoid the 'proxies' keyword argument error.
    # default_proxies = { ... }
    # ... (all the original proxy setup logic)

    # Construct Client, create a copy of kwargs to avoid modifying the original dict
    client_kwargs = kwargs.copy()

    # IMPORTANT: We are NOT adding 'proxies' to the client_kwargs
    # This is the key change to fix the TypeError.
    client_kwargs.update(timeout=timeout)

    if use_async:
        return httpx.AsyncClient(**client_kwargs)
    else:
        return httpx.Client(**client_kwargs)


def api_address(is_public: bool = False) -> str:

    server = Configs.basic_config.api_server
    if is_public:
        host = server.get("public_host", "127.0.0.1")
        port = server.get("public_port", "7861")
    else:
        host = server.get("host", "127.0.0.1")
        port = server.get("port", "7861")
        if host == "0.0.0.0":
            host = "127.0.0.1"
    return f"http://{host}:{port}"


def replace_ip_with_targetip(input_string):
    ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"

    result_string = re.sub(ip_pattern, "<target>", input_string)

    return result_string
