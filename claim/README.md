# 理赔规则全局字段定义（最终版）

## 一、保单信息字段（实际可获取）

| 字段名 | 中文名 | 类型 | 必填 | 说明 |
|--------|--------|------|------|------|
| policyNumber | 保单号 | String | 是 | |
| mpolicyNumber | 主保单号 | String | 是 | |
| policyName | 保单名称 | String | 是 | |
| insuranceType | 保险险种 | String | 是 | 详见附录 |
| insuranceProductCode | 保险产品代码 | String | 否 | |
| insuranceProductName | 保险产品名称 | String | 是 | |
| policyStartDate | 保单开始日期 | String | 是 | yyyy-MM-dd |
| policyEndDate | 保单结束日期 | String | 是 | yyyy-MM-dd |

---

## 二、条款配置字段（统一标准）

### 2.1 基础信息

| 字段名 | 中文名 | 类型 | 说明 |
|--------|--------|------|------|
| productCode | 产品代码 | String | 来自保单: insuranceProductCode |
| claimType | 赔付类型 | String | 给付型/报销型/津贴型 |
| paymentPeriodType | 缴费期间类型 | String | 短期/长期 |
| paymentFrequency | 缴费频率 | String | 年缴/季缴/月缴/趸缴 |
| reimbursementCategory | 报销类别 | Array | 门诊/住院 |
| reimbursementScope | 报销范围 | Array | 疾病/意外 |

### 2.2 等待期

| 字段名 | 中文名 | 类型 | 说明 |
|--------|--------|------|------|
| diseaseWaitingPeriod | 疾病等待期 | Number | 天数 |
| accidentWaitingPeriod | 意外等待期 | Number | 天数 |

### 2.3 免赔额

| 字段名 | 中文名 | 类型 | 说明 |
|--------|--------|------|------|
| deductibleType | 免赔额类型 | String | 年免赔/次免赔/不适用 |
| deductible | 免赔额金额 | Number | 元 |
| cumulativeDeductible | 累计免赔额 | Number | 元 |

### 2.4 赔付参数

| 字段名 | 中文名 | 类型 | 说明 |
|--------|--------|------|------|
| coinsuranceRate | 赔付比例 | Number | 0-1 |
| annualLimit | 年度限额 | Number | 元 |
| singleLimit | 单次限额 | Number | 元 |
| coverageAmount | 保额 | Number | 元（给付型用） |

### 2.5 住院津贴

| 字段名 | 中文名 | 类型 | 说明 |
|--------|--------|------|------|
| hospitalizationAllowance | 每日津贴 | Number | 元/天 |
| hospitalizationDaysLimit | 年度天数上限 | Number | 天 |

---

## 三、发票信息字段（来自Schema）

| 字段名 | 中文名 | 类型 | 说明 |
|--------|--------|------|------|
| invoiceId | 电子票据ID | String | |
| invoiceCode | 电子票据代码 | String | |
| invoiceNumber | 电子票据号码 | String | |
| totalAmount | 总金额 | Number | |
| issueDate | 开票日期 | Date | |
| invoicingPartyName | 开票单位名称 | String | 医院名称 |
| payerPartyName | 交款人名称 | String | 患者姓名 |
| medicalType | 医疗类别 | String | 1-门诊,2-住院,3-慢特病 |
| medicalDate | 就诊日期 | Date | |
| inHospitalDate | 住院日期 | Date | 住院时 |
| outHospitalDate | 出院日期 | Date | 住院时 |
| orgType | 医疗机构类型 | String | |
| isMedicalInsurance | 是否医保票据 | String | 0-否,1-是 |
| fundPayAmount | 医保统筹基金支付 | Number | |
| accountPayAmount | 个人账户支付 | Number | |
| ownPayAmount | 个人现金支付 | Number | |
| selfpaymentAmount | 个人自付 | Number | |
| selfpaymentCost | 个人自费 | Number | |
| otherPayAmount | 其他支付 | Number | |

---

## 四、理赔申请字段

| 字段名 | 中文名 | 类型 | 说明 |
|--------|--------|------|------|
| accidentDate | 事故/就诊日期 | Date | |
| reportDate | 报案日期 | Date | |
| claimType | 理赔类型 | String | 意外医疗/疾病医疗等 |

---

## 五、配置示例

### 5.1 config.yaml（统一结构）

```yaml
# 基础信息（来自保单）
product_code: "P001"
claim_type: "报销型"
reimbursement_category:
  - "门诊"
  - "住院"
reimbursement_scope:
  - "疾病"
  - "意外"

# 等待期
disease_waiting_period: 30
accident_waiting_period: 0

# 免赔额
deductible_type: "次免赔"
deductible: 100
cumulative_deductible: 0

# 赔付
coinsurance_rate: 0.80
annual_limit: 10000
single_limit: 5000
coverage_amount: 0

# 津贴
hospitalization_allowance: 50
hospitalization_days_limit: 180

# 承保责任
covered_types:
  - "outpatient"
  - "hospitalization"
```

### 5.2 数据映射

```python
# 保单信息映射
policy_mapping = {
    "policyNumber": "保单号",
    "policyStartDate": "生效日期",
    "policyEndDate": "终止日期",
    "insuranceProductCode": "产品代码",
    "insuranceType": "险种"
}

# 条款配置参数
# 需要从条款配置系统读取，与保单信息关联
```
