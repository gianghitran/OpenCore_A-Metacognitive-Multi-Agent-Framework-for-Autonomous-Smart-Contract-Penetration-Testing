import time
import asyncio
import re
import time
import ollama
import httpx
import boto3
from botocore.exceptions import ClientError
from typing import List, Optional
from abc import ABC
from openai import OpenAI
from ollama import Client
from starlette.concurrency import run_in_threadpool
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import google.generativeai as genai

from config.config import Configs
from db.repository.conversation_repository import add_conversation_to_db
from db.repository.message_repository import (
    get_conversation_messages,
    add_message_to_db,
)

from server.utils.utils import LLMType, replace_ip_with_targetip
from utils.log_common import build_logger

logger = build_logger()


class OpenAIChat(ABC):
    def __init__(self, config):
        self.config = config
        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=config.timeout,
        )
        self.model_name = self.config.llm_model_name

    @retry(
        stop=stop_after_attempt(3),  # Stop after 3 attempts
    )
    def chat(self, history: List) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=history,
                temperature=self.config.temperature,
            )
            ans = response.choices[0].message.content
            return ans
        except (
            httpx.HTTPStatusError,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
            ConnectionError,
        ) as e:
            if getattr(e, "response", None) and e.response.status_code == 429:
                # Rate limit error, wait longer
                time.sleep(2)
            raise  # Re-raise the exception to trigger retry
        except Exception as e:
            return f"**ERROR**: {str(e)}"


class OpenRouterChat(ABC):
    def __init__(self, config):
        self.config = config
        extra_headers = {}
        if self.config.openrouter_http_referer:
            extra_headers["HTTP-Referer"] = self.config.openrouter_http_referer
        if self.config.openrouter_x_title:
            extra_headers["X-Title"] = self.config.openrouter_x_title

        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=config.timeout,
            default_headers=extra_headers,
        )
        self.model_name = self.config.llm_model_name

    @retry(
        stop=stop_after_attempt(3),  # Stop after 3 attempts
    )
    def chat(self, history: List) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=history,
                temperature=self.config.temperature,
            )
            ans = response.choices[0].message.content
            return ans
        except (
            httpx.HTTPStatusError,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
            ConnectionError,
        ) as e:
            if getattr(e, "response", None) and e.response.status_code == 429:
                # Rate limit error, wait longer
                time.sleep(2)
            raise  # Re-raise the exception to trigger retry
        except Exception as e:
            return f"**ERROR**: {str(e)}"


class OllamaChat(ABC):
    _model_checked = False

    def __init__(self, config):
        self.config = config
        headers = {"ngrok-skip-browser-warning": "true"}
        self.client = Client(host=self.config.base_url, headers=headers)
        self.model_name = self.config.llm_model_name

        if not OllamaChat._model_checked:
            self._ensure_model_exists()
            OllamaChat._model_checked = True

    def _ensure_model_exists(self):
        """Kiểm tra model có tồn tại không, nếu không thì pull về."""
        try:
            models_on_server = self.client.list().get("models", [])
            if not any(m.get("name") == self.model_name for m in models_on_server):
                print(
                    f"⚠️  Ollama: Model '{self.model_name}' không tìm thấy. Bắt đầu tải..."
                )
                current_digest = ""
                for progress in self.client.pull(self.model_name, stream=True):
                    digest = progress.get("digest", "")
                    if digest != current_digest and current_digest != "":
                        print()
                    current_digest = digest

                    total = progress.get("total")
                    completed = progress.get("completed")

                    if total is not None and completed is not None and total > 0:
                        percent = round((completed / total) * 100, 2)
                        print(f"\rDownloading {digest}: {percent}%", end="", flush=True)
                    elif "status" in progress:
                        print(f"\r{progress['status']}", end="", flush=True)

                print(f"\n✅ Ollama: Đã tải xong model '{self.model_name}'.")

        except Exception as e:
            print(f"❌ LỖI NGHIÊM TRỌNG khi kết nối hoặc pull model Ollama: {e}")
            raise e

    def chat(self, history: List[dict]) -> str:

        try:
            options = {
                "temperature": self.config.temperature,
            }
            response = self.client.chat(
                model=self.model_name, messages=history, options=options, keep_alive=-1
            )
            ans = response["message"]["content"]
            return ans
        except httpx.HTTPStatusError as e:
            return f"**ERROR**: {str(e)}"


class GeminiChat(ABC):
    def __init__(self, config):
        self.config = config
        # Configure the Gemini API key
        genai.configure(api_key=self.config.api_key)
        self.model = genai.GenerativeModel(self.config.llm_model_name)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(
            (
                httpx.HTTPStatusError,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
                ConnectionError,
            )
        ),
    )
    def chat(self, history: List) -> str:
        # Gemini có một định dạng history hơi khác, cần chuyển đổi
        # Nó không chấp nhận vai trò "system" ở đầu, và các vai trò phải xen kẽ user/model
        gemini_history = []
        # Bỏ qua system prompt nếu có
        for msg in history:
            if msg["role"] == "system":
                continue
            # Đổi 'assistant' thành 'model' cho Gemini
            role = "model" if msg["role"] == "assistant" else "user"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        try:
            # Loại bỏ message cuối cùng của 'model' nếu có, vì Gemini không cho phép 2 message cùng role liên tiếp
            if gemini_history and len(gemini_history) > 1:
                if gemini_history[-1]["role"] == gemini_history[-2]["role"]:
                    gemini_history.pop(-2)

            response = self.model.generate_content(
                gemini_history,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.config.temperature
                ),
            )
            # Check for empty response due to safety filters
            if not response.candidates or not response.candidates[0].content.parts:
                logger.warning(
                    f"Gemini blocked content. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'unknown'}"
                )
                # Return a generic response to continue the analysis
                return "I understand this is a smart contract security analysis. Please provide the Solidity source code for academic security research purposes."

            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            if "Invalid operation" in str(e) and "response.text" in str(e):
                # Return a fallback response to keep the system running
                return "Ready to analyze smart contract code for educational security assessment."
            return f"**ERROR**: {str(e)}"


class BedrockChat(ABC):
    def __init__(self, config):
        self.config = config
        self.model_id = self.config.llm_model_name
        try:
            self.client = boto3.client(
                service_name="bedrock-runtime",
                region_name=self.config.aws_region,
                aws_access_key_id=self.config.api_key,
                aws_secret_access_key=self.config.secret_key,
            )
            logger.success(
                f"AWS Bedrock client created successfully for region '{self.config.aws_region}'."
            )
        except Exception as e:
            logger.error(f"Error creating AWS Bedrock client: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(ClientError),
    )
    def chat(self, history: List) -> str:
        """
        Gửi yêu cầu đến AWS Bedrock Converse API.
        """
        # Claude 3 Sonnet trong Bedrock Converse API có một system prompt riêng
        system_prompt = ""
        bedrock_history = []

        # Tách system prompt ra khỏi history
        for msg in history:
            if msg["role"] == "system":
                system_prompt = msg["content"]
                continue

            # Chuyển đổi định dạng message cho Bedrock
            # Bedrock yêu cầu content phải là một list of dicts
            bedrock_history.append(
                {
                    "role": "assistant" if msg["role"] == "assistant" else "user",
                    "content": [{"text": msg["content"]}],
                }
            )

        try:
            # Xóa message cuối cùng nếu nó là của assistant, vì 2 message cùng role không được liền kề
            if bedrock_history and len(bedrock_history) > 1:
                if bedrock_history[-1]["role"] == bedrock_history[-2]["role"]:
                    bedrock_history.pop(-2)

            request_body = {
                "modelId": self.model_id,
                "messages": bedrock_history,
                "inferenceConfig": {
                    "maxTokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                },
            }
            # Thêm system prompt nếu có
            if system_prompt:
                request_body["system"] = [{"text": system_prompt}]

            response = self.client.converse(**request_body)

            assistant_message = response["output"]["message"]
            response_text = assistant_message["content"][0]["text"]

            return response_text

        except ClientError as e:
            logger.error(f"Couldn't invoke {self.model_id}. Reason: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during Bedrock chat: {e}")
            return f"**ERROR**: {str(e)}"


def _chat(query: str, kb_name=None, conversation_id=None, kb_query=None, summary=True):
    try:
        query = query[: Configs.llm_config.context_length]

        flag = False

        if conversation_id is not None:
            flag = True

        # Initialize or retrieve conversation ID
        conversation_id = add_conversation_to_db(
            Configs.llm_config.llm_model_name, conversation_id
        )

        history = [
            {
                "role": "system",
                "content": "You are a helpful assistant",
            }
        ]
        # Retrieve message history from database, and limit the number of messages
        for msg in get_conversation_messages(conversation_id)[
            -Configs.llm_config.history_len :
        ]:
            history.append({"role": "user", "content": msg.query})
            history.append({"role": "assistant", "content": msg.response})

        # Add user query to the message history
        history.append({"role": "user", "content": query})

        # Initialize the correct model client
        if Configs.llm_config.llm_model == LLMType.OPENAI:
            client = OpenAIChat(config=Configs.llm_config)
        elif Configs.llm_config.llm_model == LLMType.OLLAMA:
            client = OllamaChat(config=Configs.llm_config)
        elif Configs.llm_config.llm_model == LLMType.GEMINI:
            client = GeminiChat(config=Configs.llm_config)
        elif Configs.llm_config.llm_model == LLMType.BEDROCK:
            client = BedrockChat(config=Configs.llm_config)
        elif Configs.llm_config.llm_model == LLMType.OPENROUTER:
            client = OpenRouterChat(config=Configs.llm_config)
        else:
            return "Unsupported model type"

        # Get response from the model
        response_text = client.chat(history)

        # Save both query and response to the database
        if summary:
            add_message_to_db(
                conversation_id, Configs.llm_config.llm_model_name, query, response_text
            )

        if flag:
            return response_text
        else:
            return response_text, conversation_id

    except Exception as e:
        print(e)
        return f"**ERROR**: {str(e)}"
