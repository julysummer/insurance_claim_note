# 通用医疗险理赔计算规则引擎设计说明 (V2.0)

**适用范围**：医疗险、百万医疗险、中端医疗险、小额医疗险、门诊医疗险、惠民保等
**核心设计理念**：发票明细级校验优先，免赔额动态累计，补偿原则强制兜底。

---

## 一、核心计算公式架构

医疗险的计算遵循**"自下而上（先明细后总体）"**的原则，避免因先扣总免赔再算分项限额导致的金额少算漏洞。

```
最终赔付 = MIN(初步赔付, 单次限额, 年度剩余限额, 补偿原则上限)

初步赔付 = MAX(0, 有效可赔基数 - 本次应扣免赔额) × 最终赔付比例

有效可赔基数 = SUM( (单项费用 - 单项除责) 经过分项/目录限额过滤后的金额 )
```

---

## 二、核心计算参数字典

| 参数类别 | 字段名 | 业务说明 |
|----------|--------|----------|
| **基础金额** | totalAmount | 发票总金额 |
| | fundPayAmount | 医保统筹基金支付（核心扣减项） |
| | accountPayAmount | 医保个人账户支付（商业险视同客户现金，**可赔**） |
| | otherPayAmount | 其他途径已补偿金额（如其他商保、大病保险等） |
| **免赔额** | deductible | 配置的免赔额度（支持年免赔/次免赔/分段免赔） |
| | history_deducted | 历史理赔已扣除的免赔额累计（用于年免赔） |
| **比例** | coinsuranceRate | 赔付比例（根据医保结算身份、既往症等动态取值） |
| **限额控制** | single/annualLimit | 单次/年度最高限额 |
| | historyPaid | 年度历史已赔付累计金额 |
| | itemLimits | 分项限额（按明细、按目录、按日等） |

---

## 三、基数定义与医保结算判断

### 3.1 实际自费基数（补偿原则上限）

商业医疗险遵循"补偿原则"，无论公式怎么算，最终赔的钱绝不能超过客户实际受到的经济损失。

```
实际经济损失 = 发票总金额 - 医保统筹基金支付 - 其他途径已补偿
```

**注意：医保个人账户（医保卡扣款）属于个人财产，视同现金，不予扣减。**

### 3.2 医保结算身份判断

发票层级的判断，决定整体的**赔付比例**。

```
if (isMedicalInsurance == "1" 且 fundPayAmount > 0) {
    结算身份 = "有医保且以医保身份就诊"
} else {
    结算身份 = "无医保或未以医保身份就诊"
}
```

---

## 四、明细级过滤与分项限额（生成"有效可赔基数"）

实务中，必须在扣除总免赔额之前，先对发票上的**每一项费用明细（Item）**进行清洗和限额。

### 4.1 除外责任拦截（多维匹配）

```json
{
  "exclusions": [
    {"type": "项目拦截", "match": "医保标准码", "values": ["330000000"]},
    {"type": "关键词", "match": "keyword", "values": ["牙周", "正畸", "减肥", "美容"]}
  ]
}
```

**计算**：从明细中剔除匹配到的除责项目

### 4.2 医保目录内外限额（惠民保必备）

同一张医保发票包含医保内和医保外费用，需根据配置按明细区分：

```
对每个费用明细 item：
    如果 config.cover_catalog == "仅医保内":
        如果 item 不在医保目录内:
            该项可赔 = 0
        否则:
            该项可赔 = item.金额
    否则（不限目录）:
        该项可赔 = item.金额
```

### 4.3 分项限额计算

```
对经过 4.1 和 4.2 过滤后的费用明细：
    项目分类 = item.get("项目分类") // 如：床位费、手术费、西药费
    如果 项目分类 存在于 config.item_limits:
        该项计入基数 = MIN(item.金额, config.item_limits[项目分类])
    否则:
        该项计入基数 = item.金额

有效可赔基数 = SUM(所有明细的计入基数)
```

#### 分项限额配置示例

```json
{
  "项目分类": {
    "西药费": 20000,
    "中成药费": 5000,
    "中药饮片": 3000,
    "检查费": 10000,
    "化验费": 5000,
    "治疗费": 8000,
    "手术费": 50000,
    "床位费": 5000,
    "诊察费": 2000,
    "护理费": 3000,
    "卫生材料费": 10000,
    "挂号费": 500,
    "一般诊疗费": 1000,
    "其他费": 5000
  }
}
```

> 注：医院等级、就诊类型、医保结算属于案件级别的总体限额配置，详见第七节。

---

## 五、免赔额计算（动态扣除）

### 5.1 免赔扣除逻辑

必须引入状态管理，尤其是"年免赔"。

| 类型 | 计算公式 |
|------|----------|
| 次免赔 | 本次应扣免赔额 = config.deductible |
| 年免赔 | 剩余待扣 = MAX(0, config.deductible - history_deducted) |
| | 本次应扣免赔额 = MIN(有效可赔基数, 剩余待扣) |
| 分段免赔 | 根据 有效可赔基数 匹配 tiered_deductible 区间获取额度 |

### 5.2 多次理赔免赔额累计

```text
第二次理赔时：
    剩余待扣免赔额 = MAX(0, 年度免赔额 - 历史已扣免赔额)
    本次应扣免赔额 = MIN(本次有效基数, 剩余待扣免赔额)
```

### 5.3 配置示例

```json
{
  "deductible": 10000,
  "deductible_type": "年免赔",  // 或 "次免赔"、"分段免赔"
  "history_deducted": 0       // 历史累计已扣免赔额
}
```

```json
{
  "deductible": 100,
  "deductible_type": "次免赔"
}
```

```json
{
  "deductible_type": "分段免赔",
  "tiered_deductible": [
    {"min": 0, "max": 1000, "deductible": 100},
    {"min": 1000, "max": 5000, "deductible": 200},
    {"min": 5000, "max": "inf", "deductible": 500}
  ]
}
```

---

## 六、赔付比例确定

### 6.1 基础赔付比例

```
基础比例 = (结算身份 == "有医保且以医保身份就诊")
           ? config.coinsurance_rate_with_insurance
           : config.coinsurance_rate_without_insurance
```

### 6.2 既往症比例

```
如果 是既往症客户 且 config.pre_history_coinsurance_rate 存在:
    最终赔付比例 = MIN(基础比例, config.pre_history_coinsurance_rate)
否则:
    最终赔付比例 = 基础比例
```

### 6.3 配置示例

```json
{
  "coinsurance_rate_with_insurance": 1.0,      // 有医保 100%
  "coinsurance_rate_without_insurance": 0.7,   // 无医保 70%
  "pre_history_coinsurance_rate": 0.5           // 既往症 50%
}
```

---

## 七、总体限额与最终赔付核算（标准化流程）

### Step 1: 医院及就诊资质拦截

校验 医院等级（三级/二级）、医院性质（公立/私营）、就诊科室（普通部/特需部）。若不在保障范围内，直接拒赔（赔付=0）。

### Step 2: 计算有效可赔基数（调用 第四节）

遍历发票明细，剔除除外责任、非保障医保目录，并应用单项限额。

### Step 3: 扣除免赔额（调用 第五节）

```
核算基数 = MAX(0, 有效可赔基数 - 本次应扣免赔额)
```

### Step 4: 应用赔付比例（调用 第六节）

```
初步赔付 = 核算基数 × 最终赔付比例
```

### Step 5: 总体限额检查

```
年度剩余限额 = config.annualLimit - historyPaid
限额后赔付 = MIN(初步赔付, config.singleLimit, 年度剩余限额, config.dailyLimit)
```

### Step 6: 补偿原则兜底（终审校验）

```
实际经济损失 = totalAmount - fundPayAmount - otherPayAmount
最终赔付 = MIN(限额后赔付, 实际经济损失)

更新数据库：historyPaid += 最终赔付, history_deducted += 本次应扣免赔额
```

---

## 八、复杂险种配置示例

### 1. 惠民保（严格区分医保内外，有既往症比例限制）

```json
{
  "deductible": 20000,
  "deductible_type": "年免赔",
  "catalog_limits": {
    "医保内": {"annual_limit": 1000000},
    "医保外": {"annual_limit": 1000000}
  },
  "coinsurance_rate_with_insurance": 0.8,
  "coinsurance_rate_without_insurance": 0.0,
  "pre_history_coinsurance_rate": 0.3,
  "hospital_req": {
    "level": ["二级", "三级"],
    "nature": "公立",
    "dept": "普通部"
  }
}
```

### 2. 高端/中端医疗险（0免赔，按明细严格限额）

```json
{
  "deductible": 0,
  "deductible_type": "无",
  "coinsurance_rate_with_insurance": 1.0,
  "coinsurance_rate_without_insurance": 1.0,
  "annual_limit": 3000000,
  "item_limits": {
    "床位费": 1500,
    "挂号费": 800,
    "卫生材料费": 5000
  },
  "hospital_req": {
    "level": ["二级", "三级"],
    "nature": "any",
    "dept": "any"
  }
}
```

### 3. 百万医疗险

```json
{
  "deductible": 10000,
  "deductible_type": "年免赔",
  "coinsurance_rate_with_insurance": 1.0,
  "coinsurance_rate_without_insurance": 0.6,
  "annual_limit": 3000000,
  "single_limit": 1000000,
  "covered_types": ["hospitalization"]
}
```

---

## 九、研发联调速查表（防坑指南）

| 易错点/客诉高发点 | 业务规则强调 | 系统代码要求 |
|------------------|--------------|--------------|
| **医保个人账户** | 视同客户掏的现金，绝对不能当做医保报销减掉！ | `基数 = totalAmount - fundPayAmount` 不扣 accountPayAmount |
| **计算先后顺序** | 如果先扣总免赔，再算明细限额，会导致客户亏钱。 | **必须先算明细级限额**，汇总成"有效基数"后，**再扣总免赔额**。 |
| **多次理赔免赔额** | 第二次理赔不能再扣一万免赔额。 | 必须引入 `history_deducted` 字段维护状态。 |
| **发票总额兜底** | 客户拿同一张发票去多家公司报销，总获赔不能超过自费。 | 最后一步必须执行 `MIN(计算值, 实际经济损失)`。 |

---

## 十、速查表

| 场景 | 公式 | 关键参数 |
|------|------|----------|
| 通用 | MIN(初步赔付, 单次/年度/分项限额, 补偿上限) | 全部可配置 |
| 有医保 | 基数 = total - 医保统筹 - 其他补偿 | fundPayAmount可赔 |
| 无医保 | 基数 = total - 其他补偿 | 无医保统筹扣减 |
| 年免赔 | 本次扣 = MIN(基数, 免赔额-历史已扣) | history_deducted |
| 既往症 | 比例 = MIN(基础比例, 既往症比例) | pre_history |
| 补偿原则 | 最终 = MIN(计算值, 实际损失) | 兜底保护 |