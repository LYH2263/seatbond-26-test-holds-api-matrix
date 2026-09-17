import { useEffect, useState } from "react";
import { api } from "../api/client";

type Conflict = {
  id: number;
  showtime_id: number;
  party_size: number;
  reason: string;
  created_at: string;
};

export default function ConflictsPage() {
  const [rows, setRows] = useState<Conflict[]>([]);
  useEffect(() => {
    api<Conflict[]>("/conflicts").then(setRows);
  }, []);
  return (
    <>
      <h2>冲突</h2>
      <table className="table">
        <thead>
          <tr>
            <th>时间</th>
            <th>场次</th>
            <th>人数</th>
            <th>原因</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id}>
              <td className="mono">{new Date(c.created_at).toLocaleString()}</td>
              <td>{c.showtime_id}</td>
              <td>{c.party_size}</td>
              <td>{c.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
