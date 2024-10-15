"""为每个指定的标识维护计数，支持对指定标识的创建、对指定标识的计数的增减；"""

# 导入模块
## 标准库模块
import sqlite3
import os
## 第三方库模块（无）
## 自定义模块
from ..errors import CounterExists, CounterNotExists

# 用于设置的全局变量；
TABLE_NAME = "id_count"  # 设置表名；
ID_ATTRIBUTE = "id"  # 设置标识属性名；
COUNT_ATTRIBUTE = "count"  # 设置计数属性名；


class CountManager:
    """
        功能简述：
            · 为每个指定的标识维护计数，支持对指定标识的创建、对指定标识的计数的增减；
        功能列举：
            · 保存修改；
            · 创建一个指定标识；
            · 查询指定标识的计数；
            · 增加指定标识的计数（如果该标识不存在，会调用“创建该标识”）；
            · 减少指定标识的计数（当该标识的计数为0时，会删除这个标识）；
        前置条件：
            · 对指定标识的计数的减少的次数不超过在这之前增加的次数，否则计数是荒谬的（即计数应当不小于0）；
            · 最大计数是有限制的，它的类型是SQLite中的INTEGER；
        使用说明：
            · 放在最前面：
                · 初始化的说明放在了__init__的文档字符串中；
                · 推荐通过with来使用；
                · 如果不是通过with使用，就需要手动的通过调用self.store_change来保存修改，并且需特别注意处理异常（
                  保证正常调用self.store_change），否则一旦发生，之前的操作会“丢失”；
                · 不支持并发；
            · 警告：
                · 见前置条件；
            · 提示：
                · 当一个标识的计数减为0时，这个标识会被删除，这意味着再次使用这个标识时需要创建它；
            · 使用示例：
                · 见“主函数”；
        特别说明：
            · 使用的SQLite的版本为3.31.1；
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
    # 内部
    def __init__(self, sqlite_dir: str, sqlite_file_name: str = "file_quote_count.sqlite"):
        """指定SQLite文件存放的目录，执行初始化操作；

        Warnings:
            * 确保这个目录中没有一个叫`sqlite_file_name`的“奇怪”文件，否则可能会导致奇怪的行为；

        Notes:
            * 如果相应的SQLite文件不存在，则会创建它；
            * 如果数据库中相应的表不存在，则会创建它；

        Args:
            sqlite_dir: SQLite文件存放的目录；
            sqlite_file_name: 设置用于存放引用计数的sqlite数据库的名字；
        Raises:
            FileNotFoundError: 如果该路径不存在；
            NotADirectoryError: 如果该路径存在但不对应一个目录；
        """
        # 条件检查；
        if not os.path.exists(sqlite_dir):
            raise FileNotFoundError(f"路径'{sqlite_dir}'不存在")
        if not os.path.isdir(sqlite_dir):
            raise NotADirectoryError(f"路径'{sqlite_dir}'存在但不对应一个目录")
        # 连接到 SQLite 数据库（如果数据库不存在，则会自动创建）
        self.conn = sqlite3.connect(os.path.join(sqlite_dir, sqlite_file_name))
        self.cursor = self.conn.cursor()
        # 如果不存在该表，则创建它；
        self.cursor.execute(f'''
                            create table if not exists {TABLE_NAME} (
                                {ID_ATTRIBUTE} text primary key,
                                {COUNT_ATTRIBUTE} integer
                            )
                            ''')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """在退出前关闭数据库连接；"""
        self.conn.commit()
        self.conn.close()

    # 外部
    def store_change(self):
        """关闭数据库以保存修改；"""
        self.conn.commit()
        self.conn.close()

    def create_quote_count_for_id(self, counter_id: str) -> None:
        """创建指定标识的计数；

        Args:
            counter_id: 指定的标识；

        Raises:
            CounterExists: 如果重复创建一个标识；
        """
        try:
            self.cursor.execute(f'insert into {TABLE_NAME} '
                                f'({ID_ATTRIBUTE}, {COUNT_ATTRIBUTE}) values (?, ?)', (counter_id, 1))
        except sqlite3.Error:
            raise CounterExists(f"不能重复创建标识'{counter_id}'")

    def add_quote_count_for_id(self, counter_id: str) -> None:
        """增加指定标识的计数；

        Args:
            counter_id: 指定的标识；

        Raises:
            可能有 sqlite 的异常；
        """
        self.cursor.execute(f'update {TABLE_NAME} '
                            f'set {COUNT_ATTRIBUTE} = {COUNT_ATTRIBUTE} + 1 '
                            f'where {ID_ATTRIBUTE} = ?', (counter_id,))
        if not self.cursor.rowcount:  # 如果没有受影响的行，说明这个标识不存在；
            self.create_quote_count_for_id(counter_id)

    def sub_quote_count_for_id(self, counter_id: str) -> bool:
        """减少指定标识的计数（当计数为0时，会删除这个标识）；

        Note:
            * 当计数为0时，会删除这个标识；

        Args:
            counter_id: 指定的标识；

        Returns:
            如果这个标识因此被删除了，返回True；否则，返回False；

        Raises:
            CounterNotExists: 如果对一个不存在的标识减少计数；
        """
        try:
            self.cursor.execute(f'update {TABLE_NAME} '
                                f'set {COUNT_ATTRIBUTE} = {COUNT_ATTRIBUTE} - 1 where {ID_ATTRIBUTE} = ?', (counter_id,))
            self.cursor.execute(f'delete from {TABLE_NAME} '
                                f'where {ID_ATTRIBUTE} = ? and {COUNT_ATTRIBUTE} = 0', (counter_id,))
            if self.cursor.rowcount:  # 如果有受影响的行，说明这个标识被删除了；
                return True
            else:
                return False
        except sqlite3.Error:
            raise CounterNotExists(f"不能减少一个不存在的标识'{counter_id}'的计数")

    def get_quote_count_for_id(self, counter_id: str) -> int:
        """查询指定标识的计数；

        Args:
            counter_id:

        Raises:
            CounterNotExists: 如果这个标识不存在；
        """
        self.cursor.execute(f"select {COUNT_ATTRIBUTE} "
                            f"from {TABLE_NAME} "
                            f"where {ID_ATTRIBUTE} = ?", (counter_id,))
        row = self.cursor.fetchone()
        if not row:
            raise CounterNotExists(f"不能查询一个不存在的标识'{counter_id}'的计数")
        return row[0]


if __name__ == "__main__":
    """一个简单的使用例子；"""

    # 注：如果要使用这个示例，请拷贝下面的代码，在外部的 python 文件中使用；

    counter_id_tmp = "test"
    with CountManager('.') as ct:  # 指定SQLite文件的存放位置为当前目录；
        ct.create_quote_count_for_id(counter_id_tmp)
        ct.add_quote_count_for_id(counter_id_tmp)
        count = ct.get_quote_count_for_id(counter_id_tmp)  # 获取该表示的计数；
        print(count)  # 输出2；
        ct.sub_quote_count_for_id(counter_id_tmp)
        ct.sub_quote_count_for_id(counter_id_tmp)  # 此操作完成后该标识由于计数减为0而被删除；
        count = ct.get_quote_count_for_id(counter_id_tmp)  # 尝试对一个已经被删除的标识进行计数的查询，这会引发异常；
        print(count)  # 这个语句不会被执行到；
