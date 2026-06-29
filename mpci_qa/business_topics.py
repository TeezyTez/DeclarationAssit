"""
Business topic routing for MPCI Q&A.

The source document is English while most users ask in Chinese. These rules give
retrieval a small amount of domain knowledge without bypassing the document.
"""

from typing import Dict, List


TOPICS: Dict[str, Dict] = {
    "filing_timing": {
        "keywords": ["时限", "截止", "几小时", "多久", "提前", "迟报", "最晚", "cut-off", "cutoff", "deadline", "pre-load", "preload", "when", "how long", "direct b/l", "direct bl"],
        "queries": [
            "Filing Timing 24 Hours Pre-load 6 Hours Pre-load",
            "filing deadline cutoff pre-load submission timing",
        ],
        "required_sections": ["3.3"],
        "boost_sections": {"3.3": 0.18},
    },
    "consignee": {
        "keywords": ["收货人", "consignee", "to order", "指示提单", "可转让", "不可转让"],
        "queries": [
            "Handling Consignee Data Element Scenarios negotiable non-negotiable to order",
            "Party Information Guidelines consignee final consignee",
        ],
        "required_sections": ["5.2", "12.3"],
        "boost_sections": {"5.2": 0.14, "12.3": 0.08},
    },
    "hs_code": {
        "keywords": ["hs code", "hs编码", "海关编码", "商品编码", "货物描述", "goods description"],
        "queries": [
            "HS Code goods description business data elements",
            "Goods Description Guidelines HS Code package weight goods item",
        ],
        "required_sections": ["5.1", "12.4"],
        "boost_sections": {"5.1": 0.14, "12.4": 0.08},
    },
    "hbl_requirements": {
        "keywords": [
            "hbl", "house bill", "house b/l", "mandatory document", "special document",
            "required document", "general information", "minimum hs code", "commodity details",
            "cnee detail", "shipper detail"
        ],
        "queries": [
            "Required Documents Freight Forwarder house bill of lading HBL",
            "Business Data Elements Bill of Lading Number shipper consignee goods description HS Code package weight container",
            "Freight Forwarder Filing House Bill of Lading mandatory data elements",
        ],
        "required_sections": ["3.2", "5.1", "5.2", "6.1.3"],
        "boost_sections": {"3.2": 0.18, "5.1": 0.16, "5.2": 0.08, "6.1.3": 0.08},
    },
    "delegation": {
        "keywords": ["委托", "delegation", "代理", "代申报", "船代"],
        "queries": ["Delegation Process freight forwarder shipping agent filing delegation"],
        "required_sections": ["4.6", "4.6.1", "4.6.2"],
        "boost_sections": {"4.6": 0.1, "4.6.1": 0.08, "4.6.2": 0.08},
    },
    "consolidation": {
        "keywords": ["consolidation", "合并", "co-load", "co-loader", "拼柜", "同行", "house bill", "下层", "下家", "上层", "提单号", "签发", "自己的提单"],
        "queries": ["Consolidation and Co-loading house bill master co-loader sub co-loader"],
        "required_sections": ["6.1", "6.1.2", "6.1.3", "6.1.5"],
        "boost_sections": {"6.1": 0.1, "6.1.2": 0.06, "6.1.3": 0.06, "6.1.5": 0.06},
    },
    "assessment": {
        "keywords": ["dnl", "do not load", "rfi", "request for information", "psf", "补料", "不装", "拒绝", "pending sub filing"],
        "queries": ["MPCI Shipment Assessment DNL RFI PSF ACT ACW response"],
        "required_sections": ["4.5", "6.1.4"],
        "boost_sections": {"4.5": 0.12, "6.1.4": 0.08},
    },
    "party_id": {
        "keywords": ["party id", "mpci party id", "mpci id", "编号", "注册"],
        "queries": ["MPCI Party ID definition usage issuance sharing"],
        "required_sections": ["5.3", "5.3.1", "5.3.2"],
        "boost_sections": {"5.3": 0.12, "5.3.1": 0.08, "5.3.2": 0.08},
    },
    "update": {
        "keywords": ["更新", "修改", "变更", "update", "amend", "switch bill", "split", "分单"],
        "queries": ["Updating a Bill of Lading update scenarios split bill switch bill"],
        "required_sections": ["6.2", "6.2.1", "6.2.2", "6.2.3"],
        "boost_sections": {"6.2": 0.12, "6.2.1": 0.08, "6.2.2": 0.08, "6.2.3": 0.08},
    },
}


def detect_topics(query: str) -> List[str]:
    normalized = query.lower()
    return [
        topic_name
        for topic_name, topic in TOPICS.items()
        if any(keyword in normalized for keyword in topic["keywords"])
    ]


def expanded_queries(query: str) -> List[str]:
    queries = [query]
    for topic_name in detect_topics(query):
        queries.extend(TOPICS[topic_name].get("queries", []))
    return list(dict.fromkeys(queries))


def required_sections(query: str) -> List[str]:
    sections = []
    for topic_name in detect_topics(query):
        sections.extend(TOPICS[topic_name].get("required_sections", []))
    return list(dict.fromkeys(sections))


def section_boost(query: str, section_num: str) -> float:
    boost = 0.0
    for topic_name in detect_topics(query):
        boost = max(boost, TOPICS[topic_name].get("boost_sections", {}).get(section_num, 0.0))
    return boost
