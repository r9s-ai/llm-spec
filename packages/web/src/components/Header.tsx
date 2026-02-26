import type { PageKey } from "../types";

interface HeaderProps {
  page: PageKey;
  notice: string;
  onNavigate: (page: PageKey) => void;
}

export function Header({ page, notice, onNavigate }: HeaderProps) {
  return (
    <header className="border-b border-slate-300 bg-white">
      <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between px-4 py-3 xl:px-7">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2.5">
            <img src="/logo.jpg" alt="logo" className="h-10 w-10 rounded-lg object-cover" />
            <div className="text-[22px] font-black leading-tight">LLM Spec</div>
          </div>

          <nav className="flex items-center gap-1" style={{ fontFamily: "var(--font-sans)" }}>
            {(["testing", "suites", "settings"] as PageKey[]).map((item) => (
              <button
                key={item}
                className={`rounded-lg px-3 py-2 text-sm font-medium ${
                  page === item
                    ? "bg-violet-50 text-violet-600"
                    : "text-slate-600 hover:text-slate-900"
                }`}
                onClick={() => onNavigate(item)}
              >
                {item[0].toUpperCase() + item.slice(1)}
              </button>
            ))}
          </nav>
        </div>

        <div className="min-h-5 text-right text-xs text-slate-500">{notice}</div>
      </div>
    </header>
  );
}
