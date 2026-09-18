import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Department, User, UserRole } from "../api/types";
import { Card } from "../components/ui/Card";

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ email: "", password: "", role: "dept_lead" as UserRole, department_id: "" });

  function refresh() {
    Promise.all([api.get<User[]>("/api/users"), api.get<Department[]>("/api/departments")]).then(([u, d]) => {
      setUsers(u);
      setDepartments(d);
      if (!form.department_id && d.length) setForm((f) => ({ ...f, department_id: String(d[0].id) }));
    });
  }

  useEffect(refresh, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/users", {
        email: form.email,
        password: form.password,
        role: form.role,
        department_id: form.role === "dept_lead" ? parseInt(form.department_id, 10) : null,
      });
      setForm((f) => ({ ...f, email: "", password: "" }));
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create user");
    }
  }

  const departmentName = (id: number | null) => departments.find((d) => d.id === id)?.name ?? "-";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ margin: 0 }}>Users &amp; Departments</h2>

      <Card title="Departments">
        <table>
          <thead>
            <tr><th>Name</th><th>Code</th></tr>
          </thead>
          <tbody>
            {departments.map((d) => (
              <tr key={d.id}><td>{d.name}</td><td>{d.code}</td></tr>
            ))}
          </tbody>
        </table>
        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 8 }}>
          Departments are seeded server-side (see backend/seed.py) -- there's no self-service creation UI yet.
        </p>
      </Card>

      <Card title="Create a user">
        <form onSubmit={submit} style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
          <label style={fieldLabel}>
            Email
            <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </label>
          <label style={fieldLabel}>
            Password
            <input required type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </label>
          <label style={fieldLabel}>
            Role
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}>
              <option value="dept_lead">dept_lead</option>
              <option value="admin_finance">admin_finance</option>
            </select>
          </label>
          {form.role === "dept_lead" && (
            <label style={fieldLabel}>
              Department
              <select value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })}>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </label>
          )}
          <button type="submit" style={{ padding: "8px 16px", borderRadius: 6, border: "none", background: "var(--series-1)", color: "white", fontWeight: 600, cursor: "pointer" }}>
            Create
          </button>
        </form>
        {error && <p style={{ color: "var(--status-critical)", marginTop: 8 }}>{error}</p>}
      </Card>

      <Card title="Existing users">
        <table>
          <thead>
            <tr><th>Email</th><th>Role</th><th>Department</th><th>Active</th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.role}</td>
                <td>{departmentName(u.department_id)}</td>
                <td>{u.is_active ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

const fieldLabel: React.CSSProperties = { fontSize: 12, color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: 4 };
