"use client";

import { cn } from "@/lib/utils";

type TabType = "overview" | "prep" | "live" | "outcomes" | "patterns";

interface MeetingTabsProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

const tabs: { id: TabType; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "prep", label: "Prep" },
  { id: "live", label: "Live" },
  { id: "outcomes", label: "Outcomes" },
  { id: "patterns", label: "Patterns" },
];

export function MeetingTabs({ activeTab, onTabChange }: MeetingTabsProps) {
  return (
    <div className="flex items-center gap-1 border-b border-slate-200">
      <button
        className="px-3 py-3 text-slate-500 hover:text-slate-700 transition-colors"
        aria-label="Previous"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 19l-7-7 7-7"
          />
        </svg>
      </button>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            "px-4 py-3 text-sm font-medium transition-colors relative",
            activeTab === tab.id
              ? "text-blue-600"
              : "text-slate-500 hover:text-slate-700"
          )}
        >
          {tab.label}
          {activeTab === tab.id && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500" />
          )}
        </button>
      ))}
    </div>
  );
}

