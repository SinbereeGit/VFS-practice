"""该模块提供了由 (特殊的文件集目录, 指定用户ID) 唯一确定的支持 *串行多用户*, *去重存储* 的虚拟文件系统.
    Warning:
        - 最好使用 `with` 来使用该类的对象.
        - 这里如果引发异常, (虽然没有看到过, 但是)可能会出现 *用户集* 和 *引用计数* 以及 *实体文件集* 的不一致 (还没有仔细考虑).
"""

# 标准库模块
from typing import Union
import os
import shutil

# 第三方库模块 (无)

# 自定义模块
from ._dir_tree_handler import DirTreeHandler
from ._utils.count_manager import CountManager
from ._utils.file_hash import FileHashCalculator
from .errors import (
    InvalidPath,
    PathNotExists,
    PathIsNotFile,
    PathIsNotDir,
    InvalidOperation,
    InvalidCurrentDirOperation,
    DirOfPathNotExists,
    PathExists
)

# 用于设置的全局变量
ENTITY_FILES_DIR_NAME = "EntityFiles"  # 设置存放实体文件的目录名.
USERS_DIR_NAME = "Users"  # 设置用户空间的目录名.
USER_JSON_FILE_NAME = "dirTreeHandler.json"  # 设置用于构建目录树的json文件 (就是所谓的'特殊文件') 的名字.


# 主类
class VirtualFileSystem:
    """该类提供一个支持 *串行多用户*, *去重存储* 的虚拟文件系统.

    ## 使用示例
    
    用法:

    ```python
    with VirtualFileSystem("root_dir", "user_id") as vfs:
        # 打印当前目录的内容
        vfs.get_dir_content("")
        # 进入某个目录
        vfs.chdir("dir_name")
        # 做一些其他的事儿...
    ```

    和用法:

    ```python
    try:
        vfs = VirtualFileSystem("root_dir", "user_id")
        # 打印当前目录的内容
        vfs.get_dir_content("")
        # 进入某个目录
        vfs.chdir("dir_name")
        # 做一些其他的事儿...
    except Exception as e:  # 当然, 实际使用的时候肯定不要这么宽泛的捕获异常.
        # 处理异常
    finally:
        vfs.store_change()
    ```

    是等价的.

    ## Warnings:
        - 根目录的所有内容都必须是由本模块 (操作) 生成的.
        - 对于同一个 *根目录* 同一时刻只能有 **一个** 系统实例运行 (因为我们 **不支持并发** !!!) .
        - 在调用了 `store_change` 之后, 请 **不要** 再使用这个实例, 因为它的资源已经被释放了.
        - 对于内部路径名, 现在还没有很好地命名限制, 甚至还支持 ` ` 作为路径名...

    ## Notes:
        - 放在最前面:
            - 初始化的说明放在了 `__init__` 的文档字符串中.
            - 如果不是通过 `with` 来使用, 请通过 `try` 来使用, 并在 `finally` 中调用 `self.store_change`.
            - **不支持** 并行.
            - 支持 *Unix/Linux*, *Windows* (原则上应该也支持 *MacOS*).
        - 初始化该系统需要指定 **根目录** 和 **用户标识**.
        - 内部的文件路径采用 `Unix 形式`, 外部的文件路径则是操作系统相关的.
        - 文件操作是 **非覆盖式** 的, 这意味着如果目标路径的文件存在会抛出异常.
        - 所有的文件操作, 默认 **最后一项** 是目标文件名.
        - 系统的目录结构如下:
          根目录
          ├── 引用计数文件
          ├── 实体文件目录
          │   ├── 散列文件1
          │   ├── 散列文件2
          |   └── ...
          └── 用户空间目录
              ├── 用户目录1
              │   └── 用户目录树文件
              ├── 用户目录2
              |   └── 用户目录树文件
              └── ...
    """
    def __init__(
        self,
        root_dir: str,
        user_id: str,
        json_indent_zero: bool = True,
        json_sep_close: bool = True
    ):
        """一些初始化的操作.

        指定系统使用的实体文件集目录和以什么身份使用这个系统.

        Warnings:
            * 在最初使用的时候使用一个空目录, 对系统文件集目录的任何操作必须都是通过本模块完成的, 否则可能导致意想不到的错误.
            * 这里没有检查用户名的合法性, 应当输入合乎文件名规范的用户名, 否则可能导致意想不到的问题.

        Args:
            root_dir: 指定根目录, 如果不存在会创建.
            user_id: 指定使用的用户ID, 如果不存在会创建.
            json_indent_zero: 设置保存的json文件的indent, True表示紧凑, False表示indent为4.
            json_sep_close: 设置保存的json文件的分隔符的紧凑程度, True表示紧凑, False表示有一个空格.
        Raises:

        """
        self._root_dir = root_dir
        self._entity_files_dir = os.path.join(root_dir, ENTITY_FILES_DIR_NAME)
        self._user_id = user_id
        self._user_path = os.path.join(root_dir, USERS_DIR_NAME, user_id)
        # 如果没有则创建'根目录'、'实体文件集目录'、'用户空间目录'、'用户目录'
        if not os.path.exists(root_dir):
            os.mkdir(root_dir)
        if not os.path.exists(self._entity_files_dir):
            os.mkdir(self._entity_files_dir)
        users_dir = os.path.join(root_dir, USERS_DIR_NAME)
        if not os.path.exists(users_dir):
            os.mkdir(users_dir)
        if not os.path.exists(self._user_path):
            os.mkdir(self._user_path)
        self._dir_tree_handler = DirTreeHandler(os.path.join(self._user_path, USER_JSON_FILE_NAME),
                                                json_indent_zero=json_indent_zero,
                                                json_sep_close=json_sep_close)
        self._file_quote_count_manager = CountManager(root_dir)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """在退出前将对目录树的操作、引用计数操作保存.

        Notes:
            * 这里有一个很有意思的地方, 即使忘了保存, 也没什么用户集看到的引用计数和实际的引用计数不一致的问题。
              唯一的问题似乎只是, 引用计数不为0的文件可能已经被删除了, 引用计数为0的文件可能还在 (我们看到这是非常开心的！) .
        """
        self.store_change()

    @staticmethod
    def __check_inner_path_validity(path: str) -> None:
        """判断一个内部路径是不是合法的.

        Notes:
            * 这里简单设置成不允许有相邻的 ‘/’ (这样就不至于有中间结点为 '', 即空字符串) .

        Raises:
            InvalidPath: 如果路径是非法的.
        """
        is_valid = True

        # 规范检查.
        if "//" in path:
            is_valid = False

        if not is_valid:
            raise InvalidPath(f"路径'{path}'是非法的")

    @staticmethod
    def __convert_inner_path_to_list_path(path: str) -> list:
        """'内部路径'转换成'列表路径'.

        Raises:
            InvalidPath: 如果内部路径是非法的.
        """
        # 条件检查.
        VirtualFileSystem.__check_inner_path_validity(path)  # 检查内部条件是否合法.

        if not path:  # 对当前路径的处理.
            return []
        if path == "/":  # 对根路径的处理.
            return ['/']
        # 绝对路径和相对路径的处理.
        if path.startswith('/'):
            result = ['/'] + path.strip('/').split('/')  # 注:''.split('/')的结果是[''], 不过在这里并不会发生 (当然, 是在满足了Warnings的要求后) .
        else:
            result = path.strip('/').split('/')
        return result

    @staticmethod
    def __convert_list_path_to_inner_path(path: list) -> str:
        """将'列表路径'转化成'内部路径'.

        Warnings:
            * 该路径要求满足'列表路径'的条件, 否则可能导致错误.
        """
        if not path:  # 如果是当前路径直接返回 ''
            return ''
        if path[0] == '/':  # 绝对路径
            return '/' + '/'.join(path[1:])
        else:  # 相对路径
            return '/'.join(path)

    # --这个方法应该没什么问题.
    @staticmethod
    def __join_two_inner_paths(path1: str, path2: str) -> str:
        """将两个'内部路径'合并.

        Warnings:
            * 这两个路径都必须满足'内部路径'的条件.
            * 后一个路径必须是相对路径 (一个结点名字当然也是相对路径) .

        Args:
            path1: 一个'内部路径'.
            path2: 一个是相对路径的'内部路径'.

        Returns:
            两个路径以'/'连接的结果.
        """
        if not path1:  # 对当前路径的处理.
            return path2
        if path1[-1] == '/':  # 其中包含了对根路径的处理.
            return path1 + path2
        else:
            return path1 + '/' + path2

    @staticmethod
    def __is_outer_path_contained(container_outer_path: str, contained_outer_path: str) -> bool:
        """检查外部路径 contained_outer_path 是否包含在外部路径 container_outer_path 中.

        Args:
            container_outer_path: 容器外部路径.
            contained_outer_path: 被包含的外部路径.

        Returns:
            如果 contained_outer_path 包含在 container_outer_path 中, 返回 True, 否则返回 False.
        """
        # 将路径转换为绝对路径
        container_outer_path = os.path.abspath(container_outer_path)
        contained_outer_path = os.path.abspath(contained_outer_path)
        # 获取相对路径
        rel_path = os.path.relpath(contained_outer_path, container_outer_path)
        # 如果相对路径不以 '..' 开头, 则 contained_path 包含在 container_path 中
        return not rel_path.startswith('..') and not os.path.isabs(rel_path)

    def __copy_file_from_outside(self, outer_path: str, inner_path: list) -> None:
        """向指定路径以复制的方式添加一个外部文件 (包含文件名)  (非覆盖式) .

        Warnings:
            * 这里只支持处理普通文件.

        Notes:
            * 如果内部路径存在, 则抛出异常.

        Args:
            outer_path: 外部路径.
            inner_path: 列表路径.

        Raises:
            FileNotFoundError: 如果外部路径不存在.
            IsADirectoryError: 如果外部路径存在但不对应一个文件 (而是一个目录) .
            InvalidOperation: 如果外部路径包含根路径.
            InvalidCurrentDirOperation: 如果列表路径是当前路径.
            DirOfPathNotExists: 如果列表路径所在的目录不存在.
            PathExists: 如果内部路径已经存在.
            其他由外部文件操作引发的异常也可能发生.
        """
        def copy_file_from_outside_help(src_file_path: str) -> None:
            """复制外部指定文件到实体文件集目录 (目标文件名是hash_value) .

            Warnings:
                -目标文件名必须是不存在的, 否则在Windows中会导致异常.

            Args:
                src_file_path: 外部的源文件路径名, 对应的必须是一个文件.

            Raises:
                其他由外部文件操作引发的异常也可能发生.
            """
            tmp_dir = self._entity_files_dir
            shutil.copy(src_file_path, tmp_dir)
            os.rename(os.path.join(tmp_dir, os.path.basename(src_file_path)),
                      os.path.join(self._entity_files_dir, file_id))

        # 条件检查.
        if not os.path.exists(outer_path):
            raise FileNotFoundError(f"外部路径'{outer_path}'不存在")
        if not os.path.isfile(outer_path):
            raise IsADirectoryError(f"外部路径'{outer_path}'存在但不对应一个文件")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation("不允许外部路径包含根路径")
        if not inner_path:
            raise InvalidCurrentDirOperation("该列表路径不能是当前路径")
        if not self._dir_tree_handler.is_path_exists(inner_path[:-1]):
            raise DirOfPathNotExists(f"列表路径'{inner_path}'所在的目录不存在")
        if self._dir_tree_handler.is_path_exists(inner_path):  # 如果目标路径是存在的.
            raise PathExists(f"路径'{inner_path}'已经存在, 不能覆盖它")

        # 计算该文件的散列值.
        file_id = FileHashCalculator.calculate_file_hash(outer_path)
        # 检查该文件的散列值是否已经有了.
        if self.is_file_exist_via_file_id(file_id):  # 如果有, 则增加引用.
            self._file_quote_count_manager.add_quote_count_for_id(file_id)
        else:  # 如果没有, 则复制该文件到实体文件集目录并创建引用.
            copy_file_from_outside_help(outer_path)
            self._file_quote_count_manager.create_quote_count_for_id(file_id)
        # 增加该文件并填上file_id.
        self._dir_tree_handler.create_file(inner_path)
        self._dir_tree_handler.set_file_hash(inner_path, file_id)

    def __copy_dir_from_outside(self, outer_path: str, inner_path: list) -> None:
        """向指定路径以复制的方式添加一个外部目录 (包含目录名)  (非覆盖式) .

        Warnings:
            * 现在只能处理目录和普通文件, 不能处理别的比如链接之类的东西, 现在的做法是略过它们.

        Notes:
            * 如果内部路径存在, 则抛出异常.

        Args:
            outer_path: 外部路径.
            inner_path: 列表路径.

        Raises:
            FileNotFoundError: 如果外部路径不存在.
            NotADirectoryError: 如果外部路径存在但不对应一个目录.
            InvalidOperation: 如果外部路径包含根路径.
            InvalidCurrentDirOperation: 如果列表路径是当前路径.
            DirOfPathNotExists: 如果列表路径所在的目录不存在.
            PathExists: 如果内部路径已经存在.
            其他由外部文件操作引发的异常也可能发生.
        """
        # 条件检查.
        if not os.path.exists(outer_path):
            raise FileNotFoundError(f"外部路径'{outer_path}'不存在")
        if not os.path.isdir(outer_path):
            raise NotADirectoryError(f"外部路径'{outer_path}'存在但不对应一个目录")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation("不允许外部路径包含根路径")
        if not inner_path:
            raise InvalidCurrentDirOperation("该列表路径不能是当前路径")
        if not self._dir_tree_handler.is_path_exists(inner_path[:-1]):
            raise DirOfPathNotExists(f"列表路径'{inner_path}'所在的目录不存在")
        if self._dir_tree_handler.is_path_exists(inner_path):  # 如果目标路径是存在的.
            raise PathExists(f"路径'{inner_path}'已经存在, 不能覆盖它")

        # 创建一个目录结点.
        self._dir_tree_handler.mkdir(inner_path)
        # 遍历目录中的内容.
        for entry in os.listdir(outer_path):  # 对于既不是目录也不是普通文件的东西, 这里直接忽略.
            full_path = os.path.join(outer_path, entry)
            if os.path.isdir(full_path):  # 如果是一个目录, 递归调用自己.
                self.__copy_dir_from_outside(full_path, inner_path + [entry])
            elif os.path.isfile(full_path):  # 如果是一个文件, 调用self.__copy_file_from_outside进行处理.
                self.__copy_file_from_outside(full_path, inner_path + [entry])

    def __copy_file_to_outside(self, inner_path: list, outer_path: str) -> None:
        """向外部指定路径以复制的方式添加内部文件 (非覆盖式) .

        Args:
            inner_path: 列表路径.
            outer_path: 外部路径.

        Raises:
            PathNotExists: 如果列表路径不存在.
            PathIsNotFile: 如果列表路径存在但不对应一个文件.
            InvalidOperation: 如果外部路径包含根路径.
            FileNotFoundError: 如果外部路径所在的目录不存在.
            FileExistsError: 如果外部路径存在.
            FileIDNotFound: 如果列表路径存在而且对应一个文件但这个文件却没有file_id.
            其他由外部文件操作引发的异常也可能发生.
        """
        # 条件检查.
        if not self._dir_tree_handler.is_path_exists(inner_path):
            raise PathNotExists(f"列表路径'{inner_path}'不存在")
        if self._dir_tree_handler.is_dir(inner_path):
            raise PathIsNotFile(f"列表路径'{inner_path}'存在但不对应一个文件")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation("不允许外部路径包含根路径")
        if not os.path.exists(os.path.dirname(outer_path)):
            raise FileNotFoundError(f"外部路径'{outer_path}'所在的目录不存在")
        if os.path.exists(outer_path):  # 如果外部路径存在.
            raise FileExistsError(f"外部路径'{outer_path}'已经存在, 不能覆盖它")

        file_id = self._dir_tree_handler.get_file_hash(inner_path)  # 获取文件的散列值
        # 将该散列值的文件复制到指定位置.
        shutil.copy(os.path.join(self._entity_files_dir, file_id), os.path.dirname(outer_path))
        os.rename(os.path.join(os.path.dirname(outer_path), file_id), outer_path)

    def __copy_dir_to_outside(self, inner_path: list, outer_path: str) -> None:
        """向外部指定路径以复制的方式添加内部目录 (非覆盖式) .

        Notes:
            * 如果这个内部目录中有文件没有file_id, 是会抛出异常的.

        Args:
            inner_path: 列表路径.
            outer_path: 外部路径.

        Raises:
            PathNotExists: 如果列表路径不存在.
            PathIsNotDir: 如果列表路径存在但不对应一个目录.
            InvalidOperation: 如果外部路径包含根路径.
            FileNotFoundError: 如果外部路径所在的目录不存在.
            FileExistsError: 如果外部路径存在.
            FileIDNotFound: 如果这个目录中存在一个文件没有file_id.
            其他由外部文件操作引发的异常也可能发生.
        """
        # 条件检查.
        if not self._dir_tree_handler.is_path_exists(inner_path):
            raise PathNotExists(f"列表路径'{inner_path}'不存在")
        if not self._dir_tree_handler.is_dir(inner_path):
            raise PathIsNotDir(f"列表路径'{inner_path}'存在但不对应一个目录")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation("不允许外部路径包含根路径")
        if not os.path.exists(os.path.dirname(outer_path)):
            raise FileNotFoundError(f"外部路径'{outer_path}'所在的目录不存在")
        if os.path.exists(outer_path):  # 如果外部路径存在.
            raise FileExistsError(f"外部路径'{outer_path}'已经存在, 不能覆盖它")

        # 创建一个目录
        os.mkdir(outer_path)
        # 获得目录的内容.
        contents = self._dir_tree_handler.get_dir_content(inner_path)
        # 遍历目录.
        for item in contents:
            path_tmp = inner_path + [item]
            if not self._dir_tree_handler.is_dir(path_tmp):  # 如果是一个文件, 将它复制到目录中.
                self.__copy_file_to_outside(path_tmp, os.path.join(outer_path, item))
            else:  # 如果是一个目录, 递归调用自己.
                self.__copy_dir_to_outside(path_tmp, os.path.join(outer_path, item))

    def __add_quote_count_for_files_in_dir(self, dir_path: list) -> None:
        """对目录中的文件递归的增加引用计数.

        Raises:
            PathNotExists: 如果该列表路径不存在.
            PathIsNotDir: 如果该列表路径存在但不对应一个目录.
        """
        # 条件检查.
        if not self._dir_tree_handler.is_path_exists(dir_path):
            raise PathNotExists(f"列表路径'{dir_path}'不存在")
        if not self._dir_tree_handler.is_dir(dir_path):
            raise PathIsNotDir(f"列表路径'{dir_path}'存在但不对应一个目录")

        # 获得目录的内容
        contents = self._dir_tree_handler.get_dir_content(dir_path)
        # 遍历目录
        for item in contents:
            path_tmp = dir_path + [item]
            if not self._dir_tree_handler.is_dir(path_tmp):  # 如果是一个文件, 增加它的引用计数
                file_id = self._dir_tree_handler.get_file_hash(path_tmp)
                self._file_quote_count_manager.add_quote_count_for_id(file_id)
            else:  # 如果是一个目录, 递归调用自己
                self.__add_quote_count_for_files_in_dir(path_tmp)

    def __sub_quote_count_for_files_in_dir(self, dir_path: list) -> None:
        """对目录中的文件递归的减少引用计数.

        Raises:
            PathNotExists: 如果该列表路径不存在.
            PathIsNotDir: 如果该列表路径存在但不对应一个目录.
        """
        # 条件检查.
        if not self._dir_tree_handler.is_path_exists(dir_path):
            raise PathNotExists(f"列表路径'{dir_path}'不存在")
        if not self._dir_tree_handler.is_dir(dir_path):
            raise PathIsNotDir(f"列表路径'{dir_path}'存在但不对应一个目录")

        # 获得目录的内容.
        contents = self._dir_tree_handler.get_dir_content(dir_path)
        # 遍历目录.
        for item in contents:
            path_tmp = dir_path + [item]
            if not self._dir_tree_handler.is_dir(path_tmp):  # 如果是一个文件, 减少它的引用计数 (当减为 0 时, 将这个实体文件删除) .
                file_id = self._dir_tree_handler.get_file_hash(path_tmp)
                if self._file_quote_count_manager.sub_quote_count_for_id(file_id):
                    os.remove(os.path.join(self._entity_files_dir, file_id))
            else:  # 如果是一个目录, 递归调用自己.
                self.__sub_quote_count_for_files_in_dir(path_tmp)

    # 后续添加
    def __copy_dir_from_outside_ex(
        self,
        outer_path: str,
        inner_path: list,
        type_filter: list
    ) -> None:
        """向指定路径以复制的方式添加一个外部目录 (包含目录名) , 只添加指定后缀的文件 (非覆盖式) .

        Warnings:
            * 现在只能处理目录和普通文件, 不能处理别的比如链接之类的东西, 现在的做法是略过它们.

        Notes:
            * 如果内部路径存在, 则抛出异常.

        Args:
            outer_path: 外部路径.
            inner_path: 列表路径.

        Raises:
            FileNotFoundError: 如果外部路径不存在.
            NotADirectoryError: 如果外部路径存在但不对应一个目录.
            InvalidOperation: 如果外部路径包含根路径.
            InvalidCurrentDirOperation: 如果列表路径是当前路径.
            DirOfPathNotExists: 如果列表路径所在的目录不存在.
            PathExists: 如果内部路径已经存在.
            其他由外部文件操作引发的异常也可能发生.
        """
        # 条件检查.
        if not os.path.exists(outer_path):
            raise FileNotFoundError(f"外部路径'{outer_path}'不存在")
        if not os.path.isdir(outer_path):
            raise NotADirectoryError(f"外部路径'{outer_path}'存在但不对应一个目录")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation("不允许外部路径包含根路径")
        if not inner_path:
            raise InvalidCurrentDirOperation("该列表路径不能是当前路径")
        if not self._dir_tree_handler.is_path_exists(inner_path[:-1]):
            raise DirOfPathNotExists(f"列表路径'{inner_path}'所在的目录不存在")
        if self._dir_tree_handler.is_path_exists(inner_path):  # 如果目标路径是存在的.
            raise PathExists(f"路径'{inner_path}'已经存在, 不能覆盖它")

        # 创建一个目录结点.
        self._dir_tree_handler.mkdir(inner_path)
        # 遍历目录中的内容.
        for entry in os.listdir(outer_path):  # 对于既不是目录也不是普通文件的东西, 这里直接忽略.
            full_path = os.path.join(outer_path, entry)
            if os.path.isdir(full_path):  # 如果是一个目录, 递归调用自己.
                self.__copy_dir_from_outside_ex(full_path, inner_path + [entry], type_filter)
            elif os.path.isfile(full_path):  # 如果是一个文件, 且满足相应的扩展名, 调用self.__copy_file_from_outside进行处理.
                if "" in type_filter:  # 专门处理一下无扩展名的
                    if "." not in os.path.basename(full_path):
                        self.__copy_file_from_outside(full_path, inner_path + [entry])
                if (os.path.basename(full_path)).split('.')[-1].lower() in type_filter:
                    self.__copy_file_from_outside(full_path, inner_path + [entry])

    def __copy_dir_to_outside_ex(
        self,
        inner_path: list,
        outer_path: str,
        type_filter: list
    ) -> None:
        """向外部指定路径以复制的方式添加内部目录, 只添加指定后缀的文件 (非覆盖式) .

        Notes:
            * 如果这个内部目录中有文件没有file_id, 是会抛出异常的.

        Args:
            inner_path: 列表路径.
            outer_path: 外部路径.

        Raises:
            PathNotExists: 如果列表路径不存在.
            PathIsNotDir: 如果列表路径存在但不对应一个目录.
            InvalidOperation: 如果外部路径包含根路径.
            FileNotFoundError: 如果外部路径所在的目录不存在.
            FileExistsError: 如果外部路径存在.
            FileIDNotFound: 如果这个目录中存在一个文件没有file_id.
            其他由外部文件操作引发的异常也可能发生.
        """
        # 条件检查.
        if not self._dir_tree_handler.is_path_exists(inner_path):
            raise PathNotExists(f"列表路径'{inner_path}'不存在")
        if not self._dir_tree_handler.is_dir(inner_path):
            raise PathIsNotDir(f"列表路径'{inner_path}'存在但不对应一个目录")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation("不允许外部路径包含根路径")
        if not os.path.exists(os.path.dirname(outer_path)):
            raise FileNotFoundError(f"外部路径'{outer_path}'所在的目录不存在")
        if os.path.exists(outer_path):  # 如果外部路径存在.
            raise FileExistsError(f"外部路径'{outer_path}'已经存在, 不能覆盖它")

        # 创建一个目录
        os.mkdir(outer_path)
        # 获得目录的内容.
        contents = self._dir_tree_handler.get_dir_content(inner_path)
        # 遍历目录.
        for item in contents:
            path_tmp = inner_path + [item]
            if not self._dir_tree_handler.is_dir(path_tmp):  # 如果是一个文件, 且满足指定的后缀, 将它复制到目录中.
                if "" in type_filter:  # 专门处理一下无扩展名的
                    if "." not in os.path.basename(path_tmp[-1]):
                        self.__copy_file_to_outside(path_tmp, os.path.join(outer_path, item))
                if path_tmp[-1].split('.')[-1].lower() in type_filter:
                    self.__copy_file_to_outside(path_tmp, os.path.join(outer_path, item))
            else:  # 如果是一个目录, 递归调用自己.
                self.__copy_dir_to_outside_ex(path_tmp, os.path.join(outer_path, item), type_filter)

    # 提供给外部的方法
    def store_change(self):
        """在退出前将对目录树的操作、引用计数操作保存.

        Notes:
            * 这里有一个很有意思的地方, 即使忘了保存, 也没什么用户集看到的引用计数和实际的引用计数不一致的问题。
              唯一的问题似乎只是, 引用计数不为0的文件可能已经被删除了, 引用计数为0的文件可能还在 (我们看到这是非常开心的！) .
        """
        self._dir_tree_handler.store_change()
        self._file_quote_count_manager.store_change()

    def get_current_dir_path(self) -> str:
        """返回当前目录."""
        return self.__convert_list_path_to_inner_path(self._dir_tree_handler.get_current_dir_path())

    def is_path_exists(self, path: str) -> bool:
        """查询指定路径的文件或目录是否存在.

        Raises:
            InvalidPath: 如果路径是非法的.
        """
        path_list = self.__convert_inner_path_to_list_path(path)
        return self._dir_tree_handler.is_path_exists(path_list)

    def chdir(self, dir_path: str) -> None:
        """切换当前目录.

        Raises:
            InvalidPath: 如果路径是非法的.
            PathNotExists: 如果该路径不存在.
            PathIsNotDir: 如果该路径存在但不对应一个目录.
        """
        dir_path_list = self.__convert_inner_path_to_list_path(dir_path)
        self._dir_tree_handler.chdir(dir_path_list)

    def get_metadata_of_path(self, path: str) -> dict:
        """查看指定路径的文件或目录的元数据.

        Raises:
            InvalidPath: 如果路径是非法的.
            PathNotExists: 如果该路径不存在.
        """
        path = self.__convert_inner_path_to_list_path(path)
        return self._dir_tree_handler.get_metadata_of_path(path)

    def modify_metadata_of_path(self, path: str, metadata: dict) -> None:
        """修改指定路径的文件或目录的元数据.

        Notes:
            * 这里传入的 metadata 会覆盖原来的.

        Raises:
            InvalidPath: 如果路径是非法的.
            PathNotExists: 如果该路径不存在.
        """
        path = self.__convert_inner_path_to_list_path(path)
        self._dir_tree_handler.modify_metadata_of_path(path, metadata)

    def get_dir_content(self, dir_path: str) -> list:
        """查看指定路径的目录的内容.

        Returns:
            以 list 形式返回目录中的文件名和目录名.

        Raises:
            InvalidPath: 如果路径是非法的.
            PathNotExists: 如果该路径不存在.
            PathIsNotDir: 如果该路径存在但不对应一个目录.
        """
        dir_path = self.__convert_inner_path_to_list_path(dir_path)
        return self._dir_tree_handler.get_dir_content(dir_path)

    def get_file_content(
        self,
        file_path: str,
        is_binary: bool = True,
        start: int = 0,
        size: int = None
    ) -> Union[bytes, str]:
        """查看指定路径的文件的指定范围的内容 (bytes、str) .

        Notes:
            * 如果文件很大, 最好分多次请求完成, 不要一次读取太多.
            * 这里 start 用于 seek, size 用于 read.
            * 当 size 为 None 时, 意味着从 start 一直读到文件末尾.
            * 这里的文件内容读取的行为和 seek、read 是一样的.

        Args:
            file_path: 待读取的文件名.
            is_binary: 是否以二进制的形式读取.
            start: 指定读取的起始位置 (0 表示开始) .
            size: 指定读取的大小 (None 表示一直到末尾) .

        Returns:
            和 is_binary 对应, 以 bytes 或 str 的形式返回指定内容.

        Raises:
            InvalidPath: 如果路径是非法的.
            PathNotExists: 如果该路径不存在.
            PathIsNotFile: 如果该路径存在但不对应一个文件 (而是一个目录) .
            FileIDNotFound: 如果该路径存在且是一个文件但没有file_id.
            ValueError: 如果请求的范围不合适.
        """
        file_path_list = self.__convert_inner_path_to_list_path(file_path)
        # 获取该文件的散列值
        hash_value = self._dir_tree_handler.get_file_hash(file_path_list)
        # 返回请求的内容
        entity_file_path = os.path.join(self._entity_files_dir, hash_value)
        if is_binary:
            open_mode = 'rb'
        else:
            open_mode = 'r'
        with open(entity_file_path, open_mode) as f:
            f.seek(start)
            data = f.read(size)
        return data

    def copy_from_outside(self, outer_path: str, inner_path: str) -> None:
        """向指定路径以复制的方式添加一个外部 (即一个本身不在该虚拟文件系统中的) 文件或目录 (原来的文件或目录是不受影响的)  (非覆盖式) .

        Notes:
            * 在使用前应检查内部路径是否存在.
            * 如果内部路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果内部路径是非法的.
            InvalidOperation: 如果外部路径包含根目录.
            FileNotFoundError: 如果外部路径不存在.
            InvalidOperation: 如果外部路径包含根路径.
            InvalidCurrentDirOperation: 如果内部路径是当前路径.
            DirOfPathNotExists: 如果内部路径所在的目录不存在.
            PathExists: 如果内部路径已经存在.
            其他由外部文件操作引发的异常也可能发生.
        """
        inner_path_list = self.__convert_inner_path_to_list_path(inner_path)
        if os.path.isfile(outer_path):  # 如果是一个文件
            self.__copy_file_from_outside(outer_path, inner_path_list)
        else:  # 如果是一个目录
            self.__copy_dir_from_outside(outer_path, inner_path_list)

    def move_from_outside(self, outer_path: str, inner_path: str) -> None:
        """向指定路径以移动的方式添加一个外部文件或目录 (原来的文件或目录被删除)  (非覆盖式) .

        Notes:
            * 在使用前应检查内部路径是否存在.
            * 如果内部路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果内部路径是非法的.
            InvalidOperation: 如果外部路径包含根目录.
            FileNotFoundError: 如果外部路径不存在.
            InvalidOperation: 如果外部路径包含根路径.
            InvalidCurrentDirOperation: 如果内部路径是当前路径.
            DirOfPathNotExists: 如果内部路径所在的目录不存在.
            PathExists: 如果内部路径已经存在.
            其他由外部文件操作引发的异常也可能发生.
        """
        self.copy_from_outside(outer_path, inner_path)
        # 删除原文件或目录
        if os.path.isfile(outer_path):
            os.remove(outer_path)
        else:
            shutil.rmtree(outer_path)

    def copy_to_outside(self, inner_path: str, outer_path: str) -> None:
        """将指定路径的文件或目录复制到外部的指定路径 (非覆盖式) .

        Notes:
            * 在使用前应当检查外部路径是否存在.
            * 如果外部路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果内部路径是非法的.
            PathNotExists: 如果内部路径不存在.
            InvalidOperation: 如果外部路径包含根路径.
            FileNotFoundError: 如果外部路径所在的目录不存在.
            FileExistsError: 如果外部路径存在.
            FileIDNotFound: 如果内部路径存在而且对应一个文件但这个文件却没有file_id.
            其他由外部文件操作引发的异常也可能发生.
        """
        inner_path_list = self.__convert_inner_path_to_list_path(inner_path)
        if not self._dir_tree_handler.is_dir(inner_path_list):  # 如果是一个文件
            self.__copy_file_to_outside(inner_path_list, outer_path)
        else:  # 如果是一个目录
            self.__copy_dir_to_outside(inner_path_list, outer_path)

    def move(self, src_path: str, dst_path: str) -> None:
        """在内部 (即在该虚拟文件系统中的) 移动一个文件或目录 (这就包括了重命名)  (非覆盖式) .

        Notes:
            * 在使用前应检查目标路径是否存在.
            * 如果目标路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果源路径或目标路径是非法的.
            PathExists: 如果目标路径已经存在.
            InvalidOperation: 如果目标路径包含源路径.
            InvalidCurrentDirOperation: 如果源路径或者目标路径是当前路径, 或源路径包含当前路径.
            PathNotExists: 如果源路径不存在, 或目标路径所在的目录不存在.
            InvalidNamingConvention: 如果待创建的结点的名称是空的或者其中包含‘/’.
        """
        # 条件检查.
        src_path_list = self.__convert_inner_path_to_list_path(src_path)
        dst_path_list = self.__convert_inner_path_to_list_path(dst_path)
        if self._dir_tree_handler.is_path_exists(dst_path_list):  # 如果目标路径存在.
            raise PathExists(f"目标路径'{dst_path}'已经存在, 不能覆盖它")

        self._dir_tree_handler.move(src_path_list, dst_path_list)

    def copy(self, src_path: str, dst_path: str) -> None:
        """在内部复制一个文件或目录.

        Notes:
            * 在使用前应检查目标路径是否存在.
            * 如果目标路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果源路径或目标路径是非法的.
            PathExists: 如果目标路径已经存在.
            InvalidOperation: 如果目标路径包含源路径.
            InvalidCurrentDirOperation: 如果源路径或者目标路径是当前路径, 或源路径包含当前路径.
            PathNotExists: 如果源路径不存在, 或目标路径所在的目录不存在.
            InvalidNamingConvention: 如果待创建的结点的名称是空的或者其中包含‘/’.
        """
        # 条件检查.
        src_path_list = self.__convert_inner_path_to_list_path(src_path)
        dst_path_list = self.__convert_inner_path_to_list_path(dst_path)
        if self._dir_tree_handler.is_path_exists(dst_path_list):  # 如果目标路径存在;
            raise PathExists(f"目标路径'{dst_path}'已经存在, 不能覆盖它")

        # 复制结点 (必须放在处理引用计数前面, 因为要使用其中的异常处理) .
        self._dir_tree_handler.copy(src_path_list, dst_path_list)
        # 处理引用计数.
        if not self._dir_tree_handler.is_dir(src_path_list):  # 如果是一个文件, 增加其引用计数.
            file_id = self._dir_tree_handler.get_file_hash(src_path_list)
            self._file_quote_count_manager.add_quote_count_for_id(file_id)
        else:  # 如果是一个目录, 递归的增加其中文件的引用计数.
            self.__add_quote_count_for_files_in_dir(src_path_list)

    def delete(self, path: str) -> None:
        """在内部删除一个文件或目录.

        Raises:
            InvalidPath: 如果该路径是非法的.
            InvalidCurrentDirOperation: 如果该路径是当前路径.
            PathNotExists: 如果该路径不存在.
        """
        # 条件检查
        if path == '':  # 如果该路径是当前路径
            raise InvalidCurrentDirOperation("在删除操作中, 待删除路径是当前路径, 这是不允许的")

        path_list = self.__convert_inner_path_to_list_path(path)
        # 处理文件引用计数.
        if not self._dir_tree_handler.is_dir(path_list):  # 如果是一个文件, 减少其引用计数 (当减为 0 时, 将这个实体文件删除) .
            file_id = self._dir_tree_handler.get_file_hash(path_list)
            if self._file_quote_count_manager.sub_quote_count_for_id(file_id):
                os.remove(os.path.join(self._entity_files_dir, file_id))
        else:  # 如果是一个目录, 递归减少引用计数.
            self.__sub_quote_count_for_files_in_dir(path_list)
        # 删除结点
        self._dir_tree_handler.delete(path_list)

    def mkdir(self, path: str) -> None:
        """在内部新建一个目录 (非覆盖式) .

        Notes:
            * 在使用前应检查该路径是否存在.
            * 如果该路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果该路径是非法的.
            PathExists: 如果该路径已经存在.
            InvalidCurrentDirOperation: 如果该路径对应当前路径.
            InvalidNamingConventionError: 如果待创建结点的名称中包含'/'.
            DirOfPathNotExists: 如果该路径所在的目录是不存在的.
        """
        # 条件检查.
        path_list = self.__convert_inner_path_to_list_path(path)
        if self._dir_tree_handler.is_path_exists(path_list):  # 如果路径存在;
            raise PathExists(f"路径'{path}'已经存在, 不能覆盖它")

        self._dir_tree_handler.mkdir(path_list)

    def is_file_exist_via_file_id(self, file_id: str) -> bool:
        """查询指定散列值的文件是否存在.

        Notes:
            * 可以考虑一下, 要不要做成和引用计数管理器相关的, 而不是和实体文件集目录相关的 (这是值得考虑的) .
        """
        return os.path.exists(os.path.join(self._entity_files_dir, file_id))

    def add_file_via_hash_value(self, path: str, file_id: str) -> None:
        """向指定路径添加指定散列值的文件 (非覆盖式) .

        Notes:
            * 在使用前应检查目标路径是否存在.
            * 如果目标路径存在, 则抛出异常.

        Raises:
            PathExists: 如果该路径已经存在.
            InvalidOperation: 如果该散列值文件不存在.
            InvalidCurrentDirOperation: 如果该路径对应当前路径.
            InvalidNamingConventionError: 如果待创建结点的名称中包含'/'.
            DirOfPathNotExists: 如果该路径所在的目录是不存在的.
        """
        # 条件检查.
        path_list = self.__convert_inner_path_to_list_path(path)
        if self._dir_tree_handler.is_path_exists(path_list):  # 如果路径存在.
            raise PathExists(f"路径'{path}'已经存在, 不能覆盖它")
        if not self.is_file_exist_via_file_id(file_id):  # 如果该散列值文件不存在.
            raise InvalidOperation(f"该散列值'{file_id}'的文件不存在")

        # 增加该文件 (必须放在处理引用计数前面, 因为要使用其中的异常处理) .
        self._dir_tree_handler.create_file(path_list)
        self._dir_tree_handler.set_file_hash(path_list, file_id)
        # 增加文件的引用.
        self._file_quote_count_manager.add_quote_count_for_id(file_id)

    # -文件复制、移动操作易用版
    def simple_copy_from_outside(
        self,
        outer_path: str,
        inner_dir: str,
        inner_dst_name: str = None
    ) -> None:
        """向指定路径以复制的方式添加一个外部 (即一个本身不在该虚拟文件系统中的) 文件或目录 (原来的文件或目录是不受影响的)  (非覆盖式) .

        Notes:
            * 在使用前应检查内部路径是否存在.
            * 如果内部路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果内部路径是非法的.
            InvalidOperation: 如果外部路径包含根目录.
            FileNotFoundError: 如果外部路径不存在.
            InvalidOperation: 如果外部路径包含根路径.
            InvalidCurrentDirOperation: 如果内部路径是当前路径.
            DirOfPathNotExists: 如果内部路径所在的目录不存在.
            PathExists: 如果内部路径已经存在.
            其他由外部文件操作引发的异常也可能发生.
        """
        if not inner_dst_name:
            self.copy_from_outside(outer_path, self.__join_two_inner_paths(inner_dir, os.path.basename(outer_path)))
        else:
            self.copy_from_outside(outer_path, self.__join_two_inner_paths(inner_dir, inner_dst_name))

    def simple_move_from_outside(
        self,
        outer_path: str,
        inner_dir: str,
        inner_dst_name: str = None
    ) -> None:
        """向指定路径以移动的方式添加一个外部文件或目录 (原来的文件或目录消失)  (非覆盖式) .

        Notes:
            * 在使用前应检查内部路径是否存在.
            * 如果内部路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果内部路径是非法的.
            InvalidOperation: 如果外部路径包含根目录.
            FileNotFoundError: 如果外部路径不存在.
            InvalidOperation: 如果外部路径包含根路径.
            InvalidCurrentDirOperation: 如果内部路径是当前路径.
            DirOfPathNotExists: 如果内部路径所在的目录不存在.
            PathExists: 如果内部路径已经存在.
            其他由外部文件操作引发的异常也可能发生.
        """
        if not inner_dst_name:
            self.move_from_outside(outer_path, self.__join_two_inner_paths(inner_dir, os.path.basename(outer_path)))
        else:
            self.move_from_outside(outer_path, self.__join_two_inner_paths(inner_dir, inner_dst_name))

    def simple_copy_to_outside(
        self,
        inner_path: str,
        outer_dir: str,
        outer_dst_name: str = None
    ) -> None:
        """将指定路径的文件或目录复制到外部的指定路径 (覆盖式) .

        Raises:
            InvalidPath: 如果内部路径是非法的.
            PathNotExists: 如果内部路径不存在.
            InvalidOperation: 如果外部路径包含根路径.
            FileNotFoundError: 如果外部路径所在的目录不存在.
            FileIDNotFound: 如果内部路径存在而且对应一个文件但这个文件却没有file_id.
            其他由外部文件操作引发的异常也可能发生.
        """
        if not outer_dst_name:
            self.copy_from_outside(inner_path, os.path.join(outer_dir, os.path.basename(inner_path)))
        else:
            self.copy_from_outside(inner_path, os.path.join(outer_dir, outer_dst_name))

    def simple_move(self, src_path: str, dst_dir: str, dst_name: str = None) -> None:
        """在内部 (即在该虚拟文件系统中的) 移动一个文件或目录 (这就包括了重命名)  (非覆盖式) .

        Notes:
            * 在使用前应检查目标路径是否存在.
            * 如果目标路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果源路径或目标路径是非法的.
            PathExists: 如果目标路径已经存在.
            InvalidOperation: 如果目标路径包含源路径.
            InvalidCurrentDirOperation: 如果源路径或者目标路径是当前路径, 或源路径包含当前路径.
            PathNotExists: 如果源路径不存在, 或目标路径所在的目录不存在.
            InvalidNamingConvention: 如果待创建的结点的名称是空的或者其中包含‘/’.
        """
        if not dst_name:
            self.move(src_path, self.__join_two_inner_paths(dst_dir, os.path.basename(src_path)))
        else:
            self.move(src_path, self.__join_two_inner_paths(dst_dir, dst_name))

    def simple_copy(self, src_path: str, dst_dir: str, dst_name: str = None) -> None:
        """在内部复制一个文件或目录.

        Notes:
            * 在使用前应检查目标路径是否存在.
            * 如果目标路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果源路径或目标路径是非法的.
            PathExists: 如果目标路径已经存在.
            InvalidOperation: 如果目标路径包含源路径.
            InvalidCurrentDirOperation: 如果源路径或者目标路径是当前路径, 或源路径包含当前路径.
            PathNotExists: 如果源路径不存在, 或目标路径所在的目录不存在.
            InvalidNamingConvention: 如果待创建的结点的名称是空的或者其中包含‘/’.
        """
        if not dst_name:
            self.copy(src_path, self.__join_two_inner_paths(dst_dir, os.path.basename(src_path)))
        else:
            self.copy(src_path, self.__join_two_inner_paths(dst_dir, dst_name))

    # 添加功能
    def copy_dir_from_outside_ex(self, outer_path: str, inner_path: str, type_filter: list) -> None:
        """向指定路径以复制的方式添加一个外部目录, 只添加指定后缀的文件 (非覆盖式) .

        Notes:
            * 在使用前应检查内部路径是否存在.
            * 如果内部路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果内部路径是非法的.
            InvalidOperation: 如果外部路径包含根目录.
            FileNotFoundError: 如果外部路径不存在.
            NotADirectoryError: 如果外部路径存在不对应一个目录.
            InvalidOperation: 如果外部路径包含根路径.
            InvalidCurrentDirOperation: 如果内部路径是当前路径.
            DirOfPathNotExists: 如果内部路径所在的目录不存在.
            PathExists: 如果内部路径已经存在.
            其他由外部文件操作引发的异常也可能发生.
        """
        # 条件检查.
        if self.__is_outer_path_contained(outer_path, self._root_dir):  # 检查外部路径中是否包含根目录.
            raise InvalidOperation("外部路径不能和根目录相关")

        inner_path_list = self.__convert_inner_path_to_list_path(inner_path)
        self.__copy_dir_from_outside_ex(outer_path, inner_path_list, type_filter)

    def copy_dir_to_outside_ex(self, inner_path: str, outer_path: str, type_filter: list) -> None:
        """将指定路径的文件或目录复制到外部的指定路径 (非覆盖式) .

        Notes:
            * 在使用前应当检查外部路径是否存在.
            * 如果外部路径存在, 则抛出异常.

        Raises:
            InvalidPath: 如果内部路径是非法的.
            PathNotExists: 如果内部路径不存在.
            PathIsNotDir: 如果内部路径存在但不对应一个目录.
            InvalidOperation: 如果外部路径包含根路径.
            FileNotFoundError: 如果外部路径所在的目录不存在.
            FileExistsError: 如果外部路径存在.
            FileIDNotFound: 如果内部路径存在而且对应一个文件但这个文件却没有file_id.
            其他由外部文件操作引发的异常也可能发生.
        """
        inner_path_list = self.__convert_inner_path_to_list_path(inner_path)
        self.__copy_dir_to_outside_ex(inner_path_list, outer_path, type_filter)

    def compare_two_dir(self, base_dir_path: str, patch_dir_path: str) -> str:
        """比较两个目录的内容.

        以补丁的形式输出 patch_dir_path 相对于 base_dir_path 的内容 (特别地, 如果没有差别, 输出为空)

        Warnings:
                -这里暂且没去管这种情况: 如果这个目录中有文件是没有 file_id 对应的.

        Args:
            base_dir_path: 作为基准的目录
            patch_dir_path: 和基准目录作比较的目录

        Returns:
            以 补丁 的形式输出 patch_dir_path 相对于 base_dir_path 的差异内容

        Raises:
            PathNotExists: 如果其中有一个路径不存在.
            PathIsNotDir: 如果其中有一个路径存在但不对应一个目录.
        """
        def get_files_in_dir(dir_path: str) -> dict:
            """获得指定目录中的所有文件信息

            Warnings:
                -这里暂且没去管这种情况: 如果这个目录中有文件是没有 file_id 对应的.

            Returns:
                返回的是一个字典, 字典中的元素的 key 是相对与这个 dir_path 的相对路径, value 是这个文件的 file_id (也就是 hash 值).

            Raises:
                PathNotExists: 如果路径不存在.
                PathIsNotDir: 如果路径存在但不对应一个目录.
            """
            def add_file_info_in_dir(dir_path: str, current_relative_path: str) -> None:
                """将该目录中的文件信息添加到 files_dict 中

                Notes:
                    -这里的 current_relative_path 是指想要加上的相对路径前缀名, 然后这个目录中的文件的文件路径就是 这个前缀名 + 文件名.
                """
                # 保存一下当前的路径
                current_dir_path = self.get_current_dir_path()

                try:
                    self.chdir(dir_path)
                    # 遍历
                    for item in self.get_dir_content(self.get_current_dir_path()):
                        if self._dir_tree_handler.is_dir([item]):  # 如果是目录, 递归调用自己
                            add_file_info_in_dir(item, self.__join_two_inner_paths(current_relative_path, item))
                        else:  # 如果是文件, 将相应的文件信息填入到文件信息字典中
                            files_dict[self.__join_two_inner_paths(current_relative_path, item)] = self._dir_tree_handler.get_file_hash([item])
                finally:
                    # 恢复调用前的当前目录
                    self.chdir(current_dir_path)

            files_dict = {}  # 待返回的文件信息字典
            add_file_info_in_dir(dir_path, "")  # 将该目录的文件信息加入到 files_dict 中
            return files_dict

        # 思路是这样的:
        # 要不我们粗暴一点?
        # 我们将分别遍历这两个目录, 然后输出相对于这个目录的所有文件路径和相应的 hash 值, 即 { relative_file_path : hash, ... },
        # 然后以补丁形式输出差别就行啦!

        # 获得文件信息字典
        base_dict = get_files_in_dir(base_dir_path)
        patch_dict = get_files_in_dir(patch_dir_path)

        diff_str = ""
        # 找出在 base_dict 中存在但在 patch_dict 中不存在的键值对
        for item in base_dict.items():
            if item[0] not in patch_dict:
                diff_str += '-' + item[0] + '\n'
            elif item[1] != patch_dict[item[0]]:
                diff_str += '-' + item[0] + '\n'

        # 找出在 patch_dict 中存在但在 base_dict 中不存在的键值对
        for item in patch_dict.items():
            if item[0] not in base_dict:
                diff_str += '+' + item[0] + '\n'
            elif item[1] != base_dict[item[0]]:
                diff_str += '+' + item[0] + '\n'

        return diff_str
