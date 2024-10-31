<div align="center"><a name="readme-top"></a>

[![][mycat]][link-to-homepage]

[mycat]: assets/images/mycat.jpg
[link-to-homepage]: https://github.com/SinbereeGit

# 虚拟文件系统

> 注：此文件由 *Copilot* 根据项目生成 😄。

该项目提供了一个虚拟文件系统，支持*串行多用户*和*去重存储*。它由（系统根目录，指定用户ID）唯一确定。

</div>

## 功能

- **串行多用户支持**：允许多个用户串行使用系统。
- **去重存储**：确保重复文件只存储一次。
- **虚拟文件系统**：提供具有各种操作的虚拟文件系统。

## 用法

### 示例

使用 `with` 语句：

```python
with VirtualFileSystem("root_dir", "user_id") as vfs:
    # 打印当前目录的内容
    vfs.get_dir_content("")
    # 切换到特定目录
    vfs.chdir("dir_name")
    # 执行其他操作...
```

使用 `try` 语句：

```python
try:
    vfs = VirtualFileSystem("root_dir", "user_id")
    # 打印当前目录的内容
    vfs.get_dir_content("")
    # 切换到特定目录
    vfs.chdir("dir_name")
    # 执行其他操作...
except Exception as e:
    # 处理异常
finally:
    vfs.store_change()
```

## 警告

- 根目录的所有内容必须由此模块生成。
- 同一根目录在同一时间只能运行一个系统实例（不支持并发）。
- 调用 `store_change` 后不要使用实例，因为其资源已被释放。
- 内部路径名目前没有严格的命名限制。

## 注意事项

- 初始化详情在 `__init__` 的文档字符串中。
- 如果不使用 `with`，请使用 `try` 并在 `finally` 中调用 `self.store_change`。
- 不支持并行。
- 支持 Unix/Linux、Windows，原则上也支持 MacOS。
- 内部文件路径使用 Unix 格式，外部路径是操作系统特定的。
- 文件操作是非覆盖性的。
- 目录结构如下：

  ```txt
  根目录
  ├── 引用计数文件
  ├── 实体文件目录
  │   ├── 哈希文件 1
  │   ├── 哈希文件 2
  │   └── ...
  └── 用户空间目录
      ├── 用户目录 1
      │   └── 用户目录树文件
      ├── 用户目录 2
      │   └── 用户目录树文件
      └── ...
  ```

## 模块

### `virtual_file_system.py`

提供主要的 `VirtualFileSystem` 类，具有各种文件系统操作。

### `_dir_tree_handler.py`

处理由此模块创建的对应于 JSON 文件的目录树。

### `errors.py`

定义文件系统中使用的各种异常。

### `_utils/count_manager.py`

维护指定标识符的计数，支持创建和增减操作。

### `_utils/file_hash.py`

使用 SHA-256 算法生成文件的哈希值。

### `tools/simple_ui.py`

提供用于使用文件系统的简单命令行界面。

## 许可证

此项目根据 [GPL-3.0](LICENSE) 许可证授权。
