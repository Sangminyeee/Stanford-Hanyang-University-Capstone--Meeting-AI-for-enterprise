import { Badge } from "@/components/common/Badge";

interface MeetingHeaderProps {
  title: string;
  date: string;
  time: string;
  endTime?: string;
  duration: string;
  attendees: string[];
  project: string;
  tags: string[];
  status: string;
}

export function MeetingHeader({
  title,
  date,
  time,
  endTime,
  duration,
  attendees,
  project,
  tags,
  status,
}: MeetingHeaderProps) {
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

  return (
    <div className="mb-6 pb-6 border-b border-slate-200">
      <h1 className="text-2xl font-semibold text-slate-900 mb-4">{title}</h1>
      <div className="flex flex-wrap items-center gap-4 text-sm text-slate-600 mb-4">
        <span>
          {date} | {time} {endTime ? `- ${endTime}` : ""} ({duration})
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-4 mb-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-600">Attendees:</span>
          <div className="flex items-center gap-2">
            {attendees.map((attendee, index) => (
              <div key={index} className="flex items-center gap-2">
                <div className="w-5 h-5 bg-slate-300 rounded-full"></div>
                <span className="text-sm text-slate-700">{attendee}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-600">Project:</span>
          <span className="text-sm font-medium text-slate-900">{project}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-600">Tag:</span>
          {tags.map((tag) => (
            <Badge
              key={tag}
              variant="tag"
              className={
                tag === "Design"
                  ? "bg-blue-50 text-blue-700"
                  : "bg-slate-100 text-slate-700"
              }
            >
              {tag}
            </Badge>
          ))}
        </div>
        <Badge variant={getStatusVariant(status) as "status-completed" | "status-in-progress" | "status-overdue" | "status-scheduled"}>{status}</Badge>
      </div>
    </div>
  );
}

