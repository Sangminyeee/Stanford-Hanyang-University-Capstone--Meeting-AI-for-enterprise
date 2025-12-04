import Link from "next/link";
import { Card } from "@/components/common/Card";
import { Button } from "@/components/common/Button";

export function TodayMeetingsCard() {
  const meetings = [
    {
      id: 1,
      title: "Marketing Strategy Review",
      project: "Project A",
      time: "9:00 AM",
    },
    {
      id: 2,
      title: "Design Feedback",
      project: "Project A",
      time: "11:00 AM",
    },
  ];

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">
          Today&apos;s Meetings
        </h2>
        <Link
          href="/meetings"
          className="text-xs font-medium text-slate-400 hover:text-slate-500"
        >
          View all Meetings
        </Link>
      </div>
      <div className="flex flex-col gap-3">
        {meetings.map((meeting) => (
          <div
            key={meeting.id}
            className="flex items-center justify-between rounded-xl border border-slate-100 bg-white px-4 py-3"
          >
            <div className="flex flex-col">
              <div className="text-sm font-semibold text-slate-900">
                {meeting.title}
              </div>
              <div className="mt-0.5 text-xs text-slate-400">
                {meeting.project}
              </div>
            </div>
            <div className="mr-4 whitespace-nowrap text-xs text-slate-400">
              {meeting.time}
            </div>
            <Button
              variant="secondary"
              size="sm"
              className="rounded-full px-4 py-1.5 text-xs bg-slate-100 hover:bg-slate-200"
            >
              View Prep Summary
            </Button>
          </div>
        ))}
      </div>
    </Card>
  );
}


