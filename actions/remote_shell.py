import re
import time
from typing import Optional
import paramiko


class SSHOutputHandler:
    """Class xử lý output từ kết nối SSH với khả năng phát hiện encoding và buffering nâng cao.
    
    Class này cung cấp các phương thức để xử lý dữ liệu output từ shell SSH,
    bao gồm việc giải mã dữ liệu với nhiều encoding khác nhau và quản lý buffer.
    
    Attributes:
        ENCODINGS (list): Danh sách các encoding được hỗ trợ
        BUFFER_SIZE (int): Kích thước buffer cho việc đọc dữ liệu
    """

    ENCODINGS = ['utf-8', 'latin-1', 'cp1252', 'ascii']
    BUFFER_SIZE = 8192

    @staticmethod
    def decode_output(data: bytes) -> str:
        """Giải mã dữ liệu bytes sử dụng nhiều encoding khác nhau.
        
        Args:
            data (bytes): Dữ liệu cần giải mã
            
        Returns:
            str: Chuỗi đã được giải mã thành công
        """
        for encoding in SSHOutputHandler.ENCODINGS:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode('utf-8', errors='replace')

    @staticmethod
    def receive_data(shell: paramiko.Channel, timeout: float) -> str:
        """Nhận dữ liệu từ shell với xử lý timeout nâng cao.
        
        Phương thức này liên tục nhận và xử lý dữ liệu từ shell cho đến khi:
        - Gặp prompt shell thông thường
        - Gặp prompt yêu cầu sudo
        - Gặp prompt yêu cầu xác nhận
        - Vượt quá số lần thử lại
        - Hết thời gian timeout
        
        Args:
            shell (paramiko.Channel): Kênh SSH để nhận dữ liệu
            timeout (float): Thời gian tối đa chờ đợi (giây)
            
        Returns:
            str: Dữ liệu đã nhận được từ shell
        """
        start_time = time.time()
        retries = 0
        out = ""

        while True:
            if shell.recv_ready():
                data = shell.recv(SSHOutputHandler.BUFFER_SIZE)
                decoded_data = SSHOutputHandler.decode_output(data)
                out += decoded_data

            lines = out.split('\n')
            lines = [x.strip() for x in lines if x.strip() != '']

            if len(lines) > 0:
                last_line = lines[-1].strip()

                if 'sudo' in last_line:
                    retries += 1

                if ('@' in last_line and (last_line[-1] == '$' or last_line[-1] == '#')) or \
                        ('bash' in last_line and (last_line[-1] == '$' or last_line[-1] == '#')):
                    break
                elif last_line[-1] in ['?', '$', '#'] or \
                        '--more--' in last_line.lower():
                    retries += 1
                elif last_line[-1] == ':' and '::' not in last_line and '-->' not in last_line:
                    retries += 1
                elif last_line[-1] == '>' and '<' not in last_line and '-->' not in last_line:
                    retries += 1
                elif any(pattern in last_line.lower() for pattern in ['[y/n]', '[Y/n/q]', 'yes/no/[fingerprint]', '(yes/no)']):
                    retries += 1
                elif 'What do you want to do about modified configuration file sshd_config?' in out:
                    break

                if retries >= 3:
                    break

            if time.time() - start_time > timeout:
                shell.send('\x03')
                break

            time.sleep(0.1)

        return out


class RemoteShell:
    """Class quản lý shell từ xa với khả năng phát hiện prompt và thực thi lệnh nâng cao.
    
    Class này cung cấp các chức năng để:
    - Thiết lập và cấu hình shell từ xa
    - Kiểm tra và thực thi các lệnh an toàn
    - Xử lý output từ các lệnh đặc biệt
    
    Attributes:
        FORBIDDEN_COMMANDS (set): Tập hợp các lệnh bị cấm
        shell (paramiko.Channel): Kênh SSH để giao tiếp
    """

    FORBIDDEN_COMMANDS = {'apt', 'apt-get''echo', }

    def __init__(self, shell: paramiko.Channel, timeout: float = 120.0):
        """Khởi tạo RemoteShell với shell và timeout được chỉ định.
        
        Args:
            shell (paramiko.Channel): Kênh SSH để giao tiếp
            timeout (float, optional): Thời gian timeout mặc định. Defaults to 120.0
        """
        self.shell = shell
        self._setup_shell(timeout)

    def _setup_shell(self, timeout: float) -> None:
        """Thiết lập cấu hình ban đầu cho shell.
        
        Cấu hình timeout, kết hợp stderr, và vô hiệu hóa các thông báo chào mừng.
        
        Args:
            timeout (float): Thời gian timeout cho shell
        """
        try:
            self.shell.settimeout(timeout)
            self.shell.set_combine_stderr(True)

            self.execute_cmd("touch ~/.hushlogin")

            motd_commands = [
                "sudo touch /etc/legal",
                "sudo chmod 644 /etc/legal",
                "sudo rm -f /etc/motd",
                "sudo rm -f /etc/update-motd.d/*"
            ]

            for cmd in motd_commands:
                self.execute_cmd(cmd)

        except Exception as e:
            print(f"Shell setup warning: {e}")

    def _check_forbidden_commands(self, cmd: str) -> Optional[str]:
        """Kiểm tra lệnh có nằm trong danh sách cấm không.
        
        Args:
            cmd (str): Lệnh cần kiểm tra
            
        Returns:
            Optional[str]: Thông báo lỗi nếu lệnh bị cấm, None nếu lệnh hợp lệ
        """
        cmd_parts = cmd.split()
        if any(cmd in self.FORBIDDEN_COMMANDS for cmd in cmd_parts):
            return "Command not allowed: network tunneling tools are restricted"
        return None

    def execute_cmd(self, cmd: str) -> str:
        """Thực thi lệnh với xử lý output và phục hồi lỗi nâng cao.
        
        Phương thức này:
        1. Kiểm tra lệnh có bị cấm không
        2. Gửi lệnh tới shell
        3. Xử lý việc thực thi thông thường
        4. Làm sạch output đặc biệt (dirb, msfconsole)
        
        Args:
            cmd (str): Lệnh cần thực thi
            
        Returns:
            str: Kết quả thực thi lệnh
        """
        if error_msg := self._check_forbidden_commands(cmd):
            return error_msg

        self.shell.send(cmd + '\n')

        output = self._handle_normal_execution()

        final_output = ''.join(output)

        ansi_cleaned_output = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', final_output)
        
        lines = ansi_cleaned_output.splitlines()
        
        if lines:
            prompt_pattern = re.compile(r"^\s*(\(.*\)\s*)?[\w\.-]+@[\w\.-]+:.*[#$]\s*$")
            if prompt_pattern.match(lines[-1].strip()):
                lines.pop()
        cleaned_output = '\n'.join(lines)

        if "dirb" in cmd and "gobuster" not in cmd:
            return clean_dirb_output(cleaned_output)

        elif "msfconsole" in cmd:
            return clean_msfconsole_output(cleaned_output)

        return cleaned_output

    def _handle_normal_execution(self) -> list:
        """Xử lý luồng thực thi lệnh thông thường.
        
        Phương thức này:
        1. Chờ một khoảng thời gian ngắn
        2. Nhận và xử lý dữ liệu từ shell
        3. Xử lý các prompt yêu cầu xác nhận
        
        Returns:
            list: Danh sách các phần output đã nhận được
        """
        output = []

        time.sleep(.5)
        data = SSHOutputHandler.receive_data(self.shell, timeout=120.0)
        if data != '':
            output.append(data)
        last_line = data.strip().split('\n')[-1]

        if any(pattern in last_line.lower() for pattern in
               ['[y/n]', '[Y/n/q]', 'yes/no/[fingerprint]', '(yes/no)']):
            self.shell.send("yes\n")
            time.sleep(.5)
            data = SSHOutputHandler.receive_data(self.shell, timeout=120.0)
            if data != '':
                output.append(data)

        return output


def clean_dirb_output(output: str) -> str:
    """Làm sạch output từ lệnh 'dirb'.
    
    Xử lý output bằng cách:
    1. Loại bỏ các chuỗi ANSI
    2. Trích xuất thông tin tóm tắt
    3. Trích xuất các URL được tìm thấy
    4. Trích xuất thống kê cuối cùng
    
    Args:
        output (str): Output gốc từ lệnh dirb
        
    Returns:
        str: Output đã được làm sạch và định dạng
    """
    output = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', output)

    summary_pattern = r"(URL_BASE:.*\n|WORDLIST_FILES:.*\n|GENERATED WORDS:.*\n|---- Scanning URL:.*\n)"
    summary = "\n".join(re.findall(summary_pattern, output))

    url_pattern = r"http[^\s]+ \(CODE:[0-9]+\|SIZE:[0-9]+\)"
    urls = "\n".join(re.findall(url_pattern, output))

    stats_pattern = r"DOWNLOADED: \d+ - FOUND: \d+"
    stats = "\n".join(re.findall(stats_pattern, output))

    cleaned_output = f"{summary}\n{urls}\n{stats}"

    return cleaned_output


