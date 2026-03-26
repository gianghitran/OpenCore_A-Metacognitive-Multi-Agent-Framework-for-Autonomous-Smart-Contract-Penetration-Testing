import re
from typing import List, Dict

from pydantic import BaseModel

from config.config import Configs
from prompts.remediator_prompt import RemediatorPrompt
from prompts.prompt import DeepPentestPrompt

from db.models.plan_model import Plan
from db.models.task_model import TaskModel, Task
from server.chat.chat import _chat


class WriteReport(BaseModel):
    """Class quản lý việc tạo và cập nhật báo cáo remediation.

    Attributes:
        plan_chat_id (str): ID của cuộc trò chuyện liên quan đến báo cáo
    """
    plan_chat_id: str

    def run(self, init_description, result) -> str:
        """Tạo báo cáo remediation dựa trên mô tả ban đầu và kết quả khai thác.

        Args:
            init_description: Mô tả mục tiêu tổng thể
            result: Kết quả khai thác/vulnerability

        Returns:
            str: Báo cáo remediation ở định dạng markdown hoặc text
        """
        summary = (f"**init_description**: {init_description}\n, **goal**: Generate a comprehensive vulnerability report and remediation plan.\n, **Result**: {result}\n"
                   f"------\n")
        prompt = RemediatorPrompt.init_plan_prompt.format(
            # init_description=init_description,
            # goal="Generate a comprehensive vulnerability report and remediation plan.",
            # Result=result
            summary=summary
        )
        # print("\n===== DEBUG: PROMPT SENT TO _chat =====\n")
        # print(prompt)
        # print("\n======================================\n")
        rsp = _chat(query=DeepPentestPrompt.write_report.format(summary=summary),
            conversation_id=self.plan_chat_id,
            kb_name=Configs.kb_config.kb_name,
            kb_query=init_description
        )
        # print("\n===== REMEDIATION REPORT =====\n")
        # print(rsp)
        # print("\n==============================\n")
        # Có thể không cần <json> nên chỉ trả về toàn bộ rsp
        return rsp

    def update(self, task_result, success_task, fail_task, init_description, result) -> str:
        """Cập nhật báo cáo remediation dựa trên kết quả mới.

        Args:
            task_result: Kết quả của nhiệm vụ đã thực hiện
            success_task: Các nhiệm vụ đã thành công
            fail_task: Các nhiệm vụ thất bại
            init_description: Mô tả ban đầu
            result: Kết quả khai thác/vulnerability

        Returns:
            str: Báo cáo remediation đã cập nhật
        """
        prompt = RemediatorPrompt.init_plan_prompt.format(
            init_description=init_description,
            goal="Update the vulnerability report and remediation plan based on new results.",
            Result=result
        )
        print("\n===== DEBUG: PROMPT SENT TO _chat (UPDATE) =====\n")
        print(prompt)
        print("\n===============================================\n")
        rsp = _chat(
            query=prompt,
            conversation_id=self.plan_chat_id,
            kb_name=Configs.kb_config.kb_name,
            kb_query=task_result.instruction
        )
        print("\n===== UPDATED REMEDIATION REPORT =====\n")
        print(rsp)
        print("\n======================================\n")
        return rsp