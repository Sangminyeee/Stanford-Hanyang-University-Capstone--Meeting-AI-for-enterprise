"use client";

import { useState } from "react";
import { Card } from "@/components/common/Card";
import { Badge } from "@/components/common/Badge";
import { MeetingHeader } from "./MeetingHeader";

const meetingData = {
  title: "Marketing Strategy Review",
  date: "Nov 30",
  time: "9:00 AM",
  endTime: "11:00 AM",
  duration: "2h",
  attendees: ["Kim minsoo", "Park minsoo", "Lee minsoo"],
  project: "Project A",
  tags: ["Design", "PM"],
  status: "Scheduled",
};

interface AgendaItem {
  id: number;
  title: string;
  status: "deferred" | "completed" | "discussion-needed";
  note?: string;
  supportingStatements?: string;
  attendeeFeedback?: {
    name: string;
    status: "agreed" | "revision-needed" | "unknown";
  }[];
}

interface ActionItem {
  id: number;
  description: string;
  assignee: string;
  dueDate: string;
  completed: boolean;
}

const defaultAgendaItems: AgendaItem[] = [
  {
    id: 1,
    title: "런칭 이벤트 경품 예산 (500만원 vs 1000만원)",
    status: "deferred",
    note: "다음 회의로 이동 예정",
  },
  {
    id: 2,
    title: "디자인 컨셉 A안으로 최종 확정",
    status: "completed",
    supportingStatements: '"사용자 친화적이라 좋다"는 의견 다수',
  },
  {
    id: 3,
    title: "인플루언서 리스트업",
    status: "discussion-needed",
    attendeeFeedback: [
      { name: "Kim minsoo", status: "agreed" },
      { name: "Park minsoo", status: "revision-needed" },
      { name: "Lee minsoo", status: "unknown" },
    ],
  },
];

const defaultActionItems: ActionItem[] = [
  {
    id: 1,
    description: "와이어프레임 수정안 공유",
    assignee: "박민수",
    dueDate: "2025/12/04",
    completed: false,
  },
  {
    id: 2,
    description: "와이어프레임 수정안 공유",
    assignee: "박민수",
    dueDate: "2025/12/04",
    completed: false,
  },
];

export function MeetingOutcomesSection() {
  const [agendaItems, setAgendaItems] = useState<AgendaItem[]>(defaultAgendaItems);
  const [actionItems, setActionItems] = useState<ActionItem[]>(defaultActionItems);
  const [expandedAgenda, setExpandedAgenda] = useState<number | null>(null);
  const [generalSummary, setGeneralSummary] = useState(
    "마케팅 채널을 인스타그램 위주로 재편함 예산 부족 이슈는 3분기에 다시 검토하기로 함"
  );

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      deferred: "보류",
      completed: "완료",
      "discussion-needed": "논의필요",
      agreed: "동의",
      "revision-needed": "수정필요",
      unknown: "모름",
    };
    return labels[status] || status;
  };

  const getStatusVariant = (status: string): "status-deferred" | "status-completed" | "status-discussion-needed" | "status-agreed" | "status-revision-needed" | "status-unknown" => {
    const variants: Record<string, any> = {
      deferred: "status-deferred",
      completed: "status-completed",
      "discussion-needed": "status-discussion-needed",
      agreed: "status-agreed",
      "revision-needed": "status-revision-needed",
      unknown: "status-unknown",
    };
    return variants[status] || "status-unknown";
  };

  const toggleAgendaExpand = (id: number) => {
    setExpandedAgenda(expandedAgenda === id ? null : id);
  };

  return (
    <div className="space-y-6">
      <MeetingHeader {...meetingData} />

      {/* 회의 내용 상세 */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">
          회의 내용 상세
        </h2>
        
        {/* General Summary */}
        <p className="text-sm text-slate-600 leading-relaxed mb-6">
          {generalSummary}
        </p>

        {/* Agenda Items */}
        <div className="grid grid-cols-3 gap-4">
          {agendaItems.map((item) => (
            <div
              key={item.id}
              className="p-4 bg-white rounded-lg border border-slate-200"
            >
              <div className="mb-3">
                <h3 className="text-xs font-semibold text-slate-500 mb-2">
                  안건{item.id}
                </h3>
                <p className="text-sm font-medium text-slate-900 mb-2 leading-relaxed">
                  {item.title}
                </p>
                <div className="mb-2">
                  <Badge variant={getStatusVariant(item.status)}>
                    {getStatusLabel(item.status)}
                  </Badge>
                </div>
              </div>

              {/* Note for deferred items */}
              {item.note && (
                <p className="text-xs text-slate-600 mt-2">{item.note}</p>
              )}

              {/* Supporting statements for completed items */}
              {item.supportingStatements && (
                <div className="mt-2">
                  <button
                    onClick={() => toggleAgendaExpand(item.id)}
                    className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-800 mb-2"
                  >
                    <span>근거발언 펼치기</span>
                    <svg
                      className={`w-3 h-3 transition-transform ${
                        expandedAgenda === item.id ? "rotate-90" : ""
                      }`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 5l7 7-7 7"
                      />
                    </svg>
                  </button>
                  {expandedAgenda === item.id && (
                    <p className="text-xs text-slate-600 leading-relaxed">
                      {item.supportingStatements}
                    </p>
                  )}
                </div>
              )}

              {/* Attendee feedback for discussion-needed items */}
              {item.attendeeFeedback && (
                <div className="space-y-2 mt-3 pt-3 border-t border-slate-100">
                  {item.attendeeFeedback.map((feedback, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <div className="w-5 h-5 bg-slate-300 rounded-full flex-shrink-0"></div>
                      <span className="text-xs text-slate-700 flex-1">
                        {feedback.name}
                      </span>
                      <Badge variant={getStatusVariant(feedback.status)}>
                        {getStatusLabel(feedback.status)}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Action Items */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">
          Action Items
        </h2>
        <div className="space-y-2">
          {actionItems.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-3 p-3 bg-white rounded-lg border border-slate-200 hover:bg-slate-50"
            >
              <input
                type="radio"
                checked={item.completed}
                onChange={(e) => {
                  setActionItems(
                    actionItems.map((ai) =>
                      ai.id === item.id
                        ? { ...ai, completed: e.target.checked }
                        : ai
                    )
                  );
                }}
                className="w-4 h-4 rounded-full border-2 border-slate-300 text-blue-600 focus:ring-2 focus:ring-blue-500 focus:ring-offset-0 cursor-pointer"
              />
              <span className="flex-1 text-sm text-slate-700">
                {item.description}
              </span>
              <span className="text-xs text-slate-500 whitespace-nowrap">
                {item.assignee} | {item.dueDate}
              </span>
              <button className="text-slate-400 hover:text-slate-600 flex-shrink-0">
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
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
