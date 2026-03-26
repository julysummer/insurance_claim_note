# 通用医疗险理赔计算公式

适用于：医疗险、百万医疗险、中端医疗险、小额医疗险、门诊医疗险、惠民保等

---

## 一、通用公式

```
最终赔付 = MIN( 初步赔付, 限额检查 )
初步赔付 = MAX(0, 可赔基数 - 免赔额) × 赔付比例
```

### 限额检查（多选）
```
限额检查 = MIN(单次限额, 年度剩余限额, 分项限额...)
```

---

## 二、核心计算参数

| 参数 | 字段来源 | 说明 |
|------|----------|------|
| 可赔基数 | ownPayAmount / totalAmount | 根据医保类型确定 |
| 免赔额 | deductible | 支持年免赔/次免赔/分段免赔 |
| 赔付比例 | coinsuranceRate | 有医保/无医保分别设置 |
| 单次限额 | singleLimit | 每次理赔最高金额 |
| 年度限额 | annualLimit | 年度累计最高金额 |
| 日限额 | dailyLimit | 门诊单日最高金额 |
| 分项限额 | itemLimits | 特定项目限额 |

---

## 三、可赔基数计算

### 3.1 医保类型判断

```
有医保(isMedicalInsurance = "1"):
    优先使用个人现金支付(ownPayAmount)
    如果 ownPayAmount <= 0，则使用发票总金额(totalAmount)
无医保:
    使用发票总金额(totalAmount)
```

### 3.2 公式
```
可赔基数 =
    有医保 ?
        (个人现金支付 > 0 ? 个人现金支付 : 发票总金额)
    :
        发票总金额
```

### 3.3 字段映射
| 发票字段 | 说明 |
|----------|------|
| totalAmount | 发票总金额 |
| fundPayAmount | 医保统筹基金支付 |
| accountPayAmount | 个人账户支付 |
| ownPayAmount | 个人现金支付 = totalAmount - fundPayAmount - accountPayAmount - otherPayAmount |
| isMedicalInsurance | 0-否，1-是 |

---

## 四、免赔额计算

### 4.1 免赔额类型

| 类型 | 配置 | 计算方式 |
|------|------|----------|
| 年免赔 | deductible=10000, type="年免赔" | 年度累计免赔额 |
| 次免赔 | deductible=100, type="次免赔" | 每次理赔扣除 |
| 分段免赔 | tiered_deductible | 不同额度区间不同免赔 |
| 组合免赔 | 年免赔+次免赔 | 先年度累计，再单次扣除 |
| 无免赔 | deductible=0 | 不扣除 |

### 4.2 分段免赔配置
```json
{
  "tiered_deductible": [
    {"min": 0, "max": 1000, "deductible": 100},
    {"min": 1000, "max": 5000, "deductible": 200},
    {"min": 5000, "max": "inf", "deductible": 500}
  ]
}
```

### 4.3 公式
```
扣除免赔额 =
    分段免赔 ? 查询区间对应免赔额
    : 可赔基数 - 免赔额
```

---

## 五、赔付比例

### 5.1 医保类型区分

```json
{
  "coinsurance_rate_with_insurance": 1.0,    // 有医保 100%
  "coinsurance_rate_without_insurance": 0.7  // 无医保 70%
}
```

### 5.2 既往症区分

```json
{
  "coinsurance_rate": 1.0,              // 正常赔付
  "pre_history_coinsurance_rate": 0.5    // 既往症赔付
}
```

### 5.3 公式
```
赔付比例 =
    有医保 ? 有医保比例 : 无医保比例

如果有过往症in历史:
    赔付比例 = min(赔付比例, 既往症比例)
```

---

## 六、限额控制

### 6.1 单次限额
```
单次限额检查 = MIN(初步赔付, 单次限额)
```

### 6.2 年度限额
```
年度剩余 = 年度限额 - 年度已赔
年度限额检查 = MIN(单次限额检查, 年度剩余)
```

### 6.3 门诊日限额（日间门诊）
```
日限额检查 = MIN(当日费用, 门诊日限额, 年度剩余)
```

### 6.4 分项限额
```
暂不处理，根据具体险种条款配置
```

当需要时再根据具体险种条款定义：
```json
{
  "item_limits": {
    "西药费": 20000,
    "中药费": 5000,
    "检查费": 10000
  }
}
```

---

## 七、除责项目

### 7.1 除外责任
```json
{
  "exclusions": [
    {"type": "牙科", "keywords": ["牙周", "种植", "正畸"]},
    {"type": "美容", "keywords": ["整形", "美容", "减肥"]}
  ]
}
```

### 7.2 计算
```
可赔基数 = 可赔基数 - 除责项目金额
```

---

## 八、完整计算流程

```
步骤1: 确定可赔基数
    有医保且个人现金支付>0 → 基数 = 个人现金支付
    否则 → 基数 = 发票总金额

步骤2: 扣除除责项目
    遍历费用明细，匹配除外关键词
    可赔基数 = 可赔基数 - 除责金额

步骤3: 计算免赔额
    根据免赔额类型计算

步骤4: 计算初步赔付
    初步赔付 = MAX(0, 可赔基数 - 免赔额) × 赔付比例

步骤5: 分项限额检查（如有）
    医保内/医保外分别计算

步骤6: 单次限额
    初步赔付 = MIN(初步赔付, 单次限额)

步骤7: 年度限额
    最终赔付 = MIN(初步赔付, 年度限额 - 年度已赔门诊医疗险、百万医疗险、惠民保等险种的理赔计算，关键在于将所有可配置参数统一到一个通用公式框架中。通过设定可赔基数、多个免赔额类型、分级赔付比例以及多种限额控制方式，实现一个公式能够适配不同险种的理赔需求。<br>

---

## 九、各产品配置示例

### 百万医疗险
```json
{
  "deductible": 10000,
  "deductible_type": "年免赔",
  "coinsurance_rate": 1.0,
  "annual_limit": 3000000,
  "single_limit": 1000000,
  "covered_types": ["hospitalization"]
}
```

### 门诊医疗险
```json
{
  "deductible": 0,
  "deductible_type": "无",
  "coinsurance_rate": 1.0,
  "annual_limit": 10000,
  "single_limit": 1000,
  "daily_limit": 500,
  "covered_types": ["outpatient"]
}
```

### 惠民保
```json
{
  "deductible": 20000,
  "deductible_type": "年免赔",
  "coinsurance_rate_with_insurance": 0.8,
  "coinsurance_rate_without_insurance": 0.6,
  "annual_limit": 1500000,
  "single_limit": 500000,
  "item_limits": {
    "医保内": 100000,
    "医保外": 500000
  },
  "pre_history_coinsurance_rate": 0.5,
  "covered_types": ["hospitalization", "special_clinic"]
}
```

---

## 十、速查表

| 场景 | 公式 | 关键参数 |
|------|------|----------|
| 通用 | MIN(初步赔付, 单次/年度/分项限额) | 全部可配置 |
| 有医保 | 基数=个人现金支付 | ownPayAmount |
| 无医保 | 基数=发票总金额 | totalAmount |
| 年免赔 | 基数-10000（年度累计） | deductible |
| 次免赔 | 基数-100（每次） | deductible |
| 分段免赔 | 根据区间查表 | tiered_deductible |
| 既往症 | 比例×50% | pre_history |
| 门诊日限 | MIN(基数, 日限) | daily_limit |
| 医保内/外 | 分项计算 | item_limits |