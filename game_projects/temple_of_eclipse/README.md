# 幽冥神殿 (Temple of Eclipse)

3D 动作冒险 RPG — 考验复杂美术设计的游戏项目

## 游戏简介

玩家深入幽冥神殿，面对石像守卫和火焰幽灵，击败所有敌人后唤醒神殿守护者 BOSS。BOSS 拥有三阶段战斗，越战越狂暴。

## 操作

| 按键 | 功能 |
|------|------|
| WASD | 移动 |
| 鼠标 | 视角 |
| 左键 | 近战攻击（30伤害） |
| Q | 范围魔法（40伤害，消耗20魔法） |
| 空格 | 闪避（无敌帧） |
| ESC | 暂停/鼠标解锁 |

## 运行

```bash
# 方式1：batch 脚本
run_game.bat

# 方式2：直接运行
"D:\GameTools\Godot\Godot_v4.4-stable_win64_console.exe" --path .
```

## 3D 资产

10 个 Blender 程序化生成的 FBX 模型：

| 模型 | 部件数 | 用途 |
|------|--------|------|
| adventurer.fbx | 13 | 玩家角色 |
| stone_guardian.fbx | 8 | 石像守卫敌人 |
| flame_wraith.fbx | 11 | 火焰幽灵敌人 |
| boss.fbx | 10 | BOSS神殿守护者 |
| column.fbx | 5 | 神殿石柱 |
| statue.fbx | 4 | 守卫雕像 |
| arch.fbx | 14 | 拱门 |
| altar.fbx | 7 | 祭坛 |
| decorative_pillar.fbx | 25 | 装饰柱 |
| torch.fbx | 5 | 火把 |

## 技术栈

- Godot 4.4 stable
- Blender 4.2.1 LTS（3D 模型生成）
- GDScript

## 评价

详见 [EVALUATION.md](EVALUATION.md) — 115/120 (95.8%)