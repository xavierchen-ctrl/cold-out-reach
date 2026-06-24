"""名單去重 / 防呆共用邏輯：公司名正規化 + 衝突偵測。
手動新增、爬蟲匯入、CSV 匯入共用同一套，避免行為不一致。
"""
import re

from models import Lead

_SUFFIXES = [
    "股份有限公司", "有限公司", "股份公司", "企業社", "工作室", "公司",
    "co.,ltd.", "co., ltd.", "co.ltd", "co ltd", "ltd.", "ltd", "inc.", "inc",
    "corporation", "corp.", "corp", "company", "co.", "group", "集團",
]


def normalize_company(name: str) -> str:
    """去除公司型態字樣、地區字樣、空白標點，用於相似公司名比對。"""
    n = (name or "").strip().lower()
    for s in _SUFFIXES:
        n = n.replace(s, "")
    n = re.sub(r"台灣|臺灣|分公司|总公司|總公司", "", n)
    n = re.sub(r"[\s\-_、,.()（）&·.]", "", n)
    return n


def domain(url: str) -> str:
    """從官網 URL 萃取主網域（去 scheme/www/path）。"""
    if not url:
        return ""
    u = url.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u.split("/")[0].split("?")[0].strip()


def build_conflict_index(db) -> dict:
    """一次載入現有名單建立查表索引（供大批匯入逐筆 O(1) 比對）。"""
    rows = db.query(
        Lead.id, Lead.company_name, Lead.department, Lead.tax_id, Lead.website
    ).all()
    by_tax: dict = {}
    by_domain: dict = {}
    by_norm: dict = {}
    for r in rows:
        info = {"id": str(r.id), "company_name": r.company_name, "department": r.department}
        tax = (r.tax_id or "").strip()
        if tax:
            by_tax.setdefault(tax, info)
        d = domain(r.website or "")
        if d:
            by_domain.setdefault(d, info)
        n = normalize_company(r.company_name or "")
        if n:
            by_norm.setdefault(n, []).append(((r.department or "").strip().lower(), info))
    return {"tax": by_tax, "domain": by_domain, "norm": by_norm}


def check_conflict(index: dict, company_name: str, tax_id: str = None,
                   website: str = None, department: str = None):
    """回傳 (status, matched, reason)
      status: 'new'（可直接建立）/ 'conflict'（與現有相似，需人工判斷）/
              'duplicate'（同公司同部門，視為單純重複）
      matched: 對應到的現有名單 {id, company_name, department} 或 None
    """
    tax = (tax_id or "").strip()
    if tax and tax in index["tax"]:
        m = index["tax"][tax]
        return "conflict", m, f"統一編號相同（{tax}）"

    d = domain(website or "")
    if d and d in index["domain"]:
        m = index["domain"][d]
        return "conflict", m, f"官網網域相同（{d}）"

    n = normalize_company(company_name or "")
    dept = (department or "").strip().lower()
    if n and n in index["norm"]:
        for (r_dept, info) in index["norm"][n]:
            if r_dept == dept:
                return "duplicate", info, ""
        m = index["norm"][n][0][1]
        return "conflict", m, f"公司名稱相似（{m['company_name']}）"

    return "new", None, ""


def add_to_index(index: dict, company_name: str, tax_id: str = None,
                 website: str = None, department: str = None):
    """把本批次已處理的公司加入索引，避免同一批內重複。"""
    info = {"id": None, "company_name": company_name, "department": department}
    tax = (tax_id or "").strip()
    if tax:
        index["tax"].setdefault(tax, info)
    d = domain(website or "")
    if d:
        index["domain"].setdefault(d, info)
    n = normalize_company(company_name or "")
    if n:
        index["norm"].setdefault(n, []).append(((department or "").strip().lower(), info))
