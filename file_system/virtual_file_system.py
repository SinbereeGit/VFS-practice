"""
    该模块提供了由（特殊的文件集目录，指定用户ID）唯一确定的的虚拟文件系统；
    功能简述：
        ·关于路径：
            ·和dir_tree_handle模块的该说明一样；
        ·关于元数据：
            ·和dir_tree_handle模块的说明一样；
        ·内部文件（目录）的整体操作：
            ·覆盖式地移动和复制操作，删除操作；
        ·内部文件（目录）的内容操作：
            ·支持元数据整体的查看和修改，暂不支持对于元数据中指定属性的单个修改；
            ·查看指定目录中的内容；
            ·查看指定文件的指定字节范围的内容；
        ·内部和外部的交互：
            ·从外部导入文件（目录）到指定目录，copy代表保留原文件（目录），move代表删除原文件（目录）；
            ·从内部导出文件（目录）到指定目录；
            ·“外部”的源路径不能和系统文件集目录相关的；
    Warning：
        ·最好使用with来使用该类的对象；
        - 这里如果引发异常, 可能会出现 用户集 和 引用计数 以及 实体文件集 的不一致 (还没有仔细考虑).
    注：
        ·--模块中几乎所有的“if not”是冗余的，不过现在我们不打算更正它们（因为实在是有点太多了）；
"""
# 打算是这样的：
#   虚拟文件系统以一个用户空间的用户特殊文件“+”一个实体文件集目录的形式存在，通过这个特殊文件可以构建虚拟文件系统的目录树；
#   对于这个目录树，内结点没有实际的文件对应，叶子结点实际上是key为虚拟文件系统的文件路径、value为实体文件集（其中的文件内容均不相同）目录中的以文件内容的散列结果命名的文件的文件路径的一个字典元素；
# 该对象的任务：
#   提供一个虚拟文件系统，需要指定根目录（这个目录中的实体文件集目录保存所有的实体文件）的路径和特殊文件的标识（这个文件保存在这个指定的根目录的一个子目录的一个以该标识命名的子子目录中）；
# 实现相关的：
#   先考虑目录树：
#       结点结构--一个列表，有三项内容：
#           是否是目录；
#           保存各种元数据信息（包含文件的类型，是目录还是普通文件还是软链接或者别的什么）的字典（特别地，有一个“额外描述”的项）；
#           内容：
#               如果是目录，则是一个子结点字典（key为子结点名，value为子结点指针）；
#               如果是普通文件，则是一个散列值；
#               如果是其他文件，则是一个字典（用于比较自由的处理）；
#       我们实际上用字典构造了这棵树；
#       我们把目录树设计成一个类，它的初始化是这个特殊文件；
#   再考虑这个特殊文件：
#       为了方便，我们将其确定为一个json文件（这可以和我们上面描述的目录树有很容易的互相转化）；
#   特别考虑增加和删除文件：
#       考虑到一些东西（比如，我们可以利用这个虚拟文件系统向上很方便地构建多用户虚拟文件系统），我们决定在每个文件上附加一个属性用来记录被引用数（注于后来，这个决定后来被我们废弃了）；
#       在新增一个实体文件时，添加这个属性并把计数设置为1；
#       每增加一个引用，就将这个计数加1，每减少一个引用，就将这个计数减1；
#       当引用计数为0时，删除这个实体文件；
#   特别考虑从外部添加文件的两种方式：
#       以复制的方式：
#           如果该文件的散列值对应的文件不存在，先将文件复制到用户的上传暂存目录，然后再移动到实体文件集目录（文件名为该文件的散列值）；
#           否则，添加引用计数后增加结点；
#       以移动的方式：
#           如果该文件的散列值对应的文件不存在，直接移动到实体文件集目录（文件名为散列值）；
#           否则，添加引用计数后增加结点；
#   特别考虑对该系统并发使用的支持：
#       注于后来：由于临界问题实在是不好高效地处理，我们如果多方面地支持在效率上貌似又不太行，所以还是不支持这点了；
#       理由--如果我们要支持通过该系统构建多用户虚拟文件系统，考虑到是这种系统常常是以用户为粒度进行并发的，这意味着文件处理的并发，这就意味着需要支持并发；
#       一些思考：
#           我们要不要为虚拟文件系统自身维护一个其自身包含的实际文件的引用计数表？
#               这样做就将对实际文件引用计数的操作分成了两步：
#                   第一步是对自身的引用技术表的引用计数的操作；
#                   第二步是当引用计数表中添加或删除一个项的时候，对实际文件的引用计数属性进行修改；
#               这样做的好处在于：
#                   减少了对实际文件的引用计数属性的修改；
#                   支持在用户空间内对文件的多份拷贝，而且不会影响效率，这对于用户空间内文件多种方式的分类是很有益的；
#               问题在于：
#                   这种需求真的是很大的吗？而且为此我们还要多维护一张表，特别是一个用户的文件很多的时候，这种表的维护可能又要考虑到效率的问题，有点不太必要；
#               结论：
#                   nope；
#           这是不是可以由通过该系统构建的系统来做，还是说在这里做会更好？
#               外界来做似乎是不合适的，因为这里关键是对实体文件的引用属性的修改，而实体文件是在外部不可见的；
#               所以还是决定在这里做：
#                   我们的虚拟文件系统有两个很好的限定--不允许更改文件内容、一个实例内是串行化的，充分利用它们是有益的；
#                   基本处理：
#                       对文件的属性的操作（查询特定属性、增加一个属性、修改指定属性），需要先获得该文件的独占锁；
#                       对文件的内容的读取操作，不加限制；
#                       当实体文件的引用计数为0时，不能再增加引用计数（这实际上意味着，我们将引用计数减为0的操作和删除这个实体文件的操作变成了一个原子操作）；
#                   特别处理：
#                       上面这样简单的处理已经能解决非临界（对引用计数>1时的操作）的情况了；
#                       对于临界情况：
#                           当实体文件的引用计数由1变为0时，一个添加文件（该文件的散列值和该实体文件相同）的操作可能会失败（不过我们非常乐意如此）；
#                           当指定散列值的实体文件不存在时，一个添加文件（该文件的散列值和这个指定的散列值相同）的操作需要特别注意；
#                       对于情况1：
#                           涉及的操作：
#                               向指定路径增加指定散列值的文件；
#                               从外部添加文件；
#                           导致失败的原因：
#                               如果该文件已经被删除，os.open(file_path, os.O_RDWR)会抛出异常；
#                               如果该文件正在被删除，由于引用计数是0，增加引用计数会抛出异常（我们设计的）；
#                       对于情况2：
#                           涉及的操作：
#                               从外部添加文件；
#                           处理：
#                               这里的添加文件实际上归结为文件的移动，而这里有一个很好的条件，即文件的内容是相同的，所以当同时有多个移动到同一位置的操作时，会出现（需做一下求证）：
#                                   该目录中只出现我们期望的该文件（无需额外的处理）；
#                                   由于同时移动到同一位置抛出异常（报告操作失败即可）；
#                                   该目录中出现我们期望的文件，以及一个重命名文件（将这重命名文件删除即可）；
#   特别考虑对不同系统的支持（Windows、Linux）：
#       我们在实现的时候慢慢注意，然后补充在这里，比较幸运的是python对文件操作是非常支持跨平台的；
#       或者，如果它们很多地方需要不一样的处理的话就只支持Linux吧；
# 系统的目录结构如下：
#     根目录
#     ├── 引用计数文件
#     ├── 实体文件目录
#     │   ├── 散列文件1
#     │   └── 散列文件2
#     └── 用户空间目录
#         ├── 以用户的唯一标识命名的目录1
#         │   ├── 上传暂存目录
#         │   ├── 下载暂存目录
#         │   └── 特殊文件
#         └── 以用户的唯一标识命名的目录2
#             ├── 上传暂存目录
#             ├── 下载暂存目录
#             └── 特殊文件
# 对该系统的使用说明：
#     放在类的说明中了；


# 导入模块
## 标准库模块
from typing import Union
import os
import re
import shutil
## 第三方库模块（无）
## 自定义模块
from ._dir_tree_handler import DirTreeHandler
from ._utils.count_manager import CountManager
from ._utils.file_hash import FileHashCalculator
from .errors import *

# 用于设置的全局变量
ENTITY_FILES_DIR_NAME = "EntityFiles"  # 设置存放实体文件的目录名；
USERS_DIR_NAME = "Users"  # 设置用户空间的目录名；
USER_JSON_FILE_NAME = "dirTreeHandler.json"  # 设置用于构建目录树的json文件（就是所谓的“特殊文件”）的名字；
UPLOAD_DIR_NAME = "upload"  # 设置用于从外部导入文件的暂存目录的目录名；
ILLEGAL_PATH_CHARS = r'[*?"<>|]'  # 路径中不允许包含的符号（暂时还没有用到）；


# 主类
class VirtualFileSystem:
    """
        功能简述：
            · 提供一个虚拟文件系统，需要指定实体文件集目录的路径和用户ID，支持各种操作；
        功能列举：
            · 保存修改；
            · 返回当前路径；
            · 查询指定路径的文件或目录是否存在；
            · 切换当前目录；
            · 查看指定路径的文件或目录的元数据；
            · 修改指定路径的文件或目录的元数据；
            · 查看指定路径的目录的内容；
            · 查看指定路径的文件的指定范围的内容（bytes 或 str）；
            · 向指定路径以复制的方式添加一个外部（即一个本身不在该虚拟文件系统中的）文件或目录（原来的文件或目录是不受影响的）；
            · 向指定路径以移动的方式添加一个外部文件或目录（原来的文件或目录被删除）；
            · 将指定路径的文件或目录复制到外部的指定路径；
            · 在内部（即在该虚拟文件系统中的）移动一个文件或目录（这就包括了重命名）；
            · 在内部复制一个文件或目录；
            · 在内部删除一个文件或目录；
            · 在内部新建一个目录；
            · 查询指定散列值的文件是否存在；
            · 向指定路径添加指定散列值的文件；
        前置条件：
            · 根目录的所有内容都是由本模块（操作）生成的；
        使用说明：
            · 放在最前面：
                · 初始化的说明放在了 __init__ 的文档字符串中；
                · 推荐通过with来使用；
                · 如果不是通过with来使用，就需要手动的通过调用self.store_change来保存修改，并且需特别注意处理异常（
                  保证正常调用self.store_change），否则一旦发生，之前的操作会“丢失”；
                · 不支持并行；
                · 支持Unix/Linux、Windows（原则上应该也支持MacOS）；
            · 警告：
                · 对于同一个实体文件集目录同一时刻只能有一个系统实例运行（因为我们不支持并发）；
                ·-- 外部文件路径的末尾不能是 ‘/’ 或 ‘\\’；
            · 提示：
                · 初始化该系统需要指定实体文件集目录和用户标识；
                · 内部的文件路径采用 Unix 形式，外部的文件路径则是操作系统相关的；
                · 文件操作是非覆盖式的，这意味着如果目标路径的文件存在会抛出异常；
                · 所有的文件操作，默认最后的“一项”是目标文件名；
                · 文件的唯一标识使用的是 SHA-256 对其内容进行散列的结果；
            · 使用示例：
                · 见这个模块的“主函数”；
            ·-- 内部路径名中有不允许的符号，可以设置什么符号不允许（但是这里也允许一些不合适的符号，比如 “\\”）（
              对于内部路径名，现在还没有很好地限制，甚至还支持“ ”作为路径名...）；
        特别说明：
            · 0.这里的设计实在是有些稀烂，以后还是老老实实按照软件工程的方法进行；
            · 1.该系统是一个虚拟文件系统，实例化该系统需要指定系统文件集目录和用户标识，对外提供和文件系统类似的体验，对内保证相同的文件内容仅有一份拷贝；
            · 2.可以利用该系统实现一个多用户虚拟文件系统 -- 实例化多个该系统，它们的系统文件集目录是相同的，但用户标识唯一；
            · 3.如果要多个系统实例并发运行，需要在外层额外做一些事：
                · 这里提供一个方法作为参考：
                    · 因为这里不太好处理的主要是临界问题，而这种临界情况在实际的情况中实际上出现的不多，所以可以考虑一种错误容纳检测机制，在发生错误时抛出异常，
                      然后让外部去处理这个异常，这似乎是可行的；
                    · 幸运地是，这里的 sqlite 貌似可以作为这个抛出异常的地方，可以在马上的版本中试试；
                · 应该还有一些东西要考虑；
            · 4.跨平台问题：
                · 支持 Unix/Linux、Windows（原则上对MacOS应该也是支持的，但是我们没有测试）；
            · 5.对于系统文件集目录中的一个文件：
                · 它是纯粹无用的，如果它的文件名不是以散列值命名的；
                · 它是无法被删除的，如果一个特殊文件中对它有引用，但这个特殊文件被删除了或者被废弃了；
                · 它是被污染的，如果直接从“外部”对它进行引用计数的修改；
                · 它是虚假的，如果它的文件名确是一个散列值，但这个散列值并不等于该文件内容对应的散列值
            · 6.关于用户迁移：
                · 由于我们的特殊文件是和根目录无关的（因为它们的相对位置是不变的），所以可以很容易地做用户从一个根目录迁移到另一个，
                  为此，只需要把该用户的 json 文件复制到另一个根目录即可（但是由此就需要考虑引用计数和实体文件的问题，所以如果确实需要这样，
                  最好在这个模块中增加一个支持这样做的方法）；
                · 当然这需要考虑到相对于一个系统文件集目录的用户的用户重名问题，这就是上层该考虑的事情了；
            · 7.一些思考：
                · 在使用该系统实现的多用户虚拟文件系统中，有多个用户同时读取同一个文件的内容时，怎么样安排更加经济是值得思考的（当然，这里可能并不兼容一些好的处理了）；
        修改说明：
            · 对本类的任何修改都应该遵守本类的文档字符串中”设计说明“中的”内部一致处理“，否则可能会导致意想不到的错误；
        设计说明：
            · 内部一致处理：
                · 放在最前面：
                    · 下面所说的“方法”不包括“内部函数”；
                    · 有些东西放在了”现在的实现“中；
                · 关于“路径”
                    · “列表路径”（参见 _dir_tree_handler 模块）；
                    · ”内部路径“、”外部路径“：
                        · 关于”内部路径“：
                            · 特别指出：
                                · '/' 代表根路径；
                                · '' 代表当前路径；
                            · 就是 _dir_tree_handler 模块中的”列表路径“的元素以 ”/“ 连接的结果；
                            · 特别地，一个“内部路径”允许以“/”结尾；
                · 用 file_id 表示实体文件的唯一标识（在这里也是它的文件名）；
                · 文件的唯一标识使用的是 SHA-256 对其内容进行散列的结果（感觉似乎没这个必要，而用 SHA-1 就够了）；
                · 对方法的要求：
                    · 遵循“返回值随便用、参数随便传，不用担心有‘副作用’”原则（在 _dir_tree_handler 中说过，只是没提这个“名字”）；
                    · 每个方法都应该特别注意对当前路径和根路径的支持；
                    · 除了 __init__ 方法，每个方法的参数中的路径如果没有指明 outer 都是指“内部路径”（如果是 str 类型）或“列表路径”（如果是 list 类型）；
                    · 内部方法中，除了进行路径转换和合法性判断的方法（比如 self.__join_two_paths、self.__is_valid_path），所有的方法中的参数必须是“列表路径”或“外部路径”，
                      就是不能是“内部路径”（这样做是为了处理上的方便）；
                    · 在内部方法中，默认被调用时传入的“列表路径”是有效的（如果不是，则可能会产生错误），也就是说，“列表路径”必须满足“列表路径”的条件；
                    · 在内部方法中，对包含根路径的外部路径抛出异常；
                    · 外部方法在调用内部方法时，如果要使用“列表路径”，必须先将“内部路径”通过 __convert_inner_path_to_list_path转换成“列表路径”；
                    ·-- 对于“外部路径”现在唯一的限制是不允许末尾出现 “/” 或 “\\”，还没有检查这样会不会出现问题；
                    · 所有的方法都是非覆盖式的（这是因为涉及内部变化的限制比较多，这样的处理可以减少很多检查）；
                · 内部路径为空字符表示当前路径；
            · 为将来实现的准备：
                · 将引用计数处理模块单独出去了，这样方便后续将这个模块变得支持并行处理；
            · 为高效实现的准备：
                · 暂无；
    """

    def __init__(self, root_dir: str, user_id: str, json_indent_zero: bool = True, json_sep_close: bool = True):
        """一些初始化的操作；

        指定系统使用的实体文件集目录和以什么身份使用这个系统；

        Warnings:
            * 在最初使用的时候使用一个空目录，对系统文件集目录的任何操作必须都是通过本模块完成的，否则可能导致意想不到的错误；
            * 这里没有检查用户名的合法性, 应当输入合乎文件名规范的用户名, 否则可能导致意想不到的问题.

        Args:
            root_dir: 指定根目录，如果不存在会创建；
            user_id: 指定使用的用户ID，如果不存在会创建；
            json_indent_zero: 设置保存的json文件的indent，True表示紧凑，False表示indent为4；
            json_sep_close: 设置保存的json文件的分隔符的紧凑程度，True表示紧凑，False表示有一个空格；
        Raises:

        """
        self._root_dir = root_dir
        self._entity_files_dir = os.path.join(root_dir, ENTITY_FILES_DIR_NAME)
        self._user_id = user_id
        self._user_path = os.path.join(root_dir, USERS_DIR_NAME, user_id)
        # 如果没有则创建“根目录”、”实体文件集目录“、“用户空间目录”、“用户目录”
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
        """在退出前将对目录树的操作、引用计数操作保存；

        Notes:
            * 这里有一个很有意思的地方，即使忘了保存，也没什么用户集看到的引用计数和实际的引用计数不一致的问题。
              唯一的问题似乎只是，引用计数不为0的文件可能已经被删除了，引用计数为0的文件可能还在（我们看到这是非常开心的！）；
        """
        self.store_change()

    @staticmethod
    def __check_inner_path_validity(path: str) -> None:
        """判断一个内部路径是不是合法的；

        Notes:
            * 这里简单设置成不允许有相邻的 ‘/’（这样就不至于有中间结点为 ''，即空字符串）；

        Raises:
            InvalidPath: 如果路径是非法的；
        """
        is_valid = True

        # 规范检查；
        if "//" in path:
            is_valid = False

        if not is_valid:
            raise InvalidPath(f"路径'{path}'是非法的")

    @staticmethod
    def __convert_inner_path_to_list_path(path: str) -> list:
        """“内部路径”转换成“列表路径”；

        Raises:
            InvalidPath: 如果内部路径是非法的；
        """
        # 条件检查；
        VirtualFileSystem.__check_inner_path_validity(path)  # 检查内部条件是否合法；

        if not path:  # 对当前路径的处理；
            return []
        if path == "/":  # 对根路径的处理；
            return ['/']
        # 绝对路径和相对路径的处理；
        if path.startswith('/'):
            result = ['/'] + path.strip('/').split('/')  # 注：''.split('/')的结果是['']，不过在这里并不会发生（当然，是在满足了Warnings的要求后）；
        else:
            result = path.strip('/').split('/')
        return result

    @staticmethod
    def __convert_list_path_to_inner_path(path: list) -> str:
        """将“列表路径”转化成“内部路径”；

        Warnings:
            * 该路径要求满足“列表路径”的条件，否则可能导致错误；
        """
        if not path:  # 如果是当前路径直接返回 ''
            return ''
        if path[0] == '/':  # 绝对路径
            return '/' + '/'.join(path[1:])
        else:  # 相对路径
            return '/'.join(path)

    # ·--这个方法应该没什么问题；
    @staticmethod
    def __join_two_inner_paths(path1: str, path2: str) -> str:
        """将两个“内部路径”合并；

        Warnings:
            * 这两个路径都必须满足“内部路径”的条件；
            * 后一个路径必须是相对路径（一个结点名字当然也是相对路径）；

        Args:
            path1: 一个“内部路径”；
            path2: 一个是相对路径的“内部路径”；

        Returns:
            两个路径以”/“连接的结果；
        """
        if not path1:  # 对当前路径的处理；
            return path2
        if path1[-1] == '/':  # 其中包含了对根路径的处理；
            return path1 + path2
        else:
            return path1 + '/' + path2

    @staticmethod
    def __is_outer_path_contained(container_outer_path: str, contained_outer_path: str) -> bool:
        """检查外部路径 contained_outer_path 是否包含在外部路径 container_outer_path 中；

        Args:
            container_outer_path: 容器外部路径；
            contained_outer_path: 被包含的外部路径；

        Returns:
            如果 contained_outer_path 包含在 container_outer_path 中，返回 True，否则返回 False；
        """
        # 将路径转换为绝对路径
        container_outer_path = os.path.abspath(container_outer_path)
        contained_outer_path = os.path.abspath(contained_outer_path)
        # 获取相对路径
        rel_path = os.path.relpath(contained_outer_path, container_outer_path)
        # 如果相对路径不以 '..' 开头，则 contained_path 包含在 container_path 中
        return not rel_path.startswith('..') and not os.path.isabs(rel_path)

    def __copy_file_from_outside(self, outer_path: str, inner_path: list) -> None:
        """向指定路径以复制的方式添加一个外部文件（包含文件名）（非覆盖式）；

        Warnings:
            * 这里只支持处理普通文件；

        Notes:
            * 如果内部路径存在，则抛出异常；

        Args:
            outer_path: 外部路径；
            inner_path: 列表路径；

        Raises:
            FileNotFoundError: 如果外部路径不存在；
            IsADirectoryError: 如果外部路径存在但不对应一个文件（而是一个目录）；
            InvalidOperation: 如果外部路径包含根路径；
            InvalidCurrentDirOperation: 如果列表路径是当前路径；
            DirOfPathNotExists: 如果列表路径所在的目录不存在；
            PathExists: 如果内部路径已经存在；
            其他由外部文件操作引发的异常也可能发生；
        """
        def copy_file_from_outside_help(src_file_path: str) -> None:
            """复制外部指定文件到实体文件集目录（目标文件名是hash_value）；

            Warnings:
                ·目标文件名必须是不存在的，否则在Windows中会导致异常；

            Args:
                src_file_path: 外部的源文件路径名，对应的必须是一个文件；

            Raises:
                其他由外部文件操作引发的异常也可能发生；
            """
            tmp_dir = self._entity_files_dir
            shutil.copy(src_file_path, tmp_dir)
            os.rename(os.path.join(tmp_dir, os.path.basename(src_file_path)),
                      os.path.join(self._entity_files_dir, file_id))

        # 条件检查；
        if not os.path.exists(outer_path):
            raise FileNotFoundError(f"外部路径'{outer_path}'不存在")
        if not os.path.isfile(outer_path):
            raise IsADirectoryError(f"外部路径'{outer_path}'存在但不对应一个文件")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation(f"不允许将外部路径包含根路径")
        if not inner_path:
            raise InvalidCurrentDirOperation(f"该列表路径不能是当前路径")
        if not self._dir_tree_handler.is_path_exists(inner_path[:-1]):
            raise DirOfPathNotExists(f"列表路径'{inner_path}'所在的目录不存在")
        if self._dir_tree_handler.is_path_exists(inner_path):  # 如果目标路径是存在的；
            raise PathExists(f"路径'{inner_path}'已经存在，不能覆盖它")

        # 计算该文件的散列值；
        file_id = FileHashCalculator.calculate_file_hash(outer_path)
        # 检查该文件的散列值是否已经有了；
        if self.is_file_exist_via_file_id(file_id):  # 如果有，则增加引用；
            self._file_quote_count_manager.add_quote_count_for_id(file_id)
        else:  # 如果没有，则复制该文件到实体文件集目录并创建引用；
            copy_file_from_outside_help(outer_path)
            self._file_quote_count_manager.create_quote_count_for_id(file_id)
        # 增加该文件并填上file_id；
        self._dir_tree_handler.create_file(inner_path)
        self._dir_tree_handler.set_file_hash(inner_path, file_id)

    def __copy_dir_from_outside(self, outer_path: str, inner_path: list) -> None:
        """向指定路径以复制的方式添加一个外部目录（包含目录名）（非覆盖式）；

        Warnings:
            * 现在只能处理目录和普通文件，不能处理别的比如链接之类的东西，现在的做法是略过它们；

        Notes:
            * 如果内部路径存在，则抛出异常；

        Args:
            outer_path: 外部路径；
            inner_path: 列表路径；

        Raises:
            FileNotFoundError: 如果外部路径不存在；
            NotADirectoryError: 如果外部路径存在但不对应一个目录；
            InvalidOperation: 如果外部路径包含根路径；
            InvalidCurrentDirOperation: 如果列表路径是当前路径；
            DirOfPathNotExists: 如果列表路径所在的目录不存在；
            PathExists: 如果内部路径已经存在；
            其他由外部文件操作引发的异常也可能发生；
        """
        # 条件检查；
        if not os.path.exists(outer_path):
            raise FileNotFoundError(f"外部路径'{outer_path}'不存在")
        if not os.path.isdir(outer_path):
            raise NotADirectoryError(f"外部路径'{outer_path}'存在但不对应一个目录")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation(f"不允许将外部路径包含根路径")
        if not inner_path:
            raise InvalidCurrentDirOperation(f"该列表路径不能是当前路径")
        if not self._dir_tree_handler.is_path_exists(inner_path[:-1]):
            raise DirOfPathNotExists(f"列表路径'{inner_path}'所在的目录不存在")
        if self._dir_tree_handler.is_path_exists(inner_path):  # 如果目标路径是存在的；
            raise PathExists(f"路径'{inner_path}'已经存在，不能覆盖它")

        # 创建一个目录结点；
        self._dir_tree_handler.mkdir(inner_path)
        # 遍历目录中的内容；
        for entry in os.listdir(outer_path):  # 对于既不是目录也不是普通文件的东西，这里直接忽略；
            full_path = os.path.join(outer_path, entry)
            if os.path.isdir(full_path):  # 如果是一个目录，递归调用自己；
                self.__copy_dir_from_outside(full_path, inner_path + [entry])
            elif os.path.isfile(full_path):  # 如果是一个文件，调用self.__copy_file_from_outside进行处理；
                self.__copy_file_from_outside(full_path, inner_path + [entry])

    def __copy_file_to_outside(self, inner_path: list, outer_path: str) -> None:
        """向外部指定路径以复制的方式添加内部文件（非覆盖式）；

        Args:
            inner_path: 列表路径；
            outer_path: 外部路径；

        Raises:
            PathNotExists: 如果列表路径不存在；
            PathIsNotFile: 如果列表路径存在但不对应一个文件；
            InvalidOperation: 如果外部路径包含根路径；
            FileNotFoundError: 如果外部路径所在的目录不存在；
            FileExistsError: 如果外部路径存在；
            FileIDNotFound: 如果列表路径存在而且对应一个文件但这个文件却没有file_id；
            其他由外部文件操作引发的异常也可能发生；
        """
        # 条件检查；
        if not self._dir_tree_handler.is_path_exists(inner_path):
            raise PathNotExists(f"列表路径'{inner_path}'不存在")
        if self._dir_tree_handler.is_dir(inner_path):
            raise PathIsNotFile(f"列表路径'{inner_path}'存在但不对应一个文件")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation(f"不允许将外部路径包含根路径")
        if not os.path.exists(os.path.dirname(outer_path)):
            raise FileNotFoundError(f"外部路径'{outer_path}'所在的目录不存在")
        if os.path.exists(outer_path):  # 如果外部路径存在；
            raise FileExistsError(f"外部路径'{outer_path}'已经存在，不能覆盖它")

        file_id = self._dir_tree_handler.get_file_hash(inner_path)  # 获取文件的散列值
        # 将该散列值的文件复制到指定位置；
        shutil.copy(os.path.join(self._entity_files_dir, file_id), os.path.dirname(outer_path))
        os.rename(os.path.join(os.path.dirname(outer_path), file_id), outer_path)

    def __copy_dir_to_outside(self, inner_path: list, outer_path: str) -> None:
        """向外部指定路径以复制的方式添加内部目录（非覆盖式）；

        Notes:
            * 如果这个内部目录中有文件没有file_id，是会抛出异常的；

        Args:
            inner_path: 列表路径；
            outer_path: 外部路径；

        Raises:
            PathNotExists: 如果列表路径不存在；
            PathIsNotDir: 如果列表路径存在但不对应一个目录；
            InvalidOperation: 如果外部路径包含根路径；
            FileNotFoundError: 如果外部路径所在的目录不存在；
            FileExistsError: 如果外部路径存在；
            FileIDNotFound: 如果这个目录中存在一个文件没有file_id；
            其他由外部文件操作引发的异常也可能发生；
        """
        # 条件检查；
        if not self._dir_tree_handler.is_path_exists(inner_path):
            raise PathNotExists(f"列表路径'{inner_path}'不存在")
        if not self._dir_tree_handler.is_dir(inner_path):
            raise PathIsNotDir(f"列表路径'{inner_path}'存在但不对应一个目录")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation(f"不允许将外部路径包含根路径")
        if not os.path.exists(os.path.dirname(outer_path)):
            raise FileNotFoundError(f"外部路径'{outer_path}'所在的目录不存在")
        if os.path.exists(outer_path):  # 如果外部路径存在；
            raise FileExistsError(f"外部路径'{outer_path}'已经存在，不能覆盖它")

        # 创建一个目录
        os.mkdir(outer_path)
        # 获得目录的内容；
        contents = self._dir_tree_handler.get_dir_content(inner_path)
        # 遍历目录；
        for item in contents:
            path_tmp = inner_path + [item]
            if not self._dir_tree_handler.is_dir(path_tmp):  # 如果是一个文件，将它复制到目录中；
                self.__copy_file_to_outside(path_tmp, os.path.join(outer_path, item))
            else:  # 如果是一个目录，递归调用自己；
                self.__copy_dir_to_outside(path_tmp, os.path.join(outer_path, item))

    def __add_quote_count_for_files_in_dir(self, dir_path: list) -> None:
        """对目录中的文件递归的增加引用计数；

        Raises:
            PathNotExists: 如果该列表路径不存在；
            PathIsNotDir: 如果该列表路径存在但不对应一个目录；
        """
        # 条件检查；
        if not self._dir_tree_handler.is_path_exists(dir_path):
            raise PathNotExists(f"列表路径'{dir_path}'不存在")
        if not self._dir_tree_handler.is_dir(dir_path):
            raise PathIsNotDir(f"列表路径'{dir_path}'存在但不对应一个目录")

        # 获得目录的内容
        contents = self._dir_tree_handler.get_dir_content(dir_path)
        # 遍历目录
        for item in contents:
            path_tmp = dir_path + [item]
            if not self._dir_tree_handler.is_dir(path_tmp):  # 如果是一个文件，增加它的引用计数
                file_id = self._dir_tree_handler.get_file_hash(path_tmp)
                self._file_quote_count_manager.add_quote_count_for_id(file_id)
            else:  # 如果是一个目录，递归调用自己
                self.__add_quote_count_for_files_in_dir(path_tmp)

    def __sub_quote_count_for_files_in_dir(self, dir_path: list) -> None:
        """对目录中的文件递归的减少引用计数；

        Raises:
            PathNotExists: 如果该列表路径不存在；
            PathIsNotDir: 如果该列表路径存在但不对应一个目录；
        """
        # 条件检查；
        if not self._dir_tree_handler.is_path_exists(dir_path):
            raise PathNotExists(f"列表路径'{dir_path}'不存在")
        if not self._dir_tree_handler.is_dir(dir_path):
            raise PathIsNotDir(f"列表路径'{dir_path}'存在但不对应一个目录")

        # 获得目录的内容；
        contents = self._dir_tree_handler.get_dir_content(dir_path)
        # 遍历目录；
        for item in contents:
            path_tmp = dir_path + [item]
            if not self._dir_tree_handler.is_dir(path_tmp):  # 如果是一个文件，减少它的引用计数（当减为 0 时，将这个实体文件删除）；
                file_id = self._dir_tree_handler.get_file_hash(path_tmp)
                if self._file_quote_count_manager.sub_quote_count_for_id(file_id):
                    os.remove(os.path.join(self._entity_files_dir, file_id))
            else:  # 如果是一个目录，递归调用自己；
                self.__sub_quote_count_for_files_in_dir(path_tmp)

    # 后续添加
    def __copy_dir_from_outside_ex(self, outer_path: str, inner_path: list, type_filter: list) -> None:
        """向指定路径以复制的方式添加一个外部目录（包含目录名）, 只添加指定后缀的文件（非覆盖式）；

        Warnings:
            * 现在只能处理目录和普通文件，不能处理别的比如链接之类的东西，现在的做法是略过它们；

        Notes:
            * 如果内部路径存在，则抛出异常；

        Args:
            outer_path: 外部路径；
            inner_path: 列表路径；

        Raises:
            FileNotFoundError: 如果外部路径不存在；
            NotADirectoryError: 如果外部路径存在但不对应一个目录；
            InvalidOperation: 如果外部路径包含根路径；
            InvalidCurrentDirOperation: 如果列表路径是当前路径；
            DirOfPathNotExists: 如果列表路径所在的目录不存在；
            PathExists: 如果内部路径已经存在；
            其他由外部文件操作引发的异常也可能发生；
        """
        # 条件检查；
        if not os.path.exists(outer_path):
            raise FileNotFoundError(f"外部路径'{outer_path}'不存在")
        if not os.path.isdir(outer_path):
            raise NotADirectoryError(f"外部路径'{outer_path}'存在但不对应一个目录")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation(f"不允许将外部路径包含根路径")
        if not inner_path:
            raise InvalidCurrentDirOperation(f"该列表路径不能是当前路径")
        if not self._dir_tree_handler.is_path_exists(inner_path[:-1]):
            raise DirOfPathNotExists(f"列表路径'{inner_path}'所在的目录不存在")
        if self._dir_tree_handler.is_path_exists(inner_path):  # 如果目标路径是存在的；
            raise PathExists(f"路径'{inner_path}'已经存在，不能覆盖它")

        # 创建一个目录结点；
        self._dir_tree_handler.mkdir(inner_path)
        # 遍历目录中的内容；
        for entry in os.listdir(outer_path):  # 对于既不是目录也不是普通文件的东西，这里直接忽略；
            full_path = os.path.join(outer_path, entry)
            if os.path.isdir(full_path):  # 如果是一个目录，递归调用自己；
                self.__copy_dir_from_outside_ex(full_path, inner_path + [entry], type_filter)
            elif os.path.isfile(full_path):  # 如果是一个文件，且满足相应的扩展名, 调用self.__copy_file_from_outside进行处理；
                if (os.path.basename(full_path)).split('.')[-1].lower() in type_filter:
                    self.__copy_file_from_outside(full_path, inner_path + [entry])

    def __copy_dir_to_outside_ex(self, inner_path: list, outer_path: str, type_filter: list) -> None:
        """向外部指定路径以复制的方式添加内部目录, 只添加指定后缀的文件（非覆盖式）；

        Notes:
            * 如果这个内部目录中有文件没有file_id，是会抛出异常的；

        Args:
            inner_path: 列表路径；
            outer_path: 外部路径；

        Raises:
            PathNotExists: 如果列表路径不存在；
            PathIsNotDir: 如果列表路径存在但不对应一个目录；
            InvalidOperation: 如果外部路径包含根路径；
            FileNotFoundError: 如果外部路径所在的目录不存在；
            FileExistsError: 如果外部路径存在；
            FileIDNotFound: 如果这个目录中存在一个文件没有file_id；
            其他由外部文件操作引发的异常也可能发生；
        """
        # 条件检查；
        if not self._dir_tree_handler.is_path_exists(inner_path):
            raise PathNotExists(f"列表路径'{inner_path}'不存在")
        if not self._dir_tree_handler.is_dir(inner_path):
            raise PathIsNotDir(f"列表路径'{inner_path}'存在但不对应一个目录")
        if self.__is_outer_path_contained(outer_path, self._root_dir):
            raise InvalidOperation(f"不允许将外部路径包含根路径")
        if not os.path.exists(os.path.dirname(outer_path)):
            raise FileNotFoundError(f"外部路径'{outer_path}'所在的目录不存在")
        if os.path.exists(outer_path):  # 如果外部路径存在；
            raise FileExistsError(f"外部路径'{outer_path}'已经存在，不能覆盖它")

        # 创建一个目录
        os.mkdir(outer_path)
        # 获得目录的内容；
        contents = self._dir_tree_handler.get_dir_content(inner_path)
        # 遍历目录；
        for item in contents:
            path_tmp = inner_path + [item]
            if not self._dir_tree_handler.is_dir(path_tmp):  # 如果是一个文件，且满足指定的后缀, 将它复制到目录中；
                if path_tmp[-1].split('.')[-1].lower() in type_filter:
                    self.__copy_file_to_outside(path_tmp, os.path.join(outer_path, item))
            else:  # 如果是一个目录，递归调用自己；
                self.__copy_dir_to_outside_ex(path_tmp, os.path.join(outer_path, item), type_filter)

    # 提供给外部的方法
    def store_change(self):
        """在退出前将对目录树的操作、引用计数操作保存；

        Notes:
            * 这里有一个很有意思的地方，即使忘了保存，也没什么用户集看到的引用计数和实际的引用计数不一致的问题。
              唯一的问题似乎只是，引用计数不为0的文件可能已经被删除了，引用计数为0的文件可能还在（我们看到这是非常开心的！）；
        """
        self._dir_tree_handler.store_change()
        self._file_quote_count_manager.store_change()

    def get_current_dir_path(self) -> str:
        """返回当前目录；"""
        return self.__convert_list_path_to_inner_path(self._dir_tree_handler.get_current_dir_path())

    def is_path_exists(self, path: str) -> bool:
        """查询指定路径的文件或目录是否存在；

        Raises:
            InvalidPath: 如果路径是非法的；
        """
        path_list = self.__convert_inner_path_to_list_path(path)
        return self._dir_tree_handler.is_path_exists(path_list)

    def chdir(self, dir_path: str) -> None:
        """切换当前目录；

        Raises:
            InvalidPath: 如果路径是非法的；
            PathNotExists: 如果该路径不存在；
            PathIsNotDir: 如果该路径存在但不对应一个目录；
        """
        dir_path_list = self.__convert_inner_path_to_list_path(dir_path)
        self._dir_tree_handler.chdir(dir_path_list)

    def get_metadata_of_path(self, path: str) -> dict:
        """查看指定路径的文件或目录的元数据；

        Raises:
            InvalidPath: 如果路径是非法的；
            PathNotExists: 如果该路径不存在；
        """
        path = self.__convert_inner_path_to_list_path(path)
        return self._dir_tree_handler.get_metadata_of_path(path)

    def modify_metadata_of_path(self, path: str, metadata: dict) -> None:
        """修改指定路径的文件或目录的元数据；

        Notes:
            * 这里传入的 metadata 会覆盖原来的；

        Raises:
            InvalidPath: 如果路径是非法的；
            PathNotExists: 如果该路径不存在；
        """
        path = self.__convert_inner_path_to_list_path(path)
        self._dir_tree_handler.modify_metadata_of_path(path, metadata)

    def get_dir_content(self, dir_path: str) -> list:
        """查看指定路径的目录的内容；

        Returns:
            以 list 形式返回目录中的文件名和目录名；

        Raises:
            InvalidPath: 如果路径是非法的；
            PathNotExists: 如果该路径不存在；
            PathIsNotDir: 如果该路径存在但不对应一个目录；
        """
        dir_path = self.__convert_inner_path_to_list_path(dir_path)
        return self._dir_tree_handler.get_dir_content(dir_path)

    def get_file_content(self, file_path: str, is_binary: bool = True, start: int = 0, size: int = None) -> Union[bytes, str]:
        """查看指定路径的文件的指定范围的内容（bytes、str）；

        Notes:
            * 如果文件很大，最好分多次请求完成，不要一次读取太多；
            * 这里 start 用于 seek，size 用于 read；
            * 当 size 为 None 时，意味着从 start 一直读到文件末尾；
            * 这里的文件内容读取的行为和 seek、read 是一样的；

        Args:
            file_path: 待读取的文件名；
            is_binary: 是否以二进制的形式读取；
            start: 指定读取的起始位置（0 表示开始）；
            size: 指定读取的大小（None 表示一直到末尾）；

        Returns:
            和 is_binary 对应，以 bytes 或 str 的形式返回指定内容；

        Raises:
            InvalidPath: 如果路径是非法的；
            PathNotExists: 如果该路径不存在；
            PathIsNotFile: 如果该路径存在但不对应一个文件（而是一个目录）；
            FileIDNotFound: 如果该路径存在且是一个文件但没有file_id；
            ValueError: 如果请求的范围不合适；
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
        """向指定路径以复制的方式添加一个外部（即一个本身不在该虚拟文件系统中的）文件或目录（原来的文件或目录是不受影响的）（非覆盖式）；

        Notes:
            * 在使用前应检查内部路径是否存在；
            * 如果内部路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果内部路径是非法的；
            InvalidOperation: 如果外部路径包含根目录；
            FileNotFoundError: 如果外部路径不存在；
            InvalidOperation: 如果外部路径包含根路径；
            InvalidCurrentDirOperation: 如果内部路径是当前路径；
            DirOfPathNotExists: 如果内部路径所在的目录不存在；
            PathExists: 如果内部路径已经存在；
            其他由外部文件操作引发的异常也可能发生；
        """
        # 条件检查；
        if self.__is_outer_path_contained(outer_path, self._root_dir):  # 检查外部路径中是否包含根目录；
            raise InvalidOperation("外部路径不能和根目录相关")

        inner_path_list = self.__convert_inner_path_to_list_path(inner_path)
        if os.path.isfile(outer_path):  # 如果是一个文件
            self.__copy_file_from_outside(outer_path, inner_path_list)
        else:  # 如果是一个目录
            self.__copy_dir_from_outside(outer_path, inner_path_list)

    def move_from_outside(self, outer_path: str, inner_path: str) -> None:
        """向指定路径以移动的方式添加一个外部文件或目录（原来的文件或目录被删除）（非覆盖式）；

        Notes:
            * 在使用前应检查内部路径是否存在；
            * 如果内部路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果内部路径是非法的；
            InvalidOperation: 如果外部路径包含根目录；
            FileNotFoundError: 如果外部路径不存在；
            InvalidOperation: 如果外部路径包含根路径；
            InvalidCurrentDirOperation: 如果内部路径是当前路径；
            DirOfPathNotExists: 如果内部路径所在的目录不存在；
            PathExists: 如果内部路径已经存在；
            其他由外部文件操作引发的异常也可能发生；
        """
        self.copy_from_outside(outer_path, inner_path)
        # 删除原文件或目录
        if os.path.isfile(outer_path):
            os.remove(outer_path)
        else:
            shutil.rmtree(outer_path)

    def copy_to_outside(self, inner_path: str, outer_path: str) -> None:
        """将指定路径的文件或目录复制到外部的指定路径（非覆盖式）；

        Notes:
            * 在使用前应当检查外部路径是否存在；
            * 如果外部路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果内部路径是非法的；
            PathNotExists: 如果内部路径不存在；
            InvalidOperation: 如果外部路径包含根路径；
            FileNotFoundError: 如果外部路径所在的目录不存在；
            FileExistsError: 如果外部路径存在；
            FileIDNotFound: 如果内部路径存在而且对应一个文件但这个文件却没有file_id；
            其他由外部文件操作引发的异常也可能发生；
        """
        inner_path_list = self.__convert_inner_path_to_list_path(inner_path)
        if not self._dir_tree_handler.is_dir(inner_path_list):  # 如果是一个文件
            self.__copy_file_to_outside(inner_path_list, outer_path)
        else:  # 如果是一个目录
            self.__copy_dir_to_outside(inner_path_list, outer_path)

    def move(self, src_path: str, dst_path: str) -> None:
        """在内部（即在该虚拟文件系统中的）移动一个文件或目录（这就包括了重命名）（非覆盖式）；

        Notes:
            * 在使用前应检查目标路径是否存在；
            * 如果目标路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果源路径或目标路径是非法的；
            PathExists: 如果目标路径已经存在；
            InvalidOperation: 如果目标路径包含源路径；
            InvalidCurrentDirOperation: 如果源路径或者目标路径是当前路径，或源路径包含当前路径；
            PathNotExists: 如果源路径不存在，或目标路径所在的目录不存在；
            InvalidNamingConvention: 如果待创建的结点的名称是空的或者其中包含‘/’；
        """
        # 条件检查；
        src_path_list = self.__convert_inner_path_to_list_path(src_path)
        dst_path_list = self.__convert_inner_path_to_list_path(dst_path)
        if self._dir_tree_handler.is_path_exists(dst_path_list):  # 如果目标路径存在；
            raise PathExists(f"目标路径'{dst_path}'已经存在，不能覆盖它")

        self._dir_tree_handler.move(src_path_list, dst_path_list)

    def copy(self, src_path: str, dst_path: str) -> None:
        """在内部复制一个文件或目录；

        Notes:
            * 在使用前应检查目标路径是否存在；
            * 如果目标路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果源路径或目标路径是非法的；
            PathExists: 如果目标路径已经存在；
            InvalidOperation: 如果目标路径包含源路径；
            InvalidCurrentDirOperation: 如果源路径或者目标路径是当前路径，或源路径包含当前路径；
            PathNotExists: 如果源路径不存在，或目标路径所在的目录不存在；
            InvalidNamingConvention: 如果待创建的结点的名称是空的或者其中包含‘/’；
        """
        # 条件检查；
        src_path_list = self.__convert_inner_path_to_list_path(src_path)
        dst_path_list = self.__convert_inner_path_to_list_path(dst_path)
        if self._dir_tree_handler.is_path_exists(dst_path_list):  # 如果目标路径存在;
            raise PathExists(f"目标路径'{dst_path}'已经存在，不能覆盖它")

        # 复制结点（必须放在处理引用计数前面，因为要使用其中的异常处理）；
        self._dir_tree_handler.copy(src_path_list, dst_path_list)
        # 处理引用计数；
        if not self._dir_tree_handler.is_dir(src_path_list):  # 如果是一个文件，增加其引用计数；
            file_id = self._dir_tree_handler.get_file_hash(src_path_list)
            self._file_quote_count_manager.add_quote_count_for_id(file_id)
        else:  # 如果是一个目录，递归的增加其中文件的引用计数；
            self.__add_quote_count_for_files_in_dir(src_path_list)

    def delete(self, path: str) -> None:
        """在内部删除一个文件或目录；

        Raises:
            InvalidPath: 如果该路径是非法的；
            InvalidCurrentDirOperation: 如果该路径是当前路径；
            PathNotExists: 如果该路径不存在；
        """
        # 条件检查
        if path == '':  # 如果该路径是当前路径
            raise InvalidCurrentDirOperation(f"在删除操作中，待删除路径是当前路径，这是不允许的")

        path_list = self.__convert_inner_path_to_list_path(path)
        # 处理文件引用计数；
        if not self._dir_tree_handler.is_dir(path_list):  # 如果是一个文件，减少其引用计数（当减为 0 时，将这个实体文件删除）；
            file_id = self._dir_tree_handler.get_file_hash(path_list)
            if self._file_quote_count_manager.sub_quote_count_for_id(file_id):
                os.remove(os.path.join(self._entity_files_dir, file_id))
        else:  # 如果是一个目录，递归减少引用计数；
            self.__sub_quote_count_for_files_in_dir(path_list)
        # 删除结点
        self._dir_tree_handler.delete(path_list)

    def mkdir(self, path: str) -> None:
        """在内部新建一个目录（非覆盖式）；

        Notes:
            * 在使用前应检查该路径是否存在；
            * 如果该路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果该路径是非法的；
            PathExists: 如果该路径已经存在；
            InvalidCurrentDirOperation: 如果该路径对应当前路径；
            InvalidNamingConventionError: 如果待创建结点的名称中包含“/”；
            DirOfPathNotExists: 如果该路径所在的目录是不存在的；
        """
        # 条件检查；
        path_list = self.__convert_inner_path_to_list_path(path)
        if self._dir_tree_handler.is_path_exists(path_list):  # 如果路径存在;
            raise PathExists(f"路径'{path}'已经存在，不能覆盖它")

        self._dir_tree_handler.mkdir(path_list)

    def is_file_exist_via_file_id(self, file_id: str) -> bool:
        """查询指定散列值的文件是否存在；

        Notes:
            * 可以考虑一下，要不要做成和引用计数管理器相关的，而不是和实体文件集目录相关的（这是值得考虑的）；
        """
        return os.path.exists(os.path.join(self._entity_files_dir, file_id))

    def add_file_via_hash_value(self, path: str, file_id: str) -> None:
        """向指定路径添加指定散列值的文件（非覆盖式）；

        Notes:
            * 在使用前应检查目标路径是否存在；
            * 如果目标路径存在，则抛出异常；

        Raises:
            PathExists: 如果该路径已经存在；
            InvalidOperation: 如果该散列值文件不存在；
            InvalidCurrentDirOperation: 如果该路径对应当前路径；
            InvalidNamingConventionError: 如果待创建结点的名称中包含“/”；
            DirOfPathNotExists: 如果该路径所在的目录是不存在的；
        """
        # 条件检查；
        path_list = self.__convert_inner_path_to_list_path(path)
        if self._dir_tree_handler.is_path_exists(path_list):  # 如果路径存在；
            raise PathExists(f"路径'{path}'已经存在，不能覆盖它")
        if not self.is_file_exist_via_file_id(file_id):  # 如果该散列值文件不存在；
            raise InvalidOperation(f"该散列值'{file_id}'的文件不存在")

        # 增加该文件（必须放在处理引用计数前面，因为要使用其中的异常处理）；
        self._dir_tree_handler.create_file(path_list)
        self._dir_tree_handler.set_file_hash(path_list, file_id)
        # 增加文件的引用；
        self._file_quote_count_manager.add_quote_count_for_id(file_id)

    # ·文件复制、移动操作易用版
    def simple_copy_from_outside(self, outer_path: str, inner_dir: str, inner_dst_name: str = None) -> None:
        """向指定路径以复制的方式添加一个外部（即一个本身不在该虚拟文件系统中的）文件或目录（原来的文件或目录是不受影响的）（非覆盖式）；

        Notes:
            * 在使用前应检查内部路径是否存在；
            * 如果内部路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果内部路径是非法的；
            InvalidOperation: 如果外部路径包含根目录；
            FileNotFoundError: 如果外部路径不存在；
            InvalidOperation: 如果外部路径包含根路径；
            InvalidCurrentDirOperation: 如果内部路径是当前路径；
            DirOfPathNotExists: 如果内部路径所在的目录不存在；
            PathExists: 如果内部路径已经存在；
            其他由外部文件操作引发的异常也可能发生；
        """
        if not inner_dst_name:
            self.copy_from_outside(outer_path, self.__join_two_inner_paths(inner_dir, os.path.basename(outer_path)))
        else:
            self.copy_from_outside(outer_path, self.__join_two_inner_paths(inner_dir, inner_dst_name))

    def simple_move_from_outside(self, outer_path: str, inner_dir: str, inner_dst_name: str = None) -> None:
        """向指定路径以移动的方式添加一个外部文件或目录（原来的文件或目录消失）（非覆盖式）；

        Notes:
            * 在使用前应检查内部路径是否存在；
            * 如果内部路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果内部路径是非法的；
            InvalidOperation: 如果外部路径包含根目录；
            FileNotFoundError: 如果外部路径不存在；
            InvalidOperation: 如果外部路径包含根路径；
            InvalidCurrentDirOperation: 如果内部路径是当前路径；
            DirOfPathNotExists: 如果内部路径所在的目录不存在；
            PathExists: 如果内部路径已经存在；
            其他由外部文件操作引发的异常也可能发生；
        """
        if not inner_dst_name:
            self.move_from_outside(outer_path, self.__join_two_inner_paths(inner_dir, os.path.basename(outer_path)))
        else:
            self.move_from_outside(outer_path, self.__join_two_inner_paths(inner_dir, inner_dst_name))

    def simple_copy_to_outside(self, inner_path: str, outer_dir: str, outer_dst_name: str = None) -> None:
        """将指定路径的文件或目录复制到外部的指定路径（覆盖式）；

        Raises:
            InvalidPath: 如果内部路径是非法的；
            PathNotExists: 如果内部路径不存在；
            InvalidOperation: 如果外部路径包含根路径；
            FileNotFoundError: 如果外部路径所在的目录不存在；
            FileIDNotFound: 如果内部路径存在而且对应一个文件但这个文件却没有file_id；
            其他由外部文件操作引发的异常也可能发生；
        """
        if not outer_dst_name:
            self.copy_from_outside(inner_path, os.path.join(outer_dir, os.path.basename(inner_path)))
        else:
            self.copy_from_outside(inner_path, os.path.join(outer_dir, outer_dst_name))

    def simple_move(self, src_path: str, dst_dir: str, dst_name: str = None) -> None:
        """在内部（即在该虚拟文件系统中的）移动一个文件或目录（这就包括了重命名）（非覆盖式）；

        Notes:
            * 在使用前应检查目标路径是否存在；
            * 如果目标路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果源路径或目标路径是非法的；
            PathExists: 如果目标路径已经存在；
            InvalidOperation: 如果目标路径包含源路径；
            InvalidCurrentDirOperation: 如果源路径或者目标路径是当前路径，或源路径包含当前路径；
            PathNotExists: 如果源路径不存在，或目标路径所在的目录不存在；
            InvalidNamingConvention: 如果待创建的结点的名称是空的或者其中包含‘/’；
        """
        if not dst_name:
            self.move(src_path, self.__join_two_inner_paths(dst_dir, os.path.basename(src_path)))
        else:
            self.move(src_path, self.__join_two_inner_paths(dst_dir, dst_name))

    def simple_copy(self, src_path: str, dst_dir: str, dst_name: str = None) -> None:
        """在内部复制一个文件或目录；

        Notes:
            * 在使用前应检查目标路径是否存在；
            * 如果目标路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果源路径或目标路径是非法的；
            PathExists: 如果目标路径已经存在；
            InvalidOperation: 如果目标路径包含源路径；
            InvalidCurrentDirOperation: 如果源路径或者目标路径是当前路径，或源路径包含当前路径；
            PathNotExists: 如果源路径不存在，或目标路径所在的目录不存在；
            InvalidNamingConvention: 如果待创建的结点的名称是空的或者其中包含‘/’；
        """
        if not dst_name:
            self.copy(src_path, self.__join_two_inner_paths(dst_dir, os.path.basename(src_path)))
        else:
            self.copy(src_path, self.__join_two_inner_paths(dst_dir, dst_name))

    # 添加功能
    def copy_dir_from_outside_ex(self, outer_path: str, inner_path: str, type_filter: list) -> None:
        """向指定路径以复制的方式添加一个外部目录, 只添加指定后缀的文件（非覆盖式）；

        Notes:
            * 在使用前应检查内部路径是否存在；
            * 如果内部路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果内部路径是非法的；
            InvalidOperation: 如果外部路径包含根目录；
            FileNotFoundError: 如果外部路径不存在；
            NotADirectoryError: 如果外部路径存在不对应一个目录.
            InvalidOperation: 如果外部路径包含根路径；
            InvalidCurrentDirOperation: 如果内部路径是当前路径；
            DirOfPathNotExists: 如果内部路径所在的目录不存在；
            PathExists: 如果内部路径已经存在；
            其他由外部文件操作引发的异常也可能发生；
        """
        # 条件检查；
        if self.__is_outer_path_contained(outer_path, self._root_dir):  # 检查外部路径中是否包含根目录；
            raise InvalidOperation("外部路径不能和根目录相关")

        inner_path_list = self.__convert_inner_path_to_list_path(inner_path)
        self.__copy_dir_from_outside_ex(outer_path, inner_path_list, type_filter)

    def copy_dir_to_outside_ex(self, inner_path: str, outer_path: str, type_filter: list) -> None:
        """将指定路径的文件或目录复制到外部的指定路径（非覆盖式）；

        Notes:
            * 在使用前应当检查外部路径是否存在；
            * 如果外部路径存在，则抛出异常；

        Raises:
            InvalidPath: 如果内部路径是非法的；
            PathNotExists: 如果内部路径不存在；
            PathIsNotDir: 如果内部路径存在但不对应一个目录.
            InvalidOperation: 如果外部路径包含根路径；
            FileNotFoundError: 如果外部路径所在的目录不存在；
            FileExistsError: 如果外部路径存在；
            FileIDNotFound: 如果内部路径存在而且对应一个文件但这个文件却没有file_id；
            其他由外部文件操作引发的异常也可能发生；
        """
        inner_path_list = self.__convert_inner_path_to_list_path(inner_path)
        self.__copy_dir_to_outside_ex(inner_path_list, outer_path, type_filter)

    def compare_two_dir(self, base_dir_path: str, patch_dir_path: str) -> str:
        """比较两个目录的内容.

        以补丁的形式输出 patch_dir_path 相对于 base_dir_path 的内容 (特别地, 如果没有差别, 输出为空)

        Warnings:
                - 这里暂且没去管这种情况: 如果这个目录中有文件是没有 file_id 对应的.

        Args:
            base_dir_path: 作为基准的目录
            patch_dir_path: 和基准目录作比较的目录

        Returns:
            以 补丁 的形式输出 patch_dir_path 相对于 base_dir_path 的差异内容

        Raises:
            PathNotExists: 如果其中有一个路径不存在；
            PathIsNotDir: 如果其中有一个路径存在但不对应一个目录.
        """
        def get_files_in_dir(dir_path: str) -> dict:
            """获得指定目录中的所有文件信息

            Warnings:
                - 这里暂且没去管这种情况: 如果这个目录中有文件是没有 file_id 对应的.

            Returns:
                返回的是一个字典, 字典中的元素的 key 是相对与这个 dir_path 的相对路径, value 是这个文件的 file_id (也就是 hash 值).

            Raises:
                PathNotExists: 如果路径不存在；
                PathIsNotDir: 如果路径存在但不对应一个目录.
            """
            def add_file_info_in_dir(dir_path: str, current_relative_path: str) -> None:
                """将该目录中的文件信息添加到 files_dict 中

                Notes:
                    - 这里的 current_relative_path 是指想要加上的相对路径前缀名, 然后这个目录中的文件的文件路径就是 这个前缀名 + 文件名.
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
        for key in base_dict:
            if key not in patch_dict:
                diff_str += '-' + key + '\n'
            elif base_dict[key] != patch_dict[key]:
                diff_str += '-' + key + '\n'

        # 找出在 patch_dict 中存在但在 base_dict 中不存在的键值对
        for key in patch_dict:
            if key not in base_dict:
                diff_str += '+' + key + '\n'
            elif patch_dict[key] != base_dict[key]:
                diff_str += '+' + key + '\n'

        return diff_str


if __name__ == "__main__":
    """以简单地导入外部目录为例；"""

    # 注：如果要测试，请拷贝下面的代码，在外部的 python 文件中使用；

    root_dir = "VSF_sinber"

    with VirtualFileSystem(root_dir, "sinber") as vfs:
        path = "file_system_"
        if vfs.is_path_exists(path):
            vfs.delete(path)
        vfs.simple_copy_from_outside(path, "")
