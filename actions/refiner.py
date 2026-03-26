from typing import Optional

from pydantic import BaseModel

from actions.write_plan import WritePlan, parse_tasks, merge_tasks
from actions.write_refinePlan import WriteRefinePlan
from config.config import Configs
from db.models.task_model import TaskModel, Task
from prompts.prompt import DeepPentestPrompt
from db.models.plan_model import Plan
from server.chat.chat import _chat
from utils.log_common import build_logger

logger = build_logger()

from db.repository.sessionsummary_repository import get_session_summaries_by_session_id
from db.repository.foundryOutput_repository import get_nearest_foundry_output_by_id


class Refiner(BaseModel):
    """Class quản lý và thực thi refine.
    
    Class này chịu trách nhiệm tạo, cập nhật và theo dõi tiến trình của các kế hoạch pentest.
    
    Attributes:
        current_plan (Plan): Kế hoạch hiện tại đang được thực thi
        init_description (str): Mô tả ban đầu cho kế hoạch
        session_id (str): ID của session hiện tại
    """
    current_plan: Plan = None
    init_description: str = ""
    session_id: str = ""

    def refine(self) -> str:
        """Tạo hoặc tiếp tục kế hoạch hiện tại.
        
        Nếu đã có task hiện tại, lấy chi tiết task tiếp theo.
        Nếu chưa có task, tạo kế hoạch mới từ mô tả ban đầu.
        
        Returns:
            str: Chi tiết của task tiếp theo cần thực hiện
        """
        # Validate current_plan exists
        if not self.current_plan:
            logger.error("Refiner: current_plan is None, cannot proceed with refine")
            return None
            
        if self.current_plan.current_task:
            next_task = self.next_task_details()
            return next_task
            
        # Get session data for refine context
        if self.session_id:
            previous_result = get_nearest_foundry_output_by_id(self.session_id)
            vulnDetect_result = get_session_summaries_by_session_id(self.session_id)
        else:
            previous_result = []
            vulnDetect_result = []
            
        response = WriteRefinePlan(plan_chat_id=self.current_plan.plan_chat_id).run(vulnDetect_result, previous_result)

        logger.info(f"refine plan: {response}")

        if not response:
            return None

        self.current_plan = parse_tasks(response, self.current_plan)

        next_task = self.next_task_details()

        return next_task

    def update_refine(self, result: str) -> Optional[str]:
        """Cập nhật refine dựa trên kết quả thực thi task.

        Kiểm tra kết quả thực thi, cập nhật trạng thái task và kế hoạch tương ứng.
        Sau đó lấy thông tin task tiếp theo nếu có.
        
        Args:
            result (str): Kết quả thực thi của task hiện tại
            
        Returns:
            Optional[str]: Chi tiết của task tiếp theo, hoặc None nếu không có task nào
        """
        # Validate current_plan exists before proceeding
        if not self.current_plan:
            logger.error("Refiner: current_plan is None, cannot update refine")
            return None
            
        if not hasattr(self.current_plan, 'react_chat_id') or not self.current_plan.react_chat_id:
            logger.error("Refiner: current_plan.react_chat_id is None or missing")
            return None

        try:
            check_success = _chat(
                query=DeepPentestPrompt.check_success.format(result=result),
                conversation_id=self.current_plan.react_chat_id
            )

            logger.info(f"refine check_success: {check_success}")

            if "yes" in check_success.lower():
                task_result = self.update_task_status(self.current_plan.id, self.current_plan.current_task_sequence,
                                                      True, True, result)
            else:
                task_result = self.update_task_status(self.current_plan.id, self.current_plan.current_task_sequence,
                                                      True, False, result)

            # Get session data for update context
            if self.session_id:
                previous_result = get_nearest_foundry_output_by_id(self.session_id)
                vulnDetect_result = get_session_summaries_by_session_id(self.session_id)
            else:
                previous_result = []
                vulnDetect_result = []
                
            # Update refine plan
            updated_response = (WriteRefinePlan(plan_chat_id=self.current_plan.plan_chat_id)
                                .update(task_result,
                                        self.current_plan.finished_success_tasks,
                                        self.current_plan.finished_fail_tasks,
                                        previous_result,
                                        vulnDetect_result))

            logger.info(f"updated_refine_plan: {updated_response}")

            if updated_response == "" or updated_response is None:
                return None

            merge_tasks(updated_response, self.current_plan)

            next_task = self.next_task_details()

            return next_task
            
        except Exception as e:
            logger.error(f"Error in update_refine: {e}")
            return None

    def next_task_details(self) -> Optional[str]:
        """Lấy chi tiết của task tiếp theo cần thực hiện.
        
        Kiểm tra và cập nhật sequence của task hiện tại,
        sau đó lấy chi tiết thực hiện thông qua chat API.
        
        Returns:
            Optional[str]: Chi tiết của task tiếp theo, hoặc None nếu không có task
        """
        # Validate current_plan and current_task exist
        if not self.current_plan:
            logger.error("Refiner: current_plan is None in next_task_details")
            return None
            
        logger.info(f"refiner current_task: {self.current_plan.current_task}")
        if self.current_plan.current_task is None:
            return None

        if not hasattr(self.current_plan, 'react_chat_id') or not self.current_plan.react_chat_id:
            logger.error("Refiner: current_plan.react_chat_id is None in next_task_details")
            return None

        try:
            self.current_plan.current_task_sequence = self.current_plan.current_task.sequence
            next_task = _chat(
                query=DeepPentestPrompt.next_task_details.format(todo_task=self.current_plan.current_task.instruction),
                conversation_id=self.current_plan.react_chat_id,
                kb_name=Configs.kb_config.kb_name,
                kb_query=self.current_plan.current_task.instruction
            )
            return next_task
        except Exception as e:
            logger.error(f"Error in next_task_details: {e}")
            return None

    def update_task_status(self, plan_id: str, task_sequence: int,
                           is_finished: bool, is_success: bool, result: Optional[str] = None) -> Task:
        """Cập nhật trạng thái của một task cụ thể.
        
        Args:
            plan_id (str): ID của kế hoạch chứa task
            task_sequence (int): Số thứ tự của task trong kế hoạch
            is_finished (bool): Trạng thái hoàn thành của task
            is_success (bool): Trạng thái thành công của task
            result (Optional[str]): Kết quả thực thi của task
            
        Returns:
            Task: Task đã được cập nhật trạng thái
        """
        if not self.current_plan or not self.current_plan.tasks:
            logger.error("Refiner: current_plan or tasks is None in update_task_status")
            return None
            
        task = next((
            task for task in self.current_plan.tasks
            if task.plan_id == plan_id and task.sequence == task_sequence
        ), None)

        if task:
            task.is_finished = is_finished
            task.is_success = is_success
            if result:
                task.result = result
            logger.info(f"Updated task {task_sequence}: finished={is_finished}, success={is_success}")
        else:
            logger.warning(f"Task not found: plan_id={plan_id}, sequence={task_sequence}")

        return task