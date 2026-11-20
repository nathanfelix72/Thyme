import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { BudgetPage } from "./modules/budget/BudgetPage";
import { CalendarPage } from "./modules/calendar/CalendarPage";
import { RagPage } from "./modules/rag/RagPage";
import { ShopPage } from "./modules/shop/ShopPage";
import { Admin } from "./pages/Admin";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { Settings } from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/understand" element={<RagPage />} />
        <Route path="/plan" element={<CalendarPage />} />
        <Route path="/shop" element={<ShopPage />} />
        <Route path="/budget" element={<BudgetPage />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/login" element={<Login />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
    </Routes>
  );
}
