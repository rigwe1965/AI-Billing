import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/ui/Layout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { UsageImportPage } from "./pages/UsageImportPage";
import { PricingPage } from "./pages/PricingPage";
import { AllocationsPage } from "./pages/AllocationsPage";
import { ConnectorsPage } from "./pages/ConnectorsPage";
import { UsersPage } from "./pages/UsersPage";
import { BudgetsPage } from "./pages/BudgetsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { InsightsPage } from "./pages/InsightsPage";
import type { ReactNode } from "react";

function ProtectedRoute({ children, adminOnly = false }: { children: ReactNode; adminOnly?: boolean }) {
  const { user, loading } = useAuth();

  if (loading) return <div style={{ padding: 24, color: "var(--text-muted)" }}>Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin_finance") return <Navigate to="/" replace />;

  return <Layout>{children}</Layout>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/usage-import" element={<ProtectedRoute><UsageImportPage /></ProtectedRoute>} />
      <Route path="/budgets" element={<ProtectedRoute><BudgetsPage /></ProtectedRoute>} />
      <Route path="/reports" element={<ProtectedRoute><ReportsPage /></ProtectedRoute>} />
      <Route path="/insights" element={<ProtectedRoute><InsightsPage /></ProtectedRoute>} />
      <Route path="/pricing" element={<ProtectedRoute adminOnly><PricingPage /></ProtectedRoute>} />
      <Route path="/allocations" element={<ProtectedRoute adminOnly><AllocationsPage /></ProtectedRoute>} />
      <Route path="/connectors" element={<ProtectedRoute adminOnly><ConnectorsPage /></ProtectedRoute>} />
      <Route path="/users" element={<ProtectedRoute adminOnly><UsersPage /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
