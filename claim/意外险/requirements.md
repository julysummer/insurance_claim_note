# 意外险理赔规则需求说明

## 一、险种定义

**意外险**是指被保险人因遭受意外伤害事故，导致身故、伤残、医疗费用支出或住院时，保险人按照约定承担给付保险金责任的保险。

**适用场景：**
- 意外身故
- 意外伤残
- 意外医疗
- 住院津贴

---

## 二、输入数据要求

### 2.1 保单信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| policyNo | string | 是 | 保单号 |
| status | string | 是 | 保单状态 |
| effectiveDate | date | 是 | 生效日期 |
| expiryDate | date | 是 | 终止日期 |
| productCode | string | 是 | 产品代码 |

### 2.2 发票信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| invoiceId | string | 是 | 发票ID |
| totalAmount | number | 是 | 发票总金额 |
| issueDate | date | 是 | 开票日期 |
| invoicingPartyName | string | 是 | 医院名称 |
| medicalType | string | 是 | 1-门诊，2-住院 |
| orgType | string | 是 | 医院等级 |
| isMedicalInsurance | string | 是 | 是否医保 |
| ownPayAmount | number | 否 | 个人现金支付 |
| fundPayAmount | number | 否 | 医保统筹 |
| inHospitalDate | date | 住院时必填 | 入院日期 |
| outHospitalDate | date | 住院时必填 | 出院日期 |
| itemDetail | array | 否 | 费用明细 |

### 2.3 事故信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| accidentType | string | 是 | 意外身故/意外伤残/意外医疗/住院津贴 |
| accidentDate | date | 是 | 事故发生日期 |
| accidentDesc | string | 是 | 事故描述 |

### 2.4 理赔申请信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| reportDate | date | 是 | 报案日期 |
| claimedThisYear | number | 否 | 年度累计赔付 |

---

## 三、规则清单

| 序号 | 规则名称 | 规则说明 | 拒赔条件 |
|------|----------|----------|----------|
| rule_001 | 保单状态 | 校验保单是否有效 | 状态非"有效" |
| rule_002 | 保障期间 | 校验事故日期是否在保障期内 | 发票日期在生效日前或终止日后 |
| rule_003 | 报案时效 | 校验报案是否及时 | 报案日期距事故日期超过约定天数 |
| rule_004 | 意外定义 | 校验是否符合意外定义 | 属于疾病/故意行为/超过180天 |
| rule_005 | 发票唯一性 | 校验发票是否重复理赔 | 发票ID已理赔 |
| rule_006 | 医院等级 | 校验医院资质 | 医院等级不在二级及以上 |
| rule_007 | 医院类型 | 校验医院是否在黑名单 | 医院在黑名单 |
| rule_008 | 除外责任 | 校验是否属于除外责任 | 事故/费用属于除外 |
| rule_009 | 责任匹配 | 校验事故类型是否在保障范围 | 不承保该事故类型 |

---

## 四、计算公式

### 4.1 意外医疗

```
最终赔付 = MIN( 初步赔付, 单次限额, 年度剩余限额 )
初步赔付 = MAX(0, 可赔基数 - 免赔额) × 赔付比例

可赔基数：
- 有医保：invoice.ownPayAmount（个人现金支付）
- 无医保：invoice.totalAmount（发票总金额）
```

### 4.2 意外身故

```
赔付金额 = policy.coverageAmount（保额）
```

### 4.3 意外伤残

```
赔付金额 = policy.coverageAmount × 伤残等级比例
```

### 4.4 住院津贴

```
赔付金额 = 住院天数 × policy.hospitalizationAllowance

住院天数 = invoice.outHospitalDate - invoice.inHospitalDate
住院天数上限 = policy.hospitalizationDaysLimit
```

---

## 五、参数来源

| 参数 | 字段来源 | 说明 |
|------|----------|------|
| 免赔额 | policy.deductible | 产品参数 |
| 赔付比例 | policy.coinsuranceRate | 产品参数 |
| 单次限额 | policy.singleLimit | 产品参数 |
| 年度限额 | policy.annualLimit | 产品参数 |
| 保额 | policy.coverageAmount | 产品参数 |
| 住院津贴 | policy.hospitalizationAllowance | 产品参数 |
| 伤残等级 | accident.disabilityLevel | 事故信息 |
| 住院天数 | invoice.out/inHospitalDate | 发票信息 |

---

## 六、产品参数

| 参数 | 说明 | 示例值 |
|------|------|--------|
| waitingPeriod | 等待期（天） | 0（意外无等待期） |
| reportingDays | 报案时效（天） | 5 |
| deductible | 免赔额 | 100 |
| coinsuranceRate | 赔付比例 | 0.80 |
| annualLimit | 年度限额 | 10000 |
| singleLimit | 单次限额 | 5000 |
| coverageAmount | 保额 | 100000 |
| hospitalizationAllowance | 住院津贴/天 | 50 |
| hospitalizationDaysLimit | 住院津贴年度上限 | 180 |

---

## 七、注意事项

1. **意外无等待期**：意外险无等待期限制
2. **180天时限**：意外伤害发生后180天内治疗有效
3. **意外定义**：突发的、外来的、非本意的、非疾病的
4. **医院要求**：二级及以上公立医院
