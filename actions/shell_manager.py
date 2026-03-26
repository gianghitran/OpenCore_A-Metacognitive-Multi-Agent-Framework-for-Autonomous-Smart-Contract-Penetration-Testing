import paramiko

from actions.remote_shell import RemoteShell
from config.config import Configs


class ShellManager:
    """Quản lý kết nối SSH và shell từ xa theo mô hình Singleton.

    Class này đảm bảo chỉ có một instance duy nhất được tạo ra và quản lý
    việc kết nối, đóng kết nối SSH cũng như shell từ xa.

    Attributes:
        _instance (ShellManager): Instance duy nhất của class
        _ssh_client (paramiko.SSHClient): Client SSH để kết nối tới máy chủ từ xa
        _shell (RemoteShell): Shell từ xa để thực thi lệnh
    """
    _instance = None
    _ssh_client = None
    _shell = None

    @classmethod
    def get_instance(cls):
        """Lấy instance duy nhất của ShellManager (Singleton pattern).

        Returns:
            ShellManager: Instance duy nhất của class ShellManager
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_shell(self) -> RemoteShell:
        """Lấy shell từ xa, tự động kết nối nếu chưa được thiết lập.

        Returns:
            RemoteShell: Đối tượng shell từ xa để thực thi lệnh
        """
        if self._shell is None:
            self._connect()
        return self._shell

    def _connect(self):
        """Thiết lập kết nối SSH và khởi tạo shell từ xa.

        Phương thức này sẽ:
        1. Tạo kết nối SSH mới nếu chưa tồn tại
        2. Cấu hình chính sách host key tự động
        3. Kết nối tới máy chủ từ xa sử dụng thông tin từ config
        4. Khởi tạo shell từ xa nếu chưa tồn tại
        """
        if self._ssh_client is None:
            self._ssh_client = paramiko.SSHClient()
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._ssh_client.connect(
                hostname=Configs.basic_config.kali['hostname'],
                username=Configs.basic_config.kali['username'],
                password=Configs.basic_config.kali['password'],
                port=Configs.basic_config.kali['port']
            )
        if self._shell is None:
            self._shell = RemoteShell(self._ssh_client.invoke_shell())

    def close(self):
        """Đóng kết nối shell và SSH client.

        Phương thức này sẽ:
        1. Đóng shell từ xa nếu đang tồn tại
        2. Đóng kết nối SSH client nếu đang tồn tại
        3. Xử lý các ngoại lệ có thể xảy ra khi đóng kết nối
        4. Reset các đối tượng về None
        """
        if self._shell:
            try:
                self._shell.shell.close()
            except:
                pass
            self._shell = None

        if self._ssh_client:
            try:
                self._ssh_client.close()
            except:
                pass
            self._ssh_client = None