import { useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";
import {
  DEPARTMENT_KIND_LABELS,
  Department,
  DepartmentFormData,
  DepartmentKind,
  ROLE_LABELS,
  User,
  UserRole,
  canManageDepartments,
  canManageUsers,
  emptyDepartmentForm,
  formatResponsibleParty,
} from "./types";

type AdminTab = "departments" | "users";
type AdminModalMode = "create" | "edit" | "edit-user" | null;

interface AdminPanelProps {
  onBack: () => void;
}

function Modal({
  title,
  onClose,
  children,
  footer,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <strong>{title}</strong>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-footer">{footer}</div> : null}
      </div>
    </div>
  );
}

function DepartmentForm({
  value,
  onChange,
}: {
  value: DepartmentFormData;
  onChange: (next: DepartmentFormData) => void;
}) {
  return (
    <div className="form-grid">
      <div className="field">
        <label htmlFor="departmentKind">Тип</label>
        <select
          id="departmentKind"
          value={value.kind}
          onChange={(event) => onChange({ ...value, kind: event.target.value as DepartmentKind })}
        >
          {Object.entries(DEPARTMENT_KIND_LABELS).map(([kind, label]) => (
            <option key={kind} value={kind}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="departmentCode">Код / краткое название</label>
        <input
          id="departmentCode"
          value={value.code}
          onChange={(event) => onChange({ ...value, code: event.target.value })}
          placeholder="Например: ОГИП или ООО Строй"
        />
      </div>
      <div className="field full-width">
        <label htmlFor="departmentName">Полное название</label>
        <input
          id="departmentName"
          value={value.name}
          onChange={(event) => onChange({ ...value, name: event.target.value })}
          placeholder="Можно оставить пустым — будет использован код"
        />
      </div>
    </div>
  );
}

export default function AdminPanel({ onBack }: AdminPanelProps) {
  const { user } = useAuth();
  const [tab, setTab] = useState<AdminTab>("departments");
  const [departments, setDepartments] = useState<Department[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [kindFilter, setKindFilter] = useState<"" | DepartmentKind>("");
  const [modalMode, setModalMode] = useState<AdminModalMode>(null);
  const [formData, setFormData] = useState<DepartmentFormData>(emptyDepartmentForm());
  const [selectedDepartment, setSelectedDepartment] = useState<Department | null>(null);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [userRole, setUserRole] = useState<UserRole>("employee");
  const [userDepartmentId, setUserDepartmentId] = useState("");

  const loadDepartments = async () => {
    const data = await api.getDepartments(kindFilter || undefined);
    setDepartments(data);
  };

  const loadUsers = async () => {
    const data = await api.getUsers();
    setUsers(data);
  };

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (tab === "departments") {
        await loadDepartments();
      } else {
        await loadUsers();
        if (!departments.length) {
          setDepartments(await api.getDepartments());
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить данные");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [tab, kindFilter]);

  const openCreate = () => {
    setFormData(emptyDepartmentForm());
    setSelectedDepartment(null);
    setModalMode("create");
  };

  const openEdit = (department: Department) => {
    setSelectedDepartment(department);
    setFormData({
      code: department.code,
      name: department.name,
      kind: department.kind,
    });
    setModalMode("edit");
  };

  const openEditUser = (target: User) => {
    setSelectedUser(target);
    setUserRole(target.role);
    setUserDepartmentId(target.department_id ? String(target.department_id) : "");
    setModalMode("edit-user");
  };

  const saveDepartment = async () => {
    if (!formData.code.trim()) {
      setError("Укажите код или краткое название");
      return;
    }
    try {
      if (modalMode === "create") {
        await api.createDepartment(formData);
        setSuccess("Запись добавлена");
      } else if (modalMode === "edit" && selectedDepartment) {
        await api.updateDepartment(selectedDepartment.id, formData);
        setSuccess("Запись обновлена");
      }
      setModalMode(null);
      await loadDepartments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  };

  const saveUser = async () => {
    if (!selectedUser) return;
    try {
      await api.updateUser(selectedUser.id, {
        role: userRole,
        department_id: userDepartmentId ? Number(userDepartmentId) : null,
      });
      setModalMode(null);
      setSuccess("Пользователь обновлён");
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  };

  const removeDepartment = async (department: Department) => {
    if (!window.confirm(`Удалить «${formatResponsibleParty(department)}»?`)) return;
    try {
      await api.deleteDepartment(department.id);
      setSuccess("Запись удалена");
      await loadDepartments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления");
    }
  };

  if (!user) return null;

  const departmentsCount = departments.filter((item) => item.kind === "department").length;
  const subcontractorsCount = departments.filter((item) => item.kind === "subcontractor").length;

  return (
    <div className="admin-page">
      <header className="topbar">
        <div>
          <h1>Административная панель</h1>
          <p>Отделы, субподряды и пользователи</p>
        </div>
        <div className="topbar-actions">
          <button className="btn btn-secondary" onClick={onBack}>
            К замечаниям
          </button>
          {tab === "departments" && canManageDepartments(user.role) ? (
            <button className="btn btn-primary" onClick={openCreate}>
              + Добавить
            </button>
          ) : null}
        </div>
      </header>

      <div className="admin-tabs">
        {canManageDepartments(user.role) ? (
          <button
            className={`admin-tab ${tab === "departments" ? "active" : ""}`}
            onClick={() => setTab("departments")}
          >
            Отделы
          </button>
        ) : null}
        {canManageUsers(user.role) ? (
          <button
            className={`admin-tab ${tab === "users" ? "active" : ""}`}
            onClick={() => setTab("users")}
          >
            Пользователи
          </button>
        ) : null}
      </div>

      {error ? <div className="alert alert-error">{error}</div> : null}
      {success ? <div className="alert alert-success">{success}</div> : null}

      {tab === "departments" ? (
        <>
          <section className="stats-grid admin-stats">
            <div className="stat-card">
              <strong>{departments.length}</strong>
              <span>Всего записей</span>
            </div>
            <div className="stat-card">
              <strong>{departmentsCount}</strong>
              <span>Отделы</span>
            </div>
            <div className="stat-card">
              <strong>{subcontractorsCount}</strong>
              <span>Субподряд</span>
            </div>
          </section>

          <div className="panel admin-panel">
            <div className="panel-header filters-panel-header">
              <span>Ответственный отдел / субподряд</span>
              <select
                className="admin-kind-filter"
                value={kindFilter}
                onChange={(event) => setKindFilter(event.target.value as "" | DepartmentKind)}
              >
                <option value="">Все типы</option>
                {Object.entries(DEPARTMENT_KIND_LABELS).map(([kind, label]) => (
                  <option key={kind} value={kind}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="panel-body">
              {loading ? (
                <div className="empty-state">Загрузка...</div>
              ) : departments.length === 0 ? (
                <div className="empty-state">Записей пока нет. Добавьте отдел или субподряд.</div>
              ) : (
                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Тип</th>
                        <th>Код</th>
                        <th>Название</th>
                        <th>Замечаний</th>
                        <th>Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {departments.map((department) => (
                        <tr key={department.id}>
                          <td>
                            <span className={`kind-badge kind-badge-${department.kind}`}>
                              {DEPARTMENT_KIND_LABELS[department.kind]}
                            </span>
                          </td>
                          <td>{department.code}</td>
                          <td>{department.name}</td>
                          <td>{department.remarks_count ?? 0}</td>
                          <td className="admin-actions">
                            <button
                              className="btn btn-secondary btn-small"
                              onClick={() => openEdit(department)}
                            >
                              Изменить
                            </button>
                            <button
                              className="btn btn-danger btn-small"
                              onClick={() => void removeDepartment(department)}
                            >
                              Удалить
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      ) : null}

      {tab === "users" ? (
        <div className="panel admin-panel">
          <div className="panel-header">
            <span>Пользователи (вход через AD)</span>
          </div>
          <div className="panel-body">
            {loading ? (
              <div className="empty-state">Загрузка...</div>
            ) : users.length === 0 ? (
              <div className="empty-state">
                Пользователи появятся после первого входа через Active Directory.
              </div>
            ) : (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Логин</th>
                      <th>Имя</th>
                      <th>Роль</th>
                      <th>Отдел</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((item) => (
                      <tr key={item.id}>
                        <td>{item.username}</td>
                        <td>{item.display_name}</td>
                        <td>{ROLE_LABELS[item.role]}</td>
                        <td>
                          {item.department ? formatResponsibleParty(item.department) : "—"}
                        </td>
                        <td className="admin-actions">
                          <button
                            className="btn btn-secondary btn-small"
                            onClick={() => openEditUser(item)}
                          >
                            Настроить
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {modalMode === "create" || modalMode === "edit" ? (
        <Modal
          title={modalMode === "create" ? "Добавить отдел / субподряд" : "Редактировать запись"}
          onClose={() => setModalMode(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setModalMode(null)}>
                Отмена
              </button>
              <button className="btn btn-primary" onClick={() => void saveDepartment()}>
                Сохранить
              </button>
            </>
          }
        >
          <DepartmentForm value={formData} onChange={setFormData} />
        </Modal>
      ) : null}

      {modalMode === "edit-user" && selectedUser ? (
        <Modal
          title={`Настройка: ${selectedUser.display_name}`}
          onClose={() => setModalMode(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setModalMode(null)}>
                Отмена
              </button>
              <button className="btn btn-primary" onClick={() => void saveUser()}>
                Сохранить
              </button>
            </>
          }
        >
          <div className="form-grid">
            <div className="field">
              <label htmlFor="userRole">Роль</label>
              <select
                id="userRole"
                value={userRole}
                onChange={(event) => setUserRole(event.target.value as UserRole)}
              >
                {Object.entries(ROLE_LABELS).map(([role, label]) => (
                  <option key={role} value={role}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="userDepartment">Отдел</label>
              <select
                id="userDepartment"
                value={userDepartmentId}
                onChange={(event) => setUserDepartmentId(event.target.value)}
              >
                <option value="">Не назначен</option>
                {departments.map((department) => (
                  <option key={department.id} value={department.id}>
                    {formatResponsibleParty(department)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="import-note">
            Назначьте отдел начальнику отдела и сотрудникам — тогда начальник сможет назначать
            исполнителей из своего отдела.
          </p>
        </Modal>
      ) : null}
    </div>
  );
}
