# 寿险理赔规则

## 概述

本模块提供寿险（定期寿险、终身寿险）的理赔规则引擎。

## 文件说明

| 文件 | 说明 |
|------|------|
| config.yaml | 产品参数配置 |
| exclusions.json | 除外责任关键词 |
| rules.py | 规则引擎代码 |

## 快速开始

```python
from rules import LifeClaimEngine, Policy, ClaimInfo
from datetime import date

engine = LifeClaimEngine()

policy = Policy(
    policy_no="POL001",
    status="有效",
    effective_date=date(2023, 1, 1),
    expiry_date=date(2026, 1, 1),
    product_code="product_001",
    product_params=engine.get_product_params("product_001")
)

claim_info = ClaimInfo(
    policy=policy,
    claim_type="death",
    death_date=date(2025, 6, 1),
    report_date=date(2025, 6, 5),
    death_reason="因病身故",
    has_death_certificate=True
)

result = engine.check_all_rules(claim_info)
print(f"状态: {result.status}, 赔付: {result.payment}元")
```

## 计算公式

```
赔付金额 = 保额（policy.coverageAmount）
```
