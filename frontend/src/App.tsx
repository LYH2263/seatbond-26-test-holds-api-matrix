import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import HallsPage from "./pages/HallsPage";
import ShowtimesPage from "./pages/ShowtimesPage";
import SeatMapPage from "./pages/SeatMapPage";
import HoldPage from "./pages/HoldPage";
import OrdersPage from "./pages/OrdersPage";
import ConflictsPage from "./pages/ConflictsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/seatmap" replace />} />
        <Route path="/halls" element={<HallsPage />} />
        <Route path="/showtimes" element={<ShowtimesPage />} />
        <Route path="/seatmap" element={<SeatMapPage />} />
        <Route path="/hold" element={<HoldPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/conflicts" element={<ConflictsPage />} />
      </Route>
    </Routes>
  );
}
