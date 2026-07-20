import { useEffect, useMemo, useState } from "react";
import AdminPanel from "./AdminPanel";
import Login from "./Login";
import { DepartmentOptions } from "./DepartmentOptions";
import { api } from "./api";
import { useAuth } from "./auth";
import {
  Department,
  Letter,
  LetterFormData,
  Notification,
  ProjectObject,
  Remark,
  RemarkResult,
  RemarkFormData,
  ROLE_LABELS,
  Stats,
  STATUS_COLORS,
  STATUS_LABELS,
  STATUS_LABELS_SHORT,
  User,
  canAssignDepartment,
  canAssignExecutor,
  canManageRemarks,
  emptyLetterForm,
  emptyObjectForm,
  emptyRemarkForm,
  formatDate,
  formatFileSize,
  formatObjectTitle,
  formatResponsibleParty,
} from "./types";

type AppPage = "remarks" | "admin";
type ModalMode =
  | "create-object"
  | "create-letter"
  | "create-remark"
  | "edit-remark"
  | "assign-department"
  | "assign-executor"
  | "submit-result"
  | "review-feedback"
  | "import"
  | null;

const MAX_UPLOAD_SIZE_BYTES = 1024 * 1024 * 1024;
const APP_VIEW_STORAGE_KEY = "zamechaniya.app-view";
const ALLOWED_UPLOAD_EXTENSIONS = [".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".pdf", ".jpg", ".jpeg", ".png", ".txt"];
const ACCEPTED_UPLOAD_TYPES = ALLOWED_UPLOAD_EXTENSIONS.join(",");
const UPLOAD_RULE_TEXT = `Можно прикреплять файлы ${ALLOWED_UPLOAD_EXTENSIONS.join(", ")} размером до 1 ГБ`;

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

export default function App() {
  const { user, loading: authLoading, logout } = useAuth();
  const [view, setView] = useState<AppPage>(() =>
    window.sessionStorage.getItem(APP_VIEW_STORAGE_KEY) === "admin" ? "admin" : "remarks",
  );
  const [objects, setObjects] = useState<ProjectObject[]>([]);
  const [letters, setLetters] = useState<Letter[]>([]);
  const [selectedObjectId, setSelectedObjectId] = useState<number | null>(null);
  const [selectedLetterId, setSelectedLetterId] = useState<number | null>(null);
  const [letterDetail, setLetterDetail] = useState<Letter | null>(null);
  const [remarks, setRemarks] = useState<Remark[]>([]);
  const [departmentPendingRemarks, setDepartmentPendingRemarks] = useState<Remark[]>([]);
  const [myTasks, setMyTasks] = useState<Remark[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentUsers, setDepartmentUsers] = useState<User[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [objectSearch, setObjectSearch] = useState("");
  const [loadingObjects, setLoadingObjects] = useState(false);
  const [loadingLetters, setLoadingLetters] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingDepartmentPending, setLoadingDepartmentPending] = useState(false);
  const [loadingMyTasks, setLoadingMyTasks] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [objectForm, setObjectForm] = useState(emptyObjectForm());
  const [letterForm, setLetterForm] = useState<LetterFormData>(emptyLetterForm());
  const [remarkForm, setRemarkForm] = useState<RemarkFormData>(emptyRemarkForm());
  const [selectedRemark, setSelectedRemark] = useState<Remark | null>(null);
  const [focusedRemarkId, setFocusedRemarkId] = useState<number | null>(null);
  const [assignDepartmentId, setAssignDepartmentId] = useState("");
  const [departmentDueDate, setDepartmentDueDate] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [executorDueDate, setExecutorDueDate] = useState("");
  const [resultNotes, setResultNotes] = useState("");
  const [resultFile, setResultFile] = useState<File | null>(null);
  const [editingResult, setEditingResult] = useState<RemarkResult | null>(null);
  const [removeResultFile, setRemoveResultFile] = useState(false);
  const [submittingResult, setSubmittingResult] = useState(false);
  const [reviewComment, setReviewComment] = useState("");
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const selectedObject = useMemo(
    () => objects.find((item) => item.id === selectedObjectId) ?? null,
    [objects, selectedObjectId],
  );

  const showManageActions = user ? canManageRemarks(user.role) : false;
  const showAssignDepartment = user ? canAssignDepartment(user.role) : false;
  const showAssignExecutor = user ? canAssignExecutor(user.role) : false;
  const showAdmin = user?.role === "admin";
  const showDepartmentHeadTasks = user?.role === "department_head";
  const showMyTasks = user?.role === "employee";
  const canReviewRemark = (_remark: Remark) =>
    user?.role === "gip";

  const canEditResult = (remark: Remark, result: RemarkResult) =>
    !!user &&
    remark.status !== "resolved" &&
    ((user.role === "employee" && result.created_by_id === user.id) ||
      (user.role === "department_head" && user.department_id === remark.department_id));

  const canSubmitResult = (remark: Remark) =>
    !!user &&
    remark.status !== "resolved" &&
    ((user.role === "employee" && remark.assignee_id === user.id) ||
      (user.role === "department_head" && user.department_id === remark.department_id));

  const validateFileRules = (file: File): string | null => {
    const extension = file.name.includes(".") ? `.${file.name.split(".").pop()?.toLowerCase()}` : "";
    if (!ALLOWED_UPLOAD_EXTENSIONS.includes(extension)) {
      return UPLOAD_RULE_TEXT;
    }
    if (file.size > MAX_UPLOAD_SIZE_BYTES) {
      return "Можно прикреплять файлы размером до 1 ГБ";
    }
    return null;
  };

  const validateUploadFile = (file: File): string | null => {
    const rulesError = validateFileRules(file);
    if (rulesError) return rulesError;
    if (letterDetail?.attachments.some((item) => item.filename === file.name && item.file_size === file.size)) {
      return "Вы прикрепляете файл, который уже прикреплен!";
    }
    return null;
  };

  const loadObjects = async (search = objectSearch) => {
    setLoadingObjects(true);
    try {
      const data = await api.getObjects(search);
      setObjects(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить объекты");
    } finally {
      setLoadingObjects(false);
    }
  };

  const loadLetters = async (objectId: number) => {
    setLoadingLetters(true);
    try {
      const data = await api.getLetters(objectId);
      setLetters(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить письма");
    } finally {
      setLoadingLetters(false);
    }
  };

  const loadLetterDetail = async (letterId: number) => {
    setLoadingDetail(true);
    try {
      const [letter, remarksData, departmentsData, statsData] = await Promise.all([
        api.getLetter(letterId),
        api.getLetterRemarks(letterId, { page_size: 200 }),
        api.getDepartments(),
        api.getStats(),
      ]);
      setLetterDetail(letter);
      setRemarks(remarksData.items);
      setDepartments(departmentsData);
      setStats(statsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить письмо");
    } finally {
      setLoadingDetail(false);
    }
  };

  const loadDepartmentPendingRemarks = async () => {
    if (!showDepartmentHeadTasks) {
      setDepartmentPendingRemarks([]);
      return;
    }
    setLoadingDepartmentPending(true);
    try {
      const data = await api.getRemarks({ no_executor: true, page_size: 200 });
      setDepartmentPendingRemarks(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить задачи отдела");
    } finally {
      setLoadingDepartmentPending(false);
    }
  };

  const loadMyTasks = async () => {
    if (!showMyTasks || !user) {
      setMyTasks([]);
      return;
    }
    setLoadingMyTasks(true);
    try {
      const data = await api.getRemarks({ assignee_id: user.id, page_size: 200 });
      setMyTasks(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить мои задачи");
    } finally {
      setLoadingMyTasks(false);
    }
  };

  const loadNotifications = async () => {
    try {
      const [items, countData] = await Promise.all([
        api.getNotifications(true),
        api.getUnreadNotificationsCount(),
      ]);
      setNotifications(items);
      setUnreadNotifications(countData.count);
    } catch {
      setNotifications([]);
      setUnreadNotifications(0);
    }
  };

  const refreshCurrent = async () => {
    await loadObjects();
    if (selectedObjectId) {
      await loadLetters(selectedObjectId);
    }
    if (selectedLetterId) {
      await loadLetterDetail(selectedLetterId);
    }
    await loadDepartmentPendingRemarks();
    await loadMyTasks();
  };

  useEffect(() => {
    if (user) {
      void loadObjects();
      void api.getStats().then(setStats).catch(() => undefined);
      void loadNotifications();
      void loadDepartmentPendingRemarks();
      void loadMyTasks();
    }
  }, [user]);

  useEffect(() => {
    window.sessionStorage.setItem(APP_VIEW_STORAGE_KEY, view);
  }, [view]);

  useEffect(() => {
    if (user && view === "admin" && user.role !== "admin") {
      setView("remarks");
    }
  }, [user, view]);

  useEffect(() => {
    if (!success) return;
    const timeoutId = window.setTimeout(() => setSuccess(null), 15_000);
    return () => window.clearTimeout(timeoutId);
  }, [success]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setInterval(() => {
      void refreshCurrent();
      void api.getStats().then(setStats).catch(() => undefined);
      void loadNotifications();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [user, selectedObjectId, selectedLetterId, objectSearch]);

  useEffect(() => {
    if (!user) return;
    const timer = setTimeout(() => void loadObjects(objectSearch), 300);
    return () => clearTimeout(timer);
  }, [objectSearch, user]);

  useEffect(() => {
    if (selectedObjectId) {
      void loadLetters(selectedObjectId);
    } else {
      setLetters([]);
    }
  }, [selectedObjectId]);

  useEffect(() => {
    if (selectedLetterId) {
      void loadLetterDetail(selectedLetterId);
    } else {
      setLetterDetail(null);
      setRemarks([]);
    }
  }, [selectedLetterId]);

  useEffect(() => {
    if (!focusedRemarkId || !remarks.some((remark) => remark.id === focusedRemarkId)) return;
    const frameId = window.requestAnimationFrame(() => {
      document.getElementById(`remark-${focusedRemarkId}`)?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    });
    const timeoutId = window.setTimeout(() => setFocusedRemarkId(null), 2500);
    return () => {
      window.cancelAnimationFrame(frameId);
      window.clearTimeout(timeoutId);
    };
  }, [focusedRemarkId, remarks]);

  const selectObject = (objectId: number) => {
    setSelectedObjectId(objectId);
    setSelectedLetterId(null);
    setLetterDetail(null);
    setRemarks([]);
  };

  const selectLetter = (letterId: number) => {
    setSelectedLetterId(letterId);
  };

  const submitCreateObject = async () => {
    if (!objectForm.name.trim()) {
      setError("Введите название объекта");
      return;
    }
    try {
      const created = await api.createObject(objectForm);
      setModalMode(null);
      setObjectForm(emptyObjectForm());
      setSuccess("Объект создан");
      await loadObjects();
      selectObject(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка создания объекта");
    }
  };

  const submitCreateLetter = async () => {
    if (!selectedObjectId) return;
    try {
      const created = await api.createLetter(selectedObjectId, letterForm);
      setModalMode(null);
      setLetterForm(emptyLetterForm());
      setSuccess("Письмо создано");
      await loadLetters(selectedObjectId);
      selectLetter(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка создания письма");
    }
  };

  const submitCreateRemark = async () => {
    if (!selectedLetterId) return;
    try {
      if (modalMode === "create-remark") {
        await api.createLetterRemark(selectedLetterId, remarkForm);
        setSuccess("Замечание создано");
      } else if (modalMode === "edit-remark" && selectedRemark) {
        await api.updateRemark(selectedRemark.id, remarkForm);
        setSuccess("Замечание обновлено");
      }
      setModalMode(null);
      await loadLetterDetail(selectedLetterId);
      await loadObjects();
      if (selectedObjectId) await loadLetters(selectedObjectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  };

  const submitAssignDepartment = async () => {
    if (!selectedRemark || !assignDepartmentId) {
      setError("Выберите отдел");
      return;
    }
    if (!departmentDueDate) {
      setError("Укажите финальный срок исполнения");
      return;
    }
    try {
      await api.assignDepartment(
        selectedRemark.id,
        Number(assignDepartmentId),
        departmentDueDate,
      );
      setModalMode(null);
      setDepartmentDueDate("");
      setSuccess("Отдел назначен");
      await loadNotifications();
      await loadDepartmentPendingRemarks();
      await loadMyTasks();
      if (selectedLetterId) await loadLetterDetail(selectedLetterId);
      void api.getStats().then(setStats).catch(() => undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка назначения");
    }
  };

  const submitAssignExecutor = async () => {
    if (!selectedRemark || !assigneeId) {
      setError("Выберите исполнителя");
      return;
    }
    if (!executorDueDate) {
      setError("Укажите срок исполнения");
      return;
    }
    try {
      await api.assignExecutor(selectedRemark.id, Number(assigneeId), executorDueDate);
      setModalMode(null);
      setExecutorDueDate("");
      setSuccess("Исполнитель назначен");
      await loadDepartmentPendingRemarks();
      await loadMyTasks();
      await loadNotifications();
      if (selectedLetterId) await loadLetterDetail(selectedLetterId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка назначения");
    }
  };

  const changeStatus = async (remark: Remark, status: string, comment?: string) => {
    try {
      await api.updateStatus(remark.id, status, comment);
      setModalMode(null);
      setReviewComment("");
      setSuccess(`Статус: ${STATUS_LABELS[status]}`);
      if (selectedLetterId) await loadLetterDetail(selectedLetterId);
      await loadDepartmentPendingRemarks();
      await loadMyTasks();
      await loadNotifications();
      void api.getStats().then(setStats).catch(() => undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка смены статуса");
    }
  };

  const submitTaskResult = async () => {
    if (!selectedRemark) return;
    const keepsExistingFile = !!editingResult?.filename && !removeResultFile;
    if (!resultNotes.trim() && !resultFile && !keepsExistingFile) {
      setError("Опишите результат или прикрепите документ");
      return;
    }
    if (resultFile) {
      const validationError = validateFileRules(resultFile);
      if (validationError) {
        setError(validationError);
        return;
      }
    }
    setSubmittingResult(true);
    try {
      if (editingResult) {
        await api.updateRemarkResult(
          selectedRemark.id,
          editingResult.id,
          resultNotes,
          resultFile,
          removeResultFile,
        );
      } else {
        await api.submitRemarkResult(selectedRemark.id, resultNotes, resultFile);
      }
      setModalMode(null);
      setResultNotes("");
      setResultFile(null);
      setEditingResult(null);
      setRemoveResultFile(false);
      setSuccess(editingResult ? "Результат обновлён" : "Результат отправлен на рассмотрение");
      await loadMyTasks();
      await loadDepartmentPendingRemarks();
      await loadNotifications();
      if (selectedLetterId) await loadLetterDetail(selectedLetterId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось отправить результат");
    } finally {
      setSubmittingResult(false);
    }
  };

  const submitRevisionFeedback = async () => {
    if (!selectedRemark || !reviewComment.trim()) {
      setError("Укажите, что необходимо доработать");
      return;
    }
    await changeStatus(selectedRemark, "needs_revision", reviewComment.trim());
  };

  const getDueState = (dueDate: string | null): "none" | "ok" | "soon" | "overdue" => {
    if (!dueDate) return "none";
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const due = new Date(dueDate);
    due.setHours(0, 0, 0, 0);
    const diffDays = Math.ceil((due.getTime() - today.getTime()) / 86400000);
    if (diffDays < 0) return "overdue";
    if (diffDays <= 2) return "soon";
    return "ok";
  };

  const markAllNotificationsRead = async () => {
    try {
      await api.markAllNotificationsRead();
      await loadNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка обновления уведомлений");
    }
  };

  const openDepartmentTask = (remark: Remark) => {
    setFocusedRemarkId(remark.id);
    if (remark.letter?.object_id) {
      setSelectedObjectId(remark.letter.object_id);
    }
    if (remark.letter_id) {
      setSelectedLetterId(remark.letter_id);
    }
  };

  const openNotification = async (notification: Notification) => {
    try {
      if (notification.remark_id) {
        const remark = await api.getRemark(notification.remark_id);
        openDepartmentTask(remark);
      }
      await api.markNotificationRead(notification.id);
      await loadNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось открыть уведомление");
    }
  };

  const startAssignExecutor = (remark: Remark) => {
    setSelectedRemark(remark);
    setAssigneeId(remark.assignee_id ? String(remark.assignee_id) : "");
    setExecutorDueDate(remark.due_date ? remark.due_date.slice(0, 10) : "");
    setModalMode("assign-executor");
    void api
      .getUsers(remark.department_id ?? undefined)
      .then(setDepartmentUsers)
      .catch(() => undefined);
  };

  const openResultModal = (remark: Remark, result: RemarkResult | null = null) => {
    setSelectedRemark(remark);
    setEditingResult(result);
    setResultNotes(result?.notes ?? "");
    setResultFile(null);
    setRemoveResultFile(false);
    setModalMode("submit-result");
  };

  const removeResult = async (remark: Remark, result: RemarkResult) => {
    if (!window.confirm("Удалить результат выполнения?")) return;
    try {
      await api.deleteRemarkResult(remark.id, result.id);
      setSuccess("Результат удалён");
      await loadMyTasks();
      await loadDepartmentPendingRemarks();
      if (selectedLetterId) await loadLetterDetail(selectedLetterId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить результат");
    }
  };

  const removeRemark = async (remark: Remark) => {
    if (!window.confirm("Удалить замечание?")) return;
    try {
      await api.deleteRemark(remark.id);
      setSuccess("Замечание удалено");
      await refreshCurrent();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления");
    }
  };

  const submitUpload = async () => {
    if (!selectedLetterId || !uploadFile) return;
    const validationError = validateUploadFile(uploadFile);
    if (validationError) {
      setError(validationError);
      return;
    }
    setUploading(true);
    try {
      await api.uploadLetterAttachment(selectedLetterId, uploadFile);
      setUploadFile(null);
      setSuccess("Файл загружен");
      await loadLetterDetail(selectedLetterId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки файла");
    } finally {
      setUploading(false);
    }
  };

  const removeAttachment = async (attachmentId: number) => {
    if (!window.confirm("Удалить файл?")) return;
    try {
      await api.deleteAttachment(attachmentId);
      setSuccess("Файл удалён");
      if (selectedLetterId) await loadLetterDetail(selectedLetterId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления файла");
    }
  };

  const submitImport = async () => {
    if (!importFile) {
      setError("Выберите Excel-файл");
      return;
    }
    try {
      const job = await api.importExcelAsync(importFile);
      setModalMode(null);
      setImportFile(null);
      setSuccess("Импорт запущен...");
      const poll = async () => {
        const status = await api.getImportJob(job.id);
        if (status.status === "processing") {
          setTimeout(() => void poll(), 1500);
          return;
        }
        setSuccess(`Импортировано: ${status.imported}, пропущено: ${status.skipped}`);
        await refreshCurrent();
      };
      void poll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка импорта");
    }
  };

  if (authLoading) {
    return <div className="empty-state">Загрузка...</div>;
  }

  if (!user) {
    return <Login />;
  }

  if (view === "admin" && showAdmin) {
    return <AdminPanel onBack={() => setView("remarks")} />;
  }

  return (
    <div className="app-shell hierarchy-shell">
      <header className="topbar">
        <div>
          <h1>Учёт замечаний</h1>
          <p>
            {user.display_name} · {ROLE_LABELS[user.role]}
          </p>
        </div>
        <div className="topbar-actions">
          {showManageActions ? (
            <>
              <button className="btn btn-secondary" onClick={() => setModalMode("import")}>
                Импорт Excel
              </button>
              <button className="btn btn-primary" onClick={() => setModalMode("create-object")}>
                + Объект
              </button>
            </>
          ) : null}
          {showAdmin ? (
            <button className="btn btn-secondary" onClick={() => setView("admin")}>
              Админ-панель
            </button>
          ) : null}
          <button
            className="btn btn-secondary"
            onClick={() => {
              setView("remarks");
              logout();
            }}
          >
            Выйти
          </button>
        </div>
      </header>

      {error ? (
        <div className="alert alert-error" onClick={() => setError(null)}>
          {error}
        </div>
      ) : null}
      {success ? (
        <div className="alert alert-success" onClick={() => setSuccess(null)}>
          {success}
        </div>
      ) : null}

      {stats ? (
        <div className="stats-strip">
          <span>
            Всего: <strong>{stats.total}</strong>
          </span>
          <span className="stats-sep">·</span>
          <span>
            Без отдела: <strong>{stats.unassigned}</strong>
          </span>
          <span className="stats-sep">·</span>
          <span>
            Без исполнителя: <strong>{stats.no_executor}</strong>
          </span>
        </div>
      ) : null}

      {unreadNotifications > 0 ? (
        <section className="notifications-panel">
          <div className="notifications-header">
            <strong>Новые уведомления: {unreadNotifications}</strong>
            <button className="btn btn-secondary btn-small" onClick={() => void markAllNotificationsRead()}>
              Отметить прочитанными
            </button>
          </div>
          <ul className="notifications-list">
            {notifications.map((notification) => (
              <li key={notification.id}>
                <button
                  className="notification-link"
                  type="button"
                  onClick={() => void openNotification(notification)}
                >
                  {notification.message}
                </button>
                <small>{formatDate(notification.created_at)}</small>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {showDepartmentHeadTasks ? (
        <section className="department-tasks-panel">
          <div className="department-tasks-header">
            <div>
              <strong>Задачи отдела без исполнителя</strong>
              <span>{departmentPendingRemarks.length}</span>
            </div>
            <button className="btn btn-secondary btn-small" onClick={() => void loadDepartmentPendingRemarks()}>
              Обновить
            </button>
          </div>
          {loadingDepartmentPending ? (
            <div className="department-tasks-empty">Загрузка...</div>
          ) : departmentPendingRemarks.length === 0 ? (
            <div className="department-tasks-empty">Нет замечаний без исполнителя</div>
          ) : (
            <div className="department-task-list">
              {departmentPendingRemarks.map((remark) => (
                <article key={remark.id} className="department-task-card">
                  <div>
                    <div className="my-task-title-row">
                      <strong>
                        {remark.object_name
                          ? `${remark.object_name}${remark.subobject_name ? `/${remark.subobject_name}` : ""}`
                          : "Объект не указан"}
                      </strong>
                      <span className={`due-badge due-${getDueState(remark.department_due_date)}`}>
                        Финальный: {formatDate(remark.department_due_date)}
                      </span>
                    </div>
                    <span>
                      {remark.document_type || "Вид документа не указан"}
                      {remark.letter_number ? ` · письмо № ${remark.letter_number}` : ""}
                    </span>
                    {remark.remark_text ? <p>{remark.remark_text}</p> : null}
                    {remark.feedback.length ? (
                      <div className="task-feedback-compact">
                        <strong>Комментарий ОГИП:</strong>{" "}
                        {remark.feedback[remark.feedback.length - 1].comment}
                      </div>
                    ) : null}
                    {remark.results.length ? (
                      <div className="task-result-compact">
                        Результатов: {remark.results.length}
                      </div>
                    ) : null}
                  </div>
                  <div className="department-task-actions">
                    <button className="btn btn-secondary btn-small" onClick={() => openDepartmentTask(remark)}>
                      Открыть
                    </button>
                    {["in_progress", "needs_revision"].includes(remark.status) ? (
                      <button className="btn btn-primary btn-small" onClick={() => startAssignExecutor(remark)}>
                        Назначить исполнителя
                      </button>
                    ) : null}
                    {remark.status !== "resolved" ? (
                      <button className="btn btn-primary btn-small" onClick={() => openResultModal(remark)}>
                        Добавить результат
                      </button>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {showMyTasks ? (
        <section className="my-tasks-panel">
          <div className="my-tasks-header">
            <div>
              <strong>Мои задачи</strong>
              <span>{myTasks.length}</span>
            </div>
            <button className="btn btn-secondary btn-small" onClick={() => void loadMyTasks()}>
              Обновить
            </button>
          </div>
          {loadingMyTasks ? (
            <div className="department-tasks-empty">Загрузка...</div>
          ) : myTasks.length === 0 ? (
            <div className="department-tasks-empty">Назначенных задач нет</div>
          ) : (
            <div className="my-task-list">
              {myTasks.map((remark) => (
                <article key={remark.id} className={`my-task-card due-${getDueState(remark.due_date)}`}>
                  <div>
                    <div className="my-task-title-row">
                      <strong>
                        {remark.object_name
                          ? `${remark.object_name}${remark.subobject_name ? `/${remark.subobject_name}` : ""}`
                          : "Объект не указан"}
                      </strong>
                      <div className="due-badge-group">
                        <span className={`due-badge due-${getDueState(remark.due_date)}`}>
                          Внутренний: {formatDate(remark.due_date)}
                        </span>
                        <span className={`due-badge due-${getDueState(remark.department_due_date)}`}>
                          Финальный: {formatDate(remark.department_due_date)}
                        </span>
                      </div>
                    </div>
                    <span className="my-task-meta">
                      {remark.document_type || "Вид документа не указан"}
                      {remark.letter_number ? ` · письмо № ${remark.letter_number}` : ""}
                      {remark.status ? ` · ${STATUS_LABELS[remark.status] ?? remark.status}` : ""}
                    </span>
                    {remark.remark_text ? <p>{remark.remark_text}</p> : null}
                    {remark.feedback.length ? (
                      <div className="task-feedback-compact">
                        <strong>Комментарий ОГИП:</strong>{" "}
                        {remark.feedback[remark.feedback.length - 1].comment}
                      </div>
                    ) : null}
                    {remark.results.length ? (
                      <div className="task-result-compact">
                        Результатов: {remark.results.length}
                      </div>
                    ) : null}
                  </div>
                  <div className="my-task-actions">
                    <button className="btn btn-secondary btn-small" onClick={() => openDepartmentTask(remark)}>
                      Открыть
                    </button>
                    {remark.status !== "resolved" ? (
                      <button
                        className="btn btn-primary btn-small"
                        onClick={() => openResultModal(remark)}
                      >
                        Добавить результат
                      </button>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      <div className="hierarchy-layout">
        <aside className="hierarchy-panel objects-panel">
          <div className="panel-header">Объекты</div>
          <div className="panel-body">
            <input
              className="search-input"
              placeholder="Поиск объекта..."
              value={objectSearch}
              onChange={(event) => setObjectSearch(event.target.value)}
            />
            {loadingObjects ? (
              <div className="panel-empty">Загрузка...</div>
            ) : objects.length === 0 ? (
              <div className="panel-empty">Объектов пока нет</div>
            ) : (
              <ul className="nav-list">
                {objects.map((obj) => (
                  <li key={obj.id}>
                    <button
                      type="button"
                      className={`nav-item ${selectedObjectId === obj.id ? "active" : ""}`}
                      onClick={() => selectObject(obj.id)}
                    >
                      <span className="nav-item-title">{formatObjectTitle(obj)}</span>
                      <span className="nav-item-meta">
                        {obj.letters_count} писем · {obj.remarks_count} замеч.
                      </span>
                    </button>
                    {selectedObjectId === obj.id ? (
                      <div className="object-letters-panel">
                        <div className="object-letters-header">
                          <span>Письма</span>
                          {showManageActions ? (
                            <button
                              className="btn btn-primary btn-small"
                              onClick={() => setModalMode("create-letter")}
                            >
                              + Письмо
                            </button>
                          ) : null}
                        </div>
                        {loadingLetters ? (
                          <div className="nested-empty">Загрузка...</div>
                        ) : letters.length === 0 ? (
                          <div className="nested-empty">Писем пока нет</div>
                        ) : (
                          <ul className="nested-letter-list">
                            {letters.map((letter) => (
                              <li key={letter.id}>
                                <button
                                  type="button"
                                  className={`nested-letter-item ${selectedLetterId === letter.id ? "active" : ""}`}
                                  onClick={() => selectLetter(letter.id)}
                                >
                                  <span className="nav-item-title">
                                    {letter.letter_number ? `№ ${letter.letter_number}` : "Без номера"}
                                    {letter.from_whom ? ` · ${letter.from_whom}` : ""}
                                  </span>
                                  <span className="nav-item-meta">
                                    {formatDate(letter.letter_date)} · {letter.remarks_count} замеч.
                                    {letter.attachments_count ? ` · ${letter.attachments_count} файл.` : ""}
                                  </span>
                                </button>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        {false ? (
        <section className="hierarchy-panel letters-panel">
          <div className="panel-header letters-header">
            <span>{selectedObject ? formatObjectTitle(selectedObject) : "Письма"}</span>
            {selectedObjectId && showManageActions ? (
              <button className="btn btn-primary btn-small" onClick={() => setModalMode("create-letter")}>
                + Письмо
              </button>
            ) : null}
          </div>
          <div className="panel-body">
            {!selectedObjectId ? (
              <div className="panel-empty">Выберите объект слева</div>
            ) : loadingLetters ? (
              <div className="panel-empty">Загрузка...</div>
            ) : letters.length === 0 ? (
              <div className="panel-empty">Писем пока нет</div>
            ) : (
              <ul className="nav-list">
                {letters.map((letter) => (
                  <li key={letter.id}>
                    <button
                      type="button"
                      className={`nav-item ${selectedLetterId === letter.id ? "active" : ""}`}
                      onClick={() => selectLetter(letter.id)}
                    >
                      <span className="nav-item-title">
                        {letter.letter_number ? `№ ${letter.letter_number}` : "Без номера"}
                        {letter.from_whom ? ` · ${letter.from_whom}` : ""}
                      </span>
                      <span className="nav-item-meta">
                        {formatDate(letter.letter_date)} · {letter.remarks_count} замеч.
                        {letter.attachments_count ? ` · ${letter.attachments_count} файл.` : ""}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        ) : null}

        <main className="hierarchy-main">
          {!selectedLetterId ? (
            <div className="panel-empty main-empty">
              {selectedObjectId ? "Выберите письмо" : "Выберите объект и письмо"}
            </div>
          ) : loadingDetail || !letterDetail ? (
            <div className="panel-empty main-empty">Загрузка...</div>
          ) : (
            <>
              <section className="letter-card panel">
                <div className="panel-header">Карточка письма</div>
                <div className="panel-body">
                  <div className="meta-grid">
                    <div className="meta-item">
                      <span>От кого</span>
                      {letterDetail.from_whom || "—"}
                    </div>
                    <div className="meta-item">
                      <span>№ письма</span>
                      {letterDetail.letter_number || "—"}
                    </div>
                    <div className="meta-item">
                      <span>Дата письма</span>
                      {formatDate(letterDetail.letter_date)}
                    </div>
                    <div className="meta-item">
                      <span>Сопровод ЛЭП</span>
                      {letterDetail.lep_accompaniment || "—"}
                    </div>
                    <div className="meta-item">
                      <span>Дата сопровода ЛЭП</span>
                      {formatDate(letterDetail.lep_accompaniment_date)}
                    </div>
                  </div>

                  <div className="attachments-section">
                    <div className="attachments-header">
                      <strong>Файлы</strong>
                        <div className="attachments-upload">
                          <label className="file-picker">
                            <input
                              key={
                                uploadFile
                                  ? `${uploadFile.name}-${uploadFile.size}-${uploadFile.lastModified}`
                                  : "empty-upload"
                              }
                              className="file-picker-input"
                              type="file"
                              accept={ACCEPTED_UPLOAD_TYPES}
                              onChange={(event) => {
                                const file = event.target.files?.[0] ?? null;
                                if (file) {
                                  const validationError = validateUploadFile(file);
                                  if (validationError) {
                                    setError(validationError);
                                    event.target.value = "";
                                    setUploadFile(null);
                                    return;
                                  }
                                }
                                setUploadFile(file);
                              }}
                            />
                            <span className="file-picker-button">Выбрать файл</span>
                            <span className="file-picker-name">
                              {uploadFile?.name || "Файл не выбран"}
                            </span>
                          </label>
                          <button
                            className="btn btn-secondary btn-small"
                            disabled={!uploadFile || uploading}
                            onClick={() => void submitUpload()}
                          >
                            {uploading ? "Загрузка..." : "Прикрепить"}
                          </button>
                        </div>
                    </div>
                    <p className="attachment-rules">{UPLOAD_RULE_TEXT}</p>
                    {letterDetail.attachments.length === 0 ? (
                      <p className="import-note">Файлы не прикреплены</p>
                    ) : (
                      <ul className="attachment-list">
                        {letterDetail.attachments.map((file) => (
                          <li key={file.id} className="attachment-item">
                            <button
                              type="button"
                              className="attachment-link"
                              onClick={() => void api.downloadAttachment(file.id, file.filename)}
                            >
                              {file.filename}
                            </button>
                            <span className="attachment-meta">
                              {formatFileSize(file.file_size)}
                              {file.uploaded_by ? ` · ${file.uploaded_by}` : ""}
                            </span>
                            {showManageActions ? (
                              <button
                                className="btn btn-danger btn-small"
                                onClick={() => void removeAttachment(file.id)}
                              >
                                Удалить
                              </button>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </section>

              <section className="remarks-section">
                <div className="results-bar">
                  Замечания: {remarks.length}
                  {showManageActions ? (
                    <button
                      className="btn btn-primary btn-small"
                      style={{ marginLeft: 12 }}
                      onClick={() => {
                        setRemarkForm(emptyRemarkForm());
                        setModalMode("create-remark");
                      }}
                    >
                      + Замечание
                    </button>
                  ) : null}
                </div>

                {remarks.length === 0 ? (
                  <div className="empty-state">Замечаний в этом письме нет</div>
                ) : (
                  <div className="remark-list">
                    {remarks.map((remark) => (
                      <article
                        id={`remark-${remark.id}`}
                        key={remark.id}
                        className={`remark-card ${focusedRemarkId === remark.id ? "remark-card-focused" : ""}`}
                      >
                        <div className="remark-card-header">
                          <div>
                            <div className="remark-card-title">
                              {remark.document_type || "Вид документа не указан"}
                            </div>
                            {remark.document_remark ? (
                              <div className="remark-document-text">
                                {remark.document_remark}
                              </div>
                            ) : null}
                          </div>
                          <div className="status-pills">
                            {Object.entries(STATUS_LABELS_SHORT).map(([value, label]) => (
                              <button
                                key={value}
                                type="button"
                                className={`status-pill ${remark.status === value ? "active" : ""}`}
                                style={
                                  remark.status === value
                                    ? {
                                        background: STATUS_COLORS[value],
                                        borderColor: STATUS_COLORS[value],
                                        color: "#fff",
                                      }
                                    : undefined
                                }
                                disabled={!canReviewRemark(remark)}
                                onClick={() => {
                                  if (!canReviewRemark(remark)) return;
                                  if (remark.status === value) return;
                                  if (value === "needs_revision") {
                                    setSelectedRemark(remark);
                                    setReviewComment("");
                                    setModalMode("review-feedback");
                                    return;
                                  }
                                  void changeStatus(remark, value);
                                }}
                              >
                                {label}
                              </button>
                            ))}
                          </div>
                        </div>

                        {remark.remark_text ? (
                          <div className="remark-text">
                            <strong>Замечание:</strong>
                            <br />
                            {remark.remark_text}
                          </div>
                        ) : null}

                        {remark.feedback.length ? (
                          <div className="feedback-summary">
                            <strong>Комментарии ОГИП</strong>
                            <div className="feedback-list">
                              {remark.feedback.map((item) => (
                                <div key={item.id} className="feedback-item">
                                  <div className="feedback-item-header">
                                    {item.created_by_name} · {formatDate(item.created_at)}
                                  </div>
                                  <p>{item.comment}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}

                        {remark.results.length ? (
                          <div className="result-summary">
                            <strong>Результаты выполнения: {remark.results.length}</strong>
                            <div className="result-list">
                              {remark.results.map((result, index) => (
                                <div key={result.id} className="result-item">
                                  <div className="result-item-header">
                                    <span>
                                      Результат {index + 1} · {result.created_by_name} · {formatDate(result.created_at)}
                                    </span>
                                    {canEditResult(remark, result) ? (
                                      <div className="result-item-actions">
                                        <button
                                          className="btn btn-secondary btn-small"
                                          onClick={() => openResultModal(remark, result)}
                                        >
                                          Изменить
                                        </button>
                                        <button
                                          className="btn btn-danger btn-small"
                                          onClick={() => void removeResult(remark, result)}
                                        >
                                          Удалить
                                        </button>
                                      </div>
                                    ) : null}
                                  </div>
                                  {result.notes ? <p>{result.notes}</p> : null}
                                  {result.filename ? (
                                    <div className="result-attachment">
                                      <button
                                        type="button"
                                        className="attachment-link"
                                        onClick={() =>
                                          void api.downloadRemarkResult(
                                            remark.id,
                                            result.id,
                                            result.filename!,
                                          )
                                        }
                                      >
                                        {result.filename}
                                      </button>
                                      <span className="attachment-meta">
                                        {formatFileSize(result.file_size ?? 0)}
                                      </span>
                                    </div>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}

                        <div className="meta-grid">
                          <div className="meta-item">
                            <span>Отдел</span>
                            {remark.department ? formatResponsibleParty(remark.department) : "Не назначен"}
                          </div>
                          <div className="meta-item">
                            <span>Исполнитель</span>
                            {remark.assignee?.display_name || "Не назначен"}
                          </div>
                          <div className="meta-item">
                            <span>Финальный срок ОГИП</span>
                            {formatDate(remark.department_due_date)}
                          </div>
                          <div className="meta-item">
                            <span>Внутренний срок исполнителя</span>
                            {formatDate(remark.due_date)}
                          </div>
                        </div>

                        <div className="card-actions">
                          {canSubmitResult(remark) ? (
                            <button className="btn btn-primary" onClick={() => openResultModal(remark)}>
                              Добавить результат
                            </button>
                          ) : null}
                          {showManageActions ? (
                            <button
                              className="btn btn-secondary"
                              onClick={() => {
                                setSelectedRemark(remark);
                                setRemarkForm({
                                  document_remark: remark.document_remark ?? "",
                                  document_type: remark.document_type ?? "",
                                  remark_text: remark.remark_text ?? "",
                                });
                                setModalMode("edit-remark");
                              }}
                            >
                              Редактировать
                            </button>
                          ) : null}
                          {showAssignDepartment ? (
                            <button
                              className="btn btn-primary"
                              onClick={() => {
                                setSelectedRemark(remark);
                                setAssignDepartmentId(
                                  remark.department_id ? String(remark.department_id) : "",
                                );
                                setDepartmentDueDate(
                                  remark.department_due_date
                                    ? remark.department_due_date.slice(0, 10)
                                    : "",
                                );
                                setModalMode("assign-department");
                              }}
                            >
                              Назначить отдел
                            </button>
                          ) : null}
                          {showAssignExecutor && remark.department_id && ["in_progress", "needs_revision"].includes(remark.status) ? (
                            <button
                              className="btn btn-primary"
                              onClick={() => startAssignExecutor(remark)}
                            >
                              Назначить исполнителя
                            </button>
                          ) : null}
                          {showManageActions ? (
                            <button className="btn btn-danger" onClick={() => void removeRemark(remark)}>
                              Удалить
                            </button>
                          ) : null}
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </main>
      </div>

      {modalMode === "create-object" ? (
        <Modal
          title="Новый объект"
          onClose={() => setModalMode(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setModalMode(null)}>
                Отмена
              </button>
              <button className="btn btn-primary" onClick={() => void submitCreateObject()}>
                Создать
              </button>
            </>
          }
        >
          <div className="field">
            <label htmlFor="objectName">Название основного объекта</label>
            <input
              id="objectName"
              value={objectForm.name}
              onChange={(event) => setObjectForm((current) => ({ ...current, name: event.target.value }))}
            />
          </div>
          <div className="field">
            <label htmlFor="subobjectName">Название подобъекта</label>
            <input
              id="subobjectName"
              value={objectForm.subobject_name}
              onChange={(event) =>
                setObjectForm((current) => ({ ...current, subobject_name: event.target.value }))
              }
            />
          </div>
        </Modal>
      ) : null}

      {modalMode === "create-letter" ? (
        <Modal
          title="Новое письмо"
          onClose={() => setModalMode(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setModalMode(null)}>
                Отмена
              </button>
              <button className="btn btn-primary" onClick={() => void submitCreateLetter()}>
                Создать
              </button>
            </>
          }
        >
          <div className="form-grid">
            <div className="field">
              <label>От кого письмо/задание</label>
              <input
                value={letterForm.from_whom}
                onChange={(e) => setLetterForm({ ...letterForm, from_whom: e.target.value })}
              />
            </div>
            <div className="field">
              <label>№ письма</label>
              <input
                value={letterForm.letter_number}
                onChange={(e) => setLetterForm({ ...letterForm, letter_number: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Дата письма</label>
              <input
                type="date"
                value={letterForm.letter_date}
                onChange={(e) => setLetterForm({ ...letterForm, letter_date: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Сопровод ЛЭП</label>
              <input
                value={letterForm.lep_accompaniment}
                onChange={(e) => setLetterForm({ ...letterForm, lep_accompaniment: e.target.value })}
              />
            </div>
            <div className="field full-width">
              <label>Дата сопровода ЛЭП</label>
              <input
                type="date"
                value={letterForm.lep_accompaniment_date}
                onChange={(e) =>
                  setLetterForm({ ...letterForm, lep_accompaniment_date: e.target.value })
                }
              />
            </div>
          </div>
        </Modal>
      ) : null}

      {modalMode === "create-remark" || modalMode === "edit-remark" ? (
        <Modal
          title={modalMode === "create-remark" ? "Новое замечание" : "Редактирование замечания"}
          onClose={() => setModalMode(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setModalMode(null)}>
                Отмена
              </button>
              <button className="btn btn-primary" onClick={() => void submitCreateRemark()}>
                Сохранить
              </button>
            </>
          }
        >
          <div className="form-grid">
            <div className="field">
              <label>Вид документа</label>
              <input
                value={remarkForm.document_type}
                onChange={(e) => setRemarkForm({ ...remarkForm, document_type: e.target.value })}
              />
            </div>
            <div className="field full-width">
              <label>Замечание к документу</label>
              <textarea
                value={remarkForm.document_remark}
                onChange={(e) => setRemarkForm({ ...remarkForm, document_remark: e.target.value })}
              />
            </div>
            <div className="field full-width">
              <label>Замечание</label>
              <textarea
                value={remarkForm.remark_text}
                onChange={(e) => setRemarkForm({ ...remarkForm, remark_text: e.target.value })}
              />
            </div>
          </div>
        </Modal>
      ) : null}

      {modalMode === "assign-department" && selectedRemark ? (
        <Modal
          title="Назначение отдела"
          onClose={() => setModalMode(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setModalMode(null)}>
                Отмена
              </button>
              <button className="btn btn-primary" onClick={() => void submitAssignDepartment()}>
                Назначить
              </button>
            </>
          }
        >
          <div className="field">
            <label>Отдел / субподряд</label>
            <select
              value={assignDepartmentId}
              onChange={(event) => setAssignDepartmentId(event.target.value)}
            >
              <option value="">Выберите</option>
              <DepartmentOptions departments={departments} />
            </select>
          </div>
          <div className="field">
            <label htmlFor="departmentDueDate">Финальный срок исполнения</label>
            <input
              id="departmentDueDate"
              type="date"
              value={departmentDueDate}
              onChange={(event) => setDepartmentDueDate(event.target.value)}
            />
          </div>
        </Modal>
      ) : null}

      {modalMode === "assign-executor" && selectedRemark ? (
        <Modal
          title="Назначение исполнителя"
          onClose={() => setModalMode(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setModalMode(null)}>
                Отмена
              </button>
              <button className="btn btn-primary" onClick={() => void submitAssignExecutor()}>
                Назначить
              </button>
            </>
          }
        >
          <div className="field">
            <label>Исполнитель</label>
            <select value={assigneeId} onChange={(event) => setAssigneeId(event.target.value)}>
              <option value="">Выберите</option>
              {departmentUsers.filter((item) => item.role === "employee").map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="executorDueDate">Срок исполнения</label>
            <input
              id="executorDueDate"
              type="date"
              value={executorDueDate}
              max={selectedRemark.department_due_date?.slice(0, 10)}
              onChange={(event) => setExecutorDueDate(event.target.value)}
            />
          </div>
        </Modal>
      ) : null}

      {modalMode === "submit-result" && selectedRemark ? (
        <Modal
          title={editingResult ? "Редактировать результат" : "Новый результат выполнения"}
          onClose={() => {
            setModalMode(null);
            setResultFile(null);
            setEditingResult(null);
            setRemoveResultFile(false);
          }}
          footer={
            <>
              <button
                className="btn btn-secondary"
                disabled={submittingResult}
                onClick={() => {
                  setModalMode(null);
                  setResultFile(null);
                  setEditingResult(null);
                  setRemoveResultFile(false);
                }}
              >
                Отмена
              </button>
              <button
                className="btn btn-primary"
                disabled={submittingResult}
                onClick={() => void submitTaskResult()}
              >
                {submittingResult
                  ? "Сохранение..."
                  : editingResult
                    ? "Сохранить изменения"
                    : "Отправить на рассмотрение"}
              </button>
            </>
          }
        >
          <div className="field">
            <label htmlFor="resultNotes">Что выполнено</label>
            <textarea
              id="resultNotes"
              value={resultNotes}
              onChange={(event) => setResultNotes(event.target.value)}
              placeholder="Опишите результат выполнения или приложите пояснение для проверки"
            />
          </div>
          <div className="field">
            <label>Документ результата</label>
            <label className="file-picker file-picker-block">
              <input
                key={
                  resultFile
                    ? `${resultFile.name}-${resultFile.size}-${resultFile.lastModified}`
                    : "empty-result"
                }
                className="file-picker-input"
                type="file"
                accept={ACCEPTED_UPLOAD_TYPES}
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  if (file) {
                    const validationError = validateFileRules(file);
                    if (validationError) {
                      setError(validationError);
                      event.target.value = "";
                      setResultFile(null);
                      return;
                    }
                  }
                  setResultFile(file);
                  if (file) setRemoveResultFile(false);
                }}
              />
              <span className="file-picker-button">Выбрать файл</span>
              <span className="file-picker-name">
                {resultFile?.name || "Файл не выбран"}
              </span>
            </label>
            <p className="result-file-note">
              {UPLOAD_RULE_TEXT}.
              {editingResult?.filename ? " Новый документ заменит текущий." : ""}
            </p>
            {editingResult?.filename ? (
              <div className="current-result-row">
                <button
                  type="button"
                  className="attachment-link current-result-file"
                  onClick={() =>
                    void api.downloadRemarkResult(
                      selectedRemark.id,
                      editingResult.id,
                      editingResult.filename!,
                    )
                  }
                >
                  Текущий файл: {editingResult.filename}
                </button>
                <label className="result-remove-file">
                  <input
                    type="checkbox"
                    checked={removeResultFile}
                    onChange={(event) => setRemoveResultFile(event.target.checked)}
                  />
                  Удалить текущий файл
                </label>
              </div>
            ) : null}
          </div>
        </Modal>
      ) : null}

      {modalMode === "review-feedback" && selectedRemark ? (
        <Modal
          title="Вернуть на доработку"
          onClose={() => {
            setModalMode(null);
            setReviewComment("");
          }}
          footer={
            <>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setModalMode(null);
                  setReviewComment("");
                }}
              >
                Отмена
              </button>
              <button className="btn btn-primary" onClick={() => void submitRevisionFeedback()}>
                Отправить отделу
              </button>
            </>
          }
        >
          <div className="field">
            <label htmlFor="reviewComment">Что необходимо доработать</label>
            <textarea
              id="reviewComment"
              autoFocus
              value={reviewComment}
              onChange={(event) => setReviewComment(event.target.value)}
              placeholder="Опишите замечания к результату выполнения"
            />
          </div>
        </Modal>
      ) : null}

      {modalMode === "import" ? (
        <Modal
          title="Импорт из Excel"
          onClose={() => setModalMode(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setModalMode(null)}>
                Отмена
              </button>
              <button className="btn btn-primary" onClick={() => void submitImport()}>
                Импортировать
              </button>
            </>
          }
        >
          <p className="import-note">
            Excel создаст объекты, письма и замечания по иерархии. Первая строка — заголовки столбцов.
          </p>
          <div className="field">
            <label>Файл .xlsx</label>
            <label className="file-picker file-picker-block">
              <input
                key={
                  importFile
                    ? `${importFile.name}-${importFile.size}-${importFile.lastModified}`
                    : "empty-import"
                }
                className="file-picker-input"
                type="file"
                accept=".xlsx,.xlsm"
                onChange={(event) => setImportFile(event.target.files?.[0] ?? null)}
              />
              <span className="file-picker-button">Выбрать файл</span>
              <span className="file-picker-name">
                {importFile?.name || "Файл не выбран"}
              </span>
            </label>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
