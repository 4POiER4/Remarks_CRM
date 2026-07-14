export type DepartmentKind = "department" | "subcontractor";

export type UserRole = "admin" | "gip" | "department_head" | "employee";

export interface Department {
  id: number;
  name: string;
  code: string;
  kind: DepartmentKind;
  remarks_count?: number;
}

export interface User {
  id: number;
  username: string;
  display_name: string;
  email: string | null;
  role: UserRole;
  department_id: number | null;
  is_active: boolean;
  last_login_at: string | null;
  department: Department | null;
}

export const DEPARTMENT_KIND_LABELS: Record<DepartmentKind, string> = {
  department: "Отдел",
  subcontractor: "Субподряд",
};

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Администратор",
  gip: "ГИП",
  department_head: "Начальник отдела",
  employee: "Сотрудник",
};

export interface DepartmentFormData {
  code: string;
  name: string;
  kind: DepartmentKind;
}

export const emptyDepartmentForm = (): DepartmentFormData => ({
  code: "",
  name: "",
  kind: "department",
});

export function formatResponsibleParty(department: Department): string {
  if (department.name && department.name !== department.code) {
    return `${department.code} — ${department.name}`;
  }
  return department.code;
}

export function canManageRemarks(role: UserRole): boolean {
  return role === "admin" || role === "gip";
}

export function canAssignDepartment(role: UserRole): boolean {
  return role === "admin" || role === "gip";
}

export function canAssignExecutor(role: UserRole): boolean {
  return role === "admin" || role === "gip" || role === "department_head";
}

export function canManageDepartments(role: UserRole): boolean {
  return role === "admin" || role === "gip";
}

export function canManageUsers(role: UserRole): boolean {
  return role === "admin";
}

export interface ProjectObject {
  id: number;
  name: string;
  subobject_name: string | null;
  letters_count: number;
  remarks_count: number;
  created_at: string;
  updated_at: string;
}

export interface ObjectFormData {
  name: string;
  subobject_name: string;
}

export const emptyObjectForm = (): ObjectFormData => ({
  name: "",
  subobject_name: "",
});

export function formatObjectTitle(object: Pick<ProjectObject, "name" | "subobject_name">): string {
  return object.subobject_name ? `${object.name}/${object.subobject_name}` : object.name;
}

export interface LetterAttachment {
  id: number;
  letter_id: number;
  filename: string;
  content_type: string | null;
  file_size: number;
  uploaded_by: string | null;
  created_at: string;
}

export interface Letter {
  id: number;
  object_id: number;
  from_whom: string | null;
  letter_number: string | null;
  letter_date: string | null;
  lep_accompaniment: string | null;
  lep_accompaniment_date: string | null;
  remarks_count: number;
  attachments_count: number;
  attachments: LetterAttachment[];
  created_at: string;
  updated_at: string;
  object?: { id: number; name: string; subobject_name: string | null } | null;
}

export interface LetterFormData {
  from_whom: string;
  letter_number: string;
  letter_date: string;
  lep_accompaniment: string;
  lep_accompaniment_date: string;
}

export const emptyLetterForm = (): LetterFormData => ({
  from_whom: "",
  letter_number: "",
  letter_date: "",
  lep_accompaniment: "",
  lep_accompaniment_date: "",
});

export interface Remark {
  id: number;
  from_whom: string | null;
  letter_number: string | null;
  letter_date: string | null;
  lep_accompaniment: string | null;
  lep_accompaniment_date: string | null;
  object_name: string | null;
  subobject_name: string | null;
  document_remark: string | null;
  document_type: string | null;
  remark_text: string | null;
  department_id: number | null;
  assignee_id: number | null;
  status: string;
  assigned_by: string | null;
  assigned_at: string | null;
  assignee_assigned_by: string | null;
  assignee_assigned_at: string | null;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
  department: Department | null;
  assignee: Pick<User, "id" | "username" | "display_name" | "role" | "department_id"> | null;
}

export type RemarkFormData = {
  document_remark: string;
  document_type: string;
  remark_text: string;
};

export interface Stats {
  total: number;
  unassigned: number;
  no_executor: number;
  by_status: Record<string, number>;
  by_department: Array<{ code: string; name: string; count: number }>;
}

export interface RemarkMeta {
  document_types: string[];
  from_whom: string[];
  objects: string[];
  lep_accompaniments: string[];
}

export interface ImportResult {
  imported: number;
  skipped: number;
  errors: string[];
}

export interface ImportJob {
  id: string;
  status: "processing" | "completed" | "failed";
  filename: string | null;
  imported: number;
  skipped: number;
  errors: string[];
  created_at: string | null;
  finished_at: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export const STATUS_LABELS: Record<string, string> = {
  in_progress: "В работе",
  pending_review: "Отработано на рассмотрении",
  resolved: "Устранено",
};

export const STATUS_LABELS_SHORT: Record<string, string> = {
  in_progress: "В работе",
  pending_review: "На рассмотр.",
  resolved: "Устранено",
};

export const STATUS_COLORS: Record<string, string> = {
  in_progress: "#ea580c",
  pending_review: "#2563eb",
  resolved: "#16a34a",
};

export const emptyRemarkForm = (): RemarkFormData => ({
  document_remark: "",
  document_type: "",
  remark_text: "",
});

export function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ru-RU");
}

export function toInputDate(value: string | null): string {
  if (!value) return "";
  return value.slice(0, 10);
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}
