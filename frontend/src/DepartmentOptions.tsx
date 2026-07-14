import type { Department } from "./types";
import { DEPARTMENT_KIND_LABELS, formatResponsibleParty } from "./types";

export function DepartmentOptions({ departments }: { departments: Department[] }) {
  const internal = departments.filter((item) => item.kind === "department");
  const subcontractors = departments.filter((item) => item.kind === "subcontractor");

  return (
    <>
      {internal.length ? (
        <optgroup label={DEPARTMENT_KIND_LABELS.department}>
          {internal.map((department) => (
            <option key={department.id} value={department.id}>
              {formatResponsibleParty(department)}
            </option>
          ))}
        </optgroup>
      ) : null}
      {subcontractors.length ? (
        <optgroup label={DEPARTMENT_KIND_LABELS.subcontractor}>
          {subcontractors.map((department) => (
            <option key={department.id} value={department.id}>
              {formatResponsibleParty(department)}
            </option>
          ))}
        </optgroup>
      ) : null}
    </>
  );
}
