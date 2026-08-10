# HULAN Monster Deleter — AI Action Pose Edition

Windows 桌面文件删除动画工具。这个版本不再使用“同一张照片旋转/缩放”伪装走路、指向和踢腿，而是要求先根据原始照片生成三组真正不同的人物动作图：

```text
原始照片
  ↓
AI 生成人物走路图
  ↓
AI 生成人物指东西图
  ↓
AI 生成人物踢腿图
  ↓
透明 PNG 动作资源
  ↓
PyQt6 播放 + 删除文件
```

> 默认删除模式仍为 `permanent`，确认后会真实永久删除目标文件/文件夹，不进入回收站。

## V2 动画标准

应用读取：

```text
assets/character/generated/
├─ walk/
│  ├─ frame_001.png
│  └─ frame_002.png
├─ point/
│  ├─ frame_001.png
│  └─ frame_002.png
└─ kick/
   ├─ frame_001.png
   └─ frame_002.png
```

动作本身必须来自不同的 AI 生成姿势。运行时只添加很轻微的呼吸、上下浮动和冲击缩放，不再拿原照片大幅旋转冒充不同动作。

## 代码结构

```text
main.py                           # 入口
ai_main.py                        # 删除动画流程、右键菜单、音效、真实删除触发
character_animator.py             # AI 动作 PNG 加载与播放
app_ui.py                         # 气泡和确认按钮
delete_engine.py                  # 永久删除/回收站模式与关键目录保护
embedded_photos.py                # 原始两张参考照片
tools/comfyui_generate_poses.py   # 调用本机 ComfyUI 自动生成 walk/point/kick
tools/validate_character_assets.py# 打包前检查透明 PNG 动作资源
build.bat                         # 一键 PyInstaller 打包
```

## 1. 拉取代码

```bat
git clone https://github.com/zerlinpi/HULANMonsterDeleter.git
cd HULANMonsterDeleter
python -m pip install -r requirements.txt
```

如果你在开发分支测试 V2：

```bat
git fetch origin
git checkout ai-action-poses-v2
```

## 2. 启动 ComfyUI

默认脚本连接：

```text
http://127.0.0.1:8188
```

先正常启动本机 ComfyUI，例如：

```bat
cd C:\你的ComfyUI目录
python main.py --listen 127.0.0.1 --port 8188
```

保持这个窗口运行。

## 3. 查看可用 checkpoint

回到本仓库目录执行：

```bat
python tools\comfyui_generate_poses.py
```

如果 ComfyUI 中有多个 checkpoint，脚本会列出可用名称，然后指定其中一个：

```bat
python tools\comfyui_generate_poses.py --checkpoint "你的模型文件名.safetensors"
```

脚本会：

1. 从 `embedded_photos.py` 导出第一张全身参考照；
2. 缩放参考图后上传到本机 ComfyUI；
3. 使用 img2img 分别生成 walk / point / kick；
4. 每个动作默认生成两个关键姿势；
5. 要求纯绿色背景；
6. 自动抠掉绿色并保存透明 PNG；
7. 写入 `assets\character\generated\...`。

默认生成参数：

```text
steps   = 30
cfg     = 5.5
denoise = 0.74
sampler = dpmpp_2m
scheduler = karras
```

如果人物身份保留较好但动作变化不足，可以提高：

```bat
python tools\comfyui_generate_poses.py --checkpoint "模型.safetensors" --denoise 0.78
```

如果动作够了但脸变化太大，可以降低：

```bat
python tools\comfyui_generate_poses.py --checkpoint "模型.safetensors" --denoise 0.68
```

## 4. 检查 AI 动作资源

```bat
python tools\validate_character_assets.py
```

需要看到：

```text
[OK] AI character assets validated
```

验证器会拒绝：

- walk / point / kick 缺失；
- 图片尺寸过小；
- 没有 Alpha 通道；
- 实际仍是不透明背景的 PNG。

## 5. 本地运行

演示模式，不删除文件：

```bat
python main.py
```

测试指定文件：

```bat
python main.py "C:\Users\你的用户名\Desktop\test.txt"
```

程序仍会显示确认按钮后才执行删除。

## 6. 打包 EXE

```bat
build.bat
```

`build.bat` 会先检查 AI 动作资源。缺少 walk / point / kick 时会停止打包，避免再次把旧的低质量动画发布出去。

成功后：

```text
dist\MonsterDeleter.exe
```

## 7. Git 提交生成后的动作图片

如果你希望以后 `git clone` 后不需要重新生成图片，可以把生成后的透明 PNG 一并提交：

```bat
git add assets\character\generated
git commit -m "Add generated walk point kick character poses"
git push
```

## 删除模式

默认：

```text
MONSTER_DELETE_MODE=permanent
```

永久模式：

- 普通文件：`Path.unlink()`
- 普通目录：`shutil.rmtree()`

临时改为回收站：

```bat
set MONSTER_DELETE_MODE=trash
python main.py "C:\path\to\test.txt"
```

## 安全保护

`delete_engine.py` 会拒绝明显高风险目标，包括：

- 磁盘根目录；
- Windows/SystemRoot 及内部路径；
- Program Files / Program Files (x86) 及内部路径；
- ProgramData 及内部路径；
- 当前用户主目录本身。

普通桌面文件和非关键目录中的普通文件夹仍可按确认流程删除。

## 更高质量的人脸一致性

仓库自带生成脚本只使用 ComfyUI 内置节点，因此兼容性高，但它是基础 img2img 方案。若后续要进一步提高“脸必须高度一致”，推荐把生成环节升级为 PuLID / InstantID / IPAdapter FaceID + OpenPose ControlNet；应用侧 `walk/point/kick` 目录格式无需再修改。
