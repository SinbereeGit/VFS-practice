"""为每个指定的标识维护计数, 支持对指定标识的创建, 对指定标识的计数的增减."""

# 标准库模块
import sqlite3
import os
# 第三方库模块 (无) 
# 自定义模块
from ..errors import CounterExists, CounterNotExists

# 用于设置的全局变量.
TABLE_NAME = "id_count"  # 设置表名.
ID_ATTRIBUTE = "id"  # 设置标识属性名.
COUNT_ATTRIBUTE = "count"  # 设置计数属性名.


class CountManager:
    """为每个指定的标识维护计数, 支持对指定标识的创建, 对指定标识的计数的增减.

    ## 使用示例
    
    用法:
    
    ```python
    with CountManager("sqlite_dir") as cm:
        # 创建一个标识 (可选)
        cm.create_quote_count_for_id("id1")
        # 增加一个标识的计数
        cm.add_quote_count_for_id("id1")
        # 减少一个标识的计数
        cm.sub_quote_count_for_id("id1")
        # 查询一个标识的计数
        count = cm.get_quote_count_for_id("id1")
        print(count)
    ```

    和用法:

    ```python
    try:
        cm = CountManager("sqlite_dir")
        # 创建一个标识 (可选)
        cm.create_quote_count_for_id("id1")
        # 增加一个标识的计数
        cm.add_quote_count_for_id("id1")
        # 减少一个标识的计数
        cm.sub_quote_count_for_id("id1")
        # 查询一个标识的计数
        count = cm.get_quote_count_for_id("id1")
        print(count)
    except Exception as exc:  # 当然, 实际使用的时候肯定不要这么宽泛的捕获异常.
        # 处理异常
    finally:
        cm.store_change()
    ```

    是等价的.

    Warnings:
        - 对指定标识的计数的减少的次数不超过在这之前增加的次数, 否则计数是荒谬的 (即计数应当不小于0) .
        - 最大计数是有限制的, 它的类型是SQLite中的INTEGER.
    
    Notes:
        - 放在最前面:
            - 初始化的说明放在了 `__init__` 的文档字符串中.
            - 如果不是通过 `with` 来使用, 请通过 `try` 来使用, 并在 `finally` 中调用 `self.store_change`.
            - **不支持** 并行.
        - 当一个标识的计数减为0时, 这个标识会被删除, 这意味着再次使用这个标识时需要创建它.
        - 当增加一个标识的计数时, 如果这个标识不存在, 会自动创建这个标识.
        - 使用的 SQLite 的版本为 3.31.1.
    """
    # 内部
    def __init__(self, sqlite_dir: str, sqlite_file_name: str = "file_quote_count.sqlite"):
        """指定SQLite文件存放的目录, 执行初始化操作.

        Warnings:
            * 确保这个目录中没有一个叫`sqlite_file_name`的“奇怪”文件, 否则可能会导致奇怪的行为.

        Notes:
            * 如果相应的SQLite文件不存在, 则会创建它.
            * 如果数据库中相应的表不存在, 则会创建它.

        Args:
            sqlite_dir: SQLite文件存放的目录.
            sqlite_file_name: 设置用于存放引用计数的sqlite数据库的名字.
        Raises:
            FileNotFoundError: 如果该路径不存在.
            NotADirectoryError: 如果该路径存在但不对应一个目录.
        """
        # 条件检查.
        if not os.path.exists(sqlite_dir):
            raise FileNotFoundError(f"路径'{sqlite_dir}'不存在")
        if not os.path.isdir(sqlite_dir):
            raise NotADirectoryError(f"路径'{sqlite_dir}'存在但不对应一个目录")
        # 连接到 SQLite 数据库 (如果数据库不存在, 则会自动创建) 
        self.conn = sqlite3.connect(os.path.join(sqlite_dir, sqlite_file_name))
        self.cursor = self.conn.cursor()
        # 如果不存在该表, 则创建它.
        self.cursor.execute(f'''
                            create table if not exists {TABLE_NAME} (
                                {ID_ATTRIBUTE} text primary key,
                                {COUNT_ATTRIBUTE} integer
                            )
                            ''')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """在退出前关闭数据库连接."""
        self.conn.commit()
        self.conn.close()

    # 外部
    def store_change(self):
        """关闭数据库以保存修改."""
        self.conn.commit()
        self.conn.close()

    def create_quote_count_for_id(self, counter_id: str) -> None:
        """创建指定标识的计数.

        Args:
            counter_id: 指定的标识.

        Raises:
            CounterExists: 如果重复创建一个标识.
        """
        try:
            self.cursor.execute(f'insert into {TABLE_NAME} '
                                f'({ID_ATTRIBUTE}, {COUNT_ATTRIBUTE}) '
                                f'values (?, ?)', (counter_id, 1))
        except sqlite3.Error as exc:
            raise CounterExists(f"不能重复创建标识'{counter_id}'") from exc

    def add_quote_count_for_id(self, counter_id: str) -> None:
        """增加指定标识的计数.

        Args:
            counter_id: 指定的标识.

        Raises:
            可能有 sqlite 的异常.
        """
        self.cursor.execute(f'update {TABLE_NAME} '
                            f'set {COUNT_ATTRIBUTE} = {COUNT_ATTRIBUTE} + 1 '
                            f'where {ID_ATTRIBUTE} = ?', (counter_id,))
        if not self.cursor.rowcount:  # 如果没有受影响的行, 说明这个标识不存在.
            self.create_quote_count_for_id(counter_id)

    def sub_quote_count_for_id(self, counter_id: str) -> bool:
        """减少指定标识的计数 (当计数为0时, 会删除这个标识) .

        Note:
            * 当计数为0时, 会删除这个标识.

        Args:
            counter_id: 指定的标识.

        Returns:
            如果这个标识因此被删除了, 返回True.否则, 返回False.

        Raises:
            CounterNotExists: 如果对一个不存在的标识减少计数.
        """
        try:
            self.cursor.execute(f'update {TABLE_NAME} '
                                f'set {COUNT_ATTRIBUTE} = {COUNT_ATTRIBUTE} - 1 '
                                f'where {ID_ATTRIBUTE} = ?', (counter_id,))
            self.cursor.execute(f'delete from {TABLE_NAME} '
                                f'where {ID_ATTRIBUTE} = ? and {COUNT_ATTRIBUTE} = 0',
                                (counter_id,))
            if self.cursor.rowcount:  # 如果有受影响的行, 说明这个标识被删除了.
                return True
            else:
                return False
        except sqlite3.Error as exc:
            raise CounterNotExists(f"不能减少一个不存在的标识'{counter_id}'的计数") from exc

    def get_quote_count_for_id(self, counter_id: str) -> int:
        """查询指定标识的计数.

        Args:
            counter_id:

        Raises:
            CounterNotExists: 如果这个标识不存在.
        """
        self.cursor.execute(f"select {COUNT_ATTRIBUTE} "
                            f"from {TABLE_NAME} "
                            f"where {ID_ATTRIBUTE} = ?", (counter_id,))
        row = self.cursor.fetchone()
        if not row:
            raise CounterNotExists(f"不能查询一个不存在的标识'{counter_id}'的计数")
        return row[0]
