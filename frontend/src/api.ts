import type {
  Department,
  DepartmentFormData,
  ImportJob,
  ImportResult,
  Letter,
  LetterAttachment,
  LetterFormData,
  LoginResponse,
  Notification,
  ObjectFormData,
  PaginatedResponse,
  ProjectObject,
  Remark,
  RemarkFormData,
  RemarkMeta,
  Stats,
  User,
  UserRole,
} from "./types";

export type RemarkQueryParams = Record<string, string | number | boolean>;
const API = "/api";
const TOKEN_KEY = "zamechaniya_token";

let authToken: string | null = localStorage.getItem(TOKEN_KEY);

export function setAuthToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getAuthToken() {
  return authToken;
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  if (options?.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    setAuthToken(null);
  }
  if (!response.ok) {
    let detail = await response.text();
    try {
      const parsed = JSON.parse(detail) as { detail?: string };
      detail = parsed.detail ?? detail;
    } catch {
      // keep raw text
    }
    throw new Error(detail || `Ошибка ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

function normalizePayload(data: RemarkFormData) {
  const payload: Record<string, string | null> = {};
  for (const [key, value] of Object.entries(data)) {
    payload[key] = value?.trim() ? value.trim() : null;
  }
  return payload;
}

function normalizeLetterPayload(data: LetterFormData) {
  const payload: Record<string, string | null> = {};
  for (const [key, value] of Object.entries(data)) {
    payload[key] = value?.trim() ? value.trim() : null;
  }
  return payload;
}

export const api = {
  login: (username: string, password: string) =>
    request<LoginResponse>(`${API}/auth/login`, {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  me: () => request<User>(`${API}/auth/me`),

  getUsers: (departmentId?: number) => {
    const query = departmentId ? `?department_id=${departmentId}` : "";
    return request<User[]>(`${API}/users${query}`);
  },

  updateUser: (
    id: number,
    data: Partial<{ role: UserRole; department_id: number | null; is_active: boolean; display_name: string }>,
  ) =>
    request<User>(`${API}/users/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  getDepartments: (kind?: Department["kind"]) => {
    const query = kind ? `?kind=${kind}` : "";
    return request<Department[]>(`${API}/departments${query}`);
  },

  createDepartment: (data: DepartmentFormData) =>
    request<Department>(`${API}/departments`, {
      method: "POST",
      body: JSON.stringify({
        code: data.code.trim(),
        name: data.name.trim() || data.code.trim(),
        kind: data.kind,
      }),
    }),

  updateDepartment: (id: number, data: Partial<DepartmentFormData>) =>
    request<Department>(`${API}/departments/${id}`, {
      method: "PUT",
      body: JSON.stringify({
        ...(data.code !== undefined ? { code: data.code.trim() } : {}),
        ...(data.name !== undefined ? { name: data.name.trim() || data.code?.trim() } : {}),
        ...(data.kind !== undefined ? { kind: data.kind } : {}),
      }),
    }),

  deleteDepartment: (id: number) =>
    request<{ ok: boolean }>(`${API}/departments/${id}`, { method: "DELETE" }),

  getObjects: (search?: string) => {
    const query = search?.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
    return request<ProjectObject[]>(`${API}/objects${query}`);
  },

  createObject: (data: ObjectFormData) =>
    request<ProjectObject>(`${API}/objects`, {
      method: "POST",
      body: JSON.stringify({
        name: data.name.trim(),
        subobject_name: data.subobject_name.trim() || null,
      }),
    }),

  getLetters: (objectId: number) => request<Letter[]>(`${API}/objects/${objectId}/letters`),

  createLetter: (objectId: number, data: LetterFormData) =>
    request<Letter>(`${API}/objects/${objectId}/letters`, {
      method: "POST",
      body: JSON.stringify(normalizeLetterPayload(data)),
    }),

  getLetter: (letterId: number) => request<Letter>(`${API}/letters/${letterId}`),

  updateLetter: (letterId: number, data: Partial<LetterFormData>) =>
    request<Letter>(`${API}/letters/${letterId}`, {
      method: "PUT",
      body: JSON.stringify(normalizeLetterPayload(data as LetterFormData)),
    }),

  getLetterRemarks: (letterId: number, params?: RemarkQueryParams) => {
    const search = new URLSearchParams();
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== "") {
          search.set(key, String(value));
        }
      }
    }
    const query = search.toString();
    return request<PaginatedResponse<Remark>>(
      `${API}/letters/${letterId}/remarks${query ? `?${query}` : ""}`,
    );
  },

  createLetterRemark: (letterId: number, data: RemarkFormData) =>
    request<Remark>(`${API}/letters/${letterId}/remarks`, {
      method: "POST",
      body: JSON.stringify(normalizePayload(data)),
    }),

  uploadLetterAttachment: async (letterId: number, file: File): Promise<LetterAttachment> => {
    const formData = new FormData();
    formData.append("file", file);
    const headers = new Headers();
    if (authToken) {
      headers.set("Authorization", `Bearer ${authToken}`);
    }
    const response = await fetch(`${API}/letters/${letterId}/attachments`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json();
  },

  deleteAttachment: (attachmentId: number) =>
    request<{ ok: boolean }>(`${API}/attachments/${attachmentId}`, { method: "DELETE" }),

  downloadAttachment: async (attachmentId: number, filename: string) => {
    const headers = new Headers();
    if (authToken) {
      headers.set("Authorization", `Bearer ${authToken}`);
    }
    const response = await fetch(`${API}/attachments/${attachmentId}/download`, { headers });
    if (!response.ok) {
      throw new Error("Не удалось скачать файл");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  },

  getRemarks: (params?: RemarkQueryParams) => {
    const search = new URLSearchParams();
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== "") {
          search.set(key, String(value));
        }
      }
    }
    const query = search.toString();
    return request<PaginatedResponse<Remark>>(`${API}/remarks${query ? `?${query}` : ""}`);
  },

  getRemarkMeta: () => request<RemarkMeta>(`${API}/remarks/meta`),

  createRemark: (letterId: number, data: RemarkFormData) =>
    request<Remark>(`${API}/letters/${letterId}/remarks`, {
      method: "POST",
      body: JSON.stringify(normalizePayload(data)),
    }),

  updateRemark: (id: number, data: RemarkFormData) =>
    request<Remark>(`${API}/remarks/${id}`, {
      method: "PUT",
      body: JSON.stringify(normalizePayload(data)),
    }),

  assignDepartment: (id: number, department_id: number) =>
    request<Remark>(`${API}/remarks/${id}/assign-department`, {
      method: "POST",
      body: JSON.stringify({ department_id, status: "in_progress" }),
    }),

  assignExecutor: (id: number, assignee_id: number, due_date?: string) =>
    request<Remark>(`${API}/remarks/${id}/assign-executor`, {
      method: "POST",
      body: JSON.stringify({ assignee_id, due_date: due_date || null }),
    }),

  getNotifications: (unreadOnly = false) => {
    const query = unreadOnly ? "?unread_only=true" : "";
    return request<Notification[]>(`${API}/notifications${query}`);
  },

  getUnreadNotificationsCount: () =>
    request<{ count: number }>(`${API}/notifications/unread-count`),

  markNotificationRead: (id: number) =>
    request<Notification>(`${API}/notifications/${id}/read`, { method: "PATCH" }),

  markAllNotificationsRead: () =>
    request<{ updated: number }>(`${API}/notifications/mark-all-read`, { method: "POST" }),

  updateStatus: (id: number, status: string, resolution_notes?: string) =>
    request<Remark>(`${API}/remarks/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, resolution_notes }),
    }),

  deleteRemark: (id: number) =>
    request<{ ok: boolean }>(`${API}/remarks/${id}`, { method: "DELETE" }),

  importExcel: async (file: File): Promise<ImportResult> => {
    const formData = new FormData();
    formData.append("file", file);
    const headers = new Headers();
    if (authToken) {
      headers.set("Authorization", `Bearer ${authToken}`);
    }
    const response = await fetch(`${API}/import/excel`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json();
  },

  importExcelAsync: async (file: File): Promise<ImportJob> => {
    const formData = new FormData();
    formData.append("file", file);
    const headers = new Headers();
    if (authToken) {
      headers.set("Authorization", `Bearer ${authToken}`);
    }
    const response = await fetch(`${API}/import/excel/async`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json();
  },

  getImportJob: (jobId: string) => request<ImportJob>(`${API}/import/jobs/${jobId}`),

  getStats: () => request<Stats>(`${API}/stats`),
};
