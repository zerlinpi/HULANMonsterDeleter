# Photo Monster Deleter

一个 Windows 桌面文件删除动画工具。当前版本已经把原来的怪兽角色替换为两张内置照片，并把照片做成轻微摇摆、行走、冲击和离场动画。右键选择文件或文件夹后，程序会播放动画并在明确确认后执行删除。

## 当前版本变化

- 使用仓库内 `embedded_photos.py` 内置的两张照片，不需要另外复制人物图片。
- 第一张全身照片用于行走、指向、冲击、离场动画。
- 第二张近景照片用于确认气泡头像和打包后的 EXE 图标。
- 动画不是 AI 生成的新姿势，而是对你提供照片做旋转、缩放、位移和镜像形成的动态效果，因此人物外观不会被重新绘制。
- 支持文件和文件夹右键菜单。
- 默认执行**真实永久删除**：文件使用 `Path.unlink()`，文件夹使用 `shutil.rmtree()`。
- 增加磁盘根目录、Windows、Program Files、用户主目录等关键路径保护。
- 如果只是双击运行 `main.py`/EXE，没有通过右键菜单传入文件路径，则进入演示模式，不会删除文件。
- 按 `Esc` 可以退出。

> **警告：默认删除模式为 permanent，删除后不会进入回收站，也无法通过本程序恢复。**

## 代码结构

```text
HULANMonsterDeleter/
├─ main.py                 # PyQt6 UI、照片动画、右键菜单、删除流程
├─ delete_engine.py        # 永久删除/回收站删除与安全路径保护
├─ embedded_photos.py      # 两张照片的 base64 数据
├─ requirements.txt
├─ build.bat               # Windows 一键打包
├─ tools/
│  └─ make_icon.py         # 从第二张照片生成 EXE 图标
└─ assets/                 # 原有 BGM / 爆炸等资源
```

## 首次拉取

```bat
git clone https://github.com/zerlinpi/HULANMonsterDeleter.git
cd HULANMonsterDeleter
python -m pip install -r requirements.txt
```

本地测试：

```bat
python main.py
```

上面是演示模式，不会删除文件。

测试某个指定文件时：

```bat
python main.py "C:\Users\你的用户名\Desktop\test.txt"
```

程序仍会要求你点击屏幕位置并再次确认，然后才会删除该路径。

## 一键打包 EXE

在仓库目录执行：

```bat
build.bat
```

脚本会自动：

1. 安装 `requirements.txt` 中的依赖；
2. 从第二张内置照片生成 `assets\generated\photo_character.ico`；
3. 使用 PyInstaller 打包；
4. 输出：

```text
dist\MonsterDeleter.exe
```

也可以手动执行：

```bat
python tools\make_icon.py
python -m PyInstaller --noconfirm --clean --onefile --windowed --name MonsterDeleter --icon assets\generated\photo_character.ico --add-data "assets;assets" --hidden-import send2trash main.py
```

## 注册右键菜单

运行一次：

```bat
dist\MonsterDeleter.exe
```

程序会在当前 Windows 用户下注册：

```text
召唤照片角色删除
```

之后可以：

1. 在资源管理器中右键文件或文件夹；
2. 选择“召唤照片角色删除”；
3. 在屏幕上点击目标所在位置；
4. 在确认框中选择“永久删除”；
5. 删除动作与爆炸效果同步执行。

注册表写入 `HKEY_CURRENT_USER`，正常情况下不需要管理员权限。

## 如果想改成回收站模式

默认：

```text
MONSTER_DELETE_MODE=permanent
```

临时切换为回收站模式：

```bat
set MONSTER_DELETE_MODE=trash
python main.py "C:\path\to\test.txt"
```

打包后的 EXE 同样支持这个环境变量：

```bat
set MONSTER_DELETE_MODE=trash
dist\MonsterDeleter.exe "C:\path\to\test.txt"
```

## Git 更新

以后仓库有新修改时：

```bat
cd HULANMonsterDeleter
git pull origin main
```

然后重新打包：

```bat
build.bat
```

如果本地已经修改过代码，建议先检查：

```bat
git status
git diff
```

再决定提交、暂存或合并后执行 `git pull`。

## 删除安全限制

永久删除前，`delete_engine.py` 会拒绝下列高风险目标：

- 磁盘根目录，例如 `C:\`；
- Windows/SystemRoot 及其内部路径；
- Program Files / Program Files (x86) 及其内部路径；
- ProgramData 及其内部路径；
- 当前用户主目录本身。

用户主目录中的普通文件（例如桌面测试文件）不受“主目录本身”保护限制，因此仍可以按正常流程永久删除。

这些限制用于防止把娱乐动画误操作成系统破坏工具。普通用户文件、桌面测试文件、非关键目录中的普通文件夹仍可正常永久删除。
