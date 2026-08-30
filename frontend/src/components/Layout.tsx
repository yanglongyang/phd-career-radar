import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { cn } from "../lib/utils";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/jobs", label: "岗位库" },
  { to: "/organizations", label: "单位库" },
  { to: "/settings", label: "设置" },
];

function ThemeToggle() {
  const [dark, setDark] = useState(() => localStorage.getItem("pcr-theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("pcr-theme", dark ? "dark" : "light");
  }, [dark]);

  return (
    <button
      onClick={() => setDark((d) => !d)}
      className="rounded-md px-2 py-1 text-sm text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
      title="切换明暗主题"
    >
      {dark ? "☀️ 浅色" : "🌙 深色"}
    </button>
  );
}

export default function Layout() {
  const location = useLocation();
  return (
    <div className="flex h-full">
      <aside className="flex w-56 shrink-0 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center gap-2 px-4 py-4">
          <span className="text-lg">📡</span>
          <div>
            <p className="text-sm font-semibold leading-tight">PhD Career Radar</p>
            <p className="text-xs text-zinc-400">求职监控工作台 V0.1</p>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-2">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={"end" in item ? item.end : false}
              className={({ isActive }) =>
                cn(
                  "block rounded-md px-3 py-2 text-sm transition-colors",
                  isActive || (item.to === "/jobs" && location.pathname.startsWith("/jobs"))
                    ? "bg-zinc-100 font-medium text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                    : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-200",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <ThemeToggle />
          <p className="mt-2 text-xs leading-relaxed text-zinc-400">
            AI 仅辅助判断；<br />
            投递决策由你本人做出。
          </p>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-8 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
