import type { InputHTMLAttributes } from "react";

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  indeterminate?: boolean;
  label?: string;
}

export function Checkbox({ indeterminate, label, className = "", ...props }: CheckboxProps) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2">
      <input
        type="checkbox"
        className={`h-4 w-4 cursor-pointer appearance-none rounded border-2 bg-center bg-no-repeat transition-all focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 ${
          indeterminate
            ? "border-violet-500 bg-violet-500"
            : "border-slate-300 checked:border-violet-500 checked:bg-violet-500"
        } ${className}`}
        style={{
          backgroundImage: indeterminate
            ? "url(\"data:image/svg+xml,%3csvg viewBox='0 0 16 16' fill='white' xmlns='http://www.w3.org/2000/svg'%3e%3crect x='3' y='7' width='10' height='2' rx='1'/%3e%3c/svg%3e\")"
            : "url(\"data:image/svg+xml,%3csvg viewBox='0 0 16 16' fill='white' xmlns='http://www.w3.org/2000/svg'%3e%3cpath d='M12.207 4.793a1 1 0 010 1.414l-5 5a1 1 0 01-1.414 0l-2-2a1 1 0 011.414-1.414L6.5 9.086l4.293-4.293a1 1 0 011.414 0z'/%3e%3c/svg%3e\")",
          backgroundSize: "12px 12px",
        }}
        ref={(el) => {
          if (el) {
            el.indeterminate = indeterminate ?? false;
          }
        }}
        {...props}
      />
      {label && <span className="select-none text-sm">{label}</span>}
    </label>
  );
}
