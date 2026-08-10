# HULAN Monster Deleter — AI Action Pose Edition

Windows 桌面文件删除动画工具。当前版本已经直接包含生成好的真人风格动作帧，不再使用“同一张照片旋转 / 缩放 / 轻微扭曲”来模拟动作。

```text
AI 生成的真实不同姿势
  ├─ walk  × 4
  ├─ point × 3
  └─ kick  × 3
       ↓
运行时去除与画布边缘连通的白色背景
       ↓
透明人物帧
       ↓
PyQt6 逐帧播放
       ↓
确认后触发删除 + 爆炸效果
```

> **警告：默认删除模式为 `permanent`。确认后会真实永久删除目标文件/文件夹，不进入回收站。**

## 当前已经包含的动作资源

仓库内置 10 张动作图：

```text
assets/character/embedded/
├─ walk_01.b64
├─ walk_02.b64
├─ walk_03.b64
├─ walk_04.b64
├─ point_01.b64
├─ point_02.b64
├─ point_03.b64
├─ kick_01.b64
├─ kick_02.b64
└─ kick_03.b64
```

这些 `.b64` 文件是动作图片的文本化封装，方便资源随 Git 仓库和 PyInstaller 一起分发。程序启动时会：

1. 解码图片；
2. 从画布边缘进行白色背景 flood-fill；
3. 只把与边缘连通的白色背景变透明，因此白裙、白袜、白鞋不会被简单全局色键误删；
4. 裁剪透明边缘并统一人物高度；
5. 直接按真实动作图逐帧播放。

`character_animator.py` **不会再给人物增加旋转、呼吸缩放或身体扭曲来伪造新动作**。每个动作帧都对应一张实际生成图。离场时仍会做水平镜像，这是方向切换，不会改变人体姿势。

当前踢腿是 3 个真实姿势：准备 → 抬腿 → 完整侧踢。最后冲击帧会额外停留一个计时周期，让爆炸与 `kick_03` 对齐。以后补 `kick_04` 时可以继续扩展。

## 代码结构

```text
HULANMonsterDeleter/
├─ main.py
├─ ai_main.py                         # UI 流程、右键菜单、动画阶段、删除触发
├─ character_animator.py              # 内置 AI 动作帧解码、抠图和逐帧播放
├─ app_ui.py                          # 气泡与确认按钮
├─ delete_engine.py                   # 永久删除 / 回收站模式与安全保护
├─ embedded_photos.py                 # 原始参考照片资源
├─ assets/
│  └─ character/
│     ├─ embedded/                    # 当前随仓库发布的 10 个动作帧
│     └─ generated/                   # 可选的本地自定义动作覆盖目录
├─ tools/
│  ├─ validate_character_assets.py    # 打包前检查内置动作资源
│  ├─ make_icon.py
│  └─ comfyui_generate_poses.py       # 可选：未来重新生成动作时使用
└─ build.bat
```

## 拉取并运行

首次下载：

```bat
git clone https://github.com/zerlinpi/HULANMonsterDeleter.git
cd HULANMonsterDeleter
python -m pip install -r requirements.txt
```

以后更新：

```bat
git checkout main
git pull origin main
```

**现在不需要启动 ComfyUI，也不需要再次生成图片。**

先检查内置动作：

```bat
python tools\validate_character_assets.py
```

正常输出类似：

```text
[OK] Included AI character assets validated:
  walk: 4 frame(s)
  point: 3 frame(s)
  kick: 3 frame(s)
```

演示模式：

```bat
python main.py
```

演示模式没有目标路径，因此不会删除文件。

测试指定文件：

```bat
python main.py "C:\Users\你的用户名\Desktop\test.txt"
```

程序会在真正删除前显示确认按钮。

## 一键打包 EXE

在仓库根目录执行：

```bat
build.bat
```

打包脚本会自动：

1. 安装依赖；
2. 验证已经随仓库提供的 walk / point / kick 动作资源；
3. 生成 EXE 图标；
4. 用 PyInstaller 打包 `assets`；
5. 输出：

```text
dist\MonsterDeleter.exe
```

不再有“先运行 ComfyUI 生成动作资源”的前置步骤。

## Windows 右键菜单

运行一次程序后，会在当前 Windows 用户下注册文件和目录右键菜单：

```text
召唤 AI 角色删除
```

随后可以在资源管理器中：

1. 右键一个普通文件或文件夹；
2. 选择“召唤 AI 角色删除”；
3. 点击屏幕上的目标位置；
4. 等角色走到目标旁并指向目标；
5. 点击确认；
6. 踢击动作播放到冲击帧时触发爆炸与删除。

## 删除模式

默认：

```text
MONSTER_DELETE_MODE=permanent
```

永久模式：

- 文件：`Path.unlink()`
- 文件夹：`shutil.rmtree()`

临时切换为回收站模式：

```bat
set MONSTER_DELETE_MODE=trash
python main.py "C:\path\to\test.txt"
```

打包后的 EXE 也支持相同环境变量。

## 删除安全保护

`delete_engine.py` 会拒绝明显高风险目标，包括：

- 磁盘根目录；
- Windows / SystemRoot 及其内部路径；
- Program Files / Program Files (x86) 及其内部路径；
- ProgramData 及其内部路径；
- 当前用户主目录本身。

普通桌面文件和非关键目录中的普通文件夹仍可按确认流程删除。

## 未来替换动作资源

如果以后想替换角色，可以直接在：

```text
assets/character/generated/
```

按动作创建：

```text
generated/
├─ walk/
├─ point/
└─ kick/
```

放入 PNG / WebP / JPG 文件。`generated` 中的文件会优先于仓库内置动作资源，代码无需再次改动。

`tools/comfyui_generate_poses.py` 仍保留，但它现在只是**可选的重新生成工具**，不是运行或打包所必需的步骤。
