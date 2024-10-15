"""使用sha256算法对一个文件生成哈希值；"""

# 导入模块
## 标准库模块
import os
import hashlib
## 第三方库模块
## 自定义模块


class FileHashCalculator:
    """
        功能简述：
            · 使用sha256算法对一个文件生成哈希值；
        功能列举：
            · 使用sha256算法对一个文件生成哈希值；
        使用说明：
            · 放在最前面：
                · 初始化的说明放在了__init__的文档字符串中（暂无）；
                · 暂无；
            · 警告：
                · 暂无；
            · 提示：
                · 暂无；
            · 使用示例：
                · 见这个模块的“主函数”；
        修改说明：
            · 对本类的任何修改都应该遵守本类的文档字符串中”设计说明“中的”内部一致处理“，否则可能会导致意想不到的错误；
        设计说明：
            · 内部一致处理：
                · 放在最前面：
                    · 暂无；
                · 暂无；
            · 为将来实现的准备：
                · 暂无；
            · 为高效实现的准备：
                · 暂无；
    """
    @classmethod
    def calculate_file_hash(cls, file_path: str, hash_algorithm: str = 'sha256', chunk_size: int = 65536) -> str:
        """使用指定算法计算文件的hash值；

        Args:
            file_path: 指定文件的路径；
            hash_algorithm: 指定计算hash的算法；
            chunk_size: 每次读取的块大小，默认 64KB；

        Returns:
            指定文件的hash值；

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


if __name__ == "__main__":
    """简单的对文件计算散列值的例子；"""

    # 注：如果要使用这个示例，请拷贝下面的代码，在外部的 python 文件中使用；

    file_path = "test.txt"
    hash_value = FileHashCalculator.calculate_file_hash(file_path)
    print(hash_value)
