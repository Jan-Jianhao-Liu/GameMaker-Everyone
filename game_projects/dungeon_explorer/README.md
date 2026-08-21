# 地牢探险者 (Dungeon Explorer)

3D 动作 RPG 迷你游戏，由智能体游戏施工团队产出。

## 快速开始

```bash
# 用 Godot 4.4 运行游戏
"D:\GameTools\Godot\Godot_v4.4-stable_win64_console.exe" --path .

# 用 Blender 重新生成 3D 模型
"D:\GameTools\blender-4.2.1-windows-x64\blender.exe" --background --python generate_models.py
```

## 操作

| 按键 | 功能 |
|------|------|
| W/A/S/D | 移动 |
| 鼠标 | 视角 |
| 左键 | 攻击 |
| E | 交互 |
| ESC | 释放/锁定鼠标 |

## 游戏目标

消灭每个关卡的所有敌人，通关全部 3 个关卡。

| 关卡 | 敌人 | 拾取物 |
|------|------|--------|
| 1    | 3    | 3      |
| 2    | 5    | 4      |
| 3    | 7    | 5      |

## 项目结构

```
dungeon_explorer/
├── project.godot           # Godot 项目配置
├── scenes/
│   └── main.tscn           # 主场景
├── scripts/
│   ├── player.gd           # 玩家控制器
│   ├── enemy.gd            # 敌人 AI
│   └── game_manager.gd     # 游戏管理器
├── assets/
│   └── models/             # Blender 生成的 FBX 模型
│       ├── player.fbx
│       ├── enemy.fbx
│       ├── dungeon.fbx
│       ├── sword.fbx
│       └── pickup.fbx
├── generate_models.py      # Blender 模型生成脚本
└── EVALUATION.md           # 游戏评价报告
```

## 评价得分

**88 / 100** — 良好 (B+)

详见 [EVALUATION.md](EVALUATION.md)