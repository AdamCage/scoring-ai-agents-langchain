import { Navigate, Route, Routes } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { Shell } from "./pages/Shell";
import { WorkbenchPage } from "./pages/WorkbenchPage";
import { ArchitecturePage } from "./pages/ArchitecturePage";
import { ObservabilityPage } from "./pages/ObservabilityPage";
import { QualityPage } from "./pages/QualityPage";
import { StatusPage } from "./pages/StatusPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Shell />}>
        <Route path="/" element={<WorkbenchPage />} />
        <Route path="/architecture" element={<ArchitecturePage />} />
        <Route path="/observability" element={<ObservabilityPage />} />
        <Route path="/quality" element={<QualityPage />} />
        <Route path="/status" element={<StatusPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
