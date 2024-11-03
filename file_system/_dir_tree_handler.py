"""该模块提供了对应于一个由本模块创建的 `json` 文件的目录树的各种处理."""

# 标准库模块
from typing import Union
from enum import Enum
import os
import json
import copy
from datetime import datetime

# 第三方库模块 (无)

# 自定义模块
from .errors import (
    PathNotExists,
    PathIsNotDir,
    InvalidCurrentDirOperation,
    InvalidNamingConvention,
    DirOfPathNotExists,
    PathIsNotFile,
    FileIDNotFound,
    InvalidOperation
)


# 枚举类
class NoteIndex(Enum):
    """结点结构的列表索引枚举."""
    IS_DIR = 0
    METADATA = 1
    CONTENT = 2


class NoteType(Enum):
    """结点类型枚举."""
    IS_FILE = 0
    IS_DIR = 1


class MetadataIndex(Enum):
    """元数据的字典的索引枚举"""
    CREATE_TIME = '0'  # 创建时间
    LAST_MODIFY_TIME = '1'  # 最后修改时间


# 主类
class DirTreeHandler:
    """该类提供了对应于一个由本模块创建的 `json` 文件的目录树的各种处理.

    ## 使用示例

    用法:

    ```python
    with DirTreeHandler(json_path) as dth:
        # 打印当前目录路径
        print(dth.get_current_dir_path())
        # 打印当前目录的内容
        print(dth.get_dir_content(handler.get_current_dir_path()))
        # 做一些其他的事儿...
    ```

    和用法:

    ```python
    try:
        dth = DirTreeHandler(json_path)
        # 打印当前目录路径
        print(dth.get_current_dir_path())
        # 打印当前目录的内容
        print(dth.get_dir_content(dth.get_current_dir_path()))
        # 做一些其他的事儿...
    except Exception as e:  # 当然, 实际使用的时候肯定不要这么宽泛的捕获异常.
        # 处理异常
    finally:
        dth.store_change()
    ```

    是等价的.

    Warnings:
        - 该 `json` 文件的修改都必须是通过本模块进行的.
        - 初始化指定的路径要么对应一个空的 `json` 文件, 要么对应一个由本模块创建的 `json` 文件.
        - 现在关于路径的名称只是限制了不能包含 `/` 以及 不为空, 应当注意取一个合适的名字.
        - 请 **不要** 使用非字符串作为元数据的 `key` 值, 不要使用 `'0'` 或 `'1'` 作为 `key` 值 (这些要求虽然不是强制的, 但不遵守会造成混乱和错误).
        
    Notes:
        - 放在最前面:
            - 初始化的说明放在了 `__init__` 的文档字符串中.
            - 如果不是通过 `with` 来使用, 请通过 `try` 来使用, 并在 `finally` 中调用 `self.store_change`.
            - **不支持** 并行.
            - 支持 *Unix/Linux*, *Windows* (原则上应该也支持 *MacOS*).
        - 对文件/目录的操作是 **覆盖式的 !!!**
        - 这里所有的操作都只可能影响这个 `json` 文件本身, 对外界没有影响.
        - 复制一个文件 **不改变** 它的 *创建时间*, 只改变它的 *最后修改时间*.
        - 现在暂 **不支持** *向后退*, 现在如果要达到 *向后退* 的效果, 必须使用 *绝对路径*.
        - 这里对文件的元数据的修改和查询是粗粒度的, 即只提供整个的元数据字典的修改和查询.
        - 对文件设置散列值 `file_id` 的时候不改变任何时间属性.
    """

    # 内部使用的方法
    def __init__(self, json_path: str, json_indent_zero: bool = True, json_sep_close: bool = True):
        """根据这个特殊json文件初始化目录树.

        Warnings:
            * 该文件如果存在且是一个JSON文件, 则必须是由本模块生成的, 否则可能会导致严重的错误.

        Note:
            * 当该文件不存在时, 会创建一个空的目录树.
            * 当该文件存在但不满足JSON格式, 会创建一个空的目录树.

        Args:
            json_path: 这个特殊json文件的路径.
            json_indent_zero: 设置保存的json文件的indent, True表示紧凑, False表示indent为4.
            json_sep_close: 设置保存的json文件的分隔符的紧凑程度, True表示紧凑, False表示有一个空格.

        Raises:
            FileNotFoundError: 如果该文件所在的目录不存在.
        """
        # 部分条件检查.
        dir_of_file = os.path.dirname(json_path)
        if (not os.path.exists(dir_of_file)) and dir_of_file:
            raise FileNotFoundError(f"{json_path}所在的目录不存在")
        # 处理.
        self._json_path = json_path
        self._dir_tree = [True, {}, {}]
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding="utf-8") as f:
                    self._dir_tree = json.load(f)
            except json.JSONDecodeError:
                pass
        self._current_dir = self._dir_tree
        self._current_dir_path = ['/']
        self._old_dir = self._current_dir
        self._old_dir_path = self._current_dir_path
        self.json_indent_zero = json_indent_zero
        self.json_sep_close = json_sep_close

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """在退出前保存所有的修改"""
        self.store_change()

    def __save(self) -> None:
        """保存当前目录和当前路径."""
        self._old_dir = self._current_dir
        self._old_dir_path = self._current_dir_path

    def __backward(self) -> None:
        """恢复当前目录和当前路径.

        Warnings:
            * 在调用该方法时, 需要特别注意self._old_dir_path对应的路径是存在的, 否则可能会导致后续发生严重的错误.

        Notes:
            * 使用该方法应该特别小心, 需要确保“前置条件”是满足的.
            * 一般是在调用了“goto”方法后使用该方法, 以恢复切换“当前目录”之前所在的“当前目录”.
            * 该方法能正常起到效果的基本前提是其他方法 (除了“goto”方法、_save方法、本方法和_set_state) 保证在被调用前后不改变self._old_dir、self._old_dir_path。
              由于本模块要求self._current_dir、self._current_dir_path只能在“goto”方法和本方法调用前后改变, 在其他方法调用前后不变, 
              所以实际上要求其他方法 (除了“goto”方法、_save方法、本方法和_set_state) 在调用前后不改变这四个成员变量的值.
        """
        self._current_dir = self._old_dir
        self._current_dir_path = self._old_dir_path

    def __get_state(self) -> tuple:
        """获得当前状态的四元组."""
        return self._old_dir, self._old_dir_path, self._current_dir, self._current_dir_path

    def __set_state(self, state: tuple) -> None:
        """设置当前状态

        Warnings:
            * 该方法必须和_get_state配套使用, 否则会破坏本模块的内部一致处理, 导致意料之外的效果.
            * 该方法的在这里唯一合理的使用是, 在方法中改变“当前目录”之前 (或等效如此) 调用_get_state, 在该方法退出前调用_set_state.
            * 注意, 这里传入的参数在后续应该丢弃 (因为该方法对它们产生了“副作用”) .
        """
        (self._old_dir, self._old_dir_path, self._current_dir, self._current_dir_path) = state

    def __goto_dir(self, dir_path: list) -> bool:
        """将当前目录切换到指定目录 (仅在内部使用) .

        更新当前路径, 更新失败则当前目录和当前路径不变.

        Notes:
            * 这是本模块的核心方法 (判断路径是否存在也是以此为基础的) , 这里没有采用如果路径不存在则抛出异常的方法, 而是采用操作成功或者失败返回相应的bool值.
            * 只要调用了该方法, 原来的self._old_dir、self._old_dir_path就被覆盖了.
            * 调用该方法后, 再调用一次backward就能回到调用该方法前的“当前目录”.
            * 如果该方法返回False, “当前目录”是不变的.

        Args:
            dir_path: 一个对应目录的路径.

        Returns:
            如果dir_path不存在或者存在但不是目录, 返回False.否则, 返回True.
        """
        self.__save()
        if not dir_path:  # 对当前路径的处理.
            return True
        # 确定是绝对路径还是相对路径
        if dir_path[0] == '/':
            self._current_dir = self._dir_tree
            self._current_dir_path = ['/']
            index_begin = 1
        else:
            index_begin = 0
        # 更改当前目录到指定路径的目录, 更新当前路径, 更新失败则当前目录和当前路径不变
        for item in dir_path[index_begin:]:  # 如果是根路径['/'], dir_path[index_begin:]是[], 是okay的.
            if item in self._current_dir[NoteIndex.CONTENT.value].keys():
                if not self._current_dir[NoteIndex.CONTENT.value][item][NoteIndex.IS_DIR.value]:
                    self.__backward()
                    return False
                self._current_dir = self._current_dir[NoteIndex.CONTENT.value][item]
                self._current_dir_path = self._current_dir_path + [item]
            else:
                self.__backward()
                return False
        return True

    def __goto_path(self, path: list) -> Union[NoteType, bool]:
        """将当前目录切换到指定路径的最后一个目录 (如果路径存在) .

        如果指定路径不存在, 则“当前目录”不变.

        Notes:
            * 只要调用了该方法, 原来的self._old_dir、self._old_dir_path就被覆盖了.
            * 调用该方法后, 再调用一次backward就能回到调用该方法前的“当前目录” (前提是它存在) .
            * 如果该方法的返回值是False, 则调用该方法前后“当前目录”是不变的.
            * 特别地, 它不仅通过 self.__save 来保存“当前目录” (
              因为其内部还调用了 self.__goto_dir) , 而是在开头用局部变量保存“当前目录”, 
              这是为了在调用 self.__goto_dir 后仍保持该方法的行为.
            * 这个方法完全可以优化一下.

        Args:
            path: 指定的路径, 可以是文件, 也可以是目录.

        Returns:
            如果指定的路径不存在, 则返回False.如果指定的路径存在并且是目录 (不是目录) , 则返回NoteType.is_dir (NoteType.is_file) .特别的, 如果path是空的, 表示是当前目录, 此时返回NoteType.is_dir.
        """
        self.__save()
        old_dir_tmp = self._old_dir  # 保存旧路径.
        old_dir_path_tmp = self._old_dir_path

        if not path:  # 对当前路径的处理.
            return NoteType.IS_DIR
        # 进入该路径所在的目录 (特别地, 如果该路径是根路径, 直接处理) .
        if len(path) == 1:
            if path[0] == '/':  # 绝对路径
                self._current_dir = self._dir_tree
                self._current_dir_path = ['/']
                return NoteType.IS_DIR
        else:
            if not self.__goto_dir(path[:-1]):  # 注:当path的长度为1的时候, 这里的path[:-1]为[], 此时被调用方法返回True, 所以一切正常.
                # 恢复路径.
                self._old_dir = old_dir_tmp
                self._old_dir_path = old_dir_path_tmp
                self.__backward()
                return False
            else:
                self._old_dir = old_dir_tmp  # 恢复旧路径.
                self._old_dir_path = old_dir_path_tmp


        # 判断该路径对应的是目录、文件还是不存在.
        if path[-1] in self._current_dir[NoteIndex.CONTENT.value].keys():
            if self._current_dir[NoteIndex.CONTENT.value][path[-1]][NoteIndex.IS_DIR.value]:
                self._current_dir = self._current_dir[NoteIndex.CONTENT.value][path[-1]]
                self._current_dir_path = self._current_dir_path + [path[-1]]
                check_result = NoteType.IS_DIR
            else:
                check_result = NoteType.IS_FILE
        else:
            self.__backward()
            check_result = False
        return check_result

    def __to_absolute_path(self, path: list) -> list:
        """将路径转换成绝对路径."""
        if not path:  # 对当前路径的处理.
            path_absolute = list(self._current_dir_path)
        elif path[0] == '/':  # 对绝对路径的处理 (包括了根路径) .
            path_absolute = list(path)
        else:  # 对相对路径的处理.
            path_absolute = self._current_dir_path + path
        return path_absolute

    def __is_path_contained(self, container_path: list, contained_path: list) -> bool:
        """检查container_path路径是不是包含contained_path路径.

        Returns:
            如果包含, 返回True.反之, 返回False.
        """
        # 化成绝对路径.
        container_path = self.__to_absolute_path(container_path)
        contained_path = self.__to_absolute_path(contained_path)
        # 判断路径是否包含.
        if contained_path == container_path[:len(contained_path)]:
            return True
        return False

    @staticmethod
    def __get_current_time() -> str:
        """获取当前时间并格式化为指定格式.

        Returns:
            返回格式化的当前时间.
        """
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    def __update_parent_last_modified_time_recursively(self, path: list) -> None:
        """对一个文件或目录的上层递归的维护修改时间 (不修改这个文件或目录的最后修改时间) .

        Notes:
            * path如果对应'/', 不会做任何处理.

        Raises:
            PathNotExists: 如果该路径不存在, 则抛出此异常.
        """
        # 条件检查.
        if not self.is_path_exists(path):
            raise PathNotExists(f"路径'{path}'不存在")
        # 保存原来的状态.
        state = self.__get_state()
        # 获取格式化的当前时间.
        current_time = self.__get_current_time()
        # 回到根节点.
        self.__goto_dir(['/'])
        # 递归地修改所属目录的最后修改时间
        path = self.__to_absolute_path(path)
        path = path[:-1]  # 如果path为根目录['/'], 这里的结果就是[], 是okay的.
        for item in path:
            self.__goto_dir([item])
            self._current_dir[NoteIndex.METADATA.value][MetadataIndex.LAST_MODIFY_TIME.value] = current_time
        # 恢复原来的状态
        self.__set_state(state)

    def __update_child_last_modified_time_recursively(self, dir_path: list) -> None:
        """对一个目录的下层递归维护修改时间 (也会更新这个目录的最后修改时间) .

        Raises:
            PathNotExist: 如果该路径不存在.
            PathIsNotDir: 如果该路径存在但不对应一个目录.
        """
        def update_child_last_modified_time_recursively_help(path: list) -> None:
            """一个内部函数, 对一个目录的下层递归维护修改时间的辅助函数.

            前置条件:
                -该路径必须存在并且对应一个目录, 否则会导致错误.
                -其外部函数在调用该函数前应该已经定义格式化的当前时间current_time.

            Notes:
                * 这里的设计需十分小心.
                * 这里不保证原来的 self.__old_dir、self.__old_dir_path 不变.
            """
            # 保存当前路径.
            current_dir_tmp = self._current_dir
            current_dir_path_tmp = self._current_dir_path

            # 获得当前目录结点
            self.__goto_dir(path)
            current_dir = self._current_dir  # 这是重要的, 因为在遍历子结点的时候”当前目录“被修改, 如果直接使用self._current_dir会导致错误 (也显得十分混乱) .
            # 修改本目录的的最后修改时间
            current_dir[NoteIndex.METADATA.value][MetadataIndex.LAST_MODIFY_TIME.value] = current_time
            # 递归地修改子结点的最后修改时间
            for name, item in current_dir[NoteIndex.CONTENT.value].items():
                if item[NoteIndex.IS_DIR.value]:  # 如果是一个目录, 递归调用自己
                    update_child_last_modified_time_recursively_help([name])
                else:  # 否则, 直接修改该文件的最后修改时间
                    item[NoteIndex.METADATA.value][MetadataIndex.LAST_MODIFY_TIME.value] = current_time

            # 恢复当前路径
            self._current_dir = current_dir_tmp  # 这是相当重要的, 如果没有这个操作, 比如目录A中有目录B和目录C (其中有文件d) , 处理目录B之后, 当前目录变成了目录B, 于是在处理目录C的时候就会出错.
            self._current_dir_path = current_dir_path_tmp

        # 条件检查.
        tmp = self.__goto_path(dir_path)
        if not tmp:
            raise PathNotExists(f"路径'{dir_path}'不存在")
        if tmp != NoteType.IS_DIR:
            self.__backward()
            raise PathIsNotDir(f"路径'{dir_path}'存在但不对应一个目录")
        self.__backward()
        # 保存原来的状态
        state = self.__get_state()
        # 获取格式化的当前时间
        current_time = self.__get_current_time()
        # 递归地修改子结点的最后修改时间
        update_child_last_modified_time_recursively_help(dir_path)
        # 恢复原来的状态
        self.__set_state(state)

    def __create_note(self, path: list, note_type: NoteType = NoteType.IS_DIR) -> None:
        """创建一个结点 (覆盖式的) .

        Args:
            path: 指定创建结点的路径.
            note_type: 创建结点的类型.

        Raises:
            InvalidCurrentDirOperation: 如果该路径对应当前路径.
            InvalidNamingConventionError: 如果待创建结点的名称是空的或者其中包含“/”.
            DirOfPathNotExists: 如果该路径所在的目录是不存在的.
        """
        # 条件检查.
        state = self.__get_state()
        if not path:  # 不能创建路径为根路径的结点
            raise InvalidCurrentDirOperation("尝试创建路径为当前路径的结点, 但这是不允许的")
        if not path[-1]:  # 待创建的结点名称不能是空的.
            raise InvalidNamingConvention("待创建结点的名称不能是空的")
        if '/' in path[-1]:  # 待创建的结点名称不能是'/'.
            raise InvalidNamingConvention("待创建结点的名称中包含“/”")
        if not self.__goto_dir(path[:-1]):
            raise DirOfPathNotExists(f"路径'{path}'所在的目录不存在")

        if note_type is NoteType.IS_DIR:
            self._current_dir[NoteIndex.CONTENT.value][path[-1]] = [True, {}, {}]
        else:
            self._current_dir[NoteIndex.CONTENT.value][path[-1]] = [False, {}, {}]
        # 获取格式化的当前时间
        current_time = self.__get_current_time()
        # 修改这个结点的创建时间和最后修改时间
        self._current_dir[NoteIndex.CONTENT.value][path[-1]][NoteIndex.METADATA.value][MetadataIndex.CREATE_TIME.value] = current_time
        self._current_dir[NoteIndex.CONTENT.value][path[-1]][NoteIndex.METADATA.value][MetadataIndex.LAST_MODIFY_TIME.value] = current_time
        # 递归修改最后修改时间
        self.__update_parent_last_modified_time_recursively([path[-1]])
        self.__set_state(state)

    # 提供给外部的方法
    def store_change(self) -> None:
        """将修改保存 (可以指定保存的json文件的一些格式, 默认的设置旨在节省空间) .

        Notes:
            * 根据参数的设置, 来确定将目录树保存成json的格式.
            * 默认为原始字符写入 (即在json.dump中ensure_ascii为False, 这在UTF-8编码下是更节省空间的) 
        Args:

        """
        if self.json_indent_zero:
            indent = None
        else:
            indent = 4
        if self.json_sep_close:
            separators = (',', ':')
        else:
            separators = (', ', ': ')
        with open(self._json_path, "w", encoding='utf-8') as f:
            json.dump(self._dir_tree, f, ensure_ascii=False, indent=indent, separators=separators)

    def get_current_dir_path(self) -> list:
        """返回当前目录路径."""
        return self._current_dir_path

    def is_path_exists(self, path: list) -> bool:
        """查询指定路径的文件或目录是否存在."""
        # 保存原来的状态.
        state = self.__get_state()

        if not self.__goto_path(path):
            return False
        #self.__backward()

        # 恢复原来的状态
        self.__set_state(state)
        return True

    def chdir(self, dir_path: list) -> None:
        """切换当前目录 (提供给外部使用) .

        更新当前路径, 更新失败则当前目录和当前路径不变.

        Notes:
            * 在使用该方法前应当检查目标路径存在且是一个目录, 否则会抛出异常.
            * 即使抛出异常, “当前路径”也是不变的.

        Args:
            dir_path: 一个对应目录的路径.

        Raises:
            PathNotExists: 如果该路径不存在.
            PathIsNotDir: 如果该路径存在但不对应一个目录.
        """
        tmp = self.__goto_path(dir_path)
        if not tmp:
            raise PathNotExists(f"路径'{dir_path}'不存在")
        if tmp != NoteType.IS_DIR:
            self.__backward()
            raise PathIsNotDir(f"路径'{dir_path}'存在但不对应一个目录")

    def get_metadata_of_path(self, path: list) -> dict:
        """查看指定路径的文件或目录的元数据.

        Notes:
            * 这里返回的之所以是深拷贝而不是浅拷贝, 是因为我们之后可能会在“元数据”中加入更复杂的东西, 而不只是字符串.

        Raises:
            PathNotExists: 如果该路径不存在.
        """
        tmp = self.__goto_path(path)
        if not tmp:
            raise PathNotExists(f"路径'{path}'不存在")
        if tmp is NoteType.IS_DIR:
            result = self._current_dir[NoteIndex.METADATA.value]
        else:
            result = self._current_dir[NoteIndex.CONTENT.value][path[-1]][NoteIndex.METADATA.value]
        self.__backward()
        return copy.deepcopy(result)

    def modify_metadata_of_path(self, path: list, metadata: dict) -> None:
        """修改指定路径的文件或目录的元数据.

        Raises:
            PathNotExists: 如果该路径不存在.
        """
        tmp = self.__goto_path(path)
        if not tmp:
            raise PathNotExists(f"路径'{path}'不存在")
        current_time = self.__get_current_time()  # 获取格式化的当前时间
        if tmp is NoteType.IS_DIR:
            # 修改元数据并维护修改时间
            create_time = self._current_dir[NoteIndex.METADATA.value][MetadataIndex.CREATE_TIME.value]
            self._current_dir[NoteIndex.METADATA.value] = metadata
            self._current_dir[NoteIndex.METADATA.value][MetadataIndex.CREATE_TIME.value] = create_time
            self._current_dir[NoteIndex.METADATA.value][MetadataIndex.LAST_MODIFY_TIME.value] = current_time
        else:
            # 修改元数据并维护修改时间
            create_time = self._current_dir[NoteIndex.CONTENT.value][path[-1]][NoteIndex.METADATA.value][MetadataIndex.CREATE_TIME.value]
            self._current_dir[NoteIndex.CONTENT.value][path[-1]][NoteIndex.METADATA.value] = metadata
            self._current_dir[NoteIndex.CONTENT.value][path[-1]][NoteIndex.METADATA.value][MetadataIndex.CREATE_TIME.value] = create_time
            self._current_dir[NoteIndex.CONTENT.value][path[-1]][NoteIndex.METADATA.value][MetadataIndex.LAST_MODIFY_TIME.value] = current_time
        # 递归修改最后修改时间
        self.__update_parent_last_modified_time_recursively(path)
        self.__backward()

    def get_dir_content(self, dir_path: list) -> list:
        """查看指定路径的目录的内容.

        Returns:
            返回一个字符串列表, 其元素代表该目录中的文件名.

        Raises:
            PathNotExists: 如果该路径不存在.
            PathIsNotDir: 如果该路径存在但不对应一个目录.
        """
        tmp = self.__goto_path(dir_path)
        if not tmp:
            raise PathNotExists(f"路径'{dir_path}'不存在")
        if tmp != NoteType.IS_DIR:
            self.__backward()
            raise PathIsNotDir(f"路径'{dir_path}'存在但不对应一个目录")
        result = list(self._current_dir[NoteIndex.CONTENT.value].keys())
        self.__backward()
        return result

    def get_file_hash(self, file_path: list) -> str:
        """查看指定路径的文件的散列值.

        Notes:
            * 如果一个文件没有散列值对应 (这是可能的) , 抛出异常FileIDNotFound.

        Raises:
            PathNotExists: 如果该路径不存在.
            PathIsNotFile: 如果该路径存在但不对应一个文件 (而是一个目录) .
            FileIDNotFound: 如果该路径存在且是一个文件但没有file_id.
        """
        tmp = self.__goto_path(file_path)
        if not tmp:
            raise PathNotExists(f"路径'{file_path}'不存在")
        if tmp is NoteType.IS_DIR:
            self.__backward()
            raise PathIsNotFile(f"路径'{file_path}'存在但不对应一个文件 (而是一个目录) ")
        result = self._current_dir[NoteIndex.CONTENT.value][file_path[-1]][NoteIndex.CONTENT.value]
        self.__backward()
        if not result:
            raise FileIDNotFound(f"路径'{file_path}'存在且是一个文件但没有file_id")
        return result

    def set_file_hash(self, file_path: list, hash_value: str) -> None:
        """设置指定路径的文件的散列值.

        Raises:
            PathNotExists: 如果该路径不存在.
            PathIsNotFile: 如果该路径存在但不对应一个文件 (而是一个目录) .
        """
        tmp = self.__goto_path(file_path)
        if not tmp:
            raise PathNotExists(f"路径'{file_path}'不存在")
        if tmp is NoteType.IS_DIR:
            self.__backward()
            raise PathIsNotFile(f"路径'{file_path}'存在但不对应一个文件 (而是一个目录) ")
        self._current_dir[NoteIndex.CONTENT.value][file_path[-1]][NoteIndex.CONTENT.value] = hash_value
        self.__backward()

    def move(self, src_path: list, dst_path: list) -> None:
        """移动一个文件或目录 (覆盖式的)  (这就包括了重命名) .

        Args:
            src_path: 源文件或目录的路径.
            dst_path: 目标路径 (包含了目标名称) .

        Raises:
            InvalidOperation: 如果目标路径包含源路径.
            InvalidCurrentDirOperation: 如果源路径或者目标路径是当前路径, 或当前路径包含源路径.
            PathNotExists: 如果源路径不存在, 或目标路径所在的目录不存在.
            InvalidNamingConvention: 如果待创建的结点的名称是空的或者其中包含'/'.
        """
        # 条件检查.
        if self.__is_path_contained(dst_path, src_path):  # 如果目标路径包含源路径;
            raise InvalidOperation(f"在移动操作中, 目标路径'{dst_path}'包含源路径'{src_path}', 这是不允许的")
        if self.__is_path_contained([], src_path):  # 如果当前路径包含源路径.
            raise InvalidCurrentDirOperation(f"在移动操作中, 当前路径包含源路径'{src_path}', 这是不允许的")
        if (not src_path) or (not dst_path):  # 如果源路径或者目标路径是当前路径.
            raise InvalidCurrentDirOperation(f"在移动操作中, 源路径'{src_path}'或者目标路径'{dst_path}'是当前路径, 这是不允许的")
        if (not self.is_path_exists(src_path)) or (not self.is_path_exists(dst_path[:-1])):  # 如果目标路径所在的目录或源路径不存在.
            raise PathNotExists(f"在移动操作中, 源路径'{src_path}'或者目标路径'{dst_path}'所在的目录不存在")
        if not dst_path[-1]:  # 带创建的结点的名称不能是空的.
            raise InvalidNamingConvention("带创建的结点的名称不能是空的")
        if '/' in dst_path[-1]:  # 待创建的结点名称不能包含'/'.
            raise InvalidNamingConvention("待创建结点的名称中不能包含'/'")

        # 保存原来的状态
        state = self.__get_state()
        # 获取格式化的当前时间.
        current_time = self.__get_current_time()
        # 获取源结点.
        self.__goto_dir(src_path[:-1])
        self.__update_parent_last_modified_time_recursively([src_path[-1]])  # 对源路径向上递归更新最后修改时间.
        note_tmp = self._current_dir[NoteIndex.CONTENT.value].pop(src_path[-1])
        self.__backward()
        # 将源结点增加到目标路径所在的目录中.
        self.__goto_dir(dst_path[:-1])
        self._current_dir[NoteIndex.CONTENT.value][dst_path[-1]] = note_tmp
        self.__update_parent_last_modified_time_recursively([dst_path[-1]])  # 对目标路径向上递归更新最后修改时间.
        if note_tmp[NoteIndex.IS_DIR.value]:  # 如果它是一个目录, 向下递归更新最后修改时间.否则只需更新该文件的最后修改时间.
            self.__update_child_last_modified_time_recursively([dst_path[-1]])
        else:
            note_tmp[NoteIndex.METADATA.value][MetadataIndex.LAST_MODIFY_TIME.value] = current_time
        # self.__backward()
        # 恢复原来的状态
        self.__set_state(state)

    def copy(self, src_path: list, dst_path: list) -> None:
        """复制一个文件或目录 (复制是覆盖式的) .

        Args:
            src_path: 源文件或目录的路径.
            dst_path: 目标路径 (包含了目标名称) .

        Raises:
            InvalidOperation: 如果目标路径包含源路径.
            InvalidCurrentDirOperation: 如果源路径或者目标路径是当前路径.
            PathNotExists: 如果源路径不存在, 或目标路径所在的目录不存在.
            InvalidNamingConvention: 如果待创建的结点的名称是空的或者其中包含'/'.
        """
        # 条件检查.
        if self.__is_path_contained(dst_path, src_path):  # 如果目标路径包含源路径.
            raise InvalidOperation(f"在移动操作中, 目标路径'{dst_path}'包含源路径'{src_path}', 这是不允许的")
        if (not src_path) or (not dst_path):  # 如果源路径或者目标路径是当前路径.
            raise InvalidCurrentDirOperation(f"在移动操作中, 源路径'{src_path}'或者目标路径'{dst_path}'是当前路径, 这是不允许的")
        if (not self.is_path_exists(src_path)) or (not self.is_path_exists(dst_path[:-1])):  # 如果源路径或目标路径不存在.
            raise PathNotExists(f"在移动操作中, 源路径'{src_path}'或者目标路径'{dst_path}'不存在")
        if not dst_path[-1]:  # 带创建的结点的名称不能是空的.
            raise InvalidNamingConvention("带创建的结点的名称不能是空的")
        if '/' in dst_path[-1]:  # 待创建的结点名称不能包含'/'.
            raise InvalidNamingConvention("待创建结点的名称中不能包含'/'")

        # 保存原来的状态
        state = self.__get_state()
        # 获取格式化的当前时间.
        current_time = self.__get_current_time()
        # 获取源结点.
        self.__goto_dir(src_path[:-1])
        note_tmp = copy.deepcopy(self._current_dir[NoteIndex.CONTENT.value][src_path[-1]])  # 生成独立的副本.
        self.__backward()
        # 将源结点增加到目标路径所在的目录中.
        self.__goto_dir(dst_path[:-1])
        self._current_dir[NoteIndex.CONTENT.value][dst_path[-1]] = note_tmp
        self.__update_parent_last_modified_time_recursively([dst_path[-1]])  # 对目标路径向上递归更新最后修改时间.
        if note_tmp[NoteIndex.IS_DIR.value]:  # 如果它是一个目录, 向下递归更新最后修改时间.否则只需更新该文件的最后修改时间.
            self.__update_child_last_modified_time_recursively([dst_path[-1]])
        else:
            note_tmp[NoteIndex.METADATA.value][MetadataIndex.LAST_MODIFY_TIME.value] = current_time
        # self.__backward()
        # 恢复原来的状态
        self.__set_state(state)

    def delete(self, path: list) -> None:
        """删除一个文件或目录.

        Raises:
            InvalidCurrentDirOperation: 如果该路径是当前路径.
            PathNotExists: 如果该路径不存在.
        """
        # 条件检查.
        if not path:  # 如果该路径是当前路径.
            raise InvalidCurrentDirOperation("在删除操作中, 待删除路径是当前路径, 这是不允许的")
        if not self.is_path_exists(path):  # 如果该路径不存在.
            raise PathNotExists(f"路径'{path}'不存在")
        # 删除指定结点.
        self.__goto_dir(path[:-1])
        self.__update_parent_last_modified_time_recursively([path[-1]])  # 对指定路径向上递归更新最后修改时间
        self._current_dir[NoteIndex.CONTENT.value].pop(path[-1])
        self.__backward()

    def mkdir(self, path: list) -> None:
        """创建一个目录 (覆盖式的) .

        Notes:
            * 这里的异常处理实际上是self._create_note的.

        Args:
            path: 指定创建结点的路径.

        Raises:
            InvalidCurrentDirOperation: 如果该路径对应当前路径.
            InvalidNamingConventionError: 如果待创建结点的名称中包含“/”.
            DirOfPathNotExists: 如果该路径所在的目录是不存在的.
        """
        self.__create_note(path)

    def create_file(self, path: list) -> None:
        """创建一个文件 (覆盖式的) .

        Notes:
            * 这里的异常处理实际上是self._create_note的.

        Args:
            path: 指定创建结点的路径.

        Raises:
            InvalidCurrentDirOperation: 如果该路径对应当前路径.
            InvalidNamingConventionError: 如果待创建结点的名称中包含“/”.
            DirOfPathNotExists: 如果该路径所在的目录是不存在的.
        """
        self.__create_note(path, NoteType.IS_FILE)

    def is_dir(self, path: list) -> bool:
        """判断指定路径对应的是否是目录.

        Notes:
            * 在使用该方法前注意检查该路径是存在的, 否则会抛出异常.

        Raises:
            PathNotExists: 如果该路径不存在.
        """
        result = self.__goto_path(path)
        self.__backward()
        if not result:
            raise PathNotExists(f"路径'{path}'不存在")
        if result == NoteType.IS_DIR:
            return True
        else:
            return False
