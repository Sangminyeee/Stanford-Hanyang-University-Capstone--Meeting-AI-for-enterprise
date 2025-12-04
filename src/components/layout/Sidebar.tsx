"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
  { name: "Dashboard", href: "/", icon: "📊" },
  { name: "Meetings", href: "/meetings", icon: "📅" },
  { name: "Settings", href: "/settings", icon: "⚙️" },
];

const projectSubItems = [
  { name: "My tasks", href: "/projects/tasks", icon: "✓" },
  { name: "Insights", href: "/projects/insights", icon: "📈" },
];

function NavLink({ item, pathname }: { item: typeof navItems[0]; pathname: string }) {
  const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors",
        isActive
          ? "bg-blue-50 text-blue-600 font-semibold"
          : "text-slate-600 hover:bg-slate-50"
      )}
    >
      <span className="text-lg">{item.icon}</span>
      <span className="text-sm">{item.name}</span>
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const isProjectsActive = pathname.startsWith("/projects");
  const [isProjectsOpen, setIsProjectsOpen] = useState(true);

  return (
    <div className="w-[260px] bg-white rounded-r-3xl shadow-sm p-6 flex flex-col gap-8 h-screen fixed left-0 top-0">
      {/* Logo & User */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-slate-200 rounded-lg flex items-center justify-center">
          <span className="text-slate-500 text-lg">L</span>
        </div>
        <div>
          <div className="text-sm font-semibold text-slate-900">홍길동</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-1">
        {/* Dashboard */}
        <NavLink item={navItems[0]} pathname={pathname} />
        
        {/* Meetings */}
        <NavLink item={navItems[1]} pathname={pathname} />

        {/* Projects with submenu */}
        <div>
          <div className="flex items-center">
            <Link
              href="/projects"
              className={cn(
                "flex-1 flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors",
                isProjectsActive && !pathname.startsWith("/projects/tasks") && !pathname.startsWith("/projects/insights")
                  ? "bg-blue-50 text-blue-600 font-semibold"
                  : "text-slate-600 hover:bg-slate-50"
              )}
            >
              <span className="text-lg">📁</span>
              <span className="text-sm">Projects</span>
            </Link>
            <button
              onClick={() => setIsProjectsOpen(!isProjectsOpen)}
              className={cn(
                "px-2 py-2.5 rounded-lg transition-colors",
                isProjectsActive
                  ? "text-blue-600 hover:bg-blue-100"
                  : "text-slate-600 hover:bg-slate-50"
              )}
            >
              <span className={cn(
                "text-xs transition-transform block",
                isProjectsOpen ? "rotate-90" : ""
              )}>
                ▶
              </span>
            </button>
          </div>
          
          {isProjectsOpen && (
            <div className="ml-6 mt-1 space-y-1">
              {projectSubItems.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2 rounded-lg transition-colors",
                      isActive
                        ? "bg-blue-50 text-blue-600 font-semibold"
                        : "text-slate-600 hover:bg-slate-50"
                    )}
                  >
                    <span className="text-sm">{item.icon}</span>
                    <span className="text-sm">{item.name}</span>
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Settings */}
        <NavLink item={navItems[2]} pathname={pathname} />
      </nav>
    </div>
  );
}

