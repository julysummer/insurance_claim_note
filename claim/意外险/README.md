# 意外险理赔规则

## 概述

本模块提供意外险（意外身故/伤残/医疗/住院津贴）的理赔规则引擎。

## 文件说明

| 文件 | 说明 |
|------|------|
| config.yaml | 产品参数配置 |
| exclusions.json | 除外责任关键词 |
| rules.py | 规则引擎代码 |
| calculation_formula.md | 计算公式说明（含字段来源） |
| requirements.md | 需求说明文档 |
| README.md | 本文件 |

## 快速开始

```python
from rules import AccidentClaimEngine, Policy, Invoice, AccidentInfo, ClaimInfo
from datetime import date

engine = AccidentClaimEngine()

policy = Policy(
    policy_no="POL001",
    status="有效",
    effective_date=date(2025, 1, 1),
    expiry_date=date(2026, 1, 1),
    product_code="product_001",
    product_params=engine.get_product_params("product_001")
)

invoice = Invoice(
    invoice_id="INV001",
    total_amount=2000,
    issue_date=date(2025, 3, 15),
    invoicing_party_name="北京医院",
    medical_type="1",
    org_type="三级甲等",
    is_medical_insurance="1",
    own_pay_amount=500,
    fund_pay_amount=1500,
    account_pay_amount=0,
    other_pay_amount=0,
    in_hospital_date=date(2025, 3, 15),
    out_hospital_date=date(2025, 3, 15),
    item_detail=[{"item_name": "药品费", "item_amount": 2000}]
)

accident_info = AccidentInfo(
    accident_type="意外医疗",
    accident_date=date(2025, 3, 15),
    accident_desc="走路摔倒受伤"
)

claim_info = ClaimInfo(
    policy=policy,
    invoice=invoice,
    accident_info=accident_info,
    report_date=date(2025, 3, 15)
)

result = engine.check_all_rules(claim_info)
print(f"状态: {result.status}, 赔付: {result.payment}元")
```

## 规则清单

共9条规则，详见 `requirements.md`

## 计算公式

详见 `calculation_formula.md`
