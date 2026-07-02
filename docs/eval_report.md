# MPCI QA Evaluation Report

Generated at: 2026-07-02 16:53:54

## Summary

- Retrieval hit rate: 15/15
- Customer-answer pass rate: 12/12

## Retrieval Cases

| Status | ID | Expected Sections | Retrieved Sections | Question |
|---|---|---|---|---|
| PASS | `timing_zh` | 3.3 | 3.3, 4.3, 4.3.1, 6.2.4, 4.5 | 申报截止时间是多久？ |
| PASS | `timing_en` | 3.3 | 3.3, 6.1.4, 3.2, 6.2.1, 6.1.3.1 | What is the filing timing for master bill and direct bill? |
| PASS | `consignee_to_order` | 5.2, 12.3 | 5.2, 12.3, 5.1, 5.3.1, 10 | To Order 提单的收货人应该怎么填？ |
| PASS | `hs_code` | 5.1, 12.4 | 12.4, 5.1, 12.4, 12.4, 12.4 | 多个 HS Code 怎么申报？ |
| PASS | `hbl_mandatory_document_general_info` | 3.2, 5.1, 5.2 | 3.2, 5.1, 12.4, 5.2, 6.1.3 | Is there any special document mandatory for HBL since some shipper only provide us general information? (Such as minimum hs code, commodity details, shipper and cnee detail) |
| PASS | `delegation` | 4.6.1 | 4.6, 4.6.1, 4.6.2, 6.1.3, 4.6.3 | 我可以委托海外货代代申报吗？ |
| PASS | `shipping_agent_delegation` | 4.6.2 | 4.6, 4.6.1, 4.6.2, 6.1.3, 4.6.3 | 船公司能不能委托船代处理 MPCI 申报？ |
| PASS | `consolidation` | 6.1 | 6.1, 3.2, 6.1.3, 6.1.5, 6.1.4 | Consolidation 和 co-loading 要怎么申报？ |
| PASS | `forwarder_child_cargo_no_own_bl` | 6.1, 6.1.3, 6.1.5 | 6.1, 3.2, 6.1.3, 6.1.5, 6.1.4 | 我是货代，我的下层会给我货物，但不需要我生成我的提单号，我应该怎么申报？ |
| PASS | `forwarder_child_cargo_no_own_hbl` | 6.1, 6.1.3, 6.1.5 | 6.1, 3.2, 6.1.3, 6.1.5, 6.1.4 | 我是货代，但是我的下层货代直接给我货物，不需要我签发自己的提单 |
| PASS | `dnl` | 4.5, 6.1.4 | 4.5, 4.3.2, 6.2.4, 3.6, 5.3.1 | 收到 Do Not Load 怎么办？ |
| PASS | `rfi` | 4.5, 6.1.4 | 4.5, 4.3.2, 6.2.4, 3.6, 5.3.1 | RFI 是什么意思？需要怎么处理？ |
| PASS | `party_id` | 5.3 | 5.3, 5.3.2, 5.3.1, 6.1.5, 4.1 | MPCI Party ID 是什么，怎么使用？ |
| PASS | `update_bl` | 6.2 | 6.2, 6.2.3, 6.2.1, 6.2.2, 6.1.3.1 | 提单更新有什么规则？ |
| PASS | `split_bill` | 6.2.3 | 6.2, 6.2.3, 6.2.1, 6.2.2, 6.1.3.1 | Split Bill of Lading 怎么处理？ |

## Customer Answer Cases

| Status | ID | Checks | Sources | Answer Preview |
|---|---|---|---|---|
| PASS | `en_hbl_general_info` | language=True, required_content=True, no_reference_leakage=True | 3.2, 5.1, 12.4, 5.2, 6.1.3 | For HBL filing, there is normally no separate “special document” that must be uploaded just because it is an HBL. The key point is that the HBL filing must contain enough complete and specific data for MPCI assessment... |
| PASS | `zh_forwarder_no_own_hbl` | language=True, required_content=True, no_reference_leakage=True | 6.1.2, 6.1, 3.2, 6.1.3, 6.1.5 | 先确认你是否实际签发自己这一层的提单，这是决定申报方式的关键。 ## 你应该怎么做 ### 1. 如果你不签发自己的 House B/L 或 Co-loader B/L 不要为了 MPCI 单独生成一个“你的提单号”。 你这一层如果没有实际签发提单，就不应该虚拟造一个 B/L 来申报。应由实际签发提单的一方申报他们签发的 B/L，并在链路中正确引用上层/下层关系。 你需要做的是协调资料： - 向上层提供你的 MPCI Party ... |
| PASS | `en_to_order_consignee` | language=True, required_content=True, no_reference_leakage=True | 3.2, 5.1, 5.2, 6.1.3, 12.3 | For a To Order B/L, do not enter "To Order" as the consignee name. Use this rule of thumb: \| B/L scenario \| Consignee handling \| \|---\|---\| \| Non-negotiable B/L \| Provide the final consignee name and address \| \| Blank-... |
| PASS | `zh_to_order_bank` | language=True, required_content=True, no_reference_leakage=True | 5.2, 12.3, 5.1, 5.3.1, 10 | ## 收货人（Consignee）填写规则 ### 不可转让提单（Non-Negotiable B/L） \| 要求 \| 说明 \| \|------\|------\| \| ✅ 收货人必须填写 \| 必须提供最终收货人的名称和地址 \| \| ❌ 禁止填货代/同行 \| 附录C明确禁止填写船公司、货运代理和consolidator信息 \| \| ✅ 必须是最终收货人 \| 即实际收到货物的一方 \| ### 可转让提单（Negotiable B/L） ... |
| PASS | `en_dnl_house` | language=True, required_content=True, no_reference_leakage=True | 5.2, 6.1.3, 6.1.2, 6.1.5, 3.2 | If one House B/L receives DNL, that issue affects the related Master B/L, but the other House B/Ls under the same master are not automatically treated as DNL. What you should do: 1. Do not load the cargo covered by th... |
| PASS | `zh_rfi_master` | language=True, required_content=True, no_reference_leakage=True | 6.1.4, 3.2, 5.1, 4.5, 5.2 | ## Request for Information (RFI) ### 含义 NAIC 认为提交的信息不完整、不准确或需要额外文件（如发票、原产地证、装箱单）。 ### RFI 在不同层级的影响 \| RFI 位置 \| 影响 \| \|:---------\|:-----\| \| **Master B/L 层** \| ❌ **不级联**到 House B/L。House 可以收到 ACT，但 Master 在 RFI 解决前不能装船 \| ... |
| PASS | `en_missing_child_psf` | language=True, required_content=True, no_reference_leakage=True | 6.1.3, 6.1.2, 6.1.5, 6.1.4, 3.2 | PSF means Pending Sub Filing. It usually indicates that a lower-layer House B/L is missing, not yet filed, or not correctly linked. What you should do: 1. Contact the relevant sub co-loader or lower-layer forwarder. 2... |
| PASS | `zh_party_id_share` | language=True, required_content=True, no_reference_leakage=True | 6.1.2, 6.1.3, 5.3, 5.3.2, 5.3.1 | ## MPCI Party ID ### 是什么 NAIC 分配给每个经济运营商（船公司、货代、NVOCC）的唯一标识符。 ### 使用场景 \| 场景 \| 要求 \| \|:----\|:-----\| \| **所有申报** \| 申报方必须提供自己的 MPCI Party ID \| \| **委托 - 本地→海外货代** \| 海外货代需引用本地货代的 Party ID \| \| **委托 - 船公司→船代** \| 船代需引用船公司的 Part... |
| PASS | `en_update_after_arrival` | language=True, required_content=True, no_reference_leakage=True | 6.2, 6.2.3, 6.2.1, 6.2.2, 2.2 | Yes, B/L updates can be submitted after the shipment arrives in UAE, but the first filing still has to be submitted before loading. Common update scenarios include: \| Scenario \| Handling \| \|---\|---\| \| Correction or re... |
| PASS | `zh_filing_timing_direct` | language=True, required_content=True, no_reference_leakage=True | 3.3, 4.3, 4.3.1, 6.2.4, 4.5 | ## 申报时限要求 \| 角色 \| 单证类型 \| 截止时间 \| \|:----\|:---------\|:--------:\| \| **船公司 (Shipping Line)** \| Master B/L（主单） \| **装船前 6 小时** \| \| \| Direct B/L（直单） \| **装船前 24 小时** \| \| **货代/Sub Co-loader** \| 最底层 House B/L \| **装船前 24 小时** \| \| ... |
| PASS | `en_vague_goods` | language=True, required_content=True, no_reference_leakage=True | 12.4, 5.1, 12.4, 12.4, 12.4 | Do not declare the goods description as only "general cargo" if the shipper cannot provide exact commodity details. Before filing, ask the shipper to provide: \| Data \| Requirement \| \|---\|---\| \| Goods description \| Spe... |
| PASS | `zh_delegate_sub_to_master` | language=True, required_content=True, no_reference_leakage=True | 6.1.2, 6.1.5, 4.6, 4.6.1, 4.6.2 | ## 委托代理机制 ### 货代委托 (4.6.1) 货代有几种委托选项： - **本地货代 → 海外货代**：委托海外货代代为申报 - **Master Co-loader → Sub Co-loader**：上层委托下层 - **Sub Co-loader → Master Co-loader**：下层委托上层 委托方式：在 NAIC 门户注册时选择： 1. 默认允许任何货代代为申报 2. 指定特定货代 3. 完全禁止委托 *... |

## Notes

- Retrieval passes when at least one expected manual section appears in the top results.
- Customer-answer checks are lightweight guardrails, not a substitute for human review.
- The report is meant to make RAG behavior visible during portfolio review and regression testing.
