import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api/client";

const filmLinks = [
  ["/seatmap", "座图", "01"],
  ["/showtimes", "场次", "02"],
  ["/hold", "锁座", "03"],
  ["/orders", "票根", "04"],
  ["/halls", "影厅", "05"],
  ["/conflicts", "冲突", "06"],
];

type Hold = {
  id: number;
  order_code: string;
  row: number;
  start_col: number;
  end_col: number;
  party_size: number;
  status: string;
};

export default function Layout() {
  const loc = useLocation();
  const isSeatHero = loc.pathname === "/seatmap" || loc.pathname === "/";
  const [holds, setHolds] = useState<Hold[]>([]);

  useEffect(() => {
    api<Hold[]>("/holds")
      .then(setHolds)
      .catch(() => setHolds([]));
    const t = setInterval(() => {
      api<Hold[]>("/holds")
        .then(setHolds)
        .catch(() => {});
    }, 8000);
    return () => clearInterval(t);
  }, [loc.pathname]);

  const active = holds.filter((h) => h.status === "held" || h.status === "active").slice(0, 6);
  const recent = holds.slice(0, 8);

  return (
    <div className="cinema-shell">
      <aside className="filmstrip-nav" aria-label="影院导航">
        <div className="filmstrip-sprocket" />
        <div className="filmstrip-brand">
          <span className="filmstrip-brand-mark">SB</span>
          <span className="filmstrip-brand-name">SeatBond</span>
          <span className="filmstrip-brand-sub">连座放映厅</span>
        </div>
        <div className="filmstrip-frames">
          {filmLinks.map(([to, label, frame]) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `film-frame${isActive ? " film-frame--lit" : ""}`
              }
            >
              <span className="film-frame-num">{frame}</span>
              <span className="film-frame-label">{label}</span>
            </NavLink>
          ))}
        </div>
        <div className="filmstrip-sprocket filmstrip-sprocket--bottom" />
      </aside>

      <section className={`auditorium-stage${isSeatHero ? " auditorium-stage--hero" : ""}`}>
        <div className="auditorium-glow" />
        <div className="auditorium-content">
          <Outlet />
        </div>
      </section>

      <aside className="ticket-stub-rail" aria-label="票根摘要">
        <div className="stub-tear">✂ 票根</div>
        <div className="stub-block">
          <div className="stub-title">当前锁座</div>
          {active.length === 0 && <p className="stub-empty">暂无持票</p>}
          {active.map((h) => (
            <div key={h.id} className="stub-ticket">
              <div className="stub-code">{h.order_code}</div>
              <div className="stub-meta">
                R{h.row} · C{h.start_col}-{h.end_col}
              </div>
              <div className="stub-meta">{h.party_size} 人 · {h.status}</div>
            </div>
          ))}
        </div>
        <div className="stub-block">
          <div className="stub-title">最近订单</div>
          {recent.map((h) => (
            <div key={`r-${h.id}`} className="stub-line">
              <span className="mono">{h.order_code}</span>
              <span>{h.status}</span>
            </div>
          ))}
        </div>
        <NavLink to="/hold" className="stub-cta">
          去锁连座 →
        </NavLink>
      </aside>
    </div>
  );
}
