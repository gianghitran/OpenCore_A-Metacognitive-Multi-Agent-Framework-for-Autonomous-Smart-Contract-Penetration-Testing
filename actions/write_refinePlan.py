import json
import re
from typing import List, Dict

from pydantic import BaseModel

from config.config import Configs
from prompts.prompt import DeepPentestPrompt
from db.models.plan_model import Plan
from db.models.task_model import TaskModel, Task
from server.chat.chat import _chat


class WriteRefinePlan(BaseModel):
    """Class quản lý việc tạo và cập nhật kế hoạch thực thi.

    Class này kế thừa từ BaseModel của Pydantic và cung cấp các phương thức
    để tạo kế hoạch mới và cập nhật kế hoạch dựa trên kết quả thực thi.

    Attributes:
        plan_chat_id (str): ID của cuộc trò chuyện liên quan đến kế hoạch
    """
    plan_chat_id: str

    def run(self, vulnDetect_result, previous_result) -> str:
        """Tạo kế hoạch mới dựa trên mô tả ban đầu.

        Args:
            init_description: Mô tả ban đầu về kế hoạch cần tạo

        Returns:
            str: Chuỗi JSON chứa thông tin kế hoạch mới
        """
        rsp = _chat(query=DeepPentestPrompt.write_RefinePlan.format(previous_result=previous_result, vulnDetect_result=vulnDetect_result), conversation_id=self.plan_chat_id, kb_name=Configs.kb_config.kb_name, kb_query=init_description)

        match = re.search(r'<json>(.*?)</json>', rsp, re.DOTALL)
        if match:
            code = match.group(1)
            return code

    def update(self, task_result, success_task, fail_task, previous_result, vulnDetect_result) -> str:
        """Cập nhật kế hoạch dựa trên kết quả thực thi nhiệm vụ.

        Args:
            task_result: Kết quả của nhiệm vụ đã thực hiện
            success_task: Các nhiệm vụ đã thành công
            fail_task: Các nhiệm vụ thất bại
            init_description: Mô tả ban đầu của kế hoạch

        Returns:
            str: Chuỗi JSON chứa thông tin kế hoạch đã cập nhật
        """
        rsp = _chat(
            query=DeepPentestPrompt.update_RefinePlan.format(current_task=task_result.instruction,
                                                      previous_result=previous_result,
                                                      vulnDetect_result=vulnDetect_result,
                                                      current_code=task_result.code,
                                                      task_result=task_result.result,
                                                      success_task=success_task,
                                                      fail_task=fail_task),
            conversation_id=self.plan_chat_id,
            kb_name=Configs.kb_config.kb_name,
            kb_query=task_result.instruction
        )
        if rsp == "":
            return rsp

        match = re.search(r'<json>(.*?)</json>', rsp, re.DOTALL)
        if match:
            code = match.group(1)
            return code
        return "" # Sửa để khi mảng rỗng thì ko bug
