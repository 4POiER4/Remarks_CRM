export interface RemarkFilters {
  search: string;
  status: string;
  assignment: "" | "assigned" | "unassigned" | "no_executor";
  department_id: string;
  letter_date_from: string;
  letter_date_to: string;
}

export const emptyFilters = (): RemarkFilters => ({
  search: "",
  status: "",
  assignment: "",
  department_id: "",
  letter_date_from: "",
  letter_date_to: "",
});

export function hasActiveFilters(filters: RemarkFilters): boolean {
  return Object.values(filters).some((value) => value !== "");
}

export function filtersToQuery(filters: RemarkFilters) {
  const params: Record<string, string | number | boolean> = {};

  if (filters.search.trim()) params.search = filters.search.trim();
  if (filters.status) params.status = filters.status;
  if (filters.assignment === "assigned") params.unassigned = false;
  if (filters.assignment === "unassigned") params.unassigned = true;
  if (filters.assignment === "no_executor") params.no_executor = true;
  if (filters.department_id) params.department_id = Number(filters.department_id);
  if (filters.letter_date_from) params.letter_date_from = filters.letter_date_from;
  if (filters.letter_date_to) params.letter_date_to = filters.letter_date_to;

  return params;
}
