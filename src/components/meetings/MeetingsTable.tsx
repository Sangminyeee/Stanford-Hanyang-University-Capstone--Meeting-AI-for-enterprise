"use client";

import Link from "next/link";
import { Card } from "@/components/common/Card";
import { Badge } from "@/components/common/Badge";

const mockMeetings = [
  {
    id: 1,
    name: "Marketing Strategy Review",
    project: "Project A",
    date: "Nov 30, 2024",
    status: "Scheduled",
    tag: "PM",
  },
  {
    id: 2,
    name: "Design Feedback Session",
    project: "Project B",
    date: "Nov 29, 2024",
    status: "Completed",
    tag: "Design",
  },
  {
    id: 3,
    name: "Sprint Planning",
    project: "Project A",
    date: "Nov 28, 2024",
    status: "In Progress",
    tag: "Dev",
  },
  {
    id: 4,
    name: "Team Sync",
    project: "Project C",
    date: "Nov 27, 2024",
    status: "Completed",
    tag: "PM",
  },
  {
    id: 5,
    name: "Product Review",
    project: "Project A",
    date: "Nov 26, 2024",
    status: "Completed",
    tag: "PM",
  },
  {
    id: 6,
    name: "Technical Discussion",
    project: "Project B",
    date: "Nov 25, 2024",
    status: "Completed",
    tag: "Dev",
  },
  {
    id: 7,
    name: "Client Meeting",
    project: "Project C",
    date: "Nov 24, 2024",
    status: "Completed",
    tag: "PM",
  },
  {
    id: 8,
    name: "Code Review",
    project: "Project A",
    date: "Nov 23, 2024",
    status: "Completed",
    tag: "Dev",
  },
];

const getStatusVariant = (status: string) => {
  switch (status) {
    case "Completed":
      return "status-completed";
    case "In Progress":
      return "status-in-progress";
    case "Scheduled":
      return "status-scheduled";
    default:
      return "status-scheduled";
  }
};

export function MeetingsTable() {
  return (
    <Card className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-slate-900">All Meetings</h2>
          <span className="text-sm text-slate-500">258</span>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search"
            className="px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <select className="px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option>All Projects</option>
          </select>
          <select className="px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option>Date</option>
          </select>
          <select className="px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option>All Status</option>
          </select>
          <select className="px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option>Tag</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="space-y-2">
        {mockMeetings.map((meeting) => (
          <Link
            key={meeting.id}
            href={`/meetings/${meeting.id}`}
            className="flex items-center gap-4 p-4 hover:bg-slate-50 rounded-lg transition-colors"
          >
            <div className="flex-1 font-semibold text-slate-900">
              {meeting.name}
            </div>
            <div className="w-32 text-sm text-slate-600">{meeting.project}</div>
            <div className="w-32 text-sm text-slate-600">{meeting.date}</div>
            <div className="w-32">
              <Badge variant={getStatusVariant(meeting.status) as "status-completed" | "status-in-progress" | "status-overdue" | "status-scheduled"}>
                {meeting.status}
              </Badge>
            </div>
            <div className="w-24">
              <Badge variant="tag">{meeting.tag}</Badge>
            </div>
            <div className="w-8 text-slate-400">⋯</div>
          </Link>
        ))}
      </div>
    </Card>
  );
}

