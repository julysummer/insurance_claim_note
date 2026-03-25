# 医疗险理赔规则

## 概述

本模块提供医疗险（门诊/住院/慢特病）的理赔规则引擎，包含规则校验和费用计算功能。

## 文件说明

| 文件 | 说明 |
|------|------|
| config.yaml | 产品参数配置 |
| exclusions.json | 除外责任关键词 |
| rules.py | 规则引擎代码 |
| calculation_formula.md | 计算公式说明 |
| requirements.md | 需求说明文档 |
| README.md | 本文件 |

## 快速开始

```python
from rules import MedicalClaimEngine, Policy, Invoice, ClaimInfo
from datetime import date

# 初始化引擎
engine = MedicalClaimEngine()

# 创建保单
policy = Policy(
    policy_no="POL001",
    status="有效",
    effective_date=date(2025, 1, 1),
    expiry_date=date(2026, 1, 1),
    product_code="product_002",
    product_params=engine.get_product_params("product_002")
)

# 创建发票
invoice = Invoice(
    invoice_id="INV001",
    total_amount=580,
    issue_date=date(2025, 3, 15),
    invoicing_party_name="北京医院",
    medical_type="1",
    org_type="三级甲等",
    is_medical_insurance="1",
    fund_pay_amount=400,
    account_pay_amount=50,
    own_pay_amount=130,
    other_pay_amount=0,
    item_detail=[{"item_name": "挂号费", "item_amount": 50}]
)

# 创建理赔申请
claim_info = ClaimInfo(
    policy=policy,
    invoice=invoice,
    accident_date=date(2025, 3, 15),
    report_date=date(2025, 3, 15)
)

# 执行规则校验
result = engine.check_all_rules(claim_info)

print(f"状态: {result.status}")
print(f"赔付: {result.payment}元")
```

## 规则清单

共11条规则，详见 `requirements.md`

## 计算公式

详见 `calculation_formula.md`
