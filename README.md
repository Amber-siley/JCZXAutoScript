# 交错战线 AutoScript

交错战线手游自动化脚本，基于 ADB + cv2 模板匹配 + PaddleOCR。Windows，Python >=3.14。

## 快速开始

```powershell
# 激活虚拟环境
.\.venv\Scripts\activate

# 安装依赖
uv pip install -e .

# 运行 Textual TUI
python -m jczx.jczxCli

# 构建可执行文件
python build.py
```

## 功能

| 功能 | 说明 |
|------|------|
| 检测式启动游戏 | 自动启动游戏 App，首次启动自动签到 |
| 自动交付订单 | 自定义订单类型，支持自动合成 |
| 周本虚影微晶 | 阿瑞斯/宙斯虚影，支持预设队伍 |
| 虚影刷好感 | 自定义队伍和次数 |
| 竞技场挑战 | OCR 战力识别，可设置战力阈值 |
| 矿场配队计算 | 计算配队方案得分 |

## 架构

| 入口 | 命令 |
|------|------|
| TUI（推荐） | `python -m jczx.jczxCli` |
| GUI（旧版） | `python jczx/jczx.py` |

旧版 PyQt6 GUI 已不再维护，推荐使用新版 Textual TUI。

## 模拟器推荐

雷电模拟器，开启 ADB 本地调试。MuMu 需开桥接模式。

已测试分辨率：1920×1080 (dpi 280)、2400×1080 (dpi 320)。

## 构造软链接（从仓库根目录运行时）

```
mklink /J resources jczx\resources
```

## 配置文件

| 文件 | 用途 |
|------|------|
| `jczx/Config/Config.txt` | 全局设置（日志、线程、ADB 路径、调试截图模式） |
| `jczx/Config/MainMenu.txt` | 任务定义和设置（支持 `type: file` 引入外部配置） |
| `jczx/Config/Queues.txt` | 任务队列定义（顺序执行多个任务） |
| `TASK_CONFIG_GUIDE.md` | 任务配置完整文档 |

## TUI 功能

| 功能 | 说明 |
|------|------|
| 任务列表 + 启停 | 左侧任务卡片，勾选启动/停止 |
| 任务设置 | 右侧设置面板，动态表单 |
| 任务队列 | 创建/编辑/删除队列，顺序执行，拖拽排序，与单任务互斥 |
| 调试截图 | 两种模式：连续截图（simple）/ 标注截图（annotated），配置控制 |

## 调试截图

`jczx/Config/Config.txt` 中设置 `debug.screenshot.mode`：
- `off` — 关闭
- `simple` — 每次截图保存至 `screenHistory/N.png`
- `annotated` — 标注匹配/点击/滑动/OCR 位置后保存

合成视频（需安装 ffmpeg）：

```powershell
# PNG 序列 → MP4（10 fps）
ffmpeg -framerate 10 -i screenHistory/%d.png -c:v libx264 -pix_fmt yuv420p output.mp4

# 指定起始序号
ffmpeg -start_number 1 -framerate 10 -i screenHistory/%d.png -c:v libx264 -pix_fmt yuv420p output.mp4

# 图片序号不连续时
ffmpeg -framerate 10 -pattern_type glob -i "screenHistory/*.png" -c:v libx264 -pix_fmt yuv420p output.mp4
```

## 快捷键

| 按键 | 功能 |
|------|------|
| `q` | 退出程序 |
| `ctrl+l` | 清空日志控制台 |
| `ctrl+shift+c` | 复制全部日志到剪贴板 |

## 依赖

```
opencv-python>=4.13
onnxruntime>=1.26
paddleocr>=3.7
textual>=8.2
uiautomator2>=3.5
requests>=2.34
fastapi>=0.136
uvicorn>=0.49
```

## 构建

```powershell
python build.py
```

交互式选择 `pyinstaller`（快，包大）或 `nuitka`（慢，包小）。
