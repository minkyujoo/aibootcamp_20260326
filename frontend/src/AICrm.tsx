import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

/** VITE_API_BASE 가 있으면 사용. 없으면 상대 경로 `/api/crm` → Vite 프록시(같은 호스트로 접속 시 LAN에서도 동작). */
const CRM_API_ROOT = (() => {
  const v = import.meta.env.VITE_API_BASE as string | undefined;
  if (v != null && String(v).trim() !== "") return String(v).replace(/\/$/, "");
  return "";
})();
const API = CRM_API_ROOT ? `${CRM_API_ROOT}/api/crm` : "/api/crm";
const PAGE_SIZE = 10;

/** 질문 실행만: 프록시/포트 불일치 시 여러 베이스로 재시도 (404는 다음 후보로). */
function crmOrchestrateBases(): string[] {
  const out: string[] = [];
  const add = (raw: string) => {
    let t = raw.replace(/\/$/, "");
    if (!t) return;
    if (!t.includes("://") && typeof window !== "undefined") {
      try {
        t = new URL(t, window.location.origin).href.replace(/\/$/, "");
      } catch {
        return;
      }
    }
    if (!out.includes(t)) out.push(t);
  };
  add(API);
  if (typeof window !== "undefined") {
    try {
      add(new URL("/api/crm", window.location.href).href);
    } catch {
      /* ignore */
    }
  }
  add("http://127.0.0.1:8000/api/crm");
  add("http://localhost:8000/api/crm");
  return out;
}

async function postCrmOrchestrate(payload: string): Promise<Response> {
  const bases = crmOrchestrateBases();
  const paths = ["/orchestrate", "/ai-query"];
  let last: Response | null = null;
  for (const base of bases) {
    for (const p of paths) {
      const r = await fetch(`${base}${p}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
      });
      if (r.ok) return r;
      last = r;
      if (r.status !== 404 && r.status !== 405) return r;
    }
  }
  return last!;
}

type SalesRep = { id: number; name: string; email: string | null };
type Company = {
  id: number;
  name: string;
  biz_reg_no: string | null;
  address: string | null;
  industry: string | null;
  dart_profile?: string | null;
  data_source_note: string;
  sales_rep_id: number | null;
};
type CompanyDetail = Company & { opportunities_count: number; activities_count: number };
type Opportunity = {
  id: number;
  company_id: number;
  name: string;
  project_type: string;
  stage: string;
  win_probability: number;
  sales_rep_id: number | null;
  win_probability_rationale?: string | null;
};
type Activity = {
  id: number;
  kind: string;
  subject: string;
  body: string;
  company_id: number | null;
  opportunity_id: number | null;
  sales_rep_id: number | null;
  created_at: string | null;
};

type ActionItemT = {
  id: number;
  company_id: number;
  opportunity_id: number | null;
  title: string;
  hint: string;
  sort_order: number;
  status: string;
  result_subject: string | null;
  result_body: string | null;
  result_attachment_excerpt: string | null;
  updated_at: string | null;
};

type Menu = "companies" | "opportunities" | "reps" | "activities";

const MENU_AI_HINT: Record<Menu, string> = {
  companies:
    "고객사 정보, 담당 배정, 연결 사업기회·활동 요약 등을 물어보세요. 질문에 고객사 이름을 넣으면 자동으로 매칭됩니다.",
  opportunities:
    "사업기회 상세, 단계·수주확률, 영업담당 매핑 등을 물어보세요. 기회 이름(예: ERP 구축)을 문장에 포함하면 도움이 됩니다.",
  reps:
    "담당자 행을 선택한 뒤 질문하면 맥락이 붙습니다(담당자가 한 명뿐이면 자동). Action item·할 일 추천도 이 메뉴에서 하세요.",
  activities:
    "활동 매핑·다음 액션 추천 등을 물어보세요. 활동 등록은 제목·본문·첨부만 넣으면 저장 시 자동으로 고객사/사업기회를 맞춥니다(직접 선택도 가능).",
};

const STAGES = ["발굴", "니즈확인", "제안", "협상", "계약", "수주", "실주"] as const;

const FILE_ACCEPT =
  ".txt,.csv,.eml,.docx,.xlsx,.xlsm,.pptx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-outlook";

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

type OrchestrateRes = {
  routed_agent: string;
  routing_reason: string;
  answer: string;
  structured?: Record<string, unknown> | null;
};

export function AICrm() {
  const [menu, setMenu] = useState<Menu>("companies");
  const [reps, setReps] = useState<SalesRep[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [err, setErr] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const [coPage, setCoPage] = useState(1);
  const [selCompany, setSelCompany] = useState<number | null>(null);
  const [companyDetail, setCompanyDetail] = useState<CompanyDetail | null>(null);
  const [editCoName, setEditCoName] = useState("");
  const [editCoBrn, setEditCoBrn] = useState("");
  const [editCoAddr, setEditCoAddr] = useState("");
  const [editCoInd, setEditCoInd] = useState("");
  const [editCoNote, setEditCoNote] = useState("");
  const [editCoDart, setEditCoDart] = useState("");
  const [editCoRep, setEditCoRep] = useState<number | "">("");
  const [newCoName, setNewCoName] = useState("");
  const [newCoBrn, setNewCoBrn] = useState("");
  const [newCoAddr, setNewCoAddr] = useState("");
  const [newCoInd, setNewCoInd] = useState("");
  const [newCoNote, setNewCoNote] = useState("");
  const [newCoRep, setNewCoRep] = useState<number | "">("");
  const [coRegisterOpen, setCoRegisterOpen] = useState(false);
  const [oppRegisterOpen, setOppRegisterOpen] = useState(false);
  const [oppPage, setOppPage] = useState(1);
  const [coCompanyActions, setCoCompanyActions] = useState<ActionItemT[]>([]);
  const [coSelActId, setCoSelActId] = useState<number | null>(null);
  const [inlineOppDetail, setInlineOppDetail] = useState<Opportunity | null>(null);
  const [inlineOppActs, setInlineOppActs] = useState<Activity[]>([]);
  const [inlineOppActions, setInlineOppActions] = useState<ActionItemT[]>([]);
  const [inlineOppSelActId, setInlineOppSelActId] = useState<number | null>(null);
  const [actionExecItem, setActionExecItem] = useState<ActionItemT | null>(null);
  const [actionExecSubj, setActionExecSubj] = useState("");
  const [actionExecBody, setActionExecBody] = useState("");
  const [actionExecFiles, setActionExecFiles] = useState<File[]>([]);
  const [selOpp, setSelOpp] = useState<number | null>(null);
  const [oppDetail, setOppDetail] = useState<Opportunity | null>(null);
  const [editOppName, setEditOppName] = useState("");
  const [editOppPt, setEditOppPt] = useState("");
  const [editOppStage, setEditOppStage] = useState("");
  const [editOppCo, setEditOppCo] = useState<number | "">("");
  const [selRep, setSelRep] = useState<number | null>(null);
  const [repSummary, setRepSummary] = useState<{
    rep: SalesRep;
    companies: Company[];
    opportunities: Opportunity[];
  } | null>(null);

  const [actSubject, setActSubject] = useState("");
  const [actBody, setActBody] = useState("");
  const [actCompany, setActCompany] = useState<number | "">("");
  const [actOpp, setActOpp] = useState<number | "">("");
  const [actRep, setActRep] = useState<number | "">("");
  const [actFiles, setActFiles] = useState<File[]>([]);
  const [suggestMsg, setSuggestMsg] = useState("");

  const [orchMsg, setOrchMsg] = useState("");
  const [orchOut, setOrchOut] = useState("");
  const [orchRoute, setOrchRoute] = useState("");
  const [orchStructured, setOrchStructured] = useState<unknown>(null);
  const [orchRunning, setOrchRunning] = useState(false);
  const [orchStatusNote, setOrchStatusNote] = useState("");

  const [coActs, setCoActs] = useState<Activity[]>([]);
  const [oppActs, setOppActs] = useState<Activity[]>([]);
  const [newRepName, setNewRepName] = useState("");
  const [oppFilterCo, setOppFilterCo] = useState<number | "">("");
  const [newOppCo, setNewOppCo] = useState<number | "">("");
  const [newOppName, setNewOppName] = useState("");
  const [newOppPt, setNewOppPt] = useState("SI");
  const [newOppStage, setNewOppStage] = useState<string>("발굴");
  const [newOppRep, setNewOppRep] = useState<number | "">("");
  const [oppActionItems, setOppActionItems] = useState<ActionItemT[]>([]);
  const [oppSelActId, setOppSelActId] = useState<number | null>(null);
  const [oppActionExecItem, setOppActionExecItem] = useState<ActionItemT | null>(null);
  const [oppExecSubj, setOppExecSubj] = useState("");
  const [oppExecBody, setOppExecBody] = useState("");
  const [oppExecFiles, setOppExecFiles] = useState<File[]>([]);

  const loadCore = useCallback(async () => {
    setErr("");
    try {
      const [r, c, o] = await Promise.all([
        j<SalesRep[]>("/sales-reps"),
        j<Company[]>("/companies"),
        j<Opportunity[]>("/opportunities"),
      ]);
      setReps(r);
      setCompanies(c);
      setOpps(o);
    } catch (e) {
      setErr(String(e));
    }
  }, []);

  useEffect(() => {
    void loadCore();
  }, [loadCore]);

  useEffect(() => {
    if (menu !== "companies") setCoRegisterOpen(false);
    if (menu !== "opportunities") setOppRegisterOpen(false);
  }, [menu]);

  useEffect(() => {
    setOppPage(1);
  }, [oppFilterCo]);

  useEffect(() => {
    if (!companyDetail) return;
    setEditCoName(companyDetail.name);
    setEditCoBrn(companyDetail.biz_reg_no ?? "");
    setEditCoAddr(companyDetail.address ?? "");
    setEditCoInd(companyDetail.industry ?? "");
    setEditCoNote(companyDetail.data_source_note ?? "");
    setEditCoDart(companyDetail.dart_profile ?? "");
    setEditCoRep(companyDetail.sales_rep_id ?? "");
  }, [companyDetail]);

  const totalCoPages = Math.max(1, Math.ceil(companies.length / PAGE_SIZE));
  useEffect(() => {
    if (coPage > totalCoPages) setCoPage(totalCoPages);
  }, [coPage, totalCoPages]);

  const pagedCompanies = useMemo(
    () => companies.slice((coPage - 1) * PAGE_SIZE, coPage * PAGE_SIZE),
    [companies, coPage],
  );

  const companyName = useCallback(
    (id: number | null | undefined) =>
      companies.find((x) => x.id === id)?.name ?? `id ${id ?? "-"}`,
    [companies],
  );

  const refreshActionListsAfterSave = async (saved: ActionItemT) => {
    if (saved.opportunity_id == null) {
      setCoCompanyActions(await j<ActionItemT[]>(`/companies/${saved.company_id}/action-items`));
    } else {
      const oid = saved.opportunity_id;
      const list = await j<ActionItemT[]>(`/opportunities/${oid}/action-items`);
      if (inlineOppDetail?.id === oid) {
        setInlineOppActions(list);
      }
      if (selOpp === oid) {
        setOppActionItems(list);
      }
    }
  };

  const openCompany = async (id: number) => {
    setCoRegisterOpen(false);
    setSelCompany(id);
    setInlineOppDetail(null);
    setInlineOppActs([]);
    setInlineOppActions([]);
    setCoSelActId(null);
    setInlineOppSelActId(null);
    setActionExecItem(null);
    setActionExecFiles([]);
    setErr("");
    try {
      const d = await j<CompanyDetail>(`/companies/${id}`);
      setCompanyDetail(d);
      const [a, ai] = await Promise.all([
        j<Activity[]>(`/activities?company_id=${id}`),
        j<ActionItemT[]>(`/companies/${id}/action-items`),
      ]);
      setCoActs(a);
      setCoCompanyActions(ai);
    } catch (e) {
      setErr(String(e));
    }
  };

  const openLinkedOppInCompany = async (oppId: number) => {
    setErr("");
    try {
      const o = await j<Opportunity>(`/opportunities/${oppId}`);
      setInlineOppDetail(o);
      const [acts, actsAi] = await Promise.all([
        j<Activity[]>(`/activities?opportunity_id=${oppId}`),
        j<ActionItemT[]>(`/opportunities/${oppId}/action-items`),
      ]);
      setInlineOppActs(acts);
      setInlineOppActions(actsAi);
      setInlineOppSelActId(null);
    } catch (e) {
      setErr(String(e));
    }
  };

  const openOpp = async (id: number) => {
    setOppRegisterOpen(false);
    setSelOpp(id);
    setErr("");
    try {
      const o = await j<Opportunity>(`/opportunities/${id}`);
      setOppDetail(o);
      setEditOppName(o.name);
      setEditOppPt(o.project_type);
      setEditOppStage(o.stage);
      setEditOppCo(o.company_id);
      const [a, oai] = await Promise.all([
        j<Activity[]>(`/activities?opportunity_id=${id}`),
        j<ActionItemT[]>(`/opportunities/${id}/action-items`),
      ]);
      setOppActs(a);
      setOppActionItems(oai);
      setOppSelActId(null);
      setOppActionExecItem(null);
      setOppExecFiles([]);
    } catch (e) {
      setErr(String(e));
    }
  };

  const openRep = async (id: number) => {
    setSelRep(id);
    setErr("");
    try {
      const s = await j<{ rep: SalesRep; companies: Company[]; opportunities: Opportunity[] }>(
        `/sales-reps/${id}/summary`,
      );
      setRepSummary(s);
    } catch (e) {
      setErr(String(e));
    }
  };

  const onSaveActivity = async () => {
    const hasText = actSubject.trim() || actBody.trim();
    if (!hasText && actFiles.length === 0) {
      setErr("제목·본문 중 하나를 쓰거나, 첨부 파일을 추가하세요.");
      return;
    }
    setLoading(true);
    setErr("");
    try {
      const fd = new FormData();
      fd.append("kind", "note");
      fd.append("subject", actSubject.trim());
      fd.append("body", actBody.trim());
      if (actCompany !== "") fd.append("company_id", String(actCompany));
      if (actOpp !== "") fd.append("opportunity_id", String(actOpp));
      if (actRep !== "") fd.append("sales_rep_id", String(actRep));
      for (const f of actFiles) fd.append("files", f);
      const r = await fetch(`${API}/activities/with-files`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(await r.text());
      setActSubject("");
      setActBody("");
      setActFiles([]);
      setSuggestMsg("저장되었습니다. 고객사/기회는 본문·첨부 기준으로 자동 매핑되었을 수 있습니다.");
      await loadCore();
      if (selCompany && actCompany === selCompany) void openCompany(selCompany);
      if (selOpp && actOpp === selOpp) void openOpp(selOpp);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const onOrchestrate = async () => {
    if (!orchMsg.trim()) return;
    setLoading(true);
    setOrchRunning(true);
    setOrchStatusNote("요청 전송 → 라우팅·MCP RAG·전문 에이전트 실행 중…");
    setOrchOut("");
    setOrchRoute("");
    setOrchStructured(null);
    setErr("");
    try {
      let ctxCompanyId: number | undefined =
        menu === "companies" && selCompany != null
          ? selCompany
          : menu === "opportunities" && oppDetail != null
            ? oppDetail.company_id
            : menu === "opportunities" && oppFilterCo !== ""
              ? Number(oppFilterCo)
              : undefined;
      if (ctxCompanyId == null && menu === "opportunities" && selOpp != null) {
        const o = opps.find((x) => x.id === selOpp);
        if (o) ctxCompanyId = o.company_id;
      }
      const ctxOppId =
        menu === "opportunities" && selOpp != null ? selOpp : undefined;
      const orchText = orchMsg.trim().replace(/\s+/g, " ");
      const body: Record<string, string | number> = {
        message: orchText,
        current_menu: menu,
      };
      if (ctxCompanyId != null) body.context_company_id = ctxCompanyId;
      if (ctxOppId != null) body.context_opportunity_id = ctxOppId;
      const ctxRepId =
        menu === "reps" && selRep != null
          ? selRep
          : menu === "reps" && reps.length === 1
            ? reps[0].id
            : undefined;
      if (ctxRepId != null) body.context_sales_rep_id = ctxRepId;
      const payload = JSON.stringify(body);
      const r = await postCrmOrchestrate(payload);
      if (!r.ok) throw new Error(await r.text());
      const res = (await r.json()) as OrchestrateRes;
      setOrchOut(res.answer);
      setOrchRoute(`${res.routed_agent} — ${res.routing_reason}`);
      setOrchStructured(res.structured ?? null);
      setOrchStatusNote(`완료 · ${new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`);
    } catch (e) {
      setErr(String(e));
      setOrchStatusNote(
        `중단/오류 · ${new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`,
      );
    } finally {
      setOrchRunning(false);
      setLoading(false);
    }
  };

  const oppsForCompany = useMemo(() => {
    if (actCompany === "") return opps;
    return opps.filter((o) => o.company_id === actCompany);
  }, [opps, actCompany]);

  const displayedOpps = useMemo(() => {
    if (oppFilterCo === "") return opps;
    return opps.filter((o) => o.company_id === oppFilterCo);
  }, [opps, oppFilterCo]);

  const totalOppPages = Math.max(1, Math.ceil(displayedOpps.length / PAGE_SIZE));
  useEffect(() => {
    if (oppPage > totalOppPages) setOppPage(totalOppPages);
  }, [oppPage, totalOppPages]);

  const pagedDisplayedOpps = useMemo(
    () => displayedOpps.slice((oppPage - 1) * PAGE_SIZE, oppPage * PAGE_SIZE),
    [displayedOpps, oppPage],
  );

  const addRep = async () => {
    const name = newRepName.trim();
    if (!name) return;
    setLoading(true);
    setErr("");
    try {
      await j("/sales-reps", { method: "POST", body: JSON.stringify({ name }) });
      setNewRepName("");
      await loadCore();
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const delRep = async (id: number) => {
    if (!confirm("이 담당자를 삭제할까요?")) return;
    setLoading(true);
    try {
      await fetch(`${API}/sales-reps/${id}`, { method: "DELETE" });
      if (selRep === id) {
        setSelRep(null);
        setRepSummary(null);
      }
      await loadCore();
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const saveCompanyInfo = async () => {
    if (!companyDetail) return;
    setLoading(true);
    setErr("");
    try {
      await j(`/companies/${companyDetail.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: editCoName.trim(),
          biz_reg_no: editCoBrn.trim() || null,
          address: editCoAddr.trim() || null,
          industry: editCoInd.trim() || null,
          dart_profile: editCoDart.trim() || null,
          data_source_note: editCoNote.trim(),
          sales_rep_id: editCoRep === "" ? null : editCoRep,
        }),
      });
      await loadCore();
      await openCompany(companyDetail.id);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const createNewCompany = async () => {
    const name = newCoName.trim();
    if (!name) {
      setErr("신규 고객사 이름을 입력하세요.");
      return;
    }
    setLoading(true);
    setErr("");
    try {
      const c = await j<Company>(`/companies`, {
        method: "POST",
        body: JSON.stringify({
          name,
          biz_reg_no: newCoBrn.trim() || null,
          address: newCoAddr.trim() || null,
          industry: newCoInd.trim() || null,
          data_source_note: newCoNote.trim() || null,
          sales_rep_id: newCoRep === "" ? null : newCoRep,
        }),
      });
      setNewCoName("");
      setNewCoBrn("");
      setNewCoAddr("");
      setNewCoInd("");
      setNewCoNote("");
      setNewCoRep("");
      await loadCore();
      await openCompany(c.id);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const submitCompanyPanelAction = async (status: "in_progress" | "done") => {
    if (!actionExecItem) return;
    setLoading(true);
    setErr("");
    try {
      const fd = new FormData();
      fd.append("status", status);
      fd.append("result_subject", actionExecSubj.trim());
      fd.append("result_body", actionExecBody.trim());
      for (const f of actionExecFiles) fd.append("files", f);
      const r = await fetch(
        `${API}/action-items/${actionExecItem.id}/execute-with-files`,
        { method: "POST", body: fd },
      );
      if (!r.ok) throw new Error(await r.text());
      const saved = (await r.json()) as ActionItemT;
      setActionExecItem(saved);
      setActionExecFiles([]);
      await refreshActionListsAfterSave(saved);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const submitOppMenuAction = async (status: "in_progress" | "done") => {
    if (!oppActionExecItem) return;
    setLoading(true);
    setErr("");
    try {
      const fd = new FormData();
      fd.append("status", status);
      fd.append("result_subject", oppExecSubj.trim());
      fd.append("result_body", oppExecBody.trim());
      for (const f of oppExecFiles) fd.append("files", f);
      const r = await fetch(
        `${API}/action-items/${oppActionExecItem.id}/execute-with-files`,
        { method: "POST", body: fd },
      );
      if (!r.ok) throw new Error(await r.text());
      const saved = (await r.json()) as ActionItemT;
      setOppActionExecItem(saved);
      setOppExecFiles([]);
      await refreshActionListsAfterSave(saved);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const patchOpp = async (
    oppId: number,
    patch: Partial<
      Pick<Opportunity, "name" | "project_type" | "stage" | "sales_rep_id" | "company_id">
    >,
  ) => {
    setLoading(true);
    try {
      const body: Record<string, unknown> = {};
      if (patch.stage != null) body.stage = patch.stage;
      if (patch.sales_rep_id !== undefined) body.sales_rep_id = patch.sales_rep_id;
      if (patch.name != null) body.name = patch.name;
      if (patch.project_type != null) body.project_type = patch.project_type;
      if (patch.company_id != null) body.company_id = patch.company_id;
      await j(`/opportunities/${oppId}`, { method: "PATCH", body: JSON.stringify(body) });
      await loadCore();
      if (selOpp === oppId) void openOpp(oppId);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const saveOppEdits = () => {
    if (!oppDetail) return;
    void patchOpp(oppDetail.id, {
      name: editOppName.trim(),
      project_type: editOppPt.trim(),
      stage: editOppStage,
      company_id: editOppCo === "" ? undefined : Number(editOppCo),
    });
  };

  const createOpp = async () => {
    if (newOppCo === "" || !newOppName.trim()) {
      setErr("신규 사업기회: 고객사와 이름을 입력하세요.");
      return;
    }
    setLoading(true);
    setErr("");
    try {
      const created = await j<Opportunity>("/opportunities", {
        method: "POST",
        body: JSON.stringify({
          company_id: newOppCo,
          name: newOppName.trim(),
          project_type: newOppPt.trim() || "SI",
          stage: newOppStage,
          sales_rep_id: newOppRep === "" ? null : newOppRep,
        }),
      });
      setNewOppName("");
      setOppRegisterOpen(false);
      await loadCore();
      await openOpp(created.id);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const deleteOpp = async (id: number) => {
    if (!confirm("이 사업기회를 삭제할까요? 연결 활동의 기회 링크는 해제됩니다.")) return;
    setLoading(true);
    try {
      await fetch(`${API}/opportunities/${id}`, { method: "DELETE" });
      if (selOpp === id) {
        setSelOpp(null);
        setOppDetail(null);
      }
      await loadCore();
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={s.wrap}>
      <aside style={s.aside}>
        <div style={s.asideTitle}>AI 영업관리 포탈</div>
        <nav style={s.nav}>
          {(
            [
              ["companies", "고객사"],
              ["opportunities", "사업기회"],
              ["reps", "영업담당"],
              ["activities", "활동등록"],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              style={menu === k ? s.navBtnOn : s.navBtn}
              onClick={() => setMenu(k)}
            >
              {label}
            </button>
          ))}
        </nav>
        <p style={s.note}>
          오른쪽 패널에서 AI 영업관리 Agent가 질문 의도에 맞는 전문 에이전트를 자동 선택합니다 (MCP RAG 맥락
          보강).
        </p>
      </aside>

      <div style={s.centerRow}>
        <div style={s.mainCol}>
          {err ? <div style={s.err}>{err}</div> : null}

          {menu === "companies" ? (
            <div style={s.split}>
              <section style={s.cardList}>
                <div style={s.coPanelHead}>
                  <h2 style={{ ...s.h2, margin: 0 }}>고객사 목록</h2>
                  <button
                    type="button"
                    style={s.primary}
                    disabled={loading}
                    onClick={() => {
                      setCoRegisterOpen(true);
                      setErr("");
                    }}
                  >
                    고객사 등록
                  </button>
                </div>
                <div style={s.pager}>
                  <button
                    type="button"
                    style={s.ghost}
                    disabled={coPage <= 1}
                    onClick={() => setCoPage((p) => Math.max(1, p - 1))}
                  >
                    이전
                  </button>
                  <span style={s.muted}>
                    {coPage} / {totalCoPages} (총 {companies.length}건, {PAGE_SIZE}건씩)
                  </span>
                  <button
                    type="button"
                    style={s.ghost}
                    disabled={coPage >= totalCoPages}
                    onClick={() => setCoPage((p) => Math.min(totalCoPages, p + 1))}
                  >
                    다음
                  </button>
                </div>
                <ul style={s.list}>
                  {pagedCompanies.map((c) => (
                    <li key={c.id} style={s.li}>
                      <button
                        type="button"
                        style={selCompany === c.id ? s.linkBtnOn : s.linkBtn}
                        onClick={() => void openCompany(c.id)}
                      >
                        {c.name}
                      </button>
                      <span style={s.muted}> · 담당 {c.sales_rep_id ? `#${c.sales_rep_id}` : "미배정"}</span>
                    </li>
                  ))}
                </ul>
              </section>
              <section style={s.cardDetail}>
                {coRegisterOpen ? (
                  <>
                    <div style={s.coPanelHead}>
                      <h2 style={{ ...s.h2, margin: 0 }}>고객사 등록</h2>
                      <button
                        type="button"
                        style={s.ghost}
                        disabled={loading}
                        onClick={() => setCoRegisterOpen(false)}
                      >
                        닫기
                      </button>
                    </div>
                    <p style={s.small}>
                      회사명은 필수입니다. 저장 후 해당 고객사 상세 화면으로 이동합니다.
                    </p>
                    <input
                      style={s.input}
                      placeholder="회사명 *"
                      value={newCoName}
                      onChange={(e) => setNewCoName(e.target.value)}
                    />
                    <input
                      style={s.input}
                      placeholder="사업자등록번호"
                      value={newCoBrn}
                      onChange={(e) => setNewCoBrn(e.target.value)}
                    />
                    <input
                      style={s.input}
                      placeholder="주소"
                      value={newCoAddr}
                      onChange={(e) => setNewCoAddr(e.target.value)}
                    />
                    <input
                      style={s.input}
                      placeholder="업종"
                      value={newCoInd}
                      onChange={(e) => setNewCoInd(e.target.value)}
                    />
                    <textarea
                      style={s.textarea}
                      rows={2}
                      placeholder="데이터 출처·비고"
                      value={newCoNote}
                      onChange={(e) => setNewCoNote(e.target.value)}
                    />
                    <label style={s.lbl}>
                      담당자
                      <select
                        style={s.select}
                        value={newCoRep === "" ? "" : String(newCoRep)}
                        onChange={(e) =>
                          setNewCoRep(e.target.value === "" ? "" : Number(e.target.value))
                        }
                      >
                        <option value="">미배정</option>
                        {reps.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      style={s.primary}
                      disabled={loading}
                      onClick={() => void createNewCompany()}
                    >
                      고객사 등록
                    </button>
                  </>
                ) : companyDetail && selCompany ? (
                  <>
                    <div style={s.coPanelHead}>
                      <h2 style={{ ...s.h2, margin: 0 }}>고객사 상세 · 편집</h2>
                      <button
                        type="button"
                        style={s.ghost}
                        disabled={loading}
                        onClick={() => {
                          setCoRegisterOpen(true);
                          setErr("");
                        }}
                      >
                        고객사 등록
                      </button>
                    </div>
                    <p style={s.small}>
                      사업기회 {companyDetail.opportunities_count}건 · 활동 {companyDetail.activities_count}건
                    </p>

                    <label style={s.lbl}>
                      회사명
                      <input
                        style={s.input}
                        value={editCoName}
                        onChange={(e) => setEditCoName(e.target.value)}
                      />
                    </label>
                    <label style={s.lbl}>
                      사업자등록번호
                      <input
                        style={s.input}
                        value={editCoBrn}
                        onChange={(e) => setEditCoBrn(e.target.value)}
                      />
                    </label>
                    <label style={s.lbl}>
                      주소
                      <input
                        style={s.input}
                        value={editCoAddr}
                        onChange={(e) => setEditCoAddr(e.target.value)}
                      />
                    </label>
                    <label style={s.lbl}>
                      업종
                      <input
                        style={s.input}
                        value={editCoInd}
                        onChange={(e) => setEditCoInd(e.target.value)}
                      />
                    </label>
                    {companyDetail.dart_profile?.trim() ? (
                      <label style={s.lbl}>
                        DART·공시 기반 개요
                        <textarea
                          style={s.textarea}
                          rows={6}
                          value={editCoDart}
                          onChange={(e) => setEditCoDart(e.target.value)}
                        />
                      </label>
                    ) : null}
                    <label style={s.lbl}>
                      데이터 출처·비고
                      <textarea
                        style={s.textarea}
                        rows={3}
                        value={editCoNote}
                        onChange={(e) => setEditCoNote(e.target.value)}
                      />
                    </label>
                    <label style={s.lbl}>
                      담당자 배정
                      <select
                        style={s.select}
                        value={editCoRep === "" ? "" : String(editCoRep)}
                        onChange={(e) =>
                          setEditCoRep(e.target.value === "" ? "" : Number(e.target.value))
                        }
                      >
                        <option value="">미배정</option>
                        {reps.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      style={s.primary}
                      disabled={loading}
                      onClick={() => void saveCompanyInfo()}
                    >
                      고객사 정보 저장
                    </button>

                    <h4 style={s.h4}>연결 사업기회 (선택 시 아래에 기회 정보·액션 표시)</h4>
                    <ul style={s.list}>
                      {opps
                        .filter((o) => o.company_id === companyDetail.id)
                        .map((o) => (
                          <li key={o.id} style={s.li}>
                            <button
                              type="button"
                              style={inlineOppDetail?.id === o.id ? s.linkBtnOn : s.linkBtn}
                              onClick={() => void openLinkedOppInCompany(o.id)}
                            >
                              {o.name}
                            </button>
                            <span style={s.muted}>
                              {" "}
                              ({o.stage}, 수주확률 {(o.win_probability * 100).toFixed(1)}%)
                            </span>
                            <button
                              type="button"
                              style={s.ghost}
                              onClick={() => {
                                setMenu("opportunities");
                                void openOpp(o.id);
                              }}
                            >
                              사업기회 메뉴로
                            </button>
                          </li>
                        ))}
                    </ul>

                    {inlineOppDetail ? (
                      <div style={s.nested}>
                        <h4 style={s.h4}>선택한 사업기회 정보</h4>
                        <p style={s.small}>
                          <strong>{inlineOppDetail.name}</strong> · 유형 {inlineOppDetail.project_type} · 단계{" "}
                          {inlineOppDetail.stage} · 수주확률{" "}
                          {(inlineOppDetail.win_probability * 100).toFixed(1)}%
                        </p>
                        <h4 style={s.h4}>이 사업기회 · 추천 액션</h4>
                        <p style={s.tiny}>완료된 항목은 ✓, 진행 중은 ▶ 표시</p>
                        <ul style={s.list}>
                          {inlineOppActions
                            .filter((it) => it.status !== "done")
                            .map((it) => (
                              <li key={it.id} style={s.li}>
                                {it.status === "in_progress" ? <span style={s.badge}>▶ </span> : null}
                                <button
                                  type="button"
                                  style={actionExecItem?.id === it.id ? s.linkBtnOn : s.linkBtn}
                                  onClick={() => {
                                    setActionExecItem(it);
                                    setActionExecSubj(it.result_subject ?? "");
                                    setActionExecBody(it.result_body ?? "");
                                    setActionExecFiles([]);
                                  }}
                                >
                                  {it.title}
                                </button>
                              </li>
                            ))}
                        </ul>
                        <ul style={s.list}>
                          {inlineOppActions
                            .filter((it) => it.status === "done")
                            .map((it) => (
                              <li key={it.id} style={s.li}>
                                <span style={s.doneMark}>✓ </span>
                                <button
                                  type="button"
                                  style={actionExecItem?.id === it.id ? s.linkBtnOn : s.linkBtn}
                                  onClick={() => {
                                    setActionExecItem(it);
                                    setActionExecSubj(it.result_subject ?? "");
                                    setActionExecBody(it.result_body ?? "");
                                    setActionExecFiles([]);
                                  }}
                                >
                                  {it.title}
                                </button>
                              </li>
                            ))}
                        </ul>
                        <h4 style={s.h4}>이 사업기회 · 영업활동</h4>
                        <ul style={s.list}>
                          {inlineOppActs.map((a) => (
                            <li key={a.id}>
                              <button
                                type="button"
                                style={inlineOppSelActId === a.id ? s.linkBtnOn : s.linkBtn}
                                onClick={() =>
                                  setInlineOppSelActId((prev) => (prev === a.id ? null : a.id))
                                }
                              >
                                {a.subject}
                              </button>
                            </li>
                          ))}
                        </ul>
                        {inlineOppSelActId ? (
                          <pre style={s.pre}>
                            {
                              inlineOppActs.find((x) => x.id === inlineOppSelActId)?.body ?? ""
                            }
                          </pre>
                        ) : null}
                      </div>
                    ) : null}

                    <h4 style={s.h4}>고객사 단위 · 추천 액션</h4>
                    <ul style={s.list}>
                      {coCompanyActions
                        .filter((it) => it.status !== "done")
                        .map((it) => (
                          <li key={it.id} style={s.li}>
                            {it.status === "in_progress" ? <span style={s.badge}>▶ </span> : null}
                            <button
                              type="button"
                              style={actionExecItem?.id === it.id ? s.linkBtnOn : s.linkBtn}
                              onClick={() => {
                                setActionExecItem(it);
                                setActionExecSubj(it.result_subject ?? "");
                                setActionExecBody(it.result_body ?? "");
                                setActionExecFiles([]);
                              }}
                            >
                              {it.title}
                            </button>
                          </li>
                        ))}
                    </ul>
                    <ul style={s.list}>
                      {coCompanyActions
                        .filter((it) => it.status === "done")
                        .map((it) => (
                          <li key={it.id} style={s.li}>
                            <span style={s.doneMark}>✓ </span>
                            <button
                              type="button"
                              style={actionExecItem?.id === it.id ? s.linkBtnOn : s.linkBtn}
                              onClick={() => {
                                setActionExecItem(it);
                                setActionExecSubj(it.result_subject ?? "");
                                setActionExecBody(it.result_body ?? "");
                                setActionExecFiles([]);
                              }}
                            >
                              {it.title}
                            </button>
                          </li>
                        ))}
                    </ul>

                    <h4 style={s.h4}>고객사 · 영업활동 (제목 선택 시 본문)</h4>
                    <ul style={s.list}>
                      {coActs.map((a) => (
                        <li key={a.id}>
                          <button
                            type="button"
                            style={coSelActId === a.id ? s.linkBtnOn : s.linkBtn}
                            onClick={() => setCoSelActId((prev) => (prev === a.id ? null : a.id))}
                          >
                            {a.subject}
                          </button>
                        </li>
                      ))}
                    </ul>
                    {coSelActId ? (
                      <pre style={s.pre}>{coActs.find((x) => x.id === coSelActId)?.body ?? ""}</pre>
                    ) : null}

                    {actionExecItem ? (
                      <div style={s.execBox}>
                        <h4 style={s.h4}>액션 실행 · {actionExecItem.title}</h4>
                        <p style={s.small}>{actionExecItem.hint}</p>
                        {actionExecItem.result_body ? (
                          <pre style={s.preSm}>기존 기록: {actionExecItem.result_body}</pre>
                        ) : null}
                        <input
                          style={s.input}
                          placeholder="제목/요약"
                          value={actionExecSubj}
                          onChange={(e) => setActionExecSubj(e.target.value)}
                        />
                        <textarea
                          style={s.textarea}
                          rows={4}
                          placeholder="진행 내용"
                          value={actionExecBody}
                          onChange={(e) => setActionExecBody(e.target.value)}
                        />
                        <label style={s.lbl}>
                          첨부
                          <input
                            type="file"
                            multiple
                            accept={FILE_ACCEPT}
                            onChange={(e) =>
                              setActionExecFiles(e.target.files ? Array.from(e.target.files) : [])
                            }
                          />
                        </label>
                        <div style={s.row}>
                          <button
                            type="button"
                            style={s.ghost}
                            disabled={loading}
                            onClick={() => void submitCompanyPanelAction("in_progress")}
                          >
                            진행 중으로 저장
                          </button>
                          <button
                            type="button"
                            style={s.primary}
                            disabled={loading}
                            onClick={() => void submitCompanyPanelAction("done")}
                          >
                            완료
                          </button>
                          <button
                            type="button"
                            style={s.ghost}
                            onClick={() => setActionExecItem(null)}
                          >
                            닫기
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <div>
                    <p style={s.placeholder}>
                      왼쪽 목록에서 고객사를 선택하면 이 영역에 상세가 표시됩니다.
                    </p>
                    <button
                      type="button"
                      style={s.primary}
                      disabled={loading}
                      onClick={() => {
                        setCoRegisterOpen(true);
                        setErr("");
                      }}
                    >
                      고객사 등록
                    </button>
                  </div>
                )}
              </section>
            </div>
          ) : null}

          {menu === "opportunities" ? (
            <div style={s.split}>
              <section style={s.cardList}>
                <div style={s.coPanelHead}>
                  <h2 style={{ ...s.h2, margin: 0 }}>사업기회</h2>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                    <button
                      type="button"
                      style={s.primary}
                      disabled={loading}
                      onClick={() => {
                        setOppRegisterOpen(true);
                        setErr("");
                      }}
                    >
                      사업기회 등록
                    </button>
                    <button
                      type="button"
                      style={s.ghost}
                      disabled={loading}
                      onClick={() => {
                        setMenu("companies");
                        setCoRegisterOpen(true);
                        setErr("");
                      }}
                    >
                      고객사 등록
                    </button>
                  </div>
                </div>
                <label style={s.lbl}>
                  목록 필터 · 고객사
                  <select
                    style={s.select}
                    value={oppFilterCo === "" ? "" : String(oppFilterCo)}
                    onChange={(e) =>
                      setOppFilterCo(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  >
                    <option value="">전체</option>
                    {companies.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="button" style={s.ghost} onClick={() => void loadCore()}>
                  목록 새로고침
                </button>
                <div style={s.pager}>
                  <button
                    type="button"
                    style={s.ghost}
                    disabled={oppPage <= 1}
                    onClick={() => setOppPage((p) => Math.max(1, p - 1))}
                  >
                    이전
                  </button>
                  <span style={s.muted}>
                    {oppPage} / {totalOppPages} (총 {displayedOpps.length}건, {PAGE_SIZE}건씩)
                  </span>
                  <button
                    type="button"
                    style={s.ghost}
                    disabled={oppPage >= totalOppPages}
                    onClick={() => setOppPage((p) => Math.min(totalOppPages, p + 1))}
                  >
                    다음
                  </button>
                </div>
                <ul style={s.list}>
                  {pagedDisplayedOpps.map((o) => (
                    <li key={o.id}>
                      <button
                        type="button"
                        style={selOpp === o.id ? s.linkBtnOn : s.linkBtn}
                        onClick={() => void openOpp(o.id)}
                      >
                        {o.name}
                      </button>
                      <span style={s.muted}>
                        {" "}
                        · {companyName(o.company_id)} · 수주확률 {(o.win_probability * 100).toFixed(1)}%
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
              <section style={s.cardDetail}>
                {oppRegisterOpen ? (
                  <>
                    <div style={s.coPanelHead}>
                      <h2 style={{ ...s.h2, margin: 0 }}>사업기회 등록</h2>
                      <button
                        type="button"
                        style={s.ghost}
                        disabled={loading}
                        onClick={() => setOppRegisterOpen(false)}
                      >
                        닫기
                      </button>
                    </div>
                    <p style={s.small}>
                      고객사·기회 이름은 필수입니다. 저장 후 해당 사업기회 상세로 이동합니다.
                    </p>
                    <label style={s.lbl}>
                      고객사
                      <select
                        style={s.select}
                        value={newOppCo === "" ? "" : String(newOppCo)}
                        onChange={(e) =>
                          setNewOppCo(e.target.value === "" ? "" : Number(e.target.value))
                        }
                      >
                        <option value="">선택</option>
                        {companies.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <input
                      style={s.input}
                      placeholder="기회 이름"
                      value={newOppName}
                      onChange={(e) => setNewOppName(e.target.value)}
                    />
                    <input
                      style={s.input}
                      placeholder="유형 (예: SI, ERP)"
                      value={newOppPt}
                      onChange={(e) => setNewOppPt(e.target.value)}
                    />
                    <label style={s.lbl}>
                      단계
                      <select
                        style={s.select}
                        value={newOppStage}
                        onChange={(e) => setNewOppStage(e.target.value)}
                      >
                        {STAGES.map((st) => (
                          <option key={st} value={st}>
                            {st}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label style={s.lbl}>
                      담당 (선택)
                      <select
                        style={s.select}
                        value={newOppRep === "" ? "" : String(newOppRep)}
                        onChange={(e) =>
                          setNewOppRep(e.target.value === "" ? "" : Number(e.target.value))
                        }
                      >
                        <option value="">미배정</option>
                        {reps.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      style={s.primary}
                      disabled={loading}
                      onClick={() => void createOpp()}
                    >
                      사업기회 등록
                    </button>
                  </>
                ) : oppDetail && selOpp ? (
                  <>
                    <div style={s.coPanelHead}>
                      <h2 style={{ ...s.h2, margin: 0 }}>사업기회 상세 · 수정</h2>
                      <button
                        type="button"
                        style={s.ghost}
                        disabled={loading}
                        onClick={() => {
                          setOppRegisterOpen(true);
                          setErr("");
                        }}
                      >
                        사업기회 등록
                      </button>
                    </div>
                    <div style={s.row}>
                      <button type="button" style={s.danger} onClick={() => void deleteOpp(oppDetail.id)}>
                        삭제
                      </button>
                    </div>
                    <label style={s.lbl}>
                      이름
                      <input
                        style={s.input}
                        value={editOppName}
                        onChange={(e) => setEditOppName(e.target.value)}
                      />
                    </label>
                    <label style={s.lbl}>
                      유형
                      <input
                        style={s.input}
                        value={editOppPt}
                        onChange={(e) => setEditOppPt(e.target.value)}
                      />
                    </label>
                    <label style={s.lbl}>
                      고객사
                      <select
                        style={s.select}
                        value={editOppCo === "" ? "" : String(editOppCo)}
                        onChange={(e) =>
                          setEditOppCo(e.target.value === "" ? "" : Number(e.target.value))
                        }
                      >
                        {companies.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label style={s.lbl}>
                      단계
                      <select
                        style={s.select}
                        value={editOppStage}
                        onChange={(e) => setEditOppStage(e.target.value)}
                      >
                        {STAGES.map((st) => (
                          <option key={st} value={st}>
                            {st}
                          </option>
                        ))}
                      </select>
                    </label>
                    <p style={s.kpi}>수주확률 {(oppDetail.win_probability * 100).toFixed(1)}%</p>
                    {oppDetail.win_probability_rationale ? (
                      <>
                        <div style={s.probabilityRationaleLabel}>규칙 기반 근거</div>
                        <p style={s.probabilityRationale}>{oppDetail.win_probability_rationale}</p>
                      </>
                    ) : null}
                    <label style={s.lbl}>
                      담당자
                      <select
                        style={s.select}
                        value={oppDetail.sales_rep_id ?? ""}
                        onChange={(e) => {
                          const v = e.target.value;
                          void patchOpp(oppDetail.id, {
                            sales_rep_id: v === "" ? null : Number(v),
                          });
                        }}
                      >
                        <option value="">미배정</option>
                        {reps.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button type="button" style={s.primary} disabled={loading} onClick={() => saveOppEdits()}>
                      이름·유형·고객사·단계 저장
                    </button>
                    <h4 style={s.h4}>추천 액션</h4>
                    <p style={s.tiny}>완료 ✓ · 진행 중 ▶</p>
                    <ul style={s.list}>
                      {oppActionItems
                        .filter((it) => it.status !== "done")
                        .map((it) => (
                          <li key={it.id} style={s.li}>
                            {it.status === "in_progress" ? <span style={s.badge}>▶ </span> : null}
                            <button
                              type="button"
                              style={oppActionExecItem?.id === it.id ? s.linkBtnOn : s.linkBtn}
                              onClick={() => {
                                setOppActionExecItem(it);
                                setOppExecSubj(it.result_subject ?? "");
                                setOppExecBody(it.result_body ?? "");
                                setOppExecFiles([]);
                              }}
                            >
                              {it.title}
                            </button>
                          </li>
                        ))}
                    </ul>
                    <ul style={s.list}>
                      {oppActionItems
                        .filter((it) => it.status === "done")
                        .map((it) => (
                          <li key={it.id} style={s.li}>
                            <span style={s.doneMark}>✓ </span>
                            <button
                              type="button"
                              style={oppActionExecItem?.id === it.id ? s.linkBtnOn : s.linkBtn}
                              onClick={() => {
                                setOppActionExecItem(it);
                                setOppExecSubj(it.result_subject ?? "");
                                setOppExecBody(it.result_body ?? "");
                                setOppExecFiles([]);
                              }}
                            >
                              {it.title}
                            </button>
                          </li>
                        ))}
                    </ul>
                    {oppActionExecItem ? (
                      <div style={s.execBox}>
                        <h4 style={s.h4}>액션 실행 · {oppActionExecItem.title}</h4>
                        <p style={s.small}>{oppActionExecItem.hint}</p>
                        <input
                          style={s.input}
                          placeholder="제목/요약"
                          value={oppExecSubj}
                          onChange={(e) => setOppExecSubj(e.target.value)}
                        />
                        <textarea
                          style={s.textarea}
                          rows={4}
                          placeholder="진행 내용"
                          value={oppExecBody}
                          onChange={(e) => setOppExecBody(e.target.value)}
                        />
                        <label style={s.lbl}>
                          첨부
                          <input
                            type="file"
                            multiple
                            accept={FILE_ACCEPT}
                            onChange={(e) =>
                              setOppExecFiles(e.target.files ? Array.from(e.target.files) : [])
                            }
                          />
                        </label>
                        <div style={s.row}>
                          <button
                            type="button"
                            style={s.ghost}
                            disabled={loading}
                            onClick={() => void submitOppMenuAction("in_progress")}
                          >
                            진행 중으로 저장
                          </button>
                          <button
                            type="button"
                            style={s.primary}
                            disabled={loading}
                            onClick={() => void submitOppMenuAction("done")}
                          >
                            완료
                          </button>
                          <button type="button" style={s.ghost} onClick={() => setOppActionExecItem(null)}>
                            닫기
                          </button>
                        </div>
                      </div>
                    ) : null}
                    <h4 style={s.h4}>영업활동 (제목 선택 시 본문)</h4>
                    <ul style={s.list}>
                      {oppActs.map((a) => (
                        <li key={a.id}>
                          <button
                            type="button"
                            style={oppSelActId === a.id ? s.linkBtnOn : s.linkBtn}
                            onClick={() => setOppSelActId((prev) => (prev === a.id ? null : a.id))}
                          >
                            {a.subject}
                          </button>
                        </li>
                      ))}
                    </ul>
                    {oppSelActId ? (
                      <pre style={s.pre}>{oppActs.find((x) => x.id === oppSelActId)?.body ?? ""}</pre>
                    ) : null}
                  </>
                ) : (
                  <div>
                    <p style={s.placeholder}>
                      왼쪽 목록에서 사업기회를 선택하면 상세가 표시됩니다. 신규는 아래에서 등록하세요.
                    </p>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                      <button
                        type="button"
                        style={s.primary}
                        disabled={loading}
                        onClick={() => {
                          setOppRegisterOpen(true);
                          setErr("");
                        }}
                      >
                        사업기회 등록
                      </button>
                      <button
                        type="button"
                        style={s.ghost}
                        disabled={loading}
                        onClick={() => {
                          setMenu("companies");
                          setCoRegisterOpen(true);
                          setErr("");
                        }}
                      >
                        고객사 등록
                      </button>
                    </div>
                  </div>
                )}
              </section>
            </div>
          ) : null}

          {menu === "reps" ? (
            <div style={s.split}>
              <section style={s.cardList}>
                <h2 style={s.h2}>영업담당 (최대 10명)</h2>
                <div style={s.row}>
                  <input
                    style={s.input}
                    placeholder="이름"
                    value={newRepName}
                    onChange={(e) => setNewRepName(e.target.value)}
                  />
                  <button type="button" style={s.primary} disabled={loading} onClick={() => void addRep()}>
                    추가
                  </button>
                </div>
                <ul style={s.list}>
                  {reps.map((r) => (
                    <li key={r.id} style={s.li}>
                      <button
                        type="button"
                        style={selRep === r.id ? s.linkBtnOn : s.linkBtn}
                        onClick={() => void openRep(r.id)}
                      >
                        {r.name}
                      </button>
                      {r.email ? <span style={s.muted}> {r.email}</span> : null}
                      <button type="button" style={s.danger} onClick={() => void delRep(r.id)}>
                        삭제
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
              <section style={s.cardDetail}>
                {repSummary && selRep ? (
                  <>
                    <h2 style={s.h2}>담당자 요약</h2>
                    <h3 style={s.h3}>{repSummary.rep.name}</h3>
                    <h4 style={s.h4}>담당 고객사</h4>
                    <ul style={s.list}>
                      {repSummary.companies.map((c) => (
                        <li key={c.id}>
                          <button type="button" style={s.linkBtn} onClick={() => void openCompany(c.id)}>
                            {c.name}
                          </button>
                        </li>
                      ))}
                    </ul>
                    <h4 style={s.h4}>담당 사업기회</h4>
                    <ul style={s.list}>
                      {repSummary.opportunities.map((o) => (
                        <li key={o.id}>
                          <button type="button" style={s.linkBtn} onClick={() => void openOpp(o.id)}>
                            {o.name}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p style={s.placeholder}>왼쪽에서 담당자를 선택하세요.</p>
                )}
              </section>
            </div>
          ) : null}

          {menu === "activities" ? (
            <section style={s.cardFull}>
              <h2 style={s.h2}>활동등록</h2>
              <p style={s.small}>
                제목·본문·첨부 중 가능한 만큼만 입력하면 됩니다. 저장 시 본문·첨부 텍스트로 고객사/사업기회를
                자동 매핑하고, 아래에서 직접 고르면 그 값이 우선합니다. 첨부: txt, csv, eml, docx, xlsx, pptx.
              </p>
              <input
                style={s.input}
                placeholder="제목 (선택)"
                value={actSubject}
                onChange={(e) => setActSubject(e.target.value)}
              />
              <textarea
                style={s.textarea}
                rows={6}
                placeholder="내용 (선택, 첨부만으로도 가능)"
                value={actBody}
                onChange={(e) => setActBody(e.target.value)}
              />
              <label style={s.lbl}>
                첨부 파일 (여러 개)
                <input
                  type="file"
                  multiple
                  accept={FILE_ACCEPT}
                  style={{ marginTop: 6 }}
                  onChange={(e) => setActFiles(e.target.files ? Array.from(e.target.files) : [])}
                />
              </label>
              {actFiles.length > 0 ? (
                <p style={s.hint}>선택됨: {actFiles.map((f) => f.name).join(", ")}</p>
              ) : null}
              <div style={s.row}>
                <label style={s.lbl}>
                  고객사
                  <select
                    style={s.select}
                    value={actCompany}
                    onChange={(e) =>
                      setActCompany(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  >
                    <option value="">자동 매핑</option>
                    {companies.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={s.lbl}>
                  사업기회
                  <select
                    style={s.select}
                    value={actOpp}
                    onChange={(e) =>
                      setActOpp(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  >
                    <option value="">자동 매핑</option>
                    {oppsForCompany.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={s.lbl}>
                  등록 담당자
                  <select
                    style={s.select}
                    value={actRep}
                    onChange={(e) =>
                      setActRep(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  >
                    <option value="">선택</option>
                    {reps.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div style={s.row}>
                <button type="button" style={s.primary} disabled={loading} onClick={() => void onSaveActivity()}>
                  저장
                </button>
              </div>
              {suggestMsg ? <p style={s.hint}>{suggestMsg}</p> : null}
            </section>
          ) : null}
        </div>

        <aside style={s.aiAside}>
          <div style={s.aiTitle}>AI 영업관리 Agent</div>
          <div
            style={{
              ...s.orchStatusBar,
              ...(orchRunning ? s.orchStatusRun : s.orchStatusIdle),
            }}
            role="status"
            aria-live="polite"
          >
            <span style={orchRunning ? s.orchDot : s.orchDotIdle} aria-hidden />
            <span>
              {orchRunning ? (
                <>
                  <strong>실행 중</strong>
                  <span style={s.orchStatusSub}> — 백엔드에서 에이전트가 동작합니다.</span>
                </>
              ) : (
                <>
                  <strong>대기 중</strong>
                  <span style={s.orchStatusSub}> — 질문 실행 시 여기에 진행 상태가 표시됩니다.</span>
                </>
              )}
            </span>
          </div>
          {orchStatusNote ? <p style={s.orchStatusNote}>{orchStatusNote}</p> : null}
          <p style={s.aiHint}>{MENU_AI_HINT[menu]}</p>
          <p style={s.aiSub}>
            에이전트·고객사·사업기회를 고르지 않아도 됩니다. 질문만 입력하면 라우터가 전문 에이전트를 고르고 MCP
            RAG로 문서 맥락을 참고합니다 (A2A). 백엔드는 127.0.0.1:8000 에서 실행 중이어야 하며,{" "}
            <code style={{ fontSize: 11 }}>npm run preview</code> 는 이제 <code style={{ fontSize: 11 }}>/api</code>{" "}
            가 프록시되도록 설정되어 있습니다. Enter로 전송, Shift+Enter로 줄바꿈됩니다.
          </p>
          <textarea
            style={s.aiTextarea}
            rows={8}
            placeholder="예: SK텔레콤 담당 사업기회 수주확률이 가장 높은 건 뭐야? (Enter 전송 · Shift+Enter 줄바꿈)"
            value={orchMsg}
            disabled={orchRunning || loading}
            onChange={(e) => setOrchMsg(e.target.value)}
            onKeyDown={(e) => {
              if (e.key !== "Enter" || e.shiftKey) return;
              const ne = e.nativeEvent;
              if ("isComposing" in ne && ne.isComposing) return;
              if (orchRunning || loading || !orchMsg.trim()) return;
              e.preventDefault();
              void onOrchestrate();
            }}
          />
          <button
            type="button"
            style={s.primary}
            disabled={orchRunning || loading}
            onClick={() => void onOrchestrate()}
          >
            {orchRunning ? "실행 중…" : "질문 실행"}
          </button>
          {orchRoute ? <p style={s.routeLine}>{orchRoute}</p> : null}
          {orchOut ? <pre style={s.answer}>{orchOut}</pre> : null}
          {orchStructured != null ? (
            <pre style={s.structOut}>{JSON.stringify(orchStructured, null, 2)}</pre>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

const s: Record<string, CSSProperties> = {
  wrap: { display: "flex", minHeight: "100vh", gap: 0 },
  aside: {
    width: 220,
    flexShrink: 0,
    borderRight: "1px solid var(--sk-gray-200)",
    padding: "1rem",
    background: "var(--sk-white)",
  },
  asideTitle: { fontWeight: 800, color: "var(--sk-navy)", marginBottom: 12 },
  nav: { display: "flex", flexDirection: "column", gap: 8 },
  navBtn: {
    textAlign: "left",
    padding: "0.5rem 0.65rem",
    borderRadius: 8,
    border: "1px solid var(--sk-gray-200)",
    background: "var(--sk-white)",
    cursor: "pointer",
    color: "var(--sk-navy)",
  },
  navBtnOn: {
    textAlign: "left",
    padding: "0.5rem 0.65rem",
    borderRadius: 8,
    border: "1px solid var(--sk-red)",
    background: "rgba(234,0,44,0.06)",
    cursor: "pointer",
    color: "var(--sk-navy)",
    fontWeight: 700,
  },
  note: { fontSize: 11, color: "var(--sk-gray-500)", marginTop: 16, lineHeight: 1.4 },
  centerRow: {
    flex: 1,
    display: "flex",
    minWidth: 0,
    alignItems: "stretch",
  },
  mainCol: {
    flex: 1,
    minWidth: 0,
    padding: "1rem 1.25rem",
    overflow: "auto",
  },
  aiAside: {
    width: 340,
    flexShrink: 0,
    borderLeft: "1px solid var(--sk-gray-200)",
    padding: "1rem",
    background: "var(--sk-gray-50)",
    overflow: "auto",
    maxHeight: "100vh",
    position: "sticky",
    top: 0,
    alignSelf: "flex-start",
  },
  aiTitle: { fontWeight: 800, color: "var(--sk-navy)", marginBottom: 8, fontSize: "0.95rem" },
  orchStatusBar: {
    display: "flex",
    alignItems: "flex-start",
    gap: 10,
    padding: "0.55rem 0.65rem",
    borderRadius: 10,
    marginBottom: 6,
    lineHeight: 1.35,
    fontSize: 12,
    color: "var(--sk-navy)",
  },
  orchStatusIdle: {
    background: "var(--sk-gray-50)",
    border: "1px solid var(--sk-gray-200)",
  },
  orchStatusRun: {
    background: "rgba(234,0,44,0.07)",
    border: "1px solid rgba(234,0,44,0.28)",
  },
  orchDot: {
    width: 10,
    height: 10,
    borderRadius: "50%",
    marginTop: 3,
    flexShrink: 0,
    background: "var(--sk-red)",
    animation: "aicrm-orch-pulse 1.1s ease-in-out infinite",
  },
  orchDotIdle: {
    width: 10,
    height: 10,
    borderRadius: "50%",
    marginTop: 3,
    flexShrink: 0,
    background: "var(--sk-gray-400)",
  },
  orchStatusSub: { fontWeight: 400, opacity: 0.88 },
  orchStatusNote: {
    fontSize: 11,
    color: "var(--sk-gray-500)",
    margin: "0 0 8px",
    lineHeight: 1.35,
  },
  aiHint: { fontSize: 12, color: "var(--sk-navy)", lineHeight: 1.45, marginBottom: 8 },
  aiSub: { fontSize: 11, color: "var(--sk-gray-500)", lineHeight: 1.4, marginBottom: 10 },
  aiTextarea: {
    width: "100%",
    borderRadius: 10,
    border: "1px solid var(--sk-gray-200)",
    padding: "0.65rem",
    fontFamily: "inherit",
    fontSize: "0.88rem",
    marginBottom: 8,
    resize: "vertical",
    boxSizing: "border-box",
  },
  routeLine: {
    marginTop: 10,
    fontSize: 11,
    color: "var(--sk-teal)",
    fontWeight: 600,
  },
  split: {
    display: "flex",
    gap: 16,
    alignItems: "flex-start",
    flexWrap: "wrap",
  },
  coPanelHead: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    flexWrap: "wrap",
    marginBottom: "0.65rem",
  },
  cardList: {
    flex: "0 1 300px",
    minWidth: 260,
    background: "var(--sk-white)",
    borderRadius: "var(--radius)",
    padding: "1.25rem 1.35rem",
    boxShadow: "var(--shadow)",
    border: "1px solid var(--sk-gray-200)",
  },
  cardDetail: {
    flex: "1 1 360px",
    minWidth: 280,
    background: "var(--sk-white)",
    borderRadius: "var(--radius)",
    padding: "1.25rem 1.35rem",
    boxShadow: "var(--shadow)",
    border: "1px solid var(--sk-gray-200)",
  },
  cardFull: {
    background: "var(--sk-white)",
    borderRadius: "var(--radius)",
    padding: "1.25rem 1.35rem",
    boxShadow: "var(--shadow)",
    border: "1px solid var(--sk-gray-200)",
    maxWidth: 720,
  },
  pager: { display: "flex", alignItems: "center", gap: 10, marginBottom: 12, flexWrap: "wrap" },
  placeholder: { color: "var(--sk-gray-500)", fontSize: "0.9rem", margin: "2rem 0" },
  box: {
    padding: "0.75rem",
    borderRadius: 8,
    border: "1px dashed var(--sk-gray-200)",
    marginBottom: 12,
  },
  h2: { margin: "0 0 0.75rem", fontSize: "1.05rem", color: "var(--sk-navy)", fontWeight: 700 },
  h3: { margin: "0 0 0.5rem", fontSize: "1rem", color: "var(--sk-navy)" },
  h4: { margin: "1rem 0 0.35rem", fontSize: "0.9rem", color: "var(--sk-navy)" },
  list: { listStyle: "none", padding: 0, margin: 0 },
  li: { marginBottom: 8, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" },
  linkBtn: {
    border: "none",
    background: "none",
    padding: 0,
    color: "var(--sk-blue)",
    cursor: "pointer",
    fontWeight: 600,
    textDecoration: "underline",
  },
  linkBtnOn: {
    border: "none",
    background: "rgba(234,0,44,0.08)",
    padding: "2px 6px",
    borderRadius: 6,
    color: "var(--sk-navy)",
    cursor: "pointer",
    fontWeight: 700,
    textDecoration: "none",
  },
  muted: { fontSize: "0.85rem", color: "var(--sk-gray-500)" },
  small: { fontSize: "0.85rem", color: "var(--sk-gray-600)", margin: "0.25rem 0" },
  lbl: { display: "flex", flexDirection: "column", gap: 4, fontSize: 12, fontWeight: 600 },
  select: {
    padding: "0.35rem 0.5rem",
    borderRadius: 8,
    border: "1px solid var(--sk-gray-200)",
    maxWidth: 320,
  },
  input: {
    width: "100%",
    maxWidth: 400,
    padding: "0.5rem 0.65rem",
    borderRadius: 8,
    border: "1px solid var(--sk-gray-200)",
    marginBottom: 8,
    boxSizing: "border-box",
  },
  textarea: {
    width: "100%",
    borderRadius: 10,
    border: "1px solid var(--sk-gray-200)",
    padding: "0.75rem",
    fontFamily: "inherit",
    marginBottom: 8,
    boxSizing: "border-box",
  },
  row: { display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end", marginBottom: 8 },
  primary: {
    padding: "0.55rem 1rem",
    borderRadius: 10,
    border: "none",
    background: "var(--sk-red)",
    color: "var(--sk-white)",
    fontWeight: 700,
    cursor: "pointer",
  },
  ghost: {
    padding: "0.5rem 0.9rem",
    borderRadius: 8,
    border: "1px solid var(--sk-gray-200)",
    background: "var(--sk-white)",
    cursor: "pointer",
  },
  danger: {
    padding: "0.35rem 0.65rem",
    fontSize: 12,
    borderRadius: 6,
    border: "1px solid var(--sk-gray-200)",
    background: "#fff5f5",
    cursor: "pointer",
  },
  tabs: { display: "flex", gap: 8, marginBottom: 10 },
  tab: {
    padding: "0.4rem 0.75rem",
    borderRadius: 8,
    border: "1px solid var(--sk-gray-200)",
    background: "var(--sk-white)",
    cursor: "pointer",
  },
  tabOn: {
    padding: "0.4rem 0.75rem",
    borderRadius: 8,
    border: "1px solid var(--sk-red)",
    background: "rgba(234,0,44,0.08)",
    cursor: "pointer",
    fontWeight: 700,
  },
  hint: { fontSize: 13, color: "var(--sk-teal)" },
  err: {
    background: "#fff0f0",
    border: "1px solid #f5c2c2",
    padding: "0.65rem 0.85rem",
    borderRadius: 8,
    marginBottom: 12,
    fontSize: 14,
  },
  pre: {
    margin: "0.35rem 0 0",
    fontSize: 12,
    whiteSpace: "pre-wrap",
    color: "var(--sk-gray-600)",
  },
  actLi: { marginBottom: 12, borderBottom: "1px solid var(--sk-gray-100)", paddingBottom: 8 },
  kpi: { fontSize: "1.1rem", fontWeight: 800, color: "var(--sk-teal)" },
  probabilityRationaleLabel: {
    fontSize: 11,
    fontWeight: 700,
    color: "var(--sk-navy)",
    margin: "0 0 4px",
  },
  probabilityRationale: {
    fontSize: 12,
    lineHeight: 1.5,
    color: "var(--sk-gray-600)",
    margin: "0 0 12px",
    padding: "0.55rem 0.65rem",
    background: "var(--sk-gray-50)",
    borderRadius: 8,
    border: "1px solid var(--sk-gray-200)",
  },
  answer: {
    marginTop: 12,
    whiteSpace: "pre-wrap",
    fontFamily: "inherit",
    fontSize: "0.88rem",
    lineHeight: 1.55,
    padding: "0.65rem",
    background: "var(--sk-white)",
    borderRadius: 10,
    border: "1px solid var(--sk-gray-200)",
  },
  structOut: {
    marginTop: 8,
    whiteSpace: "pre-wrap",
    fontFamily: "ui-monospace, monospace",
    fontSize: "0.72rem",
    lineHeight: 1.45,
    padding: "0.5rem",
    background: "#fff",
    borderRadius: 8,
    border: "1px solid var(--sk-gray-200)",
    maxHeight: 220,
    overflow: "auto",
  },
  nested: {
    marginTop: 14,
    padding: "0.85rem",
    borderRadius: 10,
    border: "1px solid var(--sk-gray-200)",
    background: "var(--sk-gray-50)",
  },
  execBox: {
    marginTop: 14,
    padding: "0.85rem",
    borderRadius: 10,
    border: "1px solid var(--sk-teal)",
    background: "rgba(0, 120, 140, 0.04)",
  },
  tiny: { fontSize: 11, color: "var(--sk-gray-500)", marginBottom: 6 },
  badge: { color: "var(--sk-orange)", fontWeight: 700 },
  doneMark: { color: "var(--sk-teal)", fontWeight: 800 },
  preSm: {
    fontSize: 11,
    whiteSpace: "pre-wrap",
    color: "var(--sk-gray-600)",
    maxHeight: 120,
    overflow: "auto",
    background: "var(--sk-white)",
    padding: "0.5rem",
    borderRadius: 6,
  },
};
