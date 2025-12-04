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
    <div className="flex gap-1 border-b border-slate-200">
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

