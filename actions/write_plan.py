import json
import re
from typing import List, Dict

from pydantic import BaseModel

from config.config import Configs
from prompts.prompt import DeepPentestPrompt
from db.models.plan_model import Plan
from db.models.task_model import TaskModel, Task
from server.chat.chat import _chat


class WritePlan(BaseModel):
    """Class quản lý việc tạo và cập nhật kế hoạch thực thi.

    Class này kế thừa từ BaseModel của Pydantic và cung cấp các phương thức
    để tạo kế hoạch mới và cập nhật kế hoạch dựa trên kết quả thực thi.

    Attributes:
        plan_chat_id (str): ID của cuộc trò chuyện liên quan đến kế hoạch
    """
    plan_chat_id: str

    def run(self, init_description) -> str:
        """Tạo kế hoạch mới dựa trên mô tả ban đầu.

        Args:
            init_description: Mô tả ban đầu về kế hoạch cần tạo

        Returns:
            str: Chuỗi JSON chứa thông tin kế hoạch mới
        """
        # rsp = _chat(query=DeepPentestPrompt.write_plan.format(init_description=init_description), conversation_id=self.plan_chat_id, kb_name=Configs.kb_config.kb_name, kb_query=init_description)
        prompt_template = DeepPentestPrompt.write_plan
        formatted_query = prompt_template.replace("{init_description}", str(init_description))
        
        rsp = _chat(
            query=formatted_query, 
            conversation_id=self.plan_chat_id, 
            kb_name=Configs.kb_config.kb_name, 
            kb_query=init_description
        )
        match = re.search(r'<json>(.*?)</json>', rsp, re.DOTALL)
        if match:
            code = match.group(1)
            return code

    def update(self, task_result, success_task, fail_task, init_description) -> str:
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
            query=DeepPentestPrompt.update_plan.format(current_task=task_result.instruction,
                                                      init_description=init_description,
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


def parse_tasks(response: str, current_plan: Plan):
    """Phân tích chuỗi JSON phản hồi và tạo danh sách nhiệm vụ mới.

    Args:
        response (str): Chuỗi JSON chứa thông tin các nhiệm vụ
        current_plan (Plan): Đối tượng kế hoạch hiện tại

    Returns:
        Plan: Kế hoạch đã được cập nhật với danh sách nhiệm vụ mới
    """
    
    response = json.loads(response)
    if response is None : 
        raise ValueError("LLM response is None — likely due to API quota error.")

    tasks = import_tasks_from_json(current_plan.id, response)

    current_plan.tasks = tasks

    return current_plan

def preprocess_json_string(json_str):
    """Tiền xử lý chuỗi JSON để xử lý các ký tự escape không hợp lệ.

    Args:
        json_str: Chuỗi JSON cần xử lý

    Returns:
        str: Chuỗi JSON đã được xử lý
    """
    json_str = re.sub(r'\\([@!])', r'\\\\\1', json_str)

    return json_str

def merge_tasks(response: str, current_plan: Plan):
    """Kết hợp các nhiệm vụ mới với các nhiệm vụ đã hoàn thành.

    Args:
        response (str): Chuỗi JSON chứa thông tin các nhiệm vụ mới
        current_plan (Plan): Đối tượng kế hoạch hiện tại

    Returns:
        Plan: Kế hoạch đã được cập nhật với danh sách nhiệm vụ đã kết hợp
    """
    processed_response = preprocess_json_string(response)

    response = json.loads(processed_response)

    tasks = merge_tasks_from_json(current_plan.id, response, current_plan.tasks)

    current_plan.tasks = tasks

    return current_plan


def import_tasks_from_json(plan_id: str, tasks_json: List[Dict]) -> List[TaskModel]:
    """Tạo danh sách các đối tượng Task từ dữ liệu JSON.

    Args:
        plan_id (str): ID của kế hoạch
        tasks_json (List[Dict]): Danh sách các nhiệm vụ dạng JSON

    Returns:
        List[TaskModel]: Danh sách các đối tượng Task đã được tạo
    """
    tasks = []
    for idx, task_data in enumerate(tasks_json):
        task = Task(
            plan_id=plan_id,
            sequence=idx,
            action=task_data['action'],
            instruction=task_data['instruction'],
            dependencies=[i for i, t in enumerate(tasks_json)
                          if t['id'] in task_data['dependent_task_ids']]
        )

        tasks.append(task)
    return tasks


def merge_tasks_from_json(plan_id: str, new_tasks_json: List[Dict], old_tasks: List[Task]) -> List[Task]:
    """Kết hợp các nhiệm vụ mới với các nhiệm vụ đã hoàn thành thành công.

    Args:
        plan_id (str): ID của kế hoạch
        new_tasks_json (List[Dict]): Danh sách các nhiệm vụ mới dạng JSON
        old_tasks (List[Task]): Danh sách các nhiệm vụ cũ

    Returns:
        List[Task]: Danh sách các nhiệm vụ đã được kết hợp
    """
    completed_tasks_map = {
        task.instruction: task
        for task in old_tasks
        if task.is_finished and task.is_success
    }

    merged_tasks = []

    for instruction, completed_task in completed_tasks_map.items():
        found = False
        for task_data in new_tasks_json:
            if task_data['instruction'] == instruction:
                found = True
                break
        if not found:
            completed_task.sequence = len(merged_tasks)
            completed_task.dependencies = []
            merged_tasks.append(completed_task)

    new_task_id_to_idx = {
        task_data.get('id'): idx+len(merged_tasks)
        for idx, task_data in enumerate(new_tasks_json)
    }
    for idx, task_data in enumerate(new_tasks_json):
        instruction = task_data['instruction']
        sequence = len(merged_tasks)

        if instruction in completed_tasks_map:
            existing_task = completed_tasks_map[instruction]
            existing_task.sequence = sequence
            existing_task.dependencies = [
                new_task_id_to_idx[dep_id]
                for dep_id in task_data['dependent_task_ids']
                if dep_id in new_task_id_to_idx
            ]
            merged_tasks.append(existing_task)
        else:
            new_task = Task(
                plan_id=plan_id,
                sequence=sequence,
                action=task_data['action'],
                instruction=task_data['instruction'],
                dependencies=[
                    new_task_id_to_idx[dep_id]
                    for dep_id in task_data['dependent_task_ids']
                    if dep_id in new_task_id_to_idx
                ],
            )
            merged_tasks.append(new_task)

    return merged_tasks