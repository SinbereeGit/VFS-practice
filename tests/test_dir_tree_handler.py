from file_system._dir_tree_handler import DirTreeHandler

if __name__ == "__main__":
    # 以从无到有创建一个目录结构如下的目录树为例.
    # /
    # ├──SoftwareDevelopmentExperiment
    # │  ├── file_system_
    # │  │   ├── __init__.py
    # │  │   ├── _dir_tree_handler.py
    # │  │   ├── _utils
    # │  │   │   ├── __init__.py
    # │  │   │   ├── count_manager.py
    # │  │   │   └── file_hash.py
    # │  │   ├── errors.py
    # │  │   ├── test.json
    # │  │   └── virtual_file_system.py
    # │  ├── main.py
    # │  ├── my_debug
    # │  │   ├── __init__.py
    # │  │   └── my_debug.py
    # │  ├── templates
    # │  │   ├── module_template.py
    # │  │   └── __init__.py
    # │  ├── test
    # │  │   ├── __init__.py
    # │  │   ├── test.json
    # │  │   └── test.py
    # │  ├── tmp
    # │  │   └── test
    # │  └── 一些说明.txt

    # 注:如果要使用这个示例, 请拷贝下面的代码, 在外部的 python 文件中使用.

    # 使用推荐的with (上下文资源管理器) 来“按顺序地深度优先”地创建这棵目录树.
    with DirTreeHandler('test.json', json_indent_zero=False, json_sep_close=False) as d:
        d.mkdir(['SoftwareDevelopmentExperiment'])
        d.chdir(['SoftwareDevelopmentExperiment'])
        d.mkdir(['file_system_'])
        d.chdir(['file_system_'])
        d.create_file(['__init__.py'])
        d.create_file(['_dir_tree_handler.py'])
        d.mkdir(['_utils'])
        d.chdir(['_utils'])
        d.create_file(['__init__.py'])
        d.create_file(['count_manager.py'])
        d.create_file(['file_hash.py'])
        d.chdir(['/', 'SoftwareDevelopmentExperiment', 'file_system_'])
        d.create_file(['errors.py'])
        d.create_file(['test.json'])
        d.create_file(['virtual_file_system.py'])
        d.chdir(['/', 'SoftwareDevelopmentExperiment'])
        d.create_file(['main.py'])
        d.mkdir(['my_debug'])
        d.chdir(['my_debug'])
        d.create_file(['__init__.py'])
        d.create_file(['my_debug.py'])
        d.chdir(['/', 'SoftwareDevelopmentExperiment'])
        d.mkdir(['templates'])
        d.chdir(['templates'])
        d.create_file(['module_template.py'])
        d.create_file(['__init__.py'])
        d.chdir(['/', 'SoftwareDevelopmentExperiment'])
        d.mkdir(['test'])
        d.chdir(['test'])
        d.create_file(['__init__.py'])
        d.create_file(['test.json'])
        d.create_file(['test.py'])
        d.chdir(['/', 'SoftwareDevelopmentExperiment'])
        d.mkdir(['tmp'])
        d.chdir(['tmp'])
        d.mkdir(['test'])
        d.chdir(['/', 'SoftwareDevelopmentExperiment'])
        d.create_file(['一些说明.txt'])
