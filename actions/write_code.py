
from pydantic import BaseModel, Field

from actions.execute_task import ExecuteTask
from prompts.prompt import DeepPentestPrompt
from server.chat.chat import _chat
from utils.log_common import build_logger

logger = build_logger()

class WriteCode(BaseModel):
    """Class quản lý việc tạo và thực thi mã code dựa trên mô tả nhiệm vụ.

    Class này kế thừa từ BaseModel của Pydantic và cung cấp chức năng
    để tạo mã code từ mô tả nhiệm vụ và thực thi mã đó.

    Attributes:
        next_task (str): Mô tả nhiệm vụ tiếp theo cần thực hiện
        action (str): Hành động cần thực hiện với mã code
    """

    next_task: str
    action: str

    def run(self):
        """Tạo và thực thi mã code dựa trên mô tả nhiệm vụ.

        Phương thức này sẽ:
        1. Ghi log nhiệm vụ tiếp theo
        2. Kiểm tra và xử lý preprocessing nếu cần
        3. Sử dụng LLM để tạo mã code từ mô tả nhiệm vụ
        4. Thực thi mã code được tạo ra

        Returns:
            Any: Kết quả từ việc thực thi mã code
        """
        logger.info(f"next_task: {self.next_task}")
        
        response, _ = _chat(query=DeepPentestPrompt.write_code.format(next_task=self.next_task))
        logger.info(f"LLM Response: {response}")

        code_executor = ExecuteTask(action=self.action, instruction=response, code=[])

        result = code_executor.run()
        return result