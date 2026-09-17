import { useEffect, useState } from "react";
import { api } from "../api/client";

type Hold = {
  id: number;
  showtime_id: number;
  order_code: string;
  row: number;
  start_col: number;
  end_col: number;
  party_size: number;
  status: string;
};

export default function OrdersPage() {
  const [rows, setRows] = useState<Hold[]>([]);
  useEffect(() => {
    api<Hold[]>("/holds").then(setRows);
  }, []);
  return (
    <>
      <h2>订单</h2>
      <table className="table">
        <thead>
          <tr>
            <th>订单号</th>
            <th>场次</th>
            <th>座位</th>
            <th>人数</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => (
            <tr key={h.id}>
              <td className="mono">{h.order_code}</td>
              <td>{h.showtime_id}</td>
              <td className="mono">
                R{h.row} C{h.start_col}-{h.end_col}
              </td>
              <td>{h.party_size}</td>
              <td>{h.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
