# 寿险理赔规则引擎
# 统一字段标准 - 含中文说明

import json
import yaml
from datetime import date
from typing import Dict, List
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Policy:
    """保单信息（来自保单系统）"""
    policy_number: str           # 保单号
    mpolicy_number: str        # 主保单号
    policy_name: str           # 保单名称
    insurance_type: str        # 保险险种
    insurance_product_code: str # 保险产品代码
    insurance_product_name: str # 保险产品名称
    policy_start_date: date    # 保单开始日期
    policy_end_date: date      # 保单结束日期
    policy_status: str = "有效" # 保单状态
    product_params: Dict = field(default_factory=dict) # 条款配置参数


@dataclass
class ClaimInfo:
    """理赔申请信息"""
    policy: Policy
    claim_type: str            # 理赔类型：身故/全残
    death_date: date          # 身故日期
    report_date: date         # 报案日期
    death_place: str = ""    # 身故地点
    death_reason: str = ""    # 身故原因
    has_death_certificate: bool = False  # 是否有死亡证明


@dataclass
class RuleResult:
    """规则校验结果"""
    rule_id: str               # 规则编号
    rule_name: str            # 规则名称
    passed: bool              # 是否通过
    message: str = ""         # 详细信息


@dataclass
class ClaimResult:
    """理赔处理结果"""
    status: str                # 处理状态：PASS/REJECT/MANUAL_REVIEW
    payment: float = 0        # 赔付金额
    rejection_reasons: List[str] = field(default_factory=list) # 拒赔原因
    rule_results: List[RuleResult] = field(default_factory=list) # 规则校验结果
    calculation: Dict = field(default_factory=dict) # 费用计算明细


class LifeClaimEngine:
    """寿险理赔规则引擎"""

    def __init__(self):
        base_path = Path(__file__).parent
        with open(base_path / "config.yaml", 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        with open(base_path / "exclusions.json", 'r', encoding='utf-8') as f:
            self.exclusions_config = json.load(f)

    def get_product_params(self, product_code: str) -> Dict:
        """获取产品条款参数"""
        default = self.config.get("default", {})
        products = self.config.get("products", {})
        if product_code in products:
            return {**default, **products[product_code]}
        return default

    def check_all_rules(self, claim_info: ClaimInfo) -> ClaimResult:
        """执行所有规则校验"""
        policy = claim_info.policy
        params = policy.product_params
        result = ClaimResult(status="PASS")
        rejection_reasons = []

        # ========== 第一阶段：保单基础校验 ==========
        # rule_001: 保单状态校验
        if policy.policy_status != "有效":
            rejection_reasons.append(f"保单状态为【{policy.policy_status}】")
            result.rule_results.append(RuleResult("rule_001", "保单状态", False, policy.policy_status))
        else:
            result.rule_results.append(RuleResult("rule_001", "保单状态", True))

        # rule_002: 保障期间校验
        if claim_info.death_date < policy.policy_start_date:
            rejection_reasons.append("身故日期早于保单生效日期")
            result.rule_results.append(RuleResult("rule_002", "保障期间", False))
        elif claim_info.death_date > policy.policy_end_date:
            rejection_reasons.append("身故日期晚于保单终止日期")
            result.rule_results.append(RuleResult("rule_002", "保障期间", False))
        else:
            result.rule_results.append(RuleResult("rule_002", "保障期间", True))

        # rule_003: 报案时效校验
        reporting_days = params.get("reporting_days", 30)
        if (claim_info.report_date - claim_info.death_date).days > reporting_days:
            rejection_reasons.append(f"报案时间距身故日期已超过{reporting_days}天")
            result.rule_results.append(RuleResult("rule_003", "报案时效", False))
        else:
            result.rule_results.append(RuleResult("rule_003", "报案时效", True))

        # ========== 第二阶段：身故原因校验 ==========
        # rule_004: 自杀条款校验（保单生效2年内自杀不赔）
        if "自杀" in claim_info.death_reason:
            days = (claim_info.death_date - policy.policy_start_date).days
            if days < 730:  # 2年
                rejection_reasons.append("保单生效2年内自杀不在保障范围内")
                result.rule_results.append(RuleResult("rule_004", "身故原因", False))
            else:
                result.rule_results.append(RuleResult("rule_004", "身故原因", True))
        else:
            result.rule_results.append(RuleResult("rule_004", "身故原因", True))

        # rule_005: 材料完整性校验
        if not claim_info.has_death_certificate:
            rejection_reasons.append("缺少死亡证明")
            result.rule_results.append(RuleResult("rule_005", "材料完整性", False))
        else:
            result.rule_results.append(RuleResult("rule_005", "材料完整性", True))

        # ========== 第三阶段：责任匹配校验 ==========
        # rule_006: 责任匹配校验
        covered = params.get("covered_types", [])
        if claim_info.claim_type not in covered:
            rejection_reasons.append(f"产品不承保{claim_info.claim_type}责任")
            result.rule_results.append(RuleResult("rule_006", "责任匹配", False))
        else:
            result.rule_results.append(RuleResult("rule_006", "责任匹配", True))

        # ========== 判断结果 ==========
        if rejection_reasons:
            result.status = "REJECT"
            result.rejection_reasons = rejection_reasons
            return result

        # ========== 费用计算 ==========
        payment, calculation = self._calculate_payment(claim_info)
        result.payment = payment
        result.calculation = calculation
        return result

    def _calculate_payment(self, claim_info: ClaimInfo) -> tuple:
        """寿险理赔费用计算

        核心公式：
        赔付金额 = 保额

        字段来源：
        - 保额: policy.product_params.coverageAmount

        Args:
            claim_info: 理赔申请信息

        Returns:
            (赔付金额, 计算明细字典)
        """
        params = claim_info.policy.product_params
        coverage_amount = params.get("coverage_amount", 0)

        calculation = {
            "公式": "保额",
            "保额": coverage_amount,
            "保额来源": "policy.product_params.coverageAmount",
            "最终赔付": coverage_amount
        }

        return coverage_amount, calculation


if __name__ == "__main__":
    engine = LifeClaimEngine()

    policy = Policy(
        policy_number="POL001",
        mpolicy_number="MPOL001",
        policy_name="定期寿险",
        insurance_type="寿险",
        insurance_product_code="product_001",
        insurance_product_name="定期寿险",
        policy_start_date=date(2023, 1, 1),
        policy_end_date=date(2026, 1, 1),
        policy_status="有效",
        product_params=engine.get_product_params("product_001")
    )

    claim_info = ClaimInfo(
        policy=policy,
        claim_type="death",
        death_date=date(2025, 6, 1),
        report_date=date(2025, 6, 5),
        death_place="北京市",
        death_reason="因病身故",
        has_death_certificate=True
    )

    result = engine.check_all_rules(claim_info)
    print(f"状态: {result.status}, 赔付: {result.payment:.2f}元")
    if result.calculation:
        print("\n计算明细:")
        for k, v in result.calculation.items():
            print(f"  {k}: {v}")
