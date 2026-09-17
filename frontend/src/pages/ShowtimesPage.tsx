import { useEffect, useState } from "react";
import { api } from "../api/client";

type Show = {
  id: number;
  hall_id: number;
  film_title: string;
  start_at: string;
  hall_name?: string;
};

export default function ShowtimesPage() {
  const [rows, setRows] = useState<Show[]>([]);
  useEffect(() => {
    api<Show[]>("/showtimes").then(setRows);
  }, []);
  return (
    <>
      <h2>场次</h2>
      <table className="table">
        <thead>
          <tr>
            <th>影片</th>
            <th>影厅</th>
            <th>开场</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td>{s.film_title}</td>
              <td>{s.hall_name}</td>
              <td className="mono">{new Date(s.start_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
