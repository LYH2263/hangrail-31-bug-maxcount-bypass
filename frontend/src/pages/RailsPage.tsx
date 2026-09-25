import { useEffect, useState } from "react";
import { api } from "../api/client";

type R = {
  id: number;
  store_id: number;
  label: string;
  length_cm: number;
  max_active_items: number | null;
  active_count: number;
};

export default function RailsPage() {
  const [rows, setRows] = useState<R[]>([]);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const reload = () => api<R[]>("/rails").then(rs => {
    setRows(rs);
    setDrafts(Object.fromEntries(rs.map(r => [r.id, r.max_active_items == null ? "" : String(r.max_active_items)])));
  });
  useEffect(() => { reload(); }, []);

  async function save(r: R) {
    setMsg(""); setErr("");
    const raw = (drafts[r.id] ?? "").trim();
    const limit = raw === "" ? null : Number(raw);
    if (limit !== null && (!Number.isInteger(limit) || limit < 1)) {
      setErr("上限需为正整数，留空表示不限件数"); return;
    }
    if (limit !== null && limit < r.active_count) {
      setErr(`${r.label} 当前已挂 ${r.active_count} 件，上限不能小于当前已挂数`); return;
    }
    try {
      await api<R>(`/rails/${r.id}`, { method: "PATCH", body: JSON.stringify({ max_active_items: limit }) });
      setMsg(`${r.label} 件数上限已保存：${limit === null ? "不限" : `${limit} 件`}`);
      reload();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }

  return (<>
    <h2>挂杆</h2>
    {msg && <div className="ok">{msg}</div>}
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr>
      <th>标签</th><th>门店</th><th>长度 cm</th><th>当前件数 / 上限</th><th>件数上限</th><th></th>
    </tr></thead>
    <tbody>{rows.map(r => (
      <tr key={r.id}>
        <td>{r.label}</td>
        <td>{r.store_id}</td>
        <td className="mono">{r.length_cm}</td>
        <td className="mono">{r.active_count} / {r.max_active_items ?? "不限"}</td>
        <td>
          <input
            style={{ width: "6rem" }}
            value={drafts[r.id] ?? ""}
            placeholder="不限"
            inputMode="numeric"
            onChange={e => setDrafts(d => ({ ...d, [r.id]: e.target.value }))}
          />
        </td>
        <td><button onClick={() => save(r)}>保存上限</button></td>
      </tr>
    ))}</tbody></table>
    <p style={{ color: "var(--hang-muted)", fontSize: ".8rem" }}>
      件数上限仅统计 active 占位；留空表示不限件数。达到上限后即使剩余厘米足够也会跳过该杆，取件释放后可再挂。
    </p>
  </>);
}
