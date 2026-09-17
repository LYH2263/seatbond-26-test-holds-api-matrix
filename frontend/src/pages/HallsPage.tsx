import { useEffect, useState } from "react";
import { api } from "../api/client";

type Hall = { id: number; name: string; rows: number; cols: number; aisle_cols: number[] };

export default function HallsPage() {
  const [rows, setRows] = useState<Hall[]>([]);
  useEffect(() => {
    api<Hall[]>("/halls").then(setRows);
  }, []);
  return (
    <>
      <h2>影厅</h2>
      <table className="table">
        <thead>
          <tr>
            <th>名称</th>
            <th>行×列</th>
            <th>过道列</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => (
            <tr key={h.id}>
              <td>{h.name}</td>
              <td className="mono">
                {h.rows} × {h.cols}
              </td>
              <td className="mono">{h.aisle_cols.join(", ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
