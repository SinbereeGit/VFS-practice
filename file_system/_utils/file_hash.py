"""使用sha256算法对一个文件生成哈希值."""

# 标准库模块
import os
import hashlib

# 第三方库模块 (无)

# 自定义模块 (无)


class FileHashCalculator:
    """使用sha256算法对一个文件生成哈希值.
    
    ## 使用示例
    
    ```python
    # 打印文件的哈希值
    file_path = "test.txt"
    hash_value = FileHashCalculator.calculate_file_hash(file_path)
    print(hash_value)
    """
    @classmethod
    def calculate_file_hash(
        cls,
        file_path: str,
        hash_algorithm: str = 'sha256',
        chunk_size: int = 65536
    ) -> str:
        """使用指定算法计算文件的hash值.

        Args:
            file_path: 指定文件的路径.
            hash_algorithm: 指定计算hash的算法.
            chunk_size: 每次读取的块大小，默认 64KB.

        Returns:
            指定文件对应指定算法的哈希值的十六进制字符串表示.

        Raises:
            FileNotFoundError: 如果该路径不存在；
            IsADirectoryError: 如果该路径存在但不对应一个文件；
        """
        # 条件检查；
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"路径'{file_path}'不存在")
        if not os.path.isfile(file_path):
            raise IsADirectoryError(f"路径'{file_path}'存在但不对应一个文件")
        # 选择哈希算法；
        hash_func = hashlib.new(hash_algorithm)
        # 对文件计算hash值；
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                hash_func.update(chunk)
        # 返回哈希值的十六进制表示；
        return hash_func.hexdigest()
