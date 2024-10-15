"""该模块包含file_system需要的各种异常类；

    功能简述：
        ·
"""

__all__ = (
    "FileSystemError",
    "PathExists",
    "PathNotExists",
    "DirOfPathNotExists",
    "PathIsNotDir",
    "PathIsNotFile",
    "InvalidOperation",
    "InvalidCurrentDirOperation",
    "InvalidRootDirOperation",
    "InvalidNamingConvention",
    "InvalidCounterOperation",
    "CounterExists",
    "CounterNotExists",
    "FileIDNotFound",
    "InvalidPath",

)

# 导入模块
## 标准库模块
## 第三方库模块
## 自定义模块


class FileSystemError(Exception):
    """该文件系统中的异常的基类；"""

    __slots__ =  ('message',)

    def __init__(self, message: str):
        super().__init__()

        self.message: str = message.capitalize()

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.message}')"


class PathExists(FileSystemError):
    """当路径存在时抛出；"""

    __slots__ = ()


class PathNotExists(FileSystemError):
    """当路径不存在时抛出；

    Notes:
        * 该类也是路径不存在的基类；
    """

    __slots__ = ()


class DirOfPathNotExists(PathNotExists):
    """当路径所在的目录不存在时抛出；"""

    __slots__ = ()


class PathIsNotDir(FileSystemError):
    """当路径对应的不是目录时抛出；"""

    __slots__ = ()


class PathIsNotFile(FileSystemError):
    """当路径对应的不是文件时抛出；"""

    __slots__ = ()


class InvalidOperation(FileSystemError):
    """非法操作的基类；"""

    __slots__ = ()


class InvalidCurrentDirOperation(InvalidOperation):
    """当对当前工作目录进行非法操作时抛出；

    当前工作目录不能被直接移动、删除或覆盖，这属于非法操作；
    """

    __slots__ = ()


class InvalidRootDirOperation(InvalidOperation):
    """当对根目录“/”进行非法操作时抛出；

    一般来说，只允许对根目录的内容做操作，而不允许对根目录本身做操作；
    """

    __slots__ = ()


class InvalidNamingConvention(InvalidOperation):
    """当对结点的命名是空字符或者其中有‘/’的非法字符时抛出；"""

    __slots__ = ()


class InvalidCounterOperation(InvalidOperation):
    """对引用计数非法操作的基类；"""

    __slots__ = ()


class CounterExists(InvalidCounterOperation):
    """当尝试创建一个已经存在的标识时抛出"""

    __slots__ = ()


class CounterNotExists(InvalidCounterOperation):
    """当尝试对一个不存在的标识进行计数的增减操作时抛出；"""
    __slots__ = ()


class FileIDNotFound(FileSystemError):
    """当在一个需要文件的file_id但该文件没有时抛出；"""

    __slots__ = ()


class InvalidPath(FileSystemError):
    """当传入的路径不是一个合法路径时抛出；"""

    __slots__ = ()
