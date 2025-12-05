import React from "react";
import { cn } from "@/lib/utils";

type BadgeVariant =
  | "status-completed"
  | "status-in-progress"
  | "status-overdue"
  | "status-scheduled"
  | "status-deferred"
  | "status-discussion-needed"
  | "status-agreed"
  | "status-revision-needed"
  | "status-unknown"
  | "tag";

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant, children, className }: BadgeProps) {
  const baseStyles = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  
  const variantStyles = {
    "status-completed": "bg-emerald-50 text-emerald-700",
    "status-in-progress": "bg-blue-50 text-blue-700",
    "status-overdue": "bg-rose-50 text-rose-700",
    "status-scheduled": "bg-slate-50 text-slate-700",
    "status-deferred": "bg-slate-50 text-slate-700",
    "status-discussion-needed": "bg-orange-50 text-orange-700",
    "status-agreed": "bg-emerald-50 text-emerald-700",
    "status-revision-needed": "bg-orange-50 text-orange-700",
    "status-unknown": "bg-slate-50 text-slate-700",
    tag: "bg-slate-100 text-slate-700",
  };
  
  return (
    <span className={cn(baseStyles, variantStyles[variant], className)}>
      {children}
    </span>
  );
}

