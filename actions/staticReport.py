import re
from typing import List, Dict

from pydantic import BaseModel

from config.config import Configs
from prompts.remediator_prompt import RemediatorPrompt
from prompts.prompt import DeepPentestPrompt

from db.models.plan_model import Plan
from db.models.task_model import TaskModel, Task
from server.chat.chat import _chat


class StatisticsReport(BaseModel):
    """Class quản lý việc tạo và cập nhật báo cáo remediation.

    Attributes:
        plan_chat_id (str): ID của cuộc trò chuyện liên quan đến báo cáo
    """
    plan_chat_id: str

    def run(self, Summary) -> str:
        """Tạo báo cáo remediation dựa trên mô tả ban đầu và kết quả khai thác.

        Args:
            init_description: Mô tả mục tiêu tổng thể
            result: Kết quả khai thác/vulnerability

        Returns:
            str: Báo cáo remediation ở định dạng markdown hoặc text
        """
        rsp = _chat(query=DeepPentestPrompt.static_Report.format(Summary=Summary),
            conversation_id=self.plan_chat_id,
            kb_name=Configs.kb_config.kb_name,

        )
        return rsp
