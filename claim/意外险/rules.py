# 意外险理赔规则引擎
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
class Invoice:
    """发票信息（来自发票Schema）"""
    invoice_id: str             # 电子票据ID
    invoice_code: str            # 电子票据代码
    invoice_number: str         # 电子票据号码
    total_amount: float         # 总金额
    issue_date: date             # 开票日期
    invoicing_party_name: str   # 开票单位名称（医院名称）
    payer_party_name: str       # 交款人名称（患者姓名）
    medical_type: str           # 医疗类别：1-门诊，2-住院
    medical_date: date          # 就诊日期
    in_hospital_date: date = None  # 住院日期
    out_hospital_date: date = None  # 出院日期
    org_type: str = ""          # 医疗机构类型
    is_medical_insurance: str = "0" # 是否医保票据：0-否，1-是
    fund_pay_amount: float = 0  # 医保统筹基金支付
    account_pay_amount: float = 0 # 个人账户支付
    own_pay_amount: float = 0  # 个人现金支付
    selfpayment_amount: float = 0 # 个人自付
    selfpayment_cost: float = 0  # 个人自费
    other_pay_amount: float = 0  # 其他支付
    item_detail: List[Dict] = field(default_factory=list) # 费用明细


@dataclass
class AccidentInfo:
    """事故信息"""
    accident_type: str          # 事故类型：意外医疗/意外身故/意外伤残/住院津贴
    accident_date: date        # 事故发生日期
    accident_desc: str          # 事故描述
    accident_place: str = ""   # 事故地点


@dataclass
class ClaimInfo:
    """理赔申请信息"""
    policy: Policy
    invoice: Invoice
    accident_info: AccidentInfo  # 事故信息
    report_date: date           # 报案日期
    claim_type: str            # 理赔类型
    claimed_invoice_ids: List[str] = field(default_factory=list) # 已理赔发票列表
    claimed_this_year: float = 0 # 年度累计赔付金额


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


class AccidentClaimEngine:
    """意外险理赔规则引擎"""

    def __init__(self):
        base_path = Path(__file__).parent
        with open(base_path / "config.yaml", 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        with open(base_path / "exclusions.json", 'r', encoding='utf-8') as f:
            self.exclusions_config = json.load(f)

        self.excluded_keywords = self.exclusions_config.get("exclusions", {})
        self.hospital_blacklist = self.exclusions_config.get("hospital_blacklist", [])
        self.hospital_levels = self.exclusions_config.get("hospital_levels", [])

    def get_product_params(self, product_code: str) -> Dict:
        """获取产品条款参数

        Args:
            product_code: 保险产品代码

        Returns:
            产品参数字典
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
        accident = claim_info.accident_info
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
        reporting_days = params.get("reporting_days", 5)
        days = (claim_info.report_date - accident.accident_date).days
        if days > reporting_days:
            rejection_reasons.append(f"报案时间距事故日期已超过{reporting_days}天")
            result.rule_results.append(RuleResult("rule_003", "报案时效", False))
        else:
            result.rule_results.append(RuleResult("rule_003", "报案时效", True))

        # ========== 第二阶段：意外定义校验 ==========
        # rule_004: 意外定义校验（突发的、外来的、非本意的、非疾病的）
        desc = accident.accident_desc.lower()
        # 检查是否疾病
        if any(kw in desc for kw in ["疾病", "生病", "高血压", "糖尿病"]):
            rejection_reasons.append("属于疾病，不属于意外")
            result.rule_results.append(RuleResult("rule_004", "意外定义", False))
        # 检查是否故意
        elif any(kw in desc for kw in ["自杀", "自残", "故意"]):
            rejection_reasons.append("属于故意行为，不属于意外")
            result.rule_results.append(RuleResult("rule_004", "意外定义", False))
        # 检查180天时限
        elif (invoice.issue_date - accident.accident_date).days > 180:
            rejection_reasons.append("超过180天理赔时限")
            result.rule_results.append(RuleResult("rule_004", "意外定义", False))
        else:
            result.rule_results.append(RuleResult("rule_004", "意外定义", True))

        # ========== 第三阶段：发票校验（仅医疗责任）==========
        has_medical = "accidental_medical" in params.get("covered_types", []) or "hospitalization_allowance" in params.get("covered_types", [])
        if has_medical:
            # rule_005: 发票唯一性校验
            if invoice.invoice_id in claim_info.claimed_invoice_ids:
                rejection_reasons.append("发票已理赔或重复")
                result.rule_results.append(RuleResult("rule_005", "发票唯一性", False))
            else:
                result.rule_results.append(RuleResult("rule_005", "发票唯一性", True))

            # rule_006: 医院等级校验
            if not any(level in invoice.org_type for level in self.hospital_levels):
                rejection_reasons.append("医院等级不符合要求")
                result.rule_results.append(RuleResult("rule_006", "医院等级", False))
            else:
                result.rule_results.append(RuleResult("rule_006", "医院等级", True))

            # rule_007: 医院类型校验
            if any(kw in invoice.invoicing_party_name for kw in self.hospital_blacklist):
                rejection_reasons.append("医院在黑名单范围内")
                result.rule_results.append(RuleResult("rule_007", "医院类型", False))
            else:
                result.rule_results.append(RuleResult("rule_007", "医院类型", True))

        # ========== 第四阶段：除外责任校验 ==========
        # rule_008: 除外责任校验
        exclusions = params.get("exclusions", [])
        excluded_found = False

        # 检查事故描述
        for exc in exclusions:
            keywords = self.excluded_keywords.get(exc.get("type", ""), [])
            if any(kw in desc for kw in keywords):
                rejection_reasons.append(f"属于除外责任: {exc.get('type', '')}")
                excluded_found = True

        # 检查费用明细
        if not excluded_found:
            for exc in exclusions:
                keywords = self.excluded_keywords.get(exc.get("type", ""), [])
                for item in invoice.item_detail:
                    item_name = item.get("item_name", "").lower()
                    if any(kw in item_name for kw in keywords):
                        rejection_reasons.append(f"费用项目【{item.get('item_name')}】属于除外责任")
                        excluded_found = True
                        break

        if excluded_found:
            result.rule_results.append(RuleResult("rule_008", "除外责任", False))
        else:
            result.rule_results.append(RuleResult("rule_008", "除外责任", True))

        # ========== 第五阶段：责任匹配校验 ==========
        # rule_009: 责任匹配校验
        coverage_map = {
            "意外医疗": "accidental_medical",
            "意外身故": "accidental_death",
            "意外伤残": "accidental_disability",
            "住院津贴": "hospitalization_allowance"
        }
        required = coverage_map.get(accident.accident_type)
        covered = params.get("covered_types", [])
        if required and required not in covered:
            rejection_reasons.append(f"产品不承保{accident.accident_type}责任")
            result.rule_results.append(RuleResult("rule_009", "责任匹配", False))
        else:
            result.rule_results.append(RuleResult("rule_009", "责任匹配", True))

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

    # ========== 费用计算 ==========
    def _calculate_payment(self, claim_info: ClaimInfo) -> tuple:
        """意外险理赔费用计算

        核心公式：

        1. 意外医疗：
           最终赔付 = MIN((基数-免赔额)×比例, 单限, 年限-已赔)
           基数 = 有医保?个人现金支付:总金额

        2. 意外身故：
           赔付金额 = 保额

        3. 意外伤残：
           赔付金额 = 保额 × 伤残等级比例

        4. 住院津贴：
           赔付金额 = 住院天数 × 每日津贴额

        字段来源：
        - 可赔基数: invoice.ownPayAmount / invoice.totalAmount
        - 免赔额: policy.product_params.deductible
        - 赔付比例: policy.product_params.coinsuranceRate
        - 保额: policy.product_params.coverageAmount
        - 每日津贴: policy.product_params.hospitalizationAllowance

        Args:
            claim_info: 理赔申请信息

        Returns:
            (赔付金额, 计算明细字典)
        """
        policy = claim_info.policy
        invoice = claim_info.invoice
        accident = claim_info.accident_info
        params = policy.product_params
        payment = 0
        calculation = {}

        if accident.accident_type == "意外医疗":
            # 意外医疗费用计算
            if invoice.is_medical_insurance == "1":
                base_amount = invoice.own_pay_amount or 0
                base_source = "invoice.ownPayAmount"
            else:
                base_amount = invoice.total_amount
                base_source = "invoice.totalAmount"

            deductible = params.get("deductible", 0)
            after_deductible = max(0, base_amount - deductible)
            coinsurance_rate = params.get("coinsurance_rate", 1.0)
            payment = after_deductible * coinsurance_rate

            # 限额检查
            payment = min(payment, params.get("single_limit", float('inf')))
            payment = min(payment, params.get("annual_limit", float('inf')) - claim_info.claimed_this_year)

            calculation = {
                "公式": "MIN((基数-免赔额)×比例, 单限, 年限-已赔)",
                "事故类型": "意外医疗",
                "可赔基数": base_amount,
                "可赔基数来源": base_source,
                "免赔额": deductible,
                "免赔额来源": "policy.product_params.deductible",
                "赔付比例": coinsurance_rate,
                "最终赔付": max(0, payment)
            }

        elif accident.accident_type == "意外身故":
            payment = params.get("coverage_amount", 0)
            calculation = {
                "公式": "保额",
                "事故类型": "意外身故",
                "保额": payment,
                "保额来源": "policy.product_params.coverageAmount"
            }

        elif accident.accident_type == "意外伤残":
            disability_rate = 0.10  # 简化：假设10级伤残
            death_amount = params.get("coverage_amount", 100000)
            payment = death_amount * disability_rate
            calculation = {
                "公式": "保额 × 伤残等级比例",
                "事故类型": "意外伤残",
                "伤残等级": "10级",
                "伤残比例": disability_rate,
                "保额": death_amount,
                "最终赔付": payment
            }

        elif accident.accident_type == "住院津贴":
            if invoice.in_hospital_date and invoice.out_hospital_date:
                days = (invoice.out_hospital_date - invoice.in_hospital_date).days
            else:
                days = 0
            daily_allowance = params.get("hospitalization_allowance", 0)
            days_limit = params.get("hospitalization_days_limit", 180)
            days = min(days, days_limit)
            payment = days * daily_allowance

            calculation = {
                "公式": "住院天数 × 每日津贴额",
                "事故类型": "住院津贴",
                "住院天数": days,
                "每日津贴": daily_allowance,
                "每日津贴来源": "policy.product_params.hospitalizationAllowance",
                "最终赔付": payment
            }

        payment = max(0, payment)
        return payment, calculation


if __name__ == "__main__":
    # 示例运行
    engine = AccidentClaimEngine()

    policy = Policy(
        policy_number="POL001",
        mpolicy_number="MPOL001",
        policy_name="综合意外险",
        insurance_type="意外险",
        insurance_product_code="product_001",
        insurance_product_name="综合意外险",
        policy_start_date=date(2025, 1, 1),
        policy_end_date=date(2026, 1, 1),
        policy_status="有效",
        product_params=engine.get_product_params("product_001")
    )

    invoice = Invoice(
        invoice_id="INV001",
        invoice_code="011001900111",
        invoice_number="12345678",
        total_amount=2000,
        issue_date=date(2025, 3, 15),
        invoicing_party_name="北京医院",
        payer_party_name="张三",
        medical_type="1",
        medical_date=date(2025, 3, 15),
        org_type="三级甲等",
        is_medical_insurance="1",
        own_pay_amount=500,
        fund_pay_amount=1500,
        item_detail=[{"item_name": "药品费", "item_amount": 2000}]
    )

    accident_info = AccidentInfo(
        accident_type="意外医疗",
        accident_date=date(2025, 3, 15),
        accident_desc="走路摔倒受伤",
        accident_place="北京市"
    )

    claim_info = ClaimInfo(
        policy=policy,
        invoice=invoice,
        accident_info=accident_info,
        report_date=date(2025, 3, 15),
        claim_type="意外医疗"
    )

    result = engine.check_all_rules(claim_info)
    print(f"状态: {result.status}, 赔付: {result.payment:.2f}元")
    if result.calculation:
        print("\n计算明细:")
        for k, v in result.calculation.items():
            print(f"  {k}: {v}")
