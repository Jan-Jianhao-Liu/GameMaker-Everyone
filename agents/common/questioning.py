"""智能体追问规则。

各角色在开始工作前，检查当前项目信息是否充分。
若关键信息缺失或模糊，生成追问并暂停流水线等待用户回答。

追问策略（参考 CodeArts 的 question 工具设计）：
  - designer: 需求太短/模糊时追问游戏类型、目标平台、美术风格、规模
  - supervisor: 契约冲突时追问优先级
  - artist3d: 缺少多边形数/风格指引时追问
  - artist2d: 缺少分辨率/色板时追问
  - coder: 缺少引擎/语言偏好时追问
  - qa: 缺少验收标准时追问

每个追问返回 Question 对象，包含：
  - role: 提问角色
  - header: 简短标题
  - question: 完整问题
  - options: 选项列表（每项 label + description）
  - context: 附加上下文（当前 state 摘要）
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QuestionOption:
    label: str
    description: str = ""


@dataclass
class Question:
    role: str
    header: str
    question: str
    options: list[QuestionOption] = field(default_factory=list)
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "header": self.header,
            "question": self.question,
            "options": [
                {"label": o.label, "description": o.description} for o in self.options
            ],
            "context": self.context,
        }


def _request_is_vague(request: str) -> bool:
    """判断用户需求是否太模糊（太短或缺少关键信息）。"""
    if len(request) < 5:
        return True
    keywords = ["游戏", "game", "rpg", "动作", "策略", "射击", "解谜", "模拟",
                "跳跃", "平台", "休闲", "卡牌", "战棋", "沙盒", "racing"]
    if not any(k in request.lower() for k in keywords):
        return True
    return False


def _missing_genre(request: str) -> bool:
    """是否缺少游戏类型。"""
    genres = ["rpg", "动作", "策略", "射击", "fps", "解谜", "模拟", "经营",
              "平台", "赛车", "恐怖", "休闲", "卡牌", "战棋", "沙盒", "跳跃"]
    return not any(g in request.lower() for g in genres)


def _missing_platform(request: str) -> bool:
    """是否缺少目标平台。"""
    platforms = ["pc", "手机", "移动", "web", "浏览器", "安卓", "ios", "switch"]
    return not any(p in request.lower() for p in platforms)


def _missing_art_style(request: str) -> bool:
    """是否缺少美术风格。"""
    styles = ["写实", "卡通", "像素", "低模", "二次元", "水墨", "赛博",
              "realistic", "cartoon", "pixel", "lowpoly"]
    return not any(s in request.lower() for s in styles)


def designer_question(request: str) -> Question | None:
    """designer 追问：需求模糊时追问关键信息。"""
    if not _request_is_vague(request):

        return None

    return Question(
        role="designer",
        header="需求不够明确",
        question=(
            "你的需求描述比较简短，为了生成更精准的游戏设计文档，请补充以下信息："
        ),
        options=[
            QuestionOption("3D 动作 RPG", "3D视角，动作战斗，角色升级，关卡推进"),
            QuestionOption("2D 平台跳跃", "2D横版，跳跃避障，收集道具，通关"),
            QuestionOption("策略战棋", "回合制，棋盘移动，战术对抗，胜负条件"),
            QuestionOption("休闲模拟经营", "资源管理，建设发展，轻松节奏，长线养成"),
        ],
        context={"request": request[:200]},
    )


def _build_options(missing: list[str]) -> list[QuestionOption]:
    opts = []
    if "游戏类型" in missing:
        opts.extend([
            QuestionOption("动作 RPG", "战斗+升级+关卡推进"),
            QuestionOption("策略/战棋", "回合制战术对抗"),
            QuestionOption("休闲/模拟", "轻松节奏，长线养成"),
        ])
    if "目标平台" in missing:
        opts.extend([
            QuestionOption("PC (Windows)", "桌面端，键鼠操作"),
            QuestionOption("移动端", "手机/平板，触控操作"),
            QuestionOption("Web 浏览器", "无需安装，网页直接玩"),
        ])
    if "美术风格" in missing:
        opts.extend([
            QuestionOption("低多边形 LowPoly", "简洁几何体，适合快速生产"),
            QuestionOption("卡通风格", "明亮色彩，轮廓描边"),
            QuestionOption("像素风格", "复古像素，2D 精灵"),
        ])
    return opts or [QuestionOption("跳过追问", "使用默认配置继续")]


def supervisor_question(state: dict) -> Question | None:
    """supervisor 追问：契约冲突时问优先级。"""
    errors = state.get("errors", [])
    if not errors:
        return None
    if len(errors) >= 3:
        return Question(
            role="supervisor",
            header="契约校验多次失败",
            question=(
                f"契约文档已连续校验失败 {len(errors)} 次。错误包括：\n"
                + "\n".join(f"  - {e}" for e in errors[:3])
                + "\n\n你希望怎么处理？"
            ),
            options=[
                QuestionOption("退回 designer 重新生成", "让策划重新设计"),
                QuestionOption("人工修改后继续", "我手动修改契约文档"),
                QuestionOption("放宽校验标准", "跳过部分校验继续推进"),
            ],
            context={"error_count": len(errors)},
        )
    return None


def artist3d_question(state: dict) -> Question | None:
    """artist3d 追问：缺少风格指引时问。"""
    art_spec = state.get("art_spec", {})
    if not art_spec.get("texture_spec"):
        return Question(
            role="artist3d",
            header="3D 美术风格确认",
            question="即将开始 3D 模型生产。请确认美术风格偏好：",
            options=[
                QuestionOption("低模 + 平面着色", "面数低，flat shading，适合快速生产"),
                QuestionOption("中模 + PBR 材质", "面数适中，PBR 材质，效果较好"),
                QuestionOption("高模 + 雕刻细节", "面数高，细节丰富，生产耗时较长"),
            ],
            context={"asset_count": len(state.get("manifest", {}).get("assets", []))},
        )
    return None


def coder_question(state: dict) -> Question | None:
    """coder 追问：缺少引擎偏好时问。"""
    gdd = state.get("gdd", {})
    if not gdd:
        return None
    if not gdd.get("genre"):
        return Question(
            role="coder",
            header="技术栈确认",
            question="即将开始编写游戏代码。请确认技术栈偏好：",
            options=[
                QuestionOption("Godot 4 + GDScript", "轻量引擎，快速原型"),
                QuestionOption("Unity + C#", "主流商业引擎，生态丰富"),
                QuestionOption("Unreal + C++/蓝图", "3A 级表现，学习曲线陡"),
            ],
        )
    return None


def qa_question(state: dict) -> Question | None:
    """qa 追问：缺少验收标准时问。"""
    build = state.get("build_result", {})
    if build and not build.get("test_criteria"):
        return Question(
            role="qa",
            header="验收标准确认",
            question="即将开始测试。请确认验收标准：",
            options=[
                QuestionOption("基础冒烟测试", "能启动+核心玩法可操作"),
                QuestionOption("完整功能测试", "所有系统功能逐一验证"),
                QuestionOption("性能+功能", "功能测试 + 帧率/内存检测"),
            ],
        )
    return None


_ROLE_QUESTIONS = {
    "designer": lambda state: designer_question(state.get("user_request", "")),
    "supervisor": supervisor_question,
    "artist3d": artist3d_question,
    "coder": coder_question,
    "qa": qa_question,
}


def check_question(role: str, state: dict) -> Question | None:
    """检查指定角色是否需要追问。返回 Question 或 None。"""
    fn = _ROLE_QUESTIONS.get(role)
    if fn is None:
        return None
    return fn(state)


def should_ask(
    role: str, state: dict, already_asked: list[dict] | None = None,
) -> bool:
    """判断角色是否应该追问（且未已问过同样问题）。"""
    already_asked = already_asked or []
    asked_roles = {q.get("role") for q in already_asked}
    if role in asked_roles:
        return False
    return check_question(role, state) is not None
