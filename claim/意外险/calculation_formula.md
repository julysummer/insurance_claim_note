# 意外险理赔计算规则引擎设计说明 (V3.0)

**适用范围**：意外身故、意外伤残、意外医疗、住院津贴
**核心设计理念**：发票明细级校验优先，补偿原则强制兜底。

---

## 一、核心计算公式架构

意外险的计算根据责任类型不同，采用不同的公式：

```
【意外医疗】
最终赔付 = MIN(初步赔付, 单次限额, 年度剩余限额, 补偿原则上限)
初步赔付 = MAX(0, 有效可赔基数 - 本次应扣免赔额) × 赔付比例
有效可赔基数 = SUM(明细经过除责过滤后的金额)

【意外身故】
赔付金额 = MAX(0, 保额 - 同案已赔伤残金)

【意外伤残】
核定比例 = 获取本次最高伤残等级比例
如果 (多处同等级且未达1级): 核定比例晋级
本次实际可赔比例 = MIN(核定比例, 100% - 历史已赔伤残比例)
赔付金额 = 保额 × 本次实际可赔比例

【住院津贴】
单次核算天数 = MAX(0, 实际住院天数 - 每次免赔天数)
单次有效天数 = MIN(单次核算天数, 单次天数上限)
年度剩余天数 = 年度天数上限 - 历史已赔天数
最终赔付天数 = MIN(单次有效天数, 年度剩余天数)
赔付金额 = 最终赔付天数 × 每日津贴额
```

---

## 二、核心计算参数字典

| 参数类别 | 字段名 | 业务说明 |
|----------|--------|----------|
| **基础金额** | totalAmount | 发票总金额 |
| | fundPayAmount | 医保统筹基金支付 |
| | accountPayAmount | 医保个人账户支付（商业险视同客户现金，**可赔**） |
| | otherPayAmount | 其他途径已补偿金额 |
| **免赔额** | deductible | 免赔额（意外医疗） |
| | history_deducted | 历史累计已扣免赔额（年免赔用） |
| **免赔天数** | deductible_days | 每次住院免赔天数（住院津贴） |
| | single_days_limit | 单次住院天数上限 |
| | annual_days_limit | 年度天数上限 |
| | history_days_paid | 历史已赔付天数 |
| **比例** | coinsurance_rate_with_insurance | 有医保赔付比例 |
| | coinsurance_rate_without_insurance | 无医保赔付比例 |
| **津贴** | hospitalizationAllowance | 每日津贴额 |
| | hospitalizationDaysLimit | 年度天数上限（已废弃，用 annual_days_limit） |
| **伤残** | history_disability_rate | 历史已赔伤残比例 |
| | same_case_disability_paid | 同案已赔伤残金 |
| **限额** | single/annualLimit | 单次/年度最高限额 |
| | historyPaid | 年度历史已赔付累计金额 |
| | itemLimits | 分项限额 |

---

## 三、意外医疗计算

### 3.1 除外责任拦截

对每条明细进行过滤：

```json
{
  "exclusions": [
    {"type": "关键词", "values": ["牙科", "美容", "整形", "减肥", "体检"]}
  ]
}
```

### 3.2 分项限额

```
对经过除责过滤后的费用明细：
    项目分类 = item.get("项目分类")
    如果 项目分类 在 item_limits 中存在:
        该项计入基数 = MIN(item.金额, item_limits[项目分类])
    否则:
        该项计入基数 = item.金额

有效可赔基数 = SUM(所有明细的计入基数)
```

#### 分项限额配置

```json
{
  "项目分类": {
    "西药费": 20000,
    "检查费": 10000,
    "治疗费": 8000,
    "手术费": 50000,
    "床位费": 5000,
    "其他费": 5000
  }
}
```

### 3.3 免赔额计算

| 类型 | 计算公式 |
|------|----------|
| 次免赔 | 本次应扣 = deductible |
| 年免赔 | 剩余 = MAX(0, deductible - history_deducted) |
| | 本次应扣 = MIN(有效可赔基数, 剩余) |

### 3.4 赔付比例计算（按社保结算身份）

```
如果 (isMedicalInsurance == "1" 且 fundPayAmount > 0):
    赔付比例 = coinsurance_rate_with_insurance  // 有医保赔付比例
否则:
    赔付比例 = coinsurance_rate_without_insurance  // 无医保赔付比例
```

```json
{
  "coinsurance_rate_with_insurance": 1.0,
  "coinsurance_rate_without_insurance": 0.8
}
```

---

## 四、意外身故/伤残计算

### 4.1 意外身故

```
同案已赔伤残金 = 同一次意外事故已支付的伤残理赔款
赔付金额 = MAX(0, 保额 - 同案已赔伤残金)
```

**注意**：客户因同一次意外先理赔伤残后身故的，需扣除已赔付的伤残金，确保总赔付不超过保额。

### 4.2 意外伤残

```
# 4.2.1 伤残等级确定
核定伤残比例 = 获取本次最高伤残等级比例

# 4.2.2 晋级原则（多处伤残）
如果 (存在两处及以上相同最高等级) 且 (未达1级):
    核定伤残比例 = 提升一级对应的比例

# 4.2.3 累计限额检查
历史已赔伤残比例 = history_disability_rate
本次实际可赔比例 = MIN(核定伤残比例, 100% - 历史已赔伤残比例)

# 4.2.4 计算赔付
赔付金额 = 保额 × 本次实际可赔比例
```

**晋级原则说明**：
- 根据《人身保险伤残评定标准》，同一次意外导致两处以上伤残
- 取最重的伤残等级赔付
- 若两处及以上最高伤残等级相同，则晋升一级（如两个5级按4级赔）

**累计限额说明**：
- 同一保单年度内多次伤残理赔，累计赔付不超过保额的100%
- 需要从数据库获取 `history_disability_rate`

```json
{
  "claim_type": "accidental_disability",
  "coverage_amount": 1000000,
  "history_disability_rate": 0,
  "disability_rates": {
    "1": 1.0,
    "2": 0.9,
    "3": 0.8,
    "4": 0.7,
    "5": 0.6,
    "6": 0.5,
    "7": 0.4,
    "8": 0.3,
    "9": 0.2,
    "10": 0.1
  }
}
```

### 5.1 计算公式

```
# Step 1: 计算住院天数
实际住院天数 = 出院日期 - 入院日期

# Step 2: 扣除免赔天数
单次核算天数 = MAX(0, 实际住院天数 - 每次免赔天数(deductible_days))

# Step 3: 应用单次天数上限
单次有效天数 = MIN(单次核算天数, 单次天数上限(single_days_limit))

# Step 4: 应用年度天数上限
年度剩余天数 = 年度天数上限(annual_days_limit) - 历史已赔付天数(history_days_paid)
最终赔付天数 = MIN(单次有效天数, 年度剩余天数)

# Step 5: 计算赔付金额
赔付金额 = 最终赔付天数 × 每日津贴额 (hospitalizationAllowance)
```

**参数说明：**

| 参数 | 字段名 | 说明 |
|------|--------|------|
| 每次免赔天数 | deductible_days | 每次住院扣除的天数（通常为0-3天） |
| 单次天数上限 | single_days_limit | 单次住院最高赔付天数（如90天） |
| 年度天数上限 | annual_days_limit | 年度最高赔付天数（如180天） |
| 历史已赔天数 | history_days_paid | 年度历史已赔付累计天数 |
| 每日津贴额 | hospitalizationAllowance | 每日给付金额 |

### 5.2 配置示例

```json
{
  "claim_type": "hospitalization_allowance",
  "hospitalization_allowance": 100,
  "deductible_days": 3,
  "single_days_limit": 90,
  "annual_days_limit": 180
}
```

---

## 六、标准化计算流程

### Step 1: 医院及就诊资质拦截

校验医院等级（根据配置要求）、就诊科室等。

### Step 2: 计算有效可赔基数

```
遍历发票明细 → 剔除除外责任 → 应用分项限额 → 汇总有效基数
```

### Step 3: 扣除免赔额

```
核算基数 = MAX(0, 有效可赔基数 - 本次应扣免赔额)
```

### Step 4: 应用赔付比例

```
初步赔付 = 核算基数 × 赔付比例
```

### Step 5: 限额检查

```
年度剩余 = annualLimit - historyPaid
限额后 = MIN(初步赔付, singleLimit, 年度剩余)
```

### Step 6: 补偿原则兜底（终审校验）

```
实际经济损失 = totalAmount - fundPayAmount - otherPayAmount
最终赔付 = MIN(限额后, 实际经济损失)

更新数据库：historyPaid += 最终赔付, history_deducted += 本次应扣免赔额
```

---

## 七、各种配置示例

### 意外医疗（有医保，100元免赔）

```json
{
  "claim_type": "accidental_medical",
  "deductible": 100,
  "deductible_type": "次免赔",
  "coinsurance_rate_with_insurance": 1.0,
  "coinsurance_rate_without_insurance": 0.8,
  "single_limit": 10000,
  "annual_limit": 50000
}
```

### 意外身故

```json
{
  "claim_type": "accidental_death",
  "coverage_amount": 1000000,
  "same_case_disability_paid": 0
}
```

### 意外伤残

```json
{
  "claim_type": "accidental_disability",
  "coverage_amount": 1000000,
  "history_disability_rate": 0,
  "disability_rates": {
    "1": 1.0,
    "2": 0.9,
    "3": 0.8,
    "4": 0.7,
    "5": 0.6,
    "6": 0.5,
    "7": 0.4,
    "8": 0.3,
    "9": 0.2,
    "10": 0.1
  }
}
```

### 住院津贴

```json
{
  "claim_type": "hospitalization_allowance",
  "hospitalization_allowance": 100,
  "deductible_days": 3,
  "single_days_limit": 90,
  "annual_days_limit": 180,
  "history_days_paid": 0
}
```

---

## 八、研发联调速查表

| 易错点 | 业务规则 | 系统要求 |
|--------|----------|----------|
| 医保个人账户 | 视同客户现金，不扣减 | `基数 = total - fundPay` 不扣 accountPay |
| 计算先后顺序 | 先明细限额汇总，再扣总免赔额 | 必须先算明细级限额 |
| 多次理赔免赔额 | 年免赔需累积已扣额度 | 引入 history_deducted 字段 |
| 补偿原则 | 总获赔不超实际损失 | MIN(计算值, 实际损失) |
| 住院津贴免赔天数 | 每次住院扣除前N天 | 引入 deductible_days 字段 |
| 住院津贴单次上限 | 单次住院天数上限 | 引入 single_days_limit 字段 |
| 伤残累计限额 | 年度累计不超保额100% | 引入 history_disability_rate 字段 |
| 身故扣减伤残 | 同次意外先伤残后身故 | 引入 same_case_disability_paid 字段 |

---

## 九、速查表

| 责任类型 | 公式 | 关键参数 |
|----------|------|----------|
| 意外医疗 | MIN(初步赔付, 单次/年度限额, 补偿上限) | deductible, coinsurance_rate_with/without_insurance |
| 意外身故 | MAX(0, 保额 - 同案已赔伤残金) | same_case_disability_paid |
| 意外伤残 | MIN(核定比例, 100% - 历史比例) × 保额 | history_disability_rate |
| 住院津贴 | MIN(核算天数, 单次上限, 年度剩余) × 日额 | deductible_days, single_days_limit, history_days_paid |