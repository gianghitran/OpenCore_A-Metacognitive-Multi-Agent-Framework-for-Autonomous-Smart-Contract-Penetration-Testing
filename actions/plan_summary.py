import uuid
from typing import List, Optional
from pydantic import BaseModel, Field

from db.repository.plan_repository import get_planner_by_id
from prompts.prompt import DeepPentestPrompt
from server.chat.chat import _chat
from utils.log_common import build_logger
from db.repository.sessionsummary_repository import save_session_summary
import traceback

logger = build_logger()


class PlannerSummary(BaseModel):
    """Class quản lý và tạo tóm tắt cho các kế hoạch đã thực hiện.
    
    Class này sử dụng danh sách các ID của planner để tạo ra bản tóm tắt
    về các task đã hoàn thành trong các phase trước đó.
    
    Attributes:
        history_planner_ids (List[str]): Danh sách các ID của planner cần tóm tắt
    """
    history_planner_ids: List[str] = Field(default_factory=list)
    id: str = Field(default_factory=lambda: uuid.uuid4().hex) 
    def get_summary(self, session_id: Optional[str] = None) -> str:
        """Tạo bản tóm tắt từ các planner đã thực hiện.
        
        Phương thức này sẽ:
        1. Kiểm tra nếu không có planner nào, trả về chuỗi rỗng
        2. Duyệt qua từng planner ID trong history
        3. Lấy thông tin của planner và các task đã hoàn thành
        4. Tạo bản tóm tắt bao gồm instruction, code và kết quả của mỗi task
        5. Sử dụng chat API để tạo bản tóm tắt cuối cùng
        
        Args:
            session_id: ID của session hiện tại để lưu summary vào database
        
        Returns:
            str: Bản tóm tắt được tạo ra từ chat API, hoặc chuỗi rỗng nếu không có planner
        """
        if len(self.history_planner_ids) == 0:
            return ""

        summary = "**Previous Phase**:\n"
        for index, planner_id in enumerate(self.history_planner_ids):
            plan = get_planner_by_id(planner_id)
            for task in plan.finished_tasks:
                summary += (f"**Instruction**: {task.instruction}\n, **Code**: {task.code}\n, **Result**: {task.result}\n"
                            f"------\n")

        response, _ = _chat(query=DeepPentestPrompt.write_summary.format(summary=str(summary)), summary=False)

        logger.info(f"summary: {response}")
        
        try:
            # Đảm bảo session_id không phải None và là ID thực của session
            if session_id and session_id.strip():
                logger.info(f"Saving summary for session_id: {session_id}")
                save_session_summary(session_id=session_id, summary=response)
            else:
                logger.warning("No valid session_id provided, skipping summary save")
            return response

        except Exception as e:
            logger.error(f"ERROR in save summary session: {e}")
            logger.error(traceback.format_exc())
            return response