# 医疗险理赔规则引擎
# 统一字段标准 - 含中文说明

import json
import yaml
from datetime import date
from typing import Dict, List, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Policy:
    """保单信息（来自保单系统）"""
    policy_number: str           # 保单号
    mpolicy_number: str          # 主保单号
    policy_name: str             # 保单名称
    insurance_type: str          # 保险险种
    insurance_product_code: str  # 保险产品代码
    insurance_product_name: str  # 保险产品名称
    policy_start_date: date      # 保单开始日期
    policy_end_date: date        # 保单结束日期
    policy_status: str = "有效"  # 保单状态
    product_params: Dict = field(default_factory=dict)  # 条款配置参数


@dataclass
class Invoice:
    """发票信息（来自发票Schema）"""
    invoice_id: str             # 电子票据ID
    invoice_code: str            # 电子票据代码
    invoice_number: str          # 电子票据号码
    total_amount: float         # 总金额
    issue_date: date             # 开票日期
    invoicing_party_name: str    # 开票单位名称（医院名称）
    payer_party_name: str        # 交款人名称（患者姓名）
    medical_type: str            # 医疗类别：1-门诊，2-住院，3-慢特病
    medical_date: date           # 就诊日期
    in_hospital_date: date = None  # 住院日期
    out_hospital_date: date = None  # 出院日期
    org_type: str = ""           # 医疗机构类型
    is_medical_insurance: str = "0"  # 是否医保票据：0-否，1-是
    fund_pay_amount: float = 0   # 医保统筹基金支付
    account_pay_amount: float = 0  # 个人账户支付
    own_pay_amount: float = 0   # 个人现金支付
    selfpayment_amount: float = 0  # 个人自付
    selfpayment_cost: float = 0  # 个人自费
    other_pay_amount: float = 0  # 其他支付
    item_detail: List[Dict] = field(default_factory=list)  # 费用明细


@dataclass
class ClaimInfo:
    """理赔申请信息"""
    policy: Policy
    invoice: Invoice
    accident_date: date          # 事故/就诊日期
    report_date: date            # 报案日期
    claim_type: str              # 理赔类型
    claimed_invoice_ids: List[str] = field(default_factory=list)  # 已理赔发票列表
    claimed_this_year: float = 0  # 年度累计赔付金额


@dataclass
class RuleResult:
    """规则校验结果"""
    rule_id: str                 # 规则编号
    rule_name: str               # 规则名称
    passed: bool                 # 是否通过
    message: str = ""            # 详细信息


@dataclass
class ClaimResult:
    """理赔处理结果"""
    status: str                  # 处理状态：PASS/REJECT/MANUAL_REVIEW
    payment: float = 0          # 赔付金额
    rejection_reasons: List[str] = field(default_factory=list)  # 拒赔原因
    rule_results: List[RuleResult] = field(default_factory=list)  # 规则校验结果
    calculation: Dict = field(default_factory=dict)  # 费用计算明细


class MedicalClaimEngine:
    """医疗险理赔规则引擎"""

    def __init__(self):
        base_path = Path(__file__).parent
        with open(base_path / "config.yaml", 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        with open(base_path / "exclusions.json", 'r', encoding='utf-8') as f:
            self.exclusions_config = json.load(f)

        # 除外关键词映射（类型 -> 关键词列表）
        self.excluded_keywords = self.exclusions_config.get("exclusions", {})
        # 医院黑名单
        self.hospital_blacklist = self.exclusions_config.get("hospital_blacklist", [])
        # 医院等级白名单
        self.hospital_levels = self.exclusions_config.get("hospital_levels", [])

    def get_product_params(self, product_code: str) -> Dict:
        """获取产品条款参数

        Args:
            product_code: 保险产品代码

        Returns:
            产品参数字典，包含免赔额、赔付比例、限额等
        """
        default = self.config.get("default", {})
        products = self.config.get("products", {})
        if product_code in products:
            return {**default, **products[product_code]}
        return default

    def check_all_rules(self, claim_info: ClaimInfo) -> ClaimResult:
        """执行所有规则校验

        Args:
            claim_info: 理赔申请信息

        Returns:
            理赔处理结果
        """
        policy = claim_info.policy
        invoice = claim_info.invoice
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
        if invoice.issue_date < policy.policy_start_date:
            rejection_reasons.append("发票日期早于保单生效日期")
            result.rule_results.append(RuleResult("rule_002", "保障期间", False))
        elif invoice.issue_date > policy.policy_end_date:
            rejection_reasons.append("发票日期晚于保单终止日期")
            result.rule_results.append(RuleResult("rule_002", "保障期间", False))
        else:
            result.rule_results.append(RuleResult("rule_002", "保障期间", True))

        # rule_003: 报案时效校验
        reporting_days = params.get("reporting_days", 30)
        days = (claim_info.report_date - claim_info.accident_date).days
        if days > reporting_days:
            rejection_reasons.append(f"报案时间距事故日期已超过{reporting_days}天")
            result.rule_results.append(RuleResult("rule_003", "报案时效", False))
        else:
            result.rule_results.append(RuleResult("rule_003", "报案时效", True))

        # ========== 第二阶段：发票校验 ==========
        # rule_004: 发票唯一性校验
        if claim_info.invoice.invoice_id in claim_info.claimed_invoice_ids:
            rejection_reasons.append("发票已理赔或重复")
            result.rule_results.append(RuleResult("rule_004", "发票唯一性", False))
        else:
            result.rule_results.append(RuleResult("rule_004", "发票唯一性", True))

        # rule_005: 发票金额校验
        if invoice.total_amount <= 0:
            rejection_reasons.append("发票金额必须大于0")
            result.rule_results.append(RuleResult("rule_005", "发票金额", False))
        else:
            result.rule_results.append(RuleResult("rule_005", "发票金额", True))

        # rule_006: 费用勾稽校验
        calculated = sum([
            invoice.fund_pay_amount or 0,
            invoice.account_pay_amount or 0,
            invoice.own_pay_amount or 0,
            invoice.other_pay_amount or 0
        ])
        if abs(invoice.total_amount - calculated) >= 1:
            rejection_reasons.append("费用勾稽不平")
            result.rule_results.append(RuleResult("rule_006", "费用勾稽", False))
        else:
            result.rule_results.append(RuleResult("rule_006", "费用勾稽", True))

        # ========== 第三阶段：医疗机构校验 ==========
        # rule_007: 医院等级校验
        if not any(level in invoice.org_type for level in self.hospital_levels):
            rejection_reasons.append("医院等级不符合要求")
            result.rule_results.append(RuleResult("rule_007", "医院等级", False))
        else:
            result.rule_results.append(RuleResult("rule_007", "医院等级", True))

        # rule_008: 医院类型校验
        if any(kw in invoice.invoicing_party_name for kw in self.hospital_blacklist):
            rejection_reasons.append("医院在黑名单范围内")
            result.rule_results.append(RuleResult("rule_008", "医院类型", False))
        else:
            result.rule_results.append(RuleResult("rule_008", "医院类型", True))

        # ========== 第四阶段：动态参数校验 ==========
        # rule_009: 等待期校验（仅疾病医疗）
        if invoice.medical_type == "1":  # 门诊无等待期
            result.rule_results.append(RuleResult("rule_009", "等待期", True))
        else:
            waiting_period = params.get("disease_waiting_period", 0)
            if waiting_period > 0:
                days = (invoice.issue_date - policy.policy_start_date).days
                if days < waiting_period:
                    rejection_reasons.append(f"投保后仅{days}天，等待期需{waiting_period}天")
                    result.rule_results.append(RuleResult("rule_009", "等待期", False))
                else:
                    result.rule_results.append(RuleResult("rule_009", "等待期", True))
            else:
                result.rule_results.append(RuleResult("rule_009", "等待期", True))

        # rule_010: 责任匹配校验
        coverage_map = {"1": "outpatient", "2": "hospitalization", "3": "special_clinic"}
        required = coverage_map.get(invoice.medical_type)
        covered = params.get("covered_types", [])
        if required and required not in covered:
            rejection_reasons.append("就诊类型不在保障范围内")
            result.rule_results.append(RuleResult("rule_010", "责任匹配", False))
        else:
            result.rule_results.append(RuleResult("rule_010", "责任匹配", True))

        # ========== 第五阶段：除外责任校验 ==========
        # rule_011: 除外责任校验
        exclusions = params.get("exclusions", [])
        excluded_found = False
        for exc in exclusions:
            keywords = self.excluded_keywords.get(exc.get("type", ""), [])
            for item in invoice.item_detail:
                item_name = item.get("item_name", "")
                if any(kw in item_name for kw in keywords):
                    rejection_reasons.append(f"费用项目【{item_name}】属于除外责任: {exc.get('type', '')}")
                    excluded_found = True
                    break
            if excluded_found:
                break

        if excluded_found:
            result.rule_results.append(RuleResult("rule_011", "除外责任", False))
        else:
            result.rule_results.append(RuleResult("rule_011", "除外责任", True))

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

    # ========== 费用计算（核心公式） ==========
    def _calculate_payment(self, claim_info: ClaimInfo) -> tuple:
        """医疗险理赔费用计算

        核心公式：
        最终赔付 = MIN(初步赔付, 单次限额, 年度剩余限额)
        初步赔付 = MAX(0, 可赔基数 - 免赔额) × 赔付比例

        字段来源说明：
        - 可赔基数(有医保): invoice.ownPayAmount（个人现金支付）
        - 可赔基数(无医保): invoice.totalAmount（发票总金额）
        - 免赔额: policy.product_params.deductible
        - 赔付比例: policy.product_params.coinsuranceRate
        - 单次限额: policy.product_params.singleLimit
        - 年度限额: policy.product_params.annualLimit
        - 年度已赔: claim_info.claimedThisYear

        边界情况处理：
        1. 个人现金支付为空时，使用发票总金额
        2. 费用明细中有除责项目时，排除该部分
        3. 部分项目有限额时，按项目分别计算
        4. 分段免赔：不同额度区间适用不同免赔额

        Args:
            claim_info: 理赔申请信息

        Returns:
            (赔付金额, 计算明细字典)
        """
        policy = claim_info.policy
        invoice = claim_info.invoice
        params = policy.product_params
        calculation_steps = []

        # ========== 1. 确定可赔基数 + 匹配责任类型 ==========
        # 根据发票的医疗类别确定责任类型
        medical_type = invoice.medical_type  # 1-门诊, 2-住院, 3-慢特病
        coverage_map = {"1": "outpatient", "2": "hospitalization", "3": "special_clinic"}
        claim_type = coverage_map.get(medical_type, "unknown")
        covered = params.get("covered_types", [])

        # 检查责任是否在保障范围内
        if claim_type not in covered:
            return 0, {"错误": f"责任类型{claim_type}不在保障范围内", "保障范围": covered}

        # 根据责任类型确定计算参数
        if claim_type == "outpatient":
            # 门诊责任
            base_source = "门诊"
            daily_limit = params.get("daily_limit")  # 日限额
            if daily_limit:
                calculation_steps.append({"步骤": "门诊日限额", "值": daily_limit})
        elif claim_type == "hospitalization":
            # 住院责任（可能有年免赔）
            base_source = "住院"
        elif claim_type == "special_clinic":
            # 特殊门诊（可能有限额）
            base_source = "特殊门诊"

        # 个人现金支付为空时使用发票总金额
        if invoice.is_medical_insurance == "1":
            # 有医保：优先使用个人现金支付
            base_amount = invoice.own_pay_amount
            base_source = "invoice.ownPayAmount"
            # 个人现金支付为0或None时，使用发票总金额
            if not base_amount or base_amount <= 0:
                base_amount = invoice.total_amount
                base_source = "invoice.totalAmount (个人现金支付为空)"
        else:
            # 无医保：使用发票总金额
            base_amount = invoice.total_amount
            base_source = "invoice.totalAmount（无医保）"

        calculation_steps.append({"步骤": "确定基数", "值": base_amount, "来源": base_source})

        # ========== 2. 扣除除责项目 ==========
        # 检查费用明细中的除外项目
        excluded_amount = 0
        excluded_items = []
        if invoice.item_detail:
            exclusions = params.get("exclusions", [])
            for item in invoice.item_detail:
                item_name = item.get("item_name", "")
                item_amount = item.get("item_amount", 0)
                is_excluded = False
                for exc in exclusions:
                    keywords = self.excluded_keywords.get(exc.get("type", ""), [])
                    if any(kw in item_name for kw in keywords):
                        is_excluded = True
                        break
                if is_excluded:
                    excluded_amount += item_amount
                    excluded_items.append(item_name)

        # 可赔基数 = 总金额 - 除责金额
        if excluded_amount > 0:
            base_amount = max(0, base_amount - excluded_amount)
            calculation_steps.append({"步骤": "扣除除责", "值": -excluded_amount, "项目": excluded_items})

        # ========== 3. 扣除免赔额 ==========
        # 分段免赔：不同额度区间适用不同免赔额
        deductible = params.get("deductible", 0)
        deductible_type = params.get("deductible_type", "次免赔")

        if deductible_type == "分段免赔":
            # 分段免赔逻辑
            # 例如：0-1000元免赔100元，1000-5000元免赔200元，5000元以上免赔500元
            tiered_deductible = params.get("tiered_deductible", [
                {"min": 0, "max": 1000, "deductible": 100},
                {"min": 1000, "max": 5000, "deductible": 200},
                {"min": 5000, "max": float('inf'), "deductible": 500}
            ])
            for tier in tiered_deductible:
                if tier["min"] <= base_amount < tier["max"]:
                    deductible = tier["deductible"]
                    break

        after_deductible = max(0, base_amount - deductible)
        calculation_steps.append({"步骤": "扣除免赔额", "免赔额": deductible, "免赔类型": deductible_type, "扣减后": after_deductible})

        # ========== 4. 计算初步赔付 ==========
        coinsurance_rate = params.get("coinsurance_rate", 1.0)
        payment = after_deductible * coinsurance_rate

        calculation_steps.append({"步骤": "初步赔付", "公式": "扣减后×赔付比例", "值": payment})

        # ========== 5. 检查项目限额 ==========
        # 部分项目有限额（如特定药品、检查项目）
        item_limits = params.get("item_limits", {})
        item_deductions = 0
        if invoice.item_detail and item_limits:
            for item in invoice.item_detail:
                item_name = item.get("item_name", "")
                item_amount = item.get("item_amount", 0)
                for limit_key, limit_value in item_limits.items():
                    if limit_key in item_name:
                        if item_amount > limit_value:
                            item_deductions += (item_amount - limit_value)

        if item_deductions > 0:
            payment = max(0, payment - item_deductions)
            calculation_steps.append({"步骤": "项目限额扣减", "值": item_deductions, "扣减后": payment})

        # ========== 6. 检查单次限额 ==========
        single_limit = params.get("single_limit", float('inf'))
        payment = min(payment, single_limit)

        # ========== 7. 检查年度限额 ==========
        annual_limit = params.get("annual_limit", float('inf'))
        remaining = annual_limit - claim_info.claimed_this_year
        payment = min(payment, remaining)

        # 确保非负
        payment = max(0, payment)

        # 计算明细
        calculation = {
            "公式": "MIN(初步赔付-项目限额, 单次限额, 年度剩余限额)",
            "初步赔付公式": "MAX(0, 可赔基数 - 免赔额) × 赔付比例",
            "可赔基数": base_amount,
            "可赔基数来源": base_source,
            "除责扣减": excluded_amount,
            "除责项目": excluded_items,
            "免赔额": deductible,
            "免赔额类型": deductible_type,
            "免赔额来源": "policy.product_params.deductible",
            "扣减后": after_deductible,
            "项目限额扣减": item_deductions,
            "赔付比例": coinsurance_rate,
            "赔付比例来源": "policy.product_params.coinsuranceRate",
            "初步赔付": after_deductible * coinsurance_rate,
            "单次限额": single_limit,
            "单次限额来源": "policy.product_params.singleLimit",
            "年度限额": annual_limit,
            "年度限额来源": "policy.product_params.annualLimit",
            "年度已赔": claim_info.claimed_this_year,
            "年度已赔来源": "claim_info.claimedThisYear",
            "年度剩余": remaining,
            "最终赔付": payment,
            "计算步骤": calculation_steps
        }

        return payment, calculation


if __name__ == "__main__":
    # 示例运行
    engine = MedicalClaimEngine()

    # 保单信息（使用实际字段名+中文说明）
    policy = Policy(
        policy_number="POL001",           # 保单号
        mpolicy_number="MPOL001",         # 主保单号
        policy_name="百万医疗险",         # 保单名称
        insurance_type="医疗险",           # 保险险种
        insurance_product_code="product_001",  # 保险产品代码
        insurance_product_name="百万医疗险", # 保险产品名称
        policy_start_date=date(2025, 1, 1),   # 保单开始日期
        policy_end_date=date(2026, 1, 1),     # 保单结束日期
        policy_status="有效",              # 保单状态
        product_params=engine.get_product_params("product_001")  # 条款配置参数
    )

    # 发票信息（使用Schema字段名+中文说明）
    invoice = Invoice(
        invoice_id="INV001",              # 电子票据ID
        invoice_code="011001900111",      # 电子票据代码
        invoice_number="12345678",        # 电子票据号码
        total_amount=580,                 # 总金额
        issue_date=date(2025, 3, 15),     # 开票日期
        invoicing_party_name="北京大学第一医院",  # 开票单位名称
        payer_party_name="张三",           # 交款人名称
        medical_type="1",                 # 医疗类别：1-门诊
        medical_date=date(2025, 3, 15),   # 就诊日期
        org_type="三级甲等",               # 医疗机构类型
        is_medical_insurance="1",         # 是否医保票据：1-是
        fund_pay_amount=400,              # 医保统筹基金支付
        account_pay_amount=50,            # 个人账户支付
        own_pay_amount=130,               # 个人现金支付
        item_detail=[{"item_name": "挂号费", "item_amount": 50}]  # 费用明细
    )

    # 理赔申请信息
    claim_info = ClaimInfo(
        policy=policy,
        invoice=invoice,
        accident_date=date(2025, 3, 15),   # 事故/就诊日期
        report_date=date(2025, 3, 15),    # 报案日期
        claim_type="疾病医疗"              # 理赔类型
    )

    # 执行规则校验
    result = engine.check_all_rules(claim_info)
    print(f"状态: {result.status}, 赔付: {result.payment:.2f}元")
    if result.calculation:
        print("\n计算明细:")
        for k, v in result.calculation.items():
            print(f"  {k}: {v}")
