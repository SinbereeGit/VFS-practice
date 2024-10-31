from file_system._utils.count_manager import CountManager

if __name__ == "__main__":
    ID_TMP = "test"
    with CountManager('.') as ct:  # 指定SQLite文件的存放位置为当前目录.
        ct.create_quote_count_for_id(ID_TMP)
        ct.add_quote_count_for_id(ID_TMP)
        count = ct.get_quote_count_for_id(ID_TMP)  # 获取该表示的计数.
        print(count)  # 输出2.
        ct.sub_quote_count_for_id(ID_TMP)
        ct.sub_quote_count_for_id(ID_TMP)  # 此操作完成后该标识由于计数减为0而被删除.
        count = ct.get_quote_count_for_id(ID_TMP)  # 尝试对一个已经被删除的标识进行计数的查询, 这会引发异常.
        print(count)  # 这个语句不会被执行到.
