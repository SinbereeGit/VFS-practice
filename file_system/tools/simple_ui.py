"""提供简单的使用文件系统的命令行 ui"""

# 标准库模块
# 第三方库模块
# 自定义模块
from ..virtual_file_system import VirtualFileSystem

# 设置命令集合
COMMAND_SET = ('q!', 'pwd', 'cd', 'ls', 'mkdir', 'cp', 'mv', 'rm',
               'cp_from_outside', 'cp_to_outside', 'cp_from_outside_ex', 'cp_to_outside_ex', 'diff')


def run():
    # 使用推荐的with（上下文资源管理器）.
    root_dir = input("输入该系统的根目录: ")
    user_id = input("输入你的用户名: ")
    with VirtualFileSystem(root_dir, user_id) as vfs:
        print(f"支持的命令: {COMMAND_SET}")
        while True:
            try:
                # 输入命令
                command = input("输入你的命令: ")
                # 是否要退出
                if command == 'q!':
                    print("退出啦...")
                    break
                # 如果是无效的命令, 抛出异常
                if command not in COMMAND_SET:
                    raise Exception(f"{command} 是一个无效的命令.\n"
                                    f"支持的命令: {COMMAND_SET}")
                # 执行相应的命令
                if command == 'pwd':
                    print(f"当前目录: {vfs.get_current_dir_path()}")
                elif command == 'cd':
                    goto_path = input("输入你要切换到的目录: ")
                    vfs.chdir(goto_path)
                    print(f'当前目录: {vfs.get_current_dir_path()}')
                elif command == 'ls':
                    print(f"{vfs.get_dir_content('')}")
                elif command == 'mkdir':
                    dir_path = input("输入你要创建的目录路径: ")
                    vfs.mkdir(dir_path)
                elif command == 'cp':
                    src_path = input("输入源路径: ")
                    dst_path = input("输入目标路径: ")
                    vfs.copy(src_path, dst_path)
                elif command == 'mv':
                    src_path = input("输入源路径: ")
                    dst_path = input("输入目标路径: ")
                    vfs.move(src_path, dst_path)
                elif command == 'rm':
                    rm_path = input("输入要删除的路径: ")
                    vfs.delete(rm_path)
                elif command == 'cp_from_outside':
                    src_path = input("输入外部路径: ")
                    dst_path = input("输入内部路径: ")
                    vfs.copy_from_outside(src_path, dst_path)
                elif command == 'cp_to_outside':
                    src_path = input("输入内部路径: ")
                    dst_path = input("输入外部路径: ")
                    vfs.copy_to_outside(src_path, dst_path)
                elif command == 'cp_from_outside_ex':
                    src_path = input("输入外部路径: ")
                    dst_path = input("输入内部路径: ")
                    type_filter = (input("输入类型列表(用 ',' 分隔): ")).split(',')
                    vfs.copy_dir_from_outside_ex(src_path, dst_path, type_filter)
                elif command == 'cp_to_outside_ex':
                    src_path = input("输入内部路径: ")
                    dst_path = input("输入外部路径: ")
                    type_filter = (input("输入类型列表(用 ',' 分隔): ")).split(',')
                    vfs.copy_dir_to_outside_ex(src_path, dst_path, type_filter)
                elif command == 'diff':
                    base_path = input("输入作为基准比对目录的内部路径: ")
                    patch_patch = input("输入作为比对目录的内部路径: ")
                    diff_results = vfs.compare_two_dir(base_path, patch_patch)
                    print(diff_results)
            except Exception as e:
                print(f"Oops! 粗错啦: {e}")
