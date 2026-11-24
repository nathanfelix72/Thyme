import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { BudgetPage } from "./modules/budget/BudgetPage";
import { CalendarPage } from "./modules/calendar/CalendarPage";
import { FindPage } from "./modules/rag/FindPage";
import { LibraryPage } from "./modules/rag/LibraryPage";
import { UploadPage } from "./modules/rag/UploadPage";
import { ShopPage } from "./modules/shop/ShopPage";
import { Admin } from "./pages/Admin";
import { AiSettings } from "./pages/AiSettings";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { Profile } from "./pages/Profile";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/find" element={<FindPage />} />
        <Route path="/understand" element={<Navigate to="/find" replace />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/plan" element={<CalendarPage />} />
        <Route path="/shop" element={<ShopPage />} />
        <Route path="/budget" element={<BudgetPage />} />
        <Route path="/ai-settings" element={<AiSettings />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/settings" element={<Navigate to="/ai-settings" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
    </Routes>
  );
}
