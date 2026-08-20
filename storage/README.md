# storage

Repository 抽象层。所有持久化通过本层访问，实现类可替换。

## 设计

```
storage/
├── base.py          # Repository 接口定义
├── sqlite_repo.py   # SQLiteRepo（Phase 1-2 默认实现）
└── arcade_repo.py   # ArcadeRepo（Phase 3 迁移，图遍历/关联查询）
```

## 覆盖范围

| 数据 | Phase 1-2 (SQLite) | Phase 3+ (ArcadeDB) |
|---|---|---|
| 任务记忆（agent/action/outcome/lesson） | SQLite 表 | 图节点 Agent-PRODUCED->Task |
| 审计日志 | SQLite 表 | 同左 |
| 工单状态 | SQLite 表 | 图节点 Task |
| 任务锁 | SQLite BEGIN IMMEDIATE | 同左 |
| 速率限制计数 | SQLite 表 | 同左 |

## 迁移触发条件

当智能体需要查询"历史上哪类美术任务失败率最高"这类图遍历/关联查询且 SQL join 写起来痛苦时，迁移到 ArcadeDB。