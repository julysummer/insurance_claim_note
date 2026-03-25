# 医疗险理赔规则需求说明

## 一、险种定义

**医疗险**是指被保险人因疾病或意外伤害而发生医疗费用支出，由保险人按照约定进行赔付的健康保险险种。

**适用场景：**
- 门诊就医
- 住院治疗
- 慢特病门诊

---

## 二、输入数据要求

### 2.1 保单信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| policyNo | string | 是 | 保单号 |
| status | string | 是 | 保单状态（有效/失效/终止） |
| effectiveDate | date | 是 | 生效日期 |
| expiryDate | date | 是 | 终止日期 |
| productCode | string | 是 | 产品代码 |

### 2.2 发票信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| invoiceId | string | 是 | 发票ID |
| totalAmount | number | 是 | 发票总金额 |
| issueDate | date | 是 | 开票日期 |
| invoicingPartyName | string | 是 | 开票单位（医院名称） |
| medicalType | string | 是 | 医疗类别：1-门诊，2-住院，3-慢特病 |
| orgType | string | 是 | 医疗机构类型 |
| isMedicalInsurance | string | 是 | 是否医保：0-否，1-是 |
| fundPayAmount | number | 否 | 医保统筹支付 |
| accountPayAmount | number | 否 | 个人账户支付 |
| ownPayAmount | number | 否 | 个人现金支付 |
| otherPayAmount | number | 否 | 其他支付 |
| itemDetail | array | 否 | 费用明细 |

### 2.3 理赔申请信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| accidentDate | date | 是 | 事故/就诊日期 |
| reportDate | date | 是 | 报案日期 |
| claimedInvoiceIds | array | 否 | 已理赔发票列表 |
| claimedThisYear | number | 否 | 年度累计赔付 |

---

## 三、规则清单

| 序号 | 规则名称 | 规则说明 | 拒赔条件 |
|------|----------|----------|----------|
| rule_001 | 保单状态 | 校验保单是否有效 | 状态非"有效" |
| rule_002 | 保障期间 | 校验事故日期是否在保障期内 | 发票日期在生效日前或终止日后 |
| rule_003 | 报案时效 | 校验报案是否及时 | 报案日期距事故日期超过约定天数 |
| rule_004 | 发票唯一性 | 校验发票是否重复理赔 | 发票ID已存在理赔记录 |
| rule_005 | 发票金额 | 校验发票金额有效性 | 发票金额≤0 |
| rule_006 | 费用勾稽 | 校验费用明细平衡 | 总金额与各项支付合计差额≥1元 |
| rule_007 | 医院等级 | 校验医院资质 | 医院等级不在二级及以上 |
| rule_008 | 医院类型 | 校验医院是否在黑名单 | 医院名称含黑名单关键词 |
| rule_009 | 等待期 | 校验是否在等待期内 | 投保后未满等待期（仅住院/慢特病） |
| rule_010 | 责任匹配 | 校验就诊类型是否在保障范围 | 就诊类型不在产品承保范围内 |
| rule_011 | 除外责任 | 校验费用是否属于除外 | 费用明细含除外关键词 |

---

## 四、计算公式

### 4.1 核心公式

```
最终赔付 = MIN( 初步赔付, 单次限额, 年度剩余限额 )
初步赔付 = MAX(0, 可赔基数 - 免赔额) × 赔付比例
```

### 4.2 可赔基数确定

| 医保状态 | 字段来源 | 说明 |
|----------|----------|------|
| 医保已结算 | `invoice.ownPayAmount` | 个人现金支付 |
| 医保未结算 | `invoice.totalAmount` | 发票总金额 |

### 4.3 参数来源

| 参数 | 字段来源 | 说明 |
|------|----------|------|
| 免赔额 | `policy.deductible` | 产品参数配置 |
| 赔付比例 | `policy.coinsuranceRate` | 产品参数配置 |
| 单次限额 | `policy.singleLimit` | 产品参数配置 |
| 年度限额 | `policy.annualLimit` | 产品参数配置 |
| 年度已赔 | `claim.claimedThisYear` | 理赔历史累计 |

---

## 五、产品参数配置

### 5.1 参数项

| 参数 | 说明 | 示例值 |
|------|------|--------|
| waitingPeriod | 等待期（天） | 30 |
| reportingDays | 报案时效（天） | 30 |
| deductible | 免赔额（元） | 100 |
| coinsuranceRate | 赔付比例 | 0.80 |
| annualLimit | 年度限额（元） | 10000 |
| singleLimit | 单次限额（元） | 5000 |
| coveredTypes | 承保责任 | [outpatient, hospitalization] |
| exclusions | 除外责任 | [牙科, 美容整形] |

### 5.2 配置示例

详见 `config.yaml`

---

## 六、输出结果

### 6.1 成功

```json
{
  "status": "PASS",
  "payment": 320.00,
  "calculation": {
    "baseAmount": 500,
    "deductible": 100,
    "afterDeductible": 400,
    "coinsuranceRate": 0.8,
    "payment": 320
  }
}
```

### 6.2 拒赔

```json
{
  "status": "REJECT",
  "rejectionReasons": [
    "保单状态为【失效】",
    "医院等级不符合要求"
  ]
}
```

---

## 七、注意事项

1. **门诊无等待期**：门诊医疗不检查等待期
2. **意外无等待期**：因意外导致的医疗无等待期限制
3. **医保优先**：有医保时使用个人现金支付作为基数
4. **费用勾稽**：允许0.99元误差
5. **累计限额**：需查询历史理赔记录计算年度已赔
