# 意外险理赔计算公式

适用于：意外身故、意外伤残、意外医疗、住院津贴

---

## 核心公式

### 1. 意外医疗费用

```
最终赔付 = MIN( 初步赔付, 单次限额, 年度剩余限额 )

初步赔付 = MAX(0, 可赔基数 - 免赔额) × 赔付比例
```

**字段来源：**

| 计算项 | 来源字段 | 说明 |
|--------|----------|------|
| 可赔基数（有医保） | `invoice.ownPayAmount` | 个人现金支付 |
| 可赔基数（无医保） | `invoice.totalAmount` | 发票总金额 |
| 免赔额 | `policy.deductible` | 产品参数配置 |
| 赔付比例 | `policy.coinsuranceRate` | 产品参数配置 |
| 单次限额 | `policy.singleLimit` | 产品参数配置 |
| 年度限额 | `policy.annualLimit` | 产品参数配置 |
| 年度已赔 | `claim.claimedThisYear` | 理赔历史累计 |

---

### 2. 意外身故

```
赔付金额 = 保额
```

**字段来源：**

| 计算项 | 来源字段 | 说明 |
|--------|----------|------|
| 保额 | `policy.coverageAmount` | 产品参数配置 |

---

### 3. 意外伤残

```
赔付金额 = 保额 × 伤残等级比例
```

**字段来源：**

| 计算项 | 来源字段 | 说明 |
|--------|----------|------|
| 保额 | `policy.coverageAmount` | 产品参数配置 |
| 伤残等级 | `accident.disabilityLevel` | 伤残鉴定结果 |
| 伤残比例 | `policy.disabilityRates[level]` | 伤残等级对应比例 |

**伤残等级比例（行业标准）：**

| 等级 | 比例 |
|------|------|
| 1级 | 100% |
| 2级 | 90% |
| 3级 | 80% |
| ... | ... |
| 10级 | 10% |

---

### 4. 住院津贴

```
赔付金额 = 住院天数 × 每日津贴额
```

**字段来源：**

| 计算项 | 来源字段 | 说明 |
|--------|----------|------|
| 住院天数 | `invoice.outHospitalDate - invoice.inHospitalDate` | 出院日期 - 入院日期 |
| 每日津贴 | `policy.hospitalizationAllowance` | 产品参数配置 |
| 年度天数上限 | `policy.hospitalizationDaysLimit` | 产品参数配置 |

---

## 详细示例

### 示例：意外医疗（有医保）

**输入参数：**

| 参数 | 值 | 字段来源 |
|------|-----|----------|
| 发票总金额 | 2000元 | `invoice.totalAmount` |
| 医保统筹支付 | 1500元 | `invoice.fundPayAmount` |
| 个人现金支付 | 500元 | `invoice.ownPayAmount` |
| 免赔额 | 100元 | `policy.deductible` |
| 赔付比例 | 80% | `policy.coinsuranceRate` |
| 单次限额 | 10000元 | `policy.singleLimit` |
| 年度限额 | 50000元 | `policy.annualLimit` |
| 年度已赔 | 0元 | `claim.claimedThisYear` |

**计算过程：**

| 步骤 | 计算 | 结果 | 字段来源 |
|------|------|------|----------|
| 1. 确定基数 | 500元 | 500元 | `invoice.ownPayAmount` |
| 2. 扣减免赔额 | 500 - 100 = 400 | 400元 | `invoice.ownPayAmount - policy.deductible` |
| 3. 初步赔付 | 400 × 80% = 320 | 320元 | `(基数-免赔额) × coinsuranceRate` |
| 4. 单次限额 | MIN(320, 10000) = 320 | 320元 | `min(初步赔付, singleLimit)` |
| 5. 年度限额 | MIN(320, 50000-0) = 320 | **320元** | `min(单次结果, annualLimit-claimed)` |

**结果：赔付 320 元**

---

### 示例：住院津贴

**输入参数：**

| 参数 | 值 | 字段来源 |
|------|-----|----------|
| 入院日期 | 2025-03-01 | `invoice.inHospitalDate` |
| 出院日期 | 2025-03-11 | `invoice.outHospitalDate` |
| 每日津贴 | 100元/天 | `policy.hospitalizationAllowance` |
| 年度上限 | 180天 | `policy.hospitalizationDaysLimit` |

**计算过程：**

| 步骤 | 计算 | 结果 | 字段来源 |
|------|------|------|----------|
| 1. 住院天数 | 10天 | 10天 | `outHospitalDate - inHospitalDate` |
| 2. 限额检查 | MIN(10, 180) = 10 | 10天 | `min(天数, daysLimit)` |
| 3. 计算赔付 | 10 × 100 = 1000 | **1000元** | `天数 × allowance` |

**结果：赔付 1000 元**

---

## 速查表

| 责任类型 | 公式 | 关键字段 |
|----------|------|----------|
| 意外医疗 | `MIN((基数-免赔额)×比例,单限,年限-已赔)` | `ownPayAmount`, `deductible`, `coinsuranceRate` |
| 意外身故 | `coverageAmount` | `coverageAmount` |
| 意外伤残 | `coverageAmount × 伤残比例` | `coverageAmount`, `disabilityLevel` |
| 住院津贴 | `天数 × 日额` | `in/outHospitalDate`, `hospitalizationAllowance` |
