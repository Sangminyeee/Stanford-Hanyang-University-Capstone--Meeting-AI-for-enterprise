import { Card } from "@/components/common/Card";
import { Button } from "@/components/common/Button";

export function RecentMeetingsCard() {
  const meetings = [
    {
      id: 1,
      title: "Business Review",
      date: "Nov 29",
      project: "Project A",
    },
    {
      id: 2,
      title: "Business Review",
      date: "Nov 30",
      project: "Project A",
    },
    {
      id: 3,
      title: "Business Review",
      date: "Dec 1",
      project: "Project A",
    },
  ];

  return (
    <Card className="p-6">
      <h2 className="mb-4 text-sm font-semibold text-slate-900">
        Recent Meetings
      </h2>
      <div className="grid grid-cols-3 gap-4">
        {meetings.map((meeting) => (
          <div
            key={meeting.id}
            className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-white px-5 py-4"
          >
            <div>
              <div className="mb-1 text-sm font-semibold text-slate-900">
                {meeting.title}
              </div>
              <div className="text-xs text-slate-400">
                {meeting.date} | {meeting.project}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Button
                variant="ghost"
                size="sm"
                className="justify-center rounded-full bg-slate-100 text-xs hover:bg-slate-200"
              >
                View Minutes
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="justify-center rounded-full bg-slate-100 text-xs hover:bg-slate-200"
              >
                View Patterns
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="justify-center rounded-full bg-slate-100 text-xs hover:bg-slate-200"
              >
                Prepare Next Meetings
              </Button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

